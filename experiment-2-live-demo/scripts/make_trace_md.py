#!/usr/bin/env python3
"""Generate TRACE_<COND>.md from a live trace log. Nothing is truncated.

Unlike experiment/traces/*.md, which were written by hand, these are generated
from the logs, so every figure is traceable and the documents can be rebuilt.
"""

# Long lines here are the literal prose emitted into the trace documents;
# wrapping them would put hard breaks in the rendered markdown.
# pylint: disable=line-too-long,missing-function-docstring,redefined-outer-name
# pylint: disable=invalid-name

import re
import sys
import pathlib
import collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
TRACES = ROOT / "traces"
TRACES.mkdir(exist_ok=True)

COND_DESC = {
    "NONE": (
        "no retrieved context",
        "the floor: agents see only the incident description",
    ),
    "RAW": (
        "unranked retrieval",
        "every matching item from the live graph, no ranking, no top-k",
    ),
    "HYBRID": (
        "ranked retrieval",
        "top 5 by 0.50·vector + 0.30·graph_proximity + 0.20·recency",
    ),
}
DEINDENT = re.compile(r"^ {23}", re.M)


def section(t, start, end=None):
    """Everything between two rule() banners, unindented, untruncated."""
    m = re.search(r"^ *" + re.escape(start) + r".*?$", t, re.M)
    if not m:
        return ""
    body = t[m.end() :]
    if end:
        e = re.search(r"^={100}\n *" + re.escape(end), body, re.M)
        if e:
            body = body[: e.start()]
    body = re.sub(r"^={100}$", "", body, flags=re.M)
    return DEINDENT.sub("", body).strip()


def scalar(t, pat, cast=str, default=None):
    m = re.search(pat, t)
    return cast(m.group(1)) if m else default


def llm_calls(t):
    """Every in-cluster call, with its FULL body."""
    out = []
    for m in re.finditer(
        r"^ *IN-CLUSTER LLM CALL +\[([\w-]+)\] +(REQUEST|RESPONSE) +\((.*?)\)\s*$"
        r".*?--- (?:REQUEST|RESPONSE) BODY -+\n(.*?)\n *-{80}",
        t,
        re.S | re.M,
    ):
        svc, kind, gen, body = m.groups()
        out.append(
            {
                "svc": svc,
                "kind": kind.lower(),
                "gen": gen,
                "body": DEINDENT.sub("", body),
            }
        )
    return out


def agent_of(body):
    m = re.search(r'"instructions":\s*"You are an? ([^"]+?)\.', body)
    return m.group(1) if m else None


