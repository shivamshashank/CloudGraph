#!/usr/bin/env python3
"""Trace ONE LIVE cluster fault through the real pipeline, per retrieval condition.

Differs from scripts/trace_scenario.py in exactly four ways:

1. NO SEEDING. The graph already holds the cluster. Nothing is injected into
   Neo4j or Qdrant by this script; it reads what the ingestion pipeline found.
2. UNSCOPED RETRIEVAL. `scenario_id=None`, so retrieval queries the whole live
   graph rather than one seeded benchmark scenario.
3. observed_symptoms come from the LIVE graph — the faulted container's own log
   lines, as captured by `_ingest_pod_logs` -> `read_namespaced_pod_log()`.
4. METRIC NODES ARE EXCLUDED. `k8s_discovery._simulate_pod_metrics` generates
   every metric value with `random.uniform()`, so metric evidence is not real
   telemetry and must not enter a prompt.

Stops after GPCS and self-consistency. Claim correctness is not labelled in this
experiment, so the verifier figures it reports are inter-method concordance, not
accuracy.

Usage, from services/api:
  NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_AUTH=neo4j/PASS \
  QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333 \
  AGENT_ORCHESTRATOR_URL=http://localhost:8082 \
  .venv/bin/python ../../experiment-live/scripts/trace_live.py \
      live-checkout none ../../experiment-2-live-demo/logs/live-NONE.log
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
import subprocess  # noqa: E402
import re as _re  # noqa: E402

sys.path.insert(0, ".")

POD_MATCH = sys.argv[1] if len(sys.argv) > 1 else "live-checkout"
CONDITION = (sys.argv[2] if len(sys.argv) > 2 else "hybrid").lower()
LOGPATH = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/live.log")

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
    _fh.write("\n" + " " * 23 + "|\n")
    _fh.write(" " * 23 + f"|  {frm}  ->  {to}\n")
    for line in what.split("\n"):
        _fh.write(" " * 23 + f"|  {line}\n")
    _fh.write(" " * 23 + "v\n")
    _fh.flush()


def block(label, text):
    raw(f"--- {label} " + "-" * max(0, 74 - len(label)))
    raw(str(text))
    raw("-" * 80)


rule(f"CloudGraph LIVE execution trace — pod~{POD_MATCH}, condition {CONDITION}")
log(f"started {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
log("every value below is captured at the moment it is computed")
raw("")
raw("   LIVE RUN: the graph was built by the ingestion pipeline from a real")
raw("   Kubernetes cluster. Nothing is seeded by this script. Retrieval is")
raw("   UNSCOPED (scenario_id=None) and searches the whole live graph.")
raw("")
raw("   METRIC NODES EXCLUDED: k8s_discovery._simulate_pod_metrics() generates")
raw("   every metric value with random.uniform(). Metric evidence is therefore")
raw("   not real telemetry and is filtered out of retrieval before prompting.")

import app.research.gpcs as gpcs  # noqa: E402
import app.research.self_consistency as sc  # noqa: E402
from app.research.evaluation import (  # noqa: E402
    run_raw_context_search,
    run_hybrid_search,
)  # noqa: E402
from app.services.graphrag_search import graphrag_search  # the FUNCTION.  # noqa: E402

# `from app.services import graphrag_search` binds the MODULE, which is not
# callable. GPCS calls search_func(payload, method=...) inside a bare
# `except (ValueError, KeyError, TypeError, RuntimeError): pass`, so the
# TypeError is swallowed and its semantic-retrieval branch silently returns
# nothing. Verified 2026-08-25: module -> 0 evidence items, function -> 10.
from app.database.neo4j_client import neo4j_client  # noqa: E402
from app.database.qdrant import qdrant_client  # noqa: E402
from app.research.llm_settings import load_stored_llm_settings  # noqa: E402

if not callable(graphrag_search):
    raise SystemExit(
        "graphrag_search is not callable — the module was imported, "
        "not the function; GPCS semantic retrieval would be dead"
    )

STATE = {
    "llm_seq": 0,
    "claim_seq": 0,
    "pod_requests": collections.Counter(),
    "gpcs": [],
    "sc": [],
    "metrics_filtered": 0,
}

# ---- wrap: in-process LLM calls (claim extraction) -----------------------
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
    out = _real_call_llm(*a, **kw)
    log(f"responded in {time.time()-t:.2f}s")
    block("RESPONSE", json.dumps(out, indent=2, default=str))
    return out


gpcs.call_llm = traced_call_llm

# ---- wrap: GPCS arithmetic ----------------------------------------------
S = gpcs.GraphProvenanceClaimScorer


# ---- filter simulated metrics out of GPCS's own evidence ----------------
# GPCS retrieves independently of the condition's retrieval_results, so the
# metric exclusion has to be applied here too. Without this, the top-scoring
# evidence for a memory claim is `metric summary pod_memory_utilization_ratio
# value 64.2...` — a random.uniform() number, not telemetry.
def _is_simulated_metric(item):
    txt = str(item.get("text") or item.get("name") or "")
    if "utilization_ratio" in txt or txt.startswith("metric summary"):
        return True
    if item.get("label") == "Metric" or item.get("type") == "Metric":
        return True
    if "Metric" in (item.get("labels") or []):
        return True
    return (item.get("metadata") or {}).get("label") == "Metric"


_real_retrieve = S._retrieve_supporting_evidence


@functools.wraps(_real_retrieve)
def traced_retrieve(self, claim, search_func):
    ev = _real_retrieve(self, claim, search_func)
    kept = [e for e in ev if not _is_simulated_metric(e)]
    STATE["metrics_filtered"] += len(ev) - len(kept)
    return kept


S._retrieve_supporting_evidence = traced_retrieve

_real_agg, _real_score = S._aggregate_evidence_metrics, S._score_claim
_pending = {}


@functools.wraps(_real_agg)
def traced_agg(self, evidence):
    best, hop, rel, bev = _real_agg(self, evidence)
    _pending["agg"] = dict(best=best, hop=hop, rel=rel, n=len(evidence))
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
        raw("        (aggregation never ran; no semantic/hop/reliability value)")
    else:
        raw(
            f"        semantic    = {agg['best']:.4f}  x {self.semantic_weight}  "
            f"= {agg['best']*self.semantic_weight:.4f}"
        )
        raw(f"        min_hop     = {agg['hop']}")
        # gpcs.py:_score_claim — hop_distance None means the evidence came from
        # semantic search with no path back into the graph. That is ABSENT
        # provenance, not zero hops, so it earns no proximity and no penalty.
        if agg["hop"] is None:
            prox = 0.0
            pen = 0.0
            raw(
                f"        proximity   = 0.0000 (hop is None -> absent provenance, "
                f"earns no graph credit)  x {self.graph_weight} = 0.0000"
            )
        else:
            prox = 1.0 / (1.0 + agg["hop"])
            pen = self.penalty_weight * (agg["hop"] * 0.05)
            raw(
                f"        proximity   = 1/(1+{agg['hop']}) = {prox:.4f}  "
                f"x {self.graph_weight} = {prox*self.graph_weight:.4f}"
            )
        raw(
            f"        reliability = {agg['rel']:.4f}  x {self.reliability_weight} "
            f"= {agg['rel']*self.reliability_weight:.4f}"
        )
        raw(f"        penalty     = -{pen:.4f}")
    unsup = trust < self.threshold
    raw(
        f"        TRUST = {trust:.3f}   ->  "
        f"{'UNSUPPORTED' if unsup else 'supported'} "
        f"({'<' if unsup else '>='} {self.threshold})"
    )
    STATE["gpcs"].append({"n": n, "trust": trust, "unsupported": unsup})
    return trust, ev


S._aggregate_evidence_metrics, S._score_claim = traced_agg, traced_score

# ---- in-cluster pod call capture ----------------------------------------
POD_SERVICES = ["investigation-engine", "agent-orchestrator"]
_NS = "cloudgraph-system"
_MARK = _re.compile(r"\[LLM (REQUEST|RESPONSE)\]\s*(.*)")
_NOISE = _re.compile(
    r"^(INFO:|WARNING:|\d+\.\d+\.\d+\.\d+ - -|"
    r"Received notification from DBMS|Qdrant )"
)


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def log_pod_calls(label, since_iso):
    total = 0
    for svc in POD_SERVICES:
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
            continue
        calls, cur = [], None
        for line in out.split("\n"):
            m = _MARK.search(line)
            if m:
                if cur:
                    calls.append(cur)
                cur = {"kind": m.group(1).lower(), "body": []}
            elif cur is not None and not _NOISE.search(line):
                cur["body"].append(line)
        if cur:
            calls.append(cur)
        for c in calls:
            total += 1
            body = "\n".join(c["body"]).strip()
            rule(f"IN-CLUSTER LLM CALL  [{svc}]  {c['kind'].upper()}  ({label})")
            try:
                parsed = json.loads(body)
                role = (parsed.get("instructions") or "")[:60]
                if role:
                    STATE["pod_requests"][role] += 1 if c["kind"] == "request" else 0
                block(f"{c['kind'].upper()} BODY", json.dumps(parsed, indent=2))
            except Exception:
                block(f"{c['kind'].upper()} BODY", body)
    log(f"captured {total} in-cluster call lines for {label}")


def store_counts():
    q = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC"
    out = {}
    try:
        for r in neo4j_client.execute_query(q) or []:
            out[r["label"] or "?"] = r["c"]
    except Exception as exc:
        out["<neo4j unavailable>"] = str(exc)
    try:
        if qdrant_client.connect():
            for cn in qdrant_client.collection_names:
                try:
                    out[f"qdrant:{cn}"] = qdrant_client.client.count(cn).count
                except Exception:
                    pass
    except Exception:
        pass
    return out


# =========================================================================
FINAL = {}
try:
    settings = load_stored_llm_settings() or {}

    rule("STEP 1 — LOCATE THE FAULT IN THE LIVE GRAPH")
    pod_rows = (
        neo4j_client.execute_query(
            "MATCH (p:Pod) WHERE p.name CONTAINS $m RETURN p.name AS name, "
            "p.status AS status, p.id AS id LIMIT 1",
            {"m": POD_MATCH},
        )
        or []
    )
    if not pod_rows:
        raise SystemExit(f"no Pod matching {POD_MATCH!r} in the graph")
    pod = pod_rows[0]
    log(f"pod            = {pod['name']}")
    log(f"status         = {pod['status']}")

    # observed_symptoms = the container's OWN log lines, as ingested.
    log_rows = (
        neo4j_client.execute_query(
            "MATCH (p:Pod)-[:GENERATES]->(l:Log) WHERE p.name = $n "
            "RETURN l.level AS level, l.message AS message, l.timestamp AS ts "
            "ORDER BY l.timestamp DESC LIMIT 40",
            {"n": pod["name"]},
        )
        or []
    )
    symptoms = [
        f"{r['level']} {r['message']}".strip() for r in log_rows if r.get("message")
    ]
    if not symptoms:
        symptoms = [f"Pod {pod['name']} reported status {pod['status']}"]
    log(
        f"observed_symptoms = {len(symptoms)} REAL log lines from the container (THE INPUT)"  # noqa: E501
    )
    for s_ in symptoms:
        raw(f"   - {s_}")

    incident = {
        "id": f"live-{POD_MATCH}",
        "target_entity": pod["name"],
        "target_service": POD_MATCH,
        "query": f"{POD_MATCH} degraded performance investigation",
        "observed_symptoms": symptoms,
        "status": pod["status"],
    }
    try:
        incident["inject_time"] = int(
            pathlib.Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("evidence/inject_time.txt")
            .read_text(encoding="utf-8")
            .strip()
        )
    except Exception:
        incident["inject_time"] = int(time.time())
    log(f"inject_time    = {incident['inject_time']}")

    rule("STEP 2 — STORE STATE (no seeding; this is the live cluster)")
    for k, v in sorted(store_counts().items()):
        raw(f"   {k:22} {v}")

    link(
        "STEP 2 store",
        "STEP 3 retrieval",
        "Nothing was seeded. Whatever retrieval returns was placed in the\n"
        "          graph by the ingestion pipeline from the real cluster.",
    )

    rule("STEP 3 — RETRIEVAL (unscoped, live graph)")
    log(f"condition={CONDITION}  query={incident['query']!r}  scenario_id=None")
    t = time.time()
    if CONDITION == "none":
        retrieval = None
    elif CONDITION == "raw":
        retrieval = run_raw_context_search(incident["query"], scenario_id=None)
    else:
        raw("   score = 0.50*vector_similarity + 0.30*graph_proximity + 0.20*recency")
        retrieval = run_hybrid_search(
            incident["query"], reference_time=incident["inject_time"], scenario_id=None
        )
    dt = time.time() - t

    # Drop simulated Metric evidence before it can reach a prompt.
    dropped = 0
    if retrieval:
        kept = []
        for r in retrieval:
            labels = r.get("labels") or []
            props = r.get("properties") or {}
            is_metric = (
                "Metric" in labels
                or (r.get("metadata") or {}).get("label") == "Metric"
                or "utilization_ratio" in str(props.get("name", ""))
            )
            if is_metric:
                dropped += 1
            else:
                kept.append(r)
        retrieval = kept
    log(
        f"returned {len(retrieval) if retrieval else 0} items in {dt:.3f}s (no LLM involved)"  # noqa: E501
    )
    if dropped:
        log(
            f"dropped {dropped} simulated Metric items before prompting "
            f"(random.uniform values — not telemetry)"
        )
    for i, r in enumerate(retrieval or [], 1):
        raw(f"   [{i}] score={r.get('score', '-')} :: {str(r.get('text') or r)}")

    scorer = gpcs.GraphProvenanceClaimScorer(llm_settings=settings)
    scorer.scenario_id = None

    link(
        "STEP 3 retrieval",
        "STEP 4 generation",
        "The retrieved items are passed to the orchestrator as\n"
        "          retrieval_results. Under condition=none this is None, so the\n"
        "          agents reason from the incident description alone.",
    )

    rule("STEP 4 — GENERATION x3 + SELF-CONSISTENCY")
    log(
        f"n_samples=3 temperature=0.8 similarity_threshold="
        f"{sc.RECURRENCE_SIMILARITY_THRESHOLD}"
    )
    _real_one = sc._generate_one_sample
    _gen_n = {"i": 0}

    @functools.wraps(_real_one)
    def traced_one_sample(*a, **kw):
        _gen_n["i"] += 1
        i = _gen_n["i"]
        since = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        rule(f"GENERATION {i} of 3 — dispatch to agent-orchestrator")
        t0 = time.time()
        out = _real_one(*a, **kw)
        log(f"generation {i} returned in {time.time()-t0:.2f}s")
        time.sleep(3)
        log_pod_calls(f"generation {i}", since)
        return out

    sc._generate_one_sample = traced_one_sample

    t = time.time()
    sc_result = sc.generate_and_score(
        incident,
        n_samples=3,
        temperature=0.8,
        call_options={"request_logger": lambda r: None, "retrieval_results": retrieval},
    )
    log(f"generation + extraction + recurrence scoring took {time.time()-t:.2f}s")
    for i, g in enumerate(sc_result["generations"], 1):
        block(f"GENERATION {i} (temperature 0.8)", json.dumps(g, indent=2, default=str))
    log(
        f"claims extracted from primary generation: {len(sc_result['extracted_claims'])}"  # noqa: E501
    )

    link(
        "STEP 4 generation",
        "STEP 5 self-consistency",
        "Generation 1 is the PRIMARY. Its claims are the claim set. Claims\n"
        "          from generations 2 and 3 exist only to answer: did this recur?",
    )

    rule("STEP 5 — SELF-CONSISTENCY VERDICTS")
    raw("   supported  <=> an equivalent claim (cosine >= 0.8) recurs in >= half")
    raw("                  of the OTHER generations.  Measures STABILITY, not truth.")
    for i, c in enumerate(sc_result["claims"], 1):
        rr = c.get("recurrence_rate")
        log(
            f"  claim {i:>2}: recurrence={rr}  -> "
            f"{'UNSUPPORTED' if c.get('unsupported') else 'supported'}"
        )
        raw(f"        {str(c.get('text'))}")
        STATE["sc"].append(
            {"n": i, "rec": rr, "unsupported": bool(c.get("unsupported"))}
        )

    link(
        "STEP 5 self-consistency",
        "STEP 6 GPCS",
        "GPCS now scores the SAME claim list, from the SAME extraction. Only\n"
        "          the mechanism differs: self-consistency asked whether the model\n"
        "          repeated itself; GPCS asks whether the live graph supports it.",
    )

    rule("STEP 6 — GPCS SCORING (arithmetic per claim)")
    log(
        f"weights semantic={scorer.semantic_weight} graph={scorer.graph_weight} "
        f"reliability={scorer.reliability_weight} penalty={scorer.penalty_weight}"
    )
    log(
        f"threshold={scorer.threshold}  evidence_floor={gpcs.MIN_SEMANTIC_EVIDENCE_SCORE}"  # noqa: E501
    )
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
    log(
        f"simulated Metric items filtered from GPCS evidence: {STATE['metrics_filtered']}"  # noqa: E501
    )

    rule("FINAL RESULT")
    g, s_ = STATE["gpcs"], STATE["sc"]
    gu = sum(1 for x in g if x["unsupported"])
    su = sum(1 for x in s_ if x["unsupported"])
    log(f"claims scored               : {len(g)}")
    if g:
        log(f"GPCS unsupported            : {gu}/{len(g)} = {gu/len(g)*100:.1f}%")
    if s_:
        log(f"self-consistency unsupported: {su}/{len(s_)} = {su/len(s_)*100:.1f}%")
    quad = collections.Counter()
    raw("")
    raw(
        f"   {'#':<4}{'TRUST':>8}  {'GPCS':<13}{'RECUR':>7}  {'SELF-CONSISTENCY':<18}CLAIM"  # noqa: E501
    )
    # Claim text is NEVER truncated here. A [:52] cap on this line is what
    # produced the 52-character claim_text column in experiment/results/claims.csv.
    for x, y, c in zip(g, s_, gpcs_result["claims"]):
        quad[(x["unsupported"], y["unsupported"])] += 1
        raw(
            f"   {x['n']:<4}{x['trust']:>8.3f}  "
            f"{'UNSUPPORTED' if x['unsupported'] else 'supported':<13}"
            f"{str(y['rec']):>7}  "
            f"{'UNSUPPORTED' if y['unsupported'] else 'supported':<18}"
            f"{str(c.get('text'))}"
        )
    if g:
        agree = quad[(False, False)] + quad[(True, True)]
        raw("")
        log(f"agreement (concordance)     : {agree}/{len(g)} = {agree/len(g)*100:.1f}%")
        raw(f"   both supported      {quad[(False, False)]:>3}")
        raw(f"   both unsupported    {quad[(True, True)]:>3}")
        raw(f"   GPCS only flagged   {quad[(True, False)]:>3}")
        raw(f"   SC only flagged     {quad[(False, True)]:>3}")
        raw("")
        raw("   Agreement is CONCORDANCE, never accuracy: both verifiers can be")
        raw("   wrong about the same claim and it still counts as agreement.")
        raw("")
        raw("   NO GROUND-TRUTH STEP HERE. The injected fault is known (sustained")
        raw("   memory pressure on live-checkout); labelling is done by hand")
        raw("   against a pre-written rubric in results/LABELS.md.")
        trusts = sorted({round(x["trust"], 3) for x in g})
        log(f"distinct trust scores observed: {trusts}")

    FINAL = {
        "condition": CONDITION,
        "pod": pod["name"],
        "retrieved": len(retrieval or []),
        "metrics_dropped": dropped,
        "claims": len(g),
        "gpcs_unsupported": gu,
        "sc_unsupported": su,
        "quad": {str(k): v for k, v in quad.items()},
    }

except SystemExit as exc:
    rule("ABORTED")
    raw(str(exc))
except Exception:
    import traceback

    rule("ERROR")
    raw(traceback.format_exc())
finally:
    rule("NO TEARDOWN — the live cluster is left as it is")
    raw("   This script seeds nothing, so there is nothing to tear down.")
    raw("   Store counts at exit:")
    try:
        for k, v in sorted(store_counts().items()):
            raw(f"   {k:22} {v}")
    except Exception as exc:
        raw(f"   (could not re-read stores: {exc})")
    rule("LLM CALL TOTALS (measured, not assumed)")
    reqs = STATE["pod_requests"]
    for role, n in sorted(reqs.items(), key=lambda kv: -kv[1]):
        raw(f"   {n:>3}  {role}")
    tot_pod = sum(reqs.values())
    raw("")
    raw(f"   in-cluster requests                    : {tot_pod}")
    raw(f"   in-process requests (claim extraction) : {STATE['llm_seq']}")
    raw(f"   TOTAL LLM CALLS                        : {tot_pod + STATE['llm_seq']}")
    if FINAL:
        raw("")
        block("MACHINE-READABLE SUMMARY", json.dumps(FINAL, indent=2))
    log(f"total wall time: {time.time()-_t0:.1f}s")
    _fh.close()
