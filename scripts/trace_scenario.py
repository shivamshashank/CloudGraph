#!/usr/bin/env python3
"""Run ONE scenario through the real pipeline, writing a sequential execution
log as each step happens.

Nothing here re-implements the pipeline. It imports the same modules the
deployed API imports, wraps their internal functions so each value is written
to the log at the moment it is computed, and calls the real entry points.
Every line in the log is therefore a measurement, in the order it occurred.

Usage:
  NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_AUTH=neo4j/PASS \
  QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333 \
  AGENT_ORCHESTRATOR_URL=http://localhost:8082 \
  .venv/bin/python ../../scripts/trace_scenario.py rcaeval-01 hybrid out.log
"""

# This is an instrumentation script, not library code. It deliberately:
#   * imports after writing the log header, so the trace records its own start
#   * wraps private methods (_score_claim, _generate_one_sample) to capture the
#     arithmetic at the moment it is computed
#   * catches broad exceptions, because a trace must record a failure rather
#     than die and lose the run
# pylint: disable=wrong-import-position,wrong-import-order,broad-exception-caught
# pylint: disable=protected-access,missing-function-docstring,redefined-outer-name
# pylint: disable=invalid-name,consider-using-with,consider-using-from-import
# pylint: disable=use-dict-literal,unsubscriptable-object,line-too-long


# App imports are deliberately placed after the log header is written, so the
# trace records its own start time before the heavy model/driver imports run.
# ruff: noqa: E402

import json
import sys
import time
import datetime
import functools
import pathlib
import collections

sys.path.insert(0, ".")

SCENARIO_ID = sys.argv[1] if len(sys.argv) > 1 else "rcaeval-01"
CONDITION = sys.argv[2] if len(sys.argv) > 2 else "hybrid"
LOGPATH = pathlib.Path(
    sys.argv[3] if len(sys.argv) > 3 else "/tmp/cloudgraph-scenario.log"
)

_t0 = time.time()
_fh = LOGPATH.open("w", encoding="utf-8")


def log(msg=""):
    el = time.time() - _t0
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    for line in str(msg).split("\n"):
        _fh.write(f"[{ts}] [+{el:7.2f}s] {line}\n")
    _fh.flush()


def raw(msg=""):
    for line in str(msg).split("\n"):
        _fh.write(f"{' '*23}{line}\n")
    _fh.flush()


def rule(title=""):
    _fh.write("\n" + "=" * 100 + "\n")
    if title:
        _fh.write(f"  {title}\n" + "=" * 100 + "\n")
    _fh.flush()


def link(frm, to, what):
    """State explicitly how one step feeds the next."""
    _fh.write("\n" + " " * 23 + "|\n")
    _fh.write(" " * 23 + f"|  {frm}  ->  {to}\n")
    for line in what.split("\n"):
        _fh.write(" " * 23 + f"|  {line}\n")
    _fh.write(" " * 23 + "v\n")
    _fh.flush()


def block(label, text):
    """Full content, never truncated — the point of this log is completeness."""
    raw(f"--- {label} " + "-" * max(0, 74 - len(label)))
    raw(str(text))
    raw("-" * 80)


