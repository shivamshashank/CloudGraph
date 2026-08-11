"""Assigns an automatic correctness label to every scored claim, so the two
verifiers can be compared against something other than each other.

The evaluation measures whether GPCS and self-consistency reach the *same*
verdict. That is concordance, not accuracy: both can be wrong on the same
claim and it counts as agreement. This script derives a third, independent
signal from the benchmark's own labels — RCAEval names the faulted service
and the injected fault type for every case — so a verifier's flags can be
scored as precision and recall rather than mere overlap.

It is deliberately conservative, and it is a *proxy* for a human judgement,
not a substitute:

  * Only **causal** claims are labelled. A state observation such as
    "checkoutservice exhibited increased memory usage" can be perfectly
    true during a CPU fault — the injected fault drives many secondary
    symptoms — so reading mechanism words in a descriptive claim as a
    wrong answer would manufacture errors that are not there.
  * A competing mechanism only counts when it is named with a *causal*
    qualifier. Bare "latency" is an effect of nearly every fault type, so
    matching it as the signature of a delay fault would mislabel most CPU
    cases. The patterns below require the qualifier ("network latency",
    "packet loss", "memory exhaustion").
  * Anything not clearly consistent or contradicted is `unverifiable`,
    and is excluded from the metrics rather than assumed correct.

The labelled subset is therefore small relative to the corpus. That is the
intended trade: a narrow, defensible label beats a broad, noisy one, and
the reported coverage makes the narrowness visible.

Usage (from services/api):
    .venv/bin/python scripts/label_claim_correctness.py
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import _bootstrap

from app.demo.datasets import load_scenarios

DEFAULT_RESULTS = _bootstrap.REPO_ROOT / "experiments" / "results"

# A fault's mechanism as it would be *named as a cause*. Bare effect words
# are excluded on purpose: "latency" and "slow" follow from every fault
# type, so matching them would attribute a delay fault to most CPU cases.
MECHANISM_PATTERNS: dict[str, list[str]] = {
    "cpu": [
        r"cpu (?:saturation|exhaustion|pressure|starvation|spin|contention|throttl)",
        r"cpu[- ]bound",
        r"(?:high|severe|excessive|sustained) cpu",
        r"cpu spike caused",
        r"processor (?:saturation|exhaustion)",
        r"compute[- ]bound",
        r"infinite loop",
    ],
    "mem": [
        r"memory (?:exhaustion|pressure|leak|saturation|starvation)",
        r"out[- ]of[- ]memory",
        r"\boom\b",
        r"heap exhaustion",
    ],
    "disk": [
        r"disk (?:saturation|exhaustion|pressure|contention|full|i/?o)",
        r"(?:high|severe|excessive) disk",
        r"i/?o (?:saturation|pressure|contention|bottleneck|wait)",
        r"storage (?:exhaustion|pressure|saturation)",
        r"filesystem",
    ],
    "delay": [
        r"network (?:delay|latency|slowness)",
        r"injected delay",
        r"packet delay",
        r"network[- ]level delay",
    ],
    "loss": [r"packet loss", r"packet drop", r"dropped packets", r"network loss"],
    "socket": [
        r"socket (?:exhaustion|saturation|leak|starvation)",
        r"file descriptor",
        r"\bfd exhaustion\b",
        r"connection (?:exhaustion|pool exhaustion|starvation)",
    ],
}

# A claim is treated as asserting a cause when it is typed causal or uses
# explicitly causal language; only these are labelled. "originated from" is
# deliberately absent: it is overwhelmingly used for log provenance
# ("log lines originated from ts-travel-service"), which is a descriptive
# statement about where text came from, not a causal attribution.
CAUSAL_MARKERS = re.compile(
    r"\b(caused|causing|due to|because|root cause|led to|leads to|"
    r"resulted in|resulting in|triggered by|triggered|stems from|"
    r"attributable to)\b",
    re.IGNORECASE,
)

# A mechanism named inside a negation is being *ruled out*, which on a
# different fault type is correct reasoning rather than a wrong answer:
# "the pattern is not caused by CPU exhaustion" on a delay fault is right.
NEGATION_NEAR = re.compile(
    r"\b(not|no|never|without|rather than|instead of|rules? out|ruled out|"
    r"excludes?|excluding|absent|unlikely|refutes?|contradicts?|"
    r"inconsistent with|does not|did not|isn't|wasn't)\b",
    re.IGNORECASE,
)

# A foreign service only indicts the claim when it sits in a *cause*
# position. Naming a neighbour as the thing harmed ("cascaded to orders",
# "downstream impact on front-end") is an effect statement and frequently
# true — the injected fault really does propagate.
FOREIGN_AS_CAUSE = (
    r"(?:caused by|due to|because of|root cause (?:is|was)?|"
    r"originates? (?:from|in)|stems from|attributable to)\s+"
    r"(?:the\s+)?(?:[a-z]+\s+){{0,2}}{service}"
    r"|{service}\s+(?:caused|is the root cause|was the root cause|"
    r"triggered|led to|is responsible)"
)


def _word_re(term: str) -> re.Pattern[str]:
    """Match a term on identifier boundaries.

    Plain \\b is wrong here: service names contain hyphens, so \\bcarts\\b
    matches inside "cartservice" and would credit an Online Boutique claim
    to Sock Shop.
    """
    return re.compile(rf"(?<![A-Za-z0-9-]){re.escape(term)}(?![A-Za-z0-9-])", re.I)


def _fault_of(scenario: dict[str, Any]) -> str:
    case = scenario.get("source_case", "")
    return re.sub(r"_\d+$", "", case).split("_")[-1] if case else ""


def build_service_vocabulary(
    scenarios: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Service names per system, harvested from the seeded telemetry.

    The faulted services alone are too narrow — a claim blaming a
    *neighbouring* service is the interesting error case, and those names
    only appear in the observations.
    """
    vocab: dict[str, set[str]] = defaultdict(set)
    metric_name = re.compile(r"metric ([A-Za-z0-9-]+?)_[a-z_]+:")
    for scenario in scenarios:
        system = scenario.get("source_system", "")
        vocab[system].add(scenario["target_service"])
        for symptom in scenario.get("observed_symptoms", []):
            for match in metric_name.finditer(str(symptom)):
                name = match.group(1)
                if len(name) > 2:
                    vocab[system].add(name)
    return vocab


