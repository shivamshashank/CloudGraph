# End-to-End Runbook: OrbStack Linux VM → full research report

Every command below, in order, with the exact path it's run from. This
assumes the flow agreed on: OrbStack Linux VM → `cloudgraph deploy` →
UI → connect an LLM provider via Settings → demo incidents → verify RCA →
full report run.

**Two things that will bite you if skipped** (both already cost real time
this session):

1. **Local uncommitted changes aren't on any remote yet.** Today's fixes
   (the timeout-chain fix, `testing/`, the extra demo
   incidents) exist only in this working directory. `git clone` from
   GitHub/GitLab right now would get you the *old* code. **Don't clone —
   copy this exact working directory to the VM** (Step 2).
2. **The published `ghcr.io/shivamshashank/cloudgraph-*:latest` images are
   stale** (built before today, from whatever was last pushed — not this
   session's fixes). `cloudgraph deploy` will happily pull and run them
   with no error. **You must build fresh images locally on the VM and load
   them in** (Step 5) or you'll be debugging the exact bugs we already
   fixed, again, on the VM.

---

## 0. On the macOS host — nothing to run yet, just know the path

Repo root on this machine: `/Users/shivam_shashank/CloudGraph`

---

## 1. Create the OrbStack Linux VM

```bash
orb create ubuntu cloudgraph-vm
orb -m cloudgraph-vm
```

> Verify against `orb --help` / `orb create --help` first — OrbStack's CLI
> flags aren't something this session has directly tested, unlike
> everything below, which has.

Everything from here runs **inside the VM** unless marked otherwise.

---

## 2. Copy the current source onto the VM

From the **macOS host**, not the VM:

```bash
rsync -avz --progress \
  --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='.git' \
  /Users/shivam_shashank/CloudGraph/ \
  cloudgraph-vm:~/CloudGraph/
```

(OrbStack machines are reachable by name over SSH automatically — if that
resolves differently in your setup, substitute the VM's actual
user@host.)

---

## 3. Install prerequisites (inside the VM)

```bash
sudo apt-get update
sudo apt-get install -y docker.io kubectl golang-go git python3 rsync
sudo usermod -aG docker "$USER" && newgrp docker
```

(No Python venv needed anywhere in this flow — `apply_demo_incidents.sh`
only needs stdlib-only `python3`, and the research report goes through
`cloudgraph report` over HTTP, not a local script.)

---

## 4. Build the CLI from this exact source

```bash
cd ~/CloudGraph
go build -o cloudgraph ./cmd/cloudgraph
```

This embeds today's Helm chart changes (`deployments/helm/cloudgraph/`) —
that's why it must be built from the rsynced tree, not `go install` from a
release tag.

---

## 5. Deploy CloudGraph, then swap in fresh images

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

## 6. Verify pods healthy

```bash
kubectl get pods -n cloudgraph-system -w
# Ctrl-C once everything shows Running/Ready
```

---

## 7. Access the UI

```bash
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000
```

Open `http://<vm-ip-or-localhost>:3000` in a browser reachable from the VM
(or forward from your Mac too, depending on your OrbStack network setup).

---

## 8. Connect an LLM provider

```bash
cd ~/CloudGraph
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080 &
```

Open `http://localhost:8080` isn't the UI — use the UI port-forward from
Step 7, navigate to **LLM Settings**, and enter a provider (OpenAI, Gemini,
or Meta Llama API), a valid paid/upgraded-tier API key, and optionally a
model name. Or set it directly over the API port-forward above:

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

## 9. Apply demo incidents

```bash
cd ~/CloudGraph
testing/intensive/apply_demo_incidents.sh --list      # see the 5 available
testing/intensive/apply_demo_incidents.sh              # apply all 5
kubectl get pods -n cloudgraph-system                  # watch them fail on purpose
```

---

## 10. Verify real RCA from the UI

In the browser (Step 7's UI): trigger cluster discovery, then click
**Run AI Diagnosis**. Confirm you get real, specific findings (not the
generic rule-based fallback text) — this is the live-path equivalent of
what the research report (Steps 11–12) measures automatically.

Teardown the incidents when done poking at them:

```bash
testing/intensive/apply_demo_incidents.sh --teardown
```

---

## 11. Generate the pilot report (verify real data before the long run)

No Python venv, no Neo4j password, no extra port-forwards needed here —
`cloudgraph report` talks to the already-running, already-configured API
over the same port-forward from Step 8:

```bash
cd ~/CloudGraph
./cloudgraph report --limit 3 http://localhost:8080
```

It checks an LLM provider is connected (failing fast with a clear message
if not — same check as the UI toast), starts the run, and sits polling
with live progress until it finishes (this ties up the terminal for the
run's duration, by design — open a new SSH session for anything else).

Check the summary at the end: `Claims scored:` should be **> 0** and the
scenarios-evaluated count should show **> 0** evaluated. If everything
comes back excluded again, stop and diagnose before running the full 25 —
same discipline as before.

---

## 12. Full report run (all 25 scenarios)

Only after Step 11 comes back clean:

```bash
cd ~/CloudGraph
./cloudgraph report http://localhost:8080
```

This can run for a long time (potentially hours) on CPU-only local
inference — 25 scenarios × up to 3 samples × up to 6 sequential LLM calls
each. Consider `tmux`/`screen` on the VM so it survives an SSH disconnect
(the run itself lives server-side in the API pod regardless — if the CLI
loses contact, re-running `cloudgraph report` after reconnecting will just
tell you a run is already in progress rather than starting a duplicate;
poll again with the same command once network is back).

Results are saved locally, on whatever machine you ran the CLI from, to
`~/.cloudgraph/reports/report-<timestamp>/`:

- `claims.csv` — the actual per-claim comparison table
- `agreement_crosstab.csv` — GPCS vs. self-consistency agreement by claim type
- `excluded_scenarios.json` — should be empty or near-empty this time
- `summary.txt` — the same summary the CLI printed, saved for later

---

## 13. Cleanup (when done)

```bash
# Tear down demo incidents if still applied
testing/intensive/apply_demo_incidents.sh --teardown

# Uninstall CloudGraph entirely
sudo ~/CloudGraph/cloudgraph uninstall

# Or just delete the whole VM from the macOS host
orb delete cloudgraph-vm
```