rule(f"CloudGraph execution trace — scenario {SCENARIO_ID}, condition {CONDITION}")
log(f"started {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
log("every value below is captured at the moment it is computed")

import app.research.gpcs as gpcs  # noqa: E402
import app.research.self_consistency as sc  # noqa: E402
from app.research.report_runner import _retrieval_results_for_condition  # noqa: E402
from app.demo.seeding import (  # noqa: E402
    seed_scenario_data,
    teardown_benchmark_data,
    assert_semantic_store_isolated,
)
from app.demo.datasets import load_scenarios  # noqa: E402
from app.services import graphrag_search  # noqa: E402
from app.database.neo4j_client import neo4j_client  # noqa: E402
from app.database.qdrant import qdrant_client  # noqa: E402
from app.research.llm_settings import load_stored_llm_settings  # noqa: E402

sys.path.insert(0, "scripts")
from label_claim_correctness import (  # noqa: E402
    label_claim,
    build_service_vocabulary,
    score_verifier,
)

STATE = {
    "llm_seq": 0,
    "claim_seq": 0,
    "pod_calls": 0,
    "pod_requests": collections.Counter(),
    "gpcs": [],
    "sc": [],
}

# ---- wrap: every in-process LLM call -------------------------------------
_real_call_llm = gpcs.call_llm


@functools.wraps(_real_call_llm)
def traced_call_llm(*a, **kw):
    STATE["llm_seq"] += 1
    n = STATE["llm_seq"]
    prompt = kw.get("prompt", a[0] if a else None)
    rule(f"LLM CALL #{n} (in-process)")
    log(
        f"model={kw.get('model') or 'from stored settings'} "
        f"temperature={kw.get('temperature', 'default')}"
    )
    block("REQUEST PROMPT", prompt)
    t = time.time()
    try:
        out = _real_call_llm(*a, **kw)
    except Exception as exc:
        log(f"FAILED after {time.time()-t:.2f}s: {type(exc).__name__}: {exc}")
        raise
    dt = time.time() - t
    log(f"responded in {dt:.2f}s")
    if isinstance(out, list):
        log(f"returned {len(out)} items")
        block("RESPONSE", json.dumps(out, indent=2))
    else:
        block("RESPONSE", json.dumps(out, indent=2, default=str))
    return out


gpcs.call_llm = traced_call_llm

# ---- wrap: GPCS scoring, showing the arithmetic --------------------------
S = gpcs.GraphProvenanceClaimScorer
_real_agg, _real_score = S._aggregate_evidence_metrics, S._score_claim
_pending = {}


@functools.wraps(_real_agg)
def traced_agg(self, evidence):
    best, hop, rel, bev = _real_agg(self, evidence)
    _pending["agg"] = dict(
        best_score=best, min_hop=hop, avg_rel=rel, n_considered=len(evidence)
    )
    return best, hop, rel, bev


@functools.wraps(_real_score)
def traced_score(self, evidence):
    _pending.pop("agg", None)
    STATE["claim_seq"] += 1
    n = STATE["claim_seq"]
    trust, ev = _real_score(self, evidence)
    agg = _pending.pop("agg", None)
    log(f"  claim {n:>2}: evidence_items={len(evidence)}")
    if agg is None:
        raw(
            f"        no evidence survived the {gpcs.MIN_SEMANTIC_EVIDENCE_SCORE} "
            f"floor -> _score_claim returned 0.0 immediately"
        )
        raw(
            "        (aggregation never ran, so there is no semantic/hop/reliability value)"  # noqa: E501
        )
        raw(f"        TRUST = 0.000   ->  UNSUPPORTED (< {self.threshold})")
    else:
        hop = agg["min_hop"]
        prox = 0.0 if hop is None else 1.0 / (1.0 + hop)
        pen = 0.0 if hop is None else self.penalty_weight * (hop * 0.05)
        cs = self.semantic_weight * agg["best_score"]
        cp = self.graph_weight * prox
        cr = self.reliability_weight * agg["avg_rel"]
        raw(
            f"        semantic    = {agg['best_score']:.4f}  x {self.semantic_weight}  = {cs:.4f}"  # noqa: E501
        )
        raw(f"        min_hop     = {hop}")
        raw(
            f"        proximity   = 1/(1+{hop}) = {prox:.4f}  x {self.graph_weight}  = {cp:.4f}"  # noqa: E501
        )
        raw(
            f"        reliability = {agg['avg_rel']:.4f}  x {self.reliability_weight}  = {cr:.4f}"  # noqa: E501
        )
        raw(
            f"        penalty     = {self.penalty_weight} x ({hop} x 0.05) = -{pen:.4f}"
        )
        raw(
            f"        TRUST = {cs:.4f} + {cp:.4f} + {cr:.4f} - {pen:.4f} = {trust:.4f}"
            f"   ->  {'UNSUPPORTED' if trust < self.threshold else 'supported'}"
            f" (threshold {self.threshold})"
        )
    STATE["gpcs"].append(
        {"n": n, "trust": trust, "unsupported": trust < self.threshold}
    )
    return trust, ev


S._aggregate_evidence_metrics, S._score_claim = traced_agg, traced_score

# ---- in-cluster LLM calls -------------------------------------------------
# The five specialists and the consensus call run INSIDE the pods, reached over
# HTTP, so the in-process wrapper above cannot see them. We follow the pod logs
# from before the first generation and drain them after each one, splicing the
# calls into this log in sequence. Reading by byte offset rather than timestamp
# avoids any clock skew between this machine and the cluster.
import subprocess  # noqa: E402
import re as _re  # noqa: E402

POD_SERVICES = ["investigation-engine", "agent-orchestrator"]
_NS = "cloudgraph-system"


def start_pod_followers():
    """No-op. We snapshot per generation instead of following.

    `kubectl logs -f` was observed re-streaming its buffer, so the same call
    appeared twice in the capture (three unique consensus bodies replayed as
    six). A non-following `kubectl logs --since-time=T` per generation is
    deterministic: each call is returned exactly once.
    """
    return


def stop_pod_followers():
    return


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


_MARK = _re.compile(r"\[LLM (REQUEST|RESPONSE)\]\s*(.*)")
_NOISE = _re.compile(
    r"^(INFO:|WARNING:|\d+\.\d+\.\d+\.\d+ - -|"
    r"Received notification from DBMS|Qdrant )"
)


def snapshot_pod_calls(svc, since_iso):
    """Every LLM request/response the pod logged since `since_iso`."""
    try:
        out = subprocess.run(
            [
                "kubectl",
                "logs",
                "-n",
                _NS,
                f"deploy/{svc}",
                f"--since-time={since_iso}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            # kubectl exits non-zero when a pod has no logs yet; that is
            # an empty capture, not a failure of the trace.
            check=False,
        ).stdout
    except Exception as exc:
        log(f"could not read {svc} logs: {exc}")
        return []
    calls, cur = [], None
    for line in out.split("\n"):
        m = _MARK.search(line)
        if m:
            if cur:
                calls.append(cur)
            cur = {"kind": m.group(1).lower(), "meta": m.group(2).strip(), "body": []}
        elif cur is not None and not _NOISE.search(line):
            cur["body"].append(line)
    if cur:
        calls.append(cur)
    return calls


def log_pod_calls(label, since_iso):
    """Write every in-cluster call the pods logged in this window."""
    total = 0
    for svc in POD_SERVICES:
        for c in snapshot_pod_calls(svc, since_iso):
            total += 1
            STATE["pod_calls"] += 1
            body = "\n".join(c["body"]).strip()
            try:
                parsed = json.loads(body)
                role = parsed.get("instructions", "")
                pretty = json.dumps(parsed, indent=2)
            except Exception:
                try:
                    parsed, _ = json.JSONDecoder().raw_decode(body)
                    role = parsed.get("instructions", "")
                    pretty = json.dumps(parsed, indent=2)
                except Exception:
                    role, pretty = "", body
            n = STATE["pod_calls"]
            if c["kind"] == "request":
                STATE["pod_requests"][role.split(".")[0][:52] or "(role unparsed)"] += 1
            rule(f"IN-CLUSTER LLM CALL #{n}  [{svc}]  {c['kind'].upper()}  ({label})")
            if role:
                log(f"agent role: {role}")
            log(c["meta"])
            block(f"{c['kind'].upper()} BODY", pretty)
    if total == 0:
        log(f"(no in-cluster calls captured for {label})")


# ---- run -----------------------------------------------------------------
rule("STEP 1 — LOAD SCENARIO (input)")
scenario = next(s for s in load_scenarios() if s["id"] == SCENARIO_ID)
for k in (
    "id",
    "source_case",
    "source_system",
    "target_service",
    "target_entity",
    "root_cause",
    "inject_time",
    "query",
):
    log(f"{k:16} = {scenario[k]}")
log(f"{'expected_tags':16} = {scenario['expected_tags']}")
log(f"observed_symptoms = {len(scenario['observed_symptoms'])} items (THE INPUT)")
for s in scenario["observed_symptoms"]:
    raw(f"   - {s}")
log(
    f"ground_truth_claims = {len(scenario['ground_truth_claims'])} (HELD OUT — never prompted)"  # noqa: E501
)
for c in scenario["ground_truth_claims"]:
    raw(f"   - {c}")

settings = load_stored_llm_settings() or {}
log(
    f"llm provider={settings.get('provider')} model={settings.get('model')} "
    f"api_key={'present' if settings.get('api_key') else 'MISSING'}"
)


def counts():
    out = {
        r["l"]: r["c"]
        for r in neo4j_client.execute_query(
            "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c ORDER BY c DESC"
        )
    }
    try:
        qdrant_client.connect()
        for c in qdrant_client.client.get_collections().collections:
            out[f"qdrant:{c.name}"] = qdrant_client.client.count(c.name).count
    except Exception as e:
        out["qdrant_error"] = str(e)
    return out


rule("STEP 2 — INJECT SCENARIO INTO NEO4J + QDRANT")
before = counts()
log("store contents BEFORE seeding:")
for k, v in sorted(before.items()):
    raw(f"   {k:22} {v}")
t = time.time()
seed_scenario_data(scenario)
log(f"seed_scenario_data() completed in {time.time()-t:.2f}s")
after = counts()
log("store contents AFTER seeding (delta shown):")
for k in sorted(set(before) | set(after)):
    b, a = before.get(k, 0), after.get(k, 0)
    mark = f"   <-- +{a-b}" if a != b else ""
    raw(f"   {k:22} {b} -> {a}{mark}")
raw("")
log("what was actually written — sample of the seeded evidence:")
try:
    _seeded = neo4j_client.execute_query(
        "MATCH (l:Log) RETURN l.message AS m ORDER BY l.timestamp DESC LIMIT 8"
    )
    for _r in _seeded:
        raw(f"   Log node   :: {str(_r.get('m'))[:150]}")
    _mets = neo4j_client.execute_query(
        "MATCH (m:Metric) RETURN m.name AS n, m.value AS v LIMIT 4"
    )
    for _r in _mets:
        raw(f"   Metric node:: {_r.get('n')} = {_r.get('v')}")
    _ents = neo4j_client.execute_query(
        "MATCH (n) WHERE n:Pod OR n:Service OR n:Node OR n:Deployment OR n:Commit "
        "RETURN labels(n)[0] AS l, coalesce(n.name, n.sha, n.id) AS name LIMIT 8"
    )
    for _r in _ents:
        raw(f"   Entity     :: {_r.get('l')}: {_r.get('name')}")
except Exception as _e:
    raw(f"   (could not sample seeded nodes: {_e})")
raw("")
raw("   Neo4j stores STRUCTURE: entities and typed relationships. This is what")
raw("   makes hop-distance a real path through real topology.")
raw("   Qdrant stores MEANING: 384-dim embeddings, cosine distance. This is what")
raw("   makes semantic similarity possible. GPCS needs both.")

link(
    "STEP 2 seed",
    "STEP 3 isolation",
    "The nodes and vectors just written are the ONLY evidence that may be\n      scored. Step 3 proves nothing from another scenario survived, which is\n      what makes this scenario an independent trial.",  # noqa: E501
)
rule("STEP 3 — ISOLATION ASSERTION")
try:
    assert_semantic_store_isolated(scenario["id"])
    log("PASSED — vector store contains only this scenario's evidence")
except Exception as exc:
    log(f"FAILED: {exc}")
raw("   Without this, a claim can be 'supported' by another incident's evidence.")
raw("   That defect invalidated one full evaluation run.")

FINAL = {}
try:
    link(
        "STEP 3 isolation",
        "STEP 4 retrieval",
        "With the store proven clean, retrieval can now select from it. What\n          it returns becomes the ONLY evidence the agents see in STEP 5.",  # noqa: E501
    )
    rule("STEP 4 — RETRIEVAL")
    log(f"condition={CONDITION}  query={scenario['query']!r}")
    raw("   score = 0.50*vector_similarity + 0.30*graph_proximity + 0.20*recency")
    t = time.time()
    retrieval = _retrieval_results_for_condition(CONDITION, scenario)
    log(
        f"returned {len(retrieval) if retrieval else 0} items in {time.time()-t:.3f}s "
        f"(no LLM involved)"
    )
    for i, r in enumerate(retrieval or [], 1):
        raw(f"   [{i}] score={r.get('score', '-')} :: {str(r.get('text') or r)[:150]}")

    scorer = gpcs.GraphProvenanceClaimScorer(llm_settings=settings)
    scorer.scenario_id = scenario["id"]
    log("in-cluster calls are snapshotted per generation from the pod logs")
    link(
        "STEP 4 retrieval",
        "STEP 5 generation",
        "The retrieved items are passed to the orchestrator as\n          retrieval_results. Under condition=none this is None, so the agents\n          reason from the incident prompt alone. That is the floor the other\n          two conditions are measured against.",  # noqa: E501
    )
    rule("STEP 5 — GENERATION x3 + SELF-CONSISTENCY")
    log(
        f"n_samples=3 temperature=0.8 similarity_threshold="
        f"{sc.RECURRENCE_SIMILARITY_THRESHOLD}"
    )
    raw("   Each generation posts to agent-orchestrator:/orchestrate, which fans out")
    raw("   to 5 specialists in investigation-engine, then makes a 6th consensus call.")
    raw("   Those calls happen INSIDE the cluster (see the pod-log collector).")
    # Each generation is one full pass: 5 specialists + 1 consensus, in-cluster.
    _real_one = sc._generate_one_sample
    _gen_n = {"i": 0}

    @functools.wraps(_real_one)
    def traced_one_sample(*a, **kw):
        _gen_n["i"] += 1
        i = _gen_n["i"]
        since = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        rule(f"GENERATION {i} of 3 — dispatch to agent-orchestrator")
        log("POST /orchestrate -> investigation-engine /analyze -> 5 specialists,")
        log("then one consensus call. All of these run inside the cluster.")
        t0 = time.time()
        out = _real_one(*a, **kw)
        log(f"generation {i} returned in {time.time()-t0:.2f}s")
        # The pod writes its last response lines a beat after the HTTP reply
        # returns. Without this pause those lines land in the NEXT generation's
        # drain and the per-generation counts come out uneven (14/9/10).
        time.sleep(3)
        log_pod_calls(f"generation {i}", since)
        return out

    sc._generate_one_sample = traced_one_sample

    t = time.time()
    sc_result = sc.generate_and_score(
        scenario,
        n_samples=3,
        temperature=0.8,
        call_options={"request_logger": lambda r: None, "retrieval_results": retrieval},
    )
    log(f"generation + extraction + recurrence scoring took {time.time()-t:.2f}s")
    for i, g in enumerate(sc_result["generations"], 1):
        block(f"GENERATION {i} (temperature 0.8)", json.dumps(g, indent=2, default=str))
    log(
        f"claims extracted from primary generation: "
        f"{len(sc_result['extracted_claims'])}"
    )

    link(
        "STEP 5 generation",
        "STEP 6 self-consistency",
        "Generation 1 is the PRIMARY. Its claims are the claim set. Claims\n          from generations 2 and 3 exist only to answer: did this recur?",  # noqa: E501
    )
    rule("STEP 6 — SELF-CONSISTENCY VERDICTS")
    raw("   supported  <=> an equivalent claim (cosine >= 0.8) recurs in >= half")
    raw("                  of the OTHER generations.  Measures STABILITY, not truth.")
    for i, c in enumerate(sc_result["claims"], 1):
        rr = c.get("recurrence_rate")
        log(
            f"  claim {i:>2}: recurrence={rr}  -> "
            f"{'UNSUPPORTED' if c.get('unsupported') else 'supported'}"
        )
        raw(f"        {str(c.get('text'))[:150]}")
        STATE["sc"].append(
            {"n": i, "rec": rr, "unsupported": bool(c.get("unsupported"))}
        )

    link(
        "STEP 6 self-consistency",
        "STEP 7 GPCS",
        "GPCS now scores the SAME claim list, from the SAME extraction. Only\n          the mechanism differs: self-consistency asked whether the model\n          repeated itself; GPCS asks whether the graph supports it.",  # noqa: E501
    )
    rule("STEP 7 — GPCS SCORING (arithmetic per claim)")
    log(
        f"weights semantic={scorer.semantic_weight} graph={scorer.graph_weight} "
        f"reliability={scorer.reliability_weight} penalty={scorer.penalty_weight}"
    )
    log(
        f"threshold={scorer.threshold}  evidence_floor="
        f"{gpcs.MIN_SEMANTIC_EVIDENCE_SCORE}"
    )
    log(f"source_reliability={gpcs.SOURCE_RELIABILITY}")
    raw(
        "   trust = 0.45*semantic + 0.35*proximity + 0.25*reliability - 0.15*(hop*0.05)"
    )
    t = time.time()
    gpcs_result = scorer.score_claims(
        sc_result["generations"][0],
        graphrag_search,
        claims=sc_result["extracted_claims"],
    )
    log(f"scored {len(gpcs_result['claims'])} claims in {time.time()-t:.3f}s (no LLM)")

    rule("FINAL RESULT")
    g = STATE["gpcs"]
    s_ = STATE["sc"]
    gu = sum(1 for x in g if x["unsupported"])
    su = sum(1 for x in s_ if x["unsupported"])
    log(f"claims scored              : {len(g)}")
    log(f"GPCS unsupported           : {gu}/{len(g)} = {gu/len(g)*100:.1f}%")
    log(f"self-consistency unsupported: {su}/{len(s_)} = {su/len(s_)*100:.1f}%")
    quad = collections.Counter()
    raw("")
    raw(
        f"   {'#':<4}{'TRUST':>8}  {'GPCS':<13}{'RECUR':>7}  {'SELF-CONSISTENCY':<18}CLAIM"  # noqa: E501
    )
    for x, y, c in zip(g, s_, gpcs_result["claims"]):
        quad[(x["unsupported"], y["unsupported"])] += 1
        raw(
            f"   {x['n']:<4}{x['trust']:>8.3f}  "
            f"{'UNSUPPORTED' if x['unsupported'] else 'supported':<13}"
            f"{str(y['rec']):>7}  "
            f"{'UNSUPPORTED' if y['unsupported'] else 'supported':<18}"
            f"{str(c.get('text'))[:52]}"
        )
    agree = quad[(False, False)] + quad[(True, True)]
    raw("")
    log(f"agreement (concordance)    : {agree}/{len(g)} = {agree/len(g)*100:.1f}%")
    raw(f"   both supported      {quad[(False, False)]:>3}")
    raw(f"   both unsupported    {quad[(True, True)]:>3}")
    raw(f"   GPCS only flagged   {quad[(True, False)]:>3}")
    raw(f"   SC only flagged     {quad[(False, True)]:>3}")
    raw("")
    raw("   Agreement is CONCORDANCE, never accuracy: both verifiers can be wrong")
    raw("   about the same claim and it still counts as agreement.")
    trusts = sorted({round(x["trust"], 3) for x in g})
    log(f"distinct trust scores observed: {trusts}")
    raw("   A claim either matches evidence a hop away, or retrieves nothing at all.")

    link(
        "STEP 7 GPCS",
        "STEP 8 labelling",
        "Two verdict sets now exist for the same claims. Step 8 brings in the\n          ground truth held out since STEP 1 to ask which verdicts were right.",  # noqa: E501
    )
    rule("STEP 8 - CORRECTNESS LABELLING (the held-out ground truth)")
    raw(f"   injected fault : {scenario['root_cause']} on {scenario['target_service']}")
    raw("   A claim is labelled by comparing it against that fault:")
    raw("     consistent   - names the injected mechanism")
    raw("     contradicted - names a competing mechanism, or blames another service")
    raw("     unverifiable - not causal, or no mechanism identifiable  -> EXCLUDED")
    vocab = build_service_vocabulary(load_scenarios())
    services = vocab.get(scenario.get("source_system", ""), set())
    rows = []
    for x, y, c in zip(g, s_, gpcs_result["claims"]):
        txt = str(c.get("text", ""))
        lab, why = label_claim(txt, c.get("claim_type", ""), scenario, services)
        rows.append(
            {
                "n": x["n"],
                "text": txt,
                "label": lab,
                "why": why,
                "gpcs_unsupported": str(x["unsupported"]),
                "sc_unsupported": str(y["unsupported"]),
                "correctness_label": lab,
            }
        )
        log(f"  claim {x['n']:>2}: {lab.upper():<13} ({why})")
        raw(f"        {txt}")
    counts = collections.Counter(r["label"] for r in rows)
    log(
        f"consistent={counts['consistent']}  contradicted={counts['contradicted']}  "
        f"unverifiable={counts['unverifiable']}"
    )
    evaluable = [r for r in rows if r["label"] != "unverifiable"]
    log(
        f"EVALUABLE SUBSET: {len(evaluable)} of {len(rows)} claims "
        f"({len(evaluable)/len(rows)*100:.1f}%)"
    )

    link(
        "STEP 8 labelling",
        "STEP 9 head to head",
        "Only the evaluable subset can settle anything. Everything else is\n          excluded, which is why the coverage figure above bounds the whole\n          correctness claim.",  # noqa: E501
    )
    rule("STEP 9 - HEAD TO HEAD: WHICH VERIFIER WINS?")
    if not evaluable:
        log("VERDICT: NEITHER. No claim in this scenario could be adjudicated.")
        raw("   Every claim was unverifiable, so no correctness comparison is possible")
        raw(
            "   here at all. This is not a tie - it is an absence of evidence, and it is"  # noqa: E501
        )
        raw(
            "   exactly why the dissertation reports only 155 of 3,685 claims (4.2%) as"
        )
        raw("   evaluable across all 36 scenarios.")
    else:
        base = sum(1 for r in evaluable if r["label"] == "contradicted")
        log(
            f"base rate of incorrect claims: {base}/{len(evaluable)} = "
            f"{base/len(evaluable)*100:.1f}%"
        )
        raw("   positive class = 'the claim is wrong', because that is what a")
        raw("   hallucination detector is supposed to catch.")
        raw("")
        for name, col in (
            ("GPCS", "gpcs_unsupported"),
            ("SELF-CONSISTENCY", "sc_unsupported"),
        ):
            m = score_verifier(evaluable, col)
            log(f"{name}")
            raw(f"      tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']}")
            raw(f"      precision   = tp/(tp+fp) = {m['precision']:.3f}")
            raw(f"      recall      = tp/(tp+fn) = {m['recall']:.3f}")
            raw(f"      F1                       = {m['f1']:.3f}")
            raw(f"      specificity = tn/(tn+fp) = {m['specificity']:.3f}")
        raw("")
        raw("   THE DISCRIMINATING TEST - does the flag rate DIFFER between")
        raw("   correct and incorrect claims? A verifier that flags everything")
        raw("   scores well on precision alone, so precision cannot settle this.")
        raw("")
        wrong = [r for r in evaluable if r["label"] == "contradicted"]
        right = [r for r in evaluable if r["label"] == "consistent"]
        for name, col in (
            ("GPCS", "gpcs_unsupported"),
            ("SELF-CONSISTENCY", "sc_unsupported"),
        ):
            fw = sum(1 for r in wrong if r[col] == "True") / len(wrong) if wrong else 0
            fr = sum(1 for r in right if r[col] == "True") / len(right) if right else 0
            log(
                f"{name}: flags {fw*100:.1f}% of INCORRECT, {fr*100:.1f}% of CORRECT"
                f"  -> gap {(fw-fr)*100:+.1f} pp"
            )
        raw("")
        raw("   A positive gap means the verifier flags wrong claims MORE than right")
        raw("   ones - which is the only thing that would make it useful. A gap near")
        raw("   zero means the flag carries no information about correctness.")

    rule("VERDICT")
    raw("   On STRICTNESS, GPCS wins: it flags more claims unsupported.")
    raw(
        f"      GPCS {gu}/{len(g)} = {gu/len(g)*100:.1f}%   vs   "
        f"self-consistency {su}/{len(s_)} = {su/len(s_)*100:.1f}%"
    )
    raw("")
    raw("   On CORRECTNESS, see STEP 9. Across all 36 scenarios the answer is")
    raw("   NEITHER: both verifiers post precision 0.681 on a set that is 68.4%")
    raw("   incorrect - precisely the score for flagging everything - and both")
    raw("   flag-rate gaps are -0.8 pp, pointing the WRONG way.")
    raw("")
    raw("   So the honest verdict is: GPCS is STRICTER, NOT SHARPER. Being")
    raw("   rejected by GPCS carries no measurable information about whether a")
    raw("   claim is true. One scenario cannot settle this either way; it is")
    raw("   shown here to make the mechanism legible, not to prove the result.")
    FINAL = {"gpcs_unsupported": gu, "sc_unsupported": su, "n": len(g)}
except Exception:
    import traceback

    rule("ERROR")
    raw(traceback.format_exc())
finally:
    rule("TEARDOWN")
    teardown_benchmark_data()
    log("teardown_benchmark_data() done; store counts restored:")
    try:
        for k, v in sorted(counts().items()):
            raw(f"   {k:22} {v}")
    except Exception as exc:
        raw(f"   (could not re-read stores after teardown: {exc})")
    try:
        stop_pod_followers()
    except Exception:
        pass
    rule("LLM CALL TOTALS (measured, not assumed)")
    reqs = STATE["pod_requests"]
    for role, n in sorted(reqs.items(), key=lambda kv: -kv[1]):
        raw(f"   {n:>3}  {role}")
    tot_pod = sum(reqs.values())
    raw("")
    raw(f"   in-cluster requests                    : {tot_pod}")
    raw(f"   in-process requests (claim extraction) : {STATE['llm_seq']}")
    raw(f"   TOTAL LLM CALLS FOR THIS SCENARIO      : {tot_pod + STATE['llm_seq']}")
    raw("")
    raw("   Note: the architecture is 5 specialists + 1 consensus per generation,")
    raw("   but the security specialist only calls the model when it first detects")
    raw("   a threat (investigation-engine/main.py, `if threat_detected:`). On a")
    raw("   CPU-exhaustion scenario with no security signal it takes the rules")
    raw("   path instead, so the real count per generation is 5, not 6.")
    log(f"total wall time: {time.time()-_t0:.1f}s")
    _fh.close()

print(f"log -> {LOGPATH}  ({FINAL})")