# build() emits one trace document top to bottom: header, summary table, each
# step, every captured LLM body, then the final verdicts. The statements are
# the document's sections in order; splitting them would scatter the layout
# across functions without making it easier to follow.
def build(cond):  # pylint: disable=too-many-statements,too-many-locals
    log = LOGS / f"live-{cond}.log"
    t = log.read_text(errors="replace")
    if "FINAL RESULT" not in t:
        return f"(live-{cond}.log has no FINAL RESULT — run incomplete)"
    short, blurb = COND_DESC[cond]
    L = []
    A = L.append

    A(f"# CloudGraph — Live Cluster Execution Trace (Condition `{cond}`)\n")
    A(
        f"Complete input-to-output chain for **condition `{cond}`** ({short}) on a "
        f"**real Kubernetes cluster**, not a seeded benchmark scenario. {blurb.capitalize()}.\n"  # noqa: E501
    )
    A(
        f"Every value is quoted from `logs/live-{cond}.log`, written live by "
        f"`scripts/trace_live.py`. **Nothing in this document is truncated.**\n"
    )
    A(
        "> **How this differs from `experiment/traces/`.** Those trace RCAEval "
        "scenarios whose telemetry is *seeded* into Neo4j and Qdrant before each run, "
        "so retrieval re-selects from a fixed 26-item pool. Here the graph was built "
        "by the ingestion pipeline from a live cluster, nothing is seeded, and "
        "retrieval is unscoped (`scenario_id=None`) against the whole graph.\n"
    )
    A(
        "> **Metric nodes are excluded throughout.** "
        "`k8s_discovery._simulate_pod_metrics()` generates every metric value with "
        "`random.uniform()`, so metric evidence is not telemetry and must not enter "
        "a prompt or a provenance score.\n"
    )
    A("---\n")

    # ---- summary -------------------------------------------------------
    claims = scalar(t, r"claims scored\s+:\s+(\d+)", int, 0)
    gpcs_u = scalar(t, r"GPCS unsupported\s+:\s+(\d+)", int, 0)
    sc_u = scalar(t, r"self-consistency unsupported:\s+(\d+)", int, 0)
    conc = scalar(t, r"agreement \(concordance\)\s+:\s+(\d+)", int, 0)
    A("## Executive summary\n")
    A("| Metric | Value |")
    A("|---|---|")
    pod_name = scalar(t, r"pod *= (\S+)")
    pod_status = scalar(t, r"status *= (\S+)")
    n_symptoms = scalar(t, r"observed_symptoms = (\d+) REAL", int, 0)
    n_retr = scalar(t, r"returned (\d+) items in", int, 0)
    n_filt = scalar(t, r"filtered from GPCS evidence: (\d+)", int, 0)
    trusts_s = scalar(t, r"distinct trust scores observed: (\[.*?\])", str, "n/a")
    n_calls = scalar(t, r"TOTAL LLM CALLS\s+:\s+(\d+)", int, 0)
    wall = scalar(t, r"total wall time: ([\d.]+)s", str, "?")
    A(f"| Faulted pod | `{pod_name}` |")
    A(f"| Pod status in graph | `{pod_status}` |")
    A(f"| Input: real container log lines | {n_symptoms} |")
    A(f"| Evidence retrieved | {n_retr} |")
    A(f"| Simulated metrics filtered from GPCS | {n_filt} |")
    A(f"| Claims extracted | {claims} |")
    A(
        f"| GPCS unsupported | {gpcs_u}/{claims}"
        + (f" = {gpcs_u/claims*100:.1f}%" if claims else "")
        + " |"
    )
    A(
        f"| Self-consistency unsupported | {sc_u}/{claims}"
        + (f" = {sc_u/claims*100:.1f}%" if claims else "")
        + " |"
    )
    A(
        f"| Concordance | {conc}/{claims}"
        + (f" = {conc/claims*100:.1f}%" if claims else "")
        + " |"
    )
    A(f"| Distinct GPCS trust values | `{trusts_s}` |")
    A(f"| Total LLM calls | {n_calls} |")
    A(f"| Wall time | {wall}s |")
    A("---\n")

    # ---- steps ---------------------------------------------------------
    steps = [
        (
            "STEP 1 — LOCATE THE FAULT IN THE LIVE GRAPH",
            "STEP 2 — STORE STATE",
            "STEP 1 — The fault, as the graph sees it",
            "The input is the faulted container's own log lines, read by "
            "`_ingest_pod_logs` → `read_namespaced_pod_log()`. These are real.",
        ),
        (
            "STEP 2 — STORE STATE (no seeding; this is the live cluster)",
            "STEP 3 — RETRIEVAL",
            "STEP 2 — Store state (nothing seeded)",
            "`qdrant:evidence_eval 0` while `qdrant:evidence` holds the data is "
            "`assert_semantic_store_isolated()` inspects a collection the "
            "evaluation does not write to, so isolation rests on the query-time filter.",  # noqa: E501
        ),
        (
            "STEP 3 — RETRIEVAL (unscoped, live graph)",
            "STEP 4 — GENERATION",
            "STEP 3 — Retrieval",
            "Unscoped: `scenario_id=None`, so this searches the whole live graph.",
        ),
        (
            "STEP 5 — SELF-CONSISTENCY VERDICTS",
            "STEP 6 — GPCS",
            "STEP 5 — Self-consistency verdicts",
            "Measures stability across 3 samples at T=0.8, cosine ≥ 0.8. "
            "Not truth — only whether the model said it again.",
        ),
        (
            "STEP 6 — GPCS SCORING (arithmetic per claim)",
            "FINAL RESULT",
            "STEP 6 — GPCS scoring, per claim",
            "`trust = 0.45·semantic + 0.35·proximity + 0.25·reliability − 0.15·(hop×0.05)`. "  # noqa: E501
            "Where `hop` is None the evidence has no path into the graph: that is "
            "absent provenance, so it earns neither proximity nor penalty.",
        ),
    ]
    for start, end, title, note in steps:
        body = section(t, start, end)
        if not body:
            continue
        A(f"## {title}\n")
        A(f"> {note}\n")
        A("```text")
        A(body)
        A("```\n")

    # ---- agents --------------------------------------------------------
    calls = llm_calls(t)
    if calls:
        A("---\n")
        A("## STEP 4 — Multi-agent analysis: every LLM call, in full\n")
        A(
            f"{len(calls)} in-cluster request/response bodies were captured. "
            "All are reproduced complete.\n"
        )
        byagent = collections.Counter(
            agent_of(c["body"])
            for c in calls
            if c["kind"] == "request" and agent_of(c["body"])
        )
        A("| Agent | Requests |")
        A("|---|---:|")
        for a_, n in byagent.most_common():
            A(f"| {a_} | {n} |")
        A("")
        A(
            "> A specialist making 0 calls took its rules path instead — its model "
            "call is gated on finding evidence first.\n"
        )
        for i, c in enumerate(calls, 1):
            who = agent_of(c["body"]) or c["svc"]
            A(
                f"<details>\n<summary><b>{i}. [{c['svc']}] {c['kind'].upper()} — {who} ({c['gen']})</b></summary>\n"  # noqa: E501
            )
            A("```json")
            A(c["body"])
            A("```\n</details>\n")

    # ---- final ---------------------------------------------------------
    fin = section(t, "FINAL RESULT", "NO TEARDOWN")
    if fin:
        A("---\n")
        A("## Final result — both verifiers over the same claims\n")
        A(
            "> Claim text below is complete. The `[:52]` cap that truncated "
            "`experiment/results/claims.csv` has been removed.\n"
        )
        A("```text")
        A(fin)
        A("```\n")
    A("---\n")
    A("## What this trace does not contain\n")
    A(
        "There is **no ground-truth labelling step and no head-to-head evaluation** "
        "(STEPs 8–9 in `experiment/traces/`). Claim correctness was not labelled "
        "for this experiment, so the figures above are **inter-method concordance, "
        "not accuracy**. Both verifiers can be wrong about the same claim and it "
        "still counts as agreement. No claim is made here about which verifier is "
        "more accurate.\n"
    )
    return "\n".join(L)


for cond in sys.argv[1:] or ["NONE", "RAW", "HYBRID"]:
    out = TRACES / f"TRACE_{cond}.md"
    md = build(cond)
    out.write_text(md, encoding="utf-8")
    print(f"  {out.name}: {len(md.splitlines())} lines, {len(md):,} chars")