def label_claim(
    claim_text: str,
    claim_type: str,
    scenario: dict[str, Any],
    services: set[str],
) -> tuple[str, str]:
    """Return (label, reason) for one claim.

    label is one of consistent | contradicted | unverifiable.
    """
    if claim_type != "causal" and not CAUSAL_MARKERS.search(claim_text):
        return "unverifiable", "not a causal claim"

    fault = _fault_of(scenario)
    target = scenario["target_service"]

    def mentioned_affirmatively(patterns: list[str]) -> bool:
        """True when a pattern matches outside a negation."""
        # Scope is the whole claim, not the text preceding the match: these
        # are single short sentences, and "stable CPU rules out CPU
        # saturation" negates a mechanism it names twice — checking only
        # what comes before the first mention reads it as an assertion.
        if NEGATION_NEAR.search(claim_text):
            return False
        return any(re.search(pattern, claim_text, re.I) for pattern in patterns)

    names_correct_mechanism = mentioned_affirmatively(MECHANISM_PATTERNS.get(fault, []))
    competing = [
        other
        for other, patterns in MECHANISM_PATTERNS.items()
        if other != fault and mentioned_affirmatively(patterns)
    ]

    blamed_foreign = [
        s
        for s in sorted(services)
        if s != target
        and re.search(FOREIGN_AS_CAUSE.format(service=re.escape(s)), claim_text, re.I)
    ]

    # Correct mechanism wins: "CPU spike caused degradation in orders" on a
    # CPU fault is right about the cause and merely describes where the
    # effect landed.
    if names_correct_mechanism:
        return "consistent", f"names the injected mechanism ({fault})"

    if blamed_foreign:
        return (
            "contradicted",
            f"blames {blamed_foreign[0]}, injected fault was on {target}",
        )

    if competing:
        return (
            "contradicted",
            f"names {competing[0]} as cause, injected fault was {fault}",
        )

    return "unverifiable", "no mechanism or service identifiable"


