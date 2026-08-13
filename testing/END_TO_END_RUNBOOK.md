# End-to-End Runbook: Linux server → full research report

Every command below, in order, with the exact path it's run from. This
assumes the flow agreed on: a Linux server → `cloudgraph deploy` →
UI → connect an LLM provider via Settings → demo incidents → verify RCA →
full report run → significance tests + figures.

**Prerequisites:** SSH access to a Linux server (Ubuntu/Debian assumed —
substitute your distro's package manager if not) with `sudo`, reachable
from wherever you're running these commands from. Any real or virtual
Linux machine works — bare metal, a cloud VM, or a local VM — nothing
below is tied to a specific hypervisor or provider.

**Two things that will bite you if skipped** (both already cost real time
this project):

1. **Local uncommitted changes aren't on any remote yet.** If you have
   working-tree changes, `git clone` from GitHub/GitLab right now would get
   you the *old* code. **Don't clone — copy this exact working directory to
   the server** (Step 1) unless you know everything you need is already
   pushed.
2. **The published `ghcr.io/shivamshashank/cloudgraph-*:latest` images are
   stale** (built before today, from whatever was last pushed — not your
   latest local fixes). `cloudgraph deploy` will happily pull and run them
   with no error. **You must build fresh images locally on the server and
   load them in** (Step 4) or you'll be debugging bugs you already fixed,
   again, on the server.

---

## 0. On your local machine — nothing to run yet, just know the path

Repo root on this machine, e.g.: `/Users/shivam_shashank/CloudGraph`
(substitute your actual path throughout).

---

## 1. Copy the current source onto the server

From your **local machine**, not the server:

```bash
rsync -avz --progress \
  --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='.git' \
  /path/to/CloudGraph/ \
  <user>@<server>:~/CloudGraph/
```

Substitute `<user>@<server>` with your actual SSH target. Everything from
here runs **on the server** (`ssh <user>@<server>`) unless marked
otherwise.

---

## 2. Install prerequisites (on the server)

```bash
sudo apt-get update
sudo apt-get install -y docker.io kubectl golang-go git python3 rsync
sudo usermod -aG docker "$USER" && newgrp docker
```

(No Python venv needed for `testing/intensive/`'s scripts — they only need
stdlib-only `python3`. A venv IS needed for `testing/report/
run_report_batched.sh` and `testing/verify/run_verification.sh` — see
Step 10.)

---

## 3. Build the CLI from this exact source

```bash
cd ~/CloudGraph
go build -o cloudgraph ./cmd/cloudgraph
```

This embeds today's Helm chart changes (`deployments/helm/cloudgraph/`) —
that's why it must be built from the rsynced tree, not `go install` from a
release tag.

---

## 4. Deploy CloudGraph, then swap in fresh images

```bash
cd ~/CloudGraph
sudo ./cloudgraph deploy
```

Follow the prompts (install kubeadm if no cluster detected). Wait for it to
finish — pods will come up running the **stale** ghcr.io images at this
point, that's expected.

Now build and load the real images (kubeadm/containerd, not the `docker`
daemon directly, is what actually runs pods — this imports into
containerd's `k8s.io` namespace so `imagePullPolicy: IfNotPresent`, already
the chart default, finds them locally instead of re-pulling):

```bash
cd ~/CloudGraph

for svc in api:cloudgraph-api ui:cloudgraph-ui \
           agent-orchestrator:cloudgraph-agent-orchestrator \
           investigation-engine:cloudgraph-investigation-engine; do
  dir="${svc%%:*}"; name="${svc##*:}"
  docker build -t "ghcr.io/shivamshashank/${name}:latest" \
    -f "services/${dir}/Dockerfile" "services/${dir}"
  docker save "ghcr.io/shivamshashank/${name}:latest" -o "/tmp/${name}.tar"
  sudo ctr -n k8s.io images import "/tmp/${name}.tar"
done

kubectl rollout restart deployment \
  cloudgraph-api cloudgraph-ui agent-orchestrator investigation-engine \
  -n cloudgraph-system
```

---

## 5. Verify pods healthy

```bash
kubectl get pods -n cloudgraph-system -w
# Ctrl-C once everything shows Running/Ready
```

**If pods are stuck `Unknown`/`NotReady` and the API server refuses
connections** (`kubectl` errors with "connection refused" on :6443): check
whether swap is enabled — kubelet refuses to start with swap on, and some
Linux server/VM images enable swap by default or re-enable it across a
restart:

```bash
sudo swapoff -a
sudo systemctl restart kubelet
# wait ~30s, then re-check
kubectl get nodes
```

This happened once already in real operation on a server set up this exact
way — it's not hypothetical.

---

## 6. Access the UI

```bash
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000
```

Open `http://<server-ip-or-localhost>:3000` in a browser that can reach the
server (or forward the port again from your local machine over SSH:
`ssh -L 3000:localhost:3000 <user>@<server>`, then browse to
`http://localhost:3000`).

---

## 7. Connect an LLM provider

```bash
cd ~/CloudGraph
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080 &
```

Navigate to **LLM Settings** in the UI (Step 6's port-forward) and enter a
provider (OpenAI, Gemini, or Meta Llama API), a valid paid/upgraded-tier
API key, and optionally a model name. Or set it directly over the API
port-forward above:

```bash
curl -s -X POST http://localhost:8080/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"provider":"openai","api_key":"sk-...","model":"gpt-4o-mini"}'
```

Verify:

```bash
curl -s http://localhost:8080/api/v1/settings
# expect: {"status":"success","settings":{"provider":"openai","api_key":"sk-...","model":"gpt-4o-mini"}}
```

---

## 8. Apply demo incidents

`testing/intensive/` is split into numbered steps — each does one thing:

```bash
cd ~/CloudGraph
testing/intensive/00_check_prereqs.sh http://localhost:8080   # cluster + API + LLM provider reachable
testing/intensive/01_apply_incidents.sh --list                # see the 5 available
testing/intensive/01_apply_incidents.sh                        # apply all 5
testing/intensive/02_verify_incidents.sh http://localhost:8080 http://localhost:3000
```

`02_verify_incidents.sh` doesn't just check `kubectl get pods` — it
triggers cluster discovery (the same step the UI does automatically) and
confirms the broken pods actually show up as graph nodes, then prints
exactly what to click next.

---

## 9. Verify real RCA from the UI

In the browser (Step 6's UI): navigate to **AI Diagnosis** and click **Run
AI Diagnosis** on one of the pods `02_verify_incidents.sh` confirmed.
Confirm you get real, specific findings (not generic rule-based-fallback
text) — this is the live-path equivalent of what the research report
(Steps 10–11) measures automatically.

Teardown the incidents when done poking at them:

```bash
testing/intensive/03_teardown_incidents.sh
```

---

## 10. Generate the research report (batched)

Two ways to run this, same underlying logic either way — see
`testing/README.md` for when to use which. This section covers the local-
checkout path (`testing/report/run_report_batched.sh`), which needs a
Python venv:

```bash
cd ~/CloudGraph/services/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then, from the repo root:

```bash
cd ~/CloudGraph
NEO4J_PASSWORD=<password> testing/report/run_report_batched.sh http://localhost:8080
```

**Why batched, not one long run:** the report job's state is in-memory
only, by design (`app/research/report_runner.py`'s own docstring) — a pod
restart mid-run discards all progress, no resume. A real crash mid-run
already cost 19/25 scenarios of progress once. Batching (default: 5
batches of 5 scenarios) means a crash only costs the current batch, and
`scripts/merge_reports.py` combines the batches into
`experiments/results/` automatically at the end.

Pilot first, to verify the pipeline works before committing to the full
run:

```bash
REPORT_TOTAL_SCENARIOS=1 REPORT_BATCH_SIZE=1 NEO4J_PASSWORD=<password> \
  testing/report/run_report_batched.sh http://localhost:8080
```

Check the summary: `Claims scored:` should be **> 0**. If everything comes
back excluded, stop and diagnose before running the full benchmark.

Full run — the shipped result used 6 batches of 6 for 36 scenarios. This
takes a long time (the published run made 1,974 agent LLM calls: 36
scenarios × 3 context conditions × up to 3 self-consistency samples × 5
specialists + 1 consensus each). Consider `tmux`/`screen` so it survives an SSH disconnect:

```bash
NEO4J_PASSWORD=<password> testing/report/run_report_batched.sh http://localhost:8080
```

Old single-shot behavior (no batching, not recommended given the crash
risk above) is still available:

```bash
NEO4J_PASSWORD=<password> testing/report/run_report_batched.sh --full
```

Alternative — the primary, no-local-checkout path via the CLI directly
(works from any machine that can reach the API, saves to
`~/.cloudgraph/reports/report-<timestamp>/` per run):

```bash
./cloudgraph report --limit 5 --offset 0 http://localhost:8080
./cloudgraph report --limit 5 --offset 5 http://localhost:8080
# ... --offset 10, 15, 20 ...
# then merge the 5 saved report-<timestamp>/ directories:
cd services/api && .venv/bin/python scripts/merge_reports.py \
  ~/.cloudgraph/reports/report-A ~/.cloudgraph/reports/report-B ... \
  --out ../../experiments/results
```

---

## 11. Verify the results are reproducible + regenerate figures

```bash
cd ~/CloudGraph
testing/verify/run_verification.sh
```

Runs the research module test suite, then re-runs
`scripts/paired_bootstrap.py` (significance tests) and
`scripts/make_figures.py` (the 3 figures) against whatever's now in
`experiments/results/` — confirms every number/figure actually
regenerates from the saved data, not just that the report ran. See
`experiments/README.md` for what the results actually say.

**Not run by this step** (needs its own real LLM calls against a live
cluster): the matched-compute control —

```bash
cd services/api
.venv/bin/python scripts/run_matched_compute_control.py
```

---

## 12. Cleanup (when done)

```bash
# Tear down demo incidents if still applied
testing/intensive/03_teardown_incidents.sh

# Uninstall CloudGraph entirely
sudo ~/CloudGraph/cloudgraph uninstall
```

Or decommission the server itself, however you provisioned it.