def score_verifier(rows: list[dict[str, Any]], column: str) -> dict[str, Any]:
    """Score one verifier's flags against the correctness label.

    Positive class is "the claim is wrong" (contradicted), because that is
    what a hallucination detector is supposed to catch.
    """
    tp = fp = fn = tn = 0
    for row in rows:
        flagged = row[column] == "True"
        wrong = row["correctness_label"] == "contradicted"
        if flagged and wrong:
            tp += 1
        elif flagged and not wrong:
            fp += 1
        elif not flagged and wrong:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": tn / (tn + fp) if tn + fp else 0.0,
    }


def main() -> None:
    """CLI entry point: label every claim and score both verifiers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()

    claims_path = args.results_dir / "claims.csv"
    if not claims_path.exists():
        print(f"Error: {claims_path} not found — run the merge first.", file=sys.stderr)
        sys.exit(1)

    scenarios = {s["id"]: s for s in load_scenarios()}
    vocabulary = build_service_vocabulary(list(scenarios.values()))

    with open(claims_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        scenario = scenarios[row["scenario_id"]]
        label, reason = label_claim(
            row["claim_text"],
            row["claim_type"],
            scenario,
            vocabulary[scenario.get("source_system", "")],
        )
        row["correctness_label"] = label
        row["correctness_reason"] = reason

    out_path = args.results_dir / "claims_labelled.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(_build_report(rows))
    print(f"Labelled claims -> {out_path}")


def _build_report(rows: list[dict[str, Any]]) -> str:
    """Render the coverage summary and per-verifier scores."""
    counts = Counter(r["correctness_label"] for r in rows)
    evaluable = [r for r in rows if r["correctness_label"] != "unverifiable"]

    lines = [
        "# Automatic correctness labelling",
        "",
        "Labels derive from RCAEval's own case metadata (faulted service and",
        "injected fault type). Only causal claims are labelled; descriptive",
        "claims are `unverifiable` and excluded from the metrics below. This",
        "is a conservative proxy for human judgement, not a replacement.",
        "",
        f"- claims total: {len(rows)}",
        f"- consistent: {counts['consistent']}",
        f"- contradicted: {counts['contradicted']}",
        f"- unverifiable (excluded): {counts['unverifiable']}",
        f"- **evaluable subset: {len(evaluable)} "
        f"({100 * len(evaluable) / len(rows):.1f}% of claims)**",
        "",
        "## Detecting incorrect claims (positive class = contradicted)",
        "",
        "| verifier | precision | recall | F1 | specificity |",
        "|---|---|---|---|---|",
    ]
    for name, column in (
        ("GPCS", "gpcs_unsupported"),
        ("Self-consistency", "self_consistency_unsupported"),
    ):
        m = score_verifier(evaluable, column)
        lines.append(
            f"| {name} | {m['precision']:.3f} | {m['recall']:.3f} | "
            f"{m['f1']:.3f} | {m['specificity']:.3f} |"
        )

    consistent = [r for r in evaluable if r["correctness_label"] == "consistent"]
    wrong = [r for r in evaluable if r["correctness_label"] == "contradicted"]
    lines += [
        "",
        "## Does either flag actually track correctness?",
        "",
        "Precision near the base rate is what flagging everything would score,",
        "so the discriminating question is whether the flag rate *differs*",
        "between correct and incorrect claims.",
        "",
        "| verifier | flags contradicted | flags consistent | gap |",
        "|---|---|---|---|",
    ]
    for name, column in (
        ("GPCS", "gpcs_unsupported"),
        ("Self-consistency", "self_consistency_unsupported"),
    ):
        f_bad = 100 * sum(1 for r in wrong if r[column] == "True") / max(1, len(wrong))
        f_ok = (
            100
            * sum(1 for r in consistent if r[column] == "True")
            / max(1, len(consistent))
        )
        lines.append(
            f"| {name} | {f_bad:.1f}% | {f_ok:.1f}% | {f_bad - f_ok:+.1f} pp |"
        )
    lines += [
        "",
        f"Base rate of contradicted claims: "
        f"{100 * len(wrong) / max(1, len(evaluable)):.1f}%.",
    ]

    report = "\n".join(lines) + "\n"
    (DEFAULT_RESULTS / "correctness_labels.md").write_text(report, encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
