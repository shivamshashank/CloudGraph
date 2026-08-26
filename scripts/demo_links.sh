#!/usr/bin/env bash
# Exposes the CloudGraph UI, Neo4j (HTTP + Bolt) and Qdrant on this machine's
# LAN address, so the demo runs on a real IP rather than localhost.
#
# Two things this handles that a bare `kubectl port-forward` does not:
#   1. --address 0.0.0.0 — OrbStack binds NodePorts to 127.0.0.1 only, so
#      without this nothing is reachable from any address but localhost.
#   2. setsid — forwards started from a shell die when that shell exits.
#      Detaching them means they survive closing the terminal.
#
# Neo4j needs BOTH ports: the Browser is served over HTTP on 7474, then your
# browser opens a separate Bolt connection to 7687. Forwarding only 7474 gives
# a page that loads and then fails to connect.
#
# Usage:  ./scripts/demo_links.sh {start|stop|status}

set -uo pipefail
NS="${CLOUDGRAPH_NAMESPACE:-cloudgraph-system}"
DIR=/tmp/cloudgraph-pf
mkdir -p "$DIR"

# name|service|local:remote
TARGETS=(
  "ui|cloudgraph-ui|8080:3000"
  "neo4j-http|cloudgraph|7474:7474"
  "neo4j-bolt|cloudgraph|7687:7687"
  "qdrant|cloudgraph-qdrant|6333:6333"
  # Needed by scripts/trace_scenario.py: generation is dispatched through the
  # orchestrator, so the harness must be able to reach it from this machine.
  "orchestrator|cloudgraph-agent-orchestrator|8082:8082"
)

ip() { ipconfig getifaddr en0 2>/dev/null || echo 127.0.0.1; }

wait_ready() {
  # After a laptop restart the pods take a while to come back. Starting
  # port-forwards against a not-yet-ready service fails silently, so wait.
  local ctx; ctx=$(kubectl config current-context 2>/dev/null)
  if [ "$ctx" != "orbstack" ]; then
    echo "  switching context: $ctx -> orbstack"
    kubectl config use-context orbstack >/dev/null 2>&1
  fi
  # Only the services we forward. Demo incident pods are DELIBERATELY broken
  # (crashloop, oom-killed), so waiting for every pod in the namespace would
  # never succeed.
  local need="cloudgraph-ui cloudgraph-api investigation-engine agent-orchestrator"
  printf "  waiting for services"
  for _ in $(seq 1 40); do
    local ok=0 want=0
    for d in $need; do
      want=$((want+1))
      if [ "$(kubectl get deploy "$d" -n "$NS" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)" = "1" ]; then
        ok=$((ok+1))
      fi
    done
    if [ "$ok" = "$want" ]; then echo "  ->  $ok/$want ready"; return 0; fi
    printf "."; sleep 3
  done
  echo "  ->  timed out; check: kubectl get pods -n $NS"
  return 1
}

start() {
  stop >/dev/null 2>&1
  wait_ready || true
  for t in "${TARGETS[@]}"; do
    IFS='|' read -r name svc ports <<< "$t"
    # nohup + detached stdio. (setsid would be tidier but is Linux-only;
    # macOS does not ship it.)
    nohup kubectl port-forward --address 0.0.0.0 -n "$NS" \
      "svc/$svc" "$ports" >"$DIR/$name.log" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    echo $! > "$DIR/$name.pid"
  done
  sleep 6
  watchdog
  status
}

stop() {
  rm -f "$DIR/watchdog.on"
  pkill -f "cloudgraph-pf-watchdog" 2>/dev/null
  pkill -f "kubectl port-forward --address 0.0.0.0 -n $NS" 2>/dev/null
  rm -f "$DIR"/*.pid
  echo "stopped"
}

# `kubectl port-forward` drops its tunnel on idle timeouts, pod restarts,
# sleep/wake and network changes, and never recovers on its own. Long runs kept
# failing partway through because a forward had silently died. This supervisor
# re-establishes any that stop listening.
watchdog() {
  touch "$DIR/watchdog.on"
  ( exec -a cloudgraph-pf-watchdog bash -c '
      NS="'"$NS"'"; DIR="'"$DIR"'"
      while [ -f "$DIR/watchdog.on" ]; do
        sleep 20
        for t in "ui|cloudgraph-ui|8080:3000" \
                 "neo4j-http|cloudgraph|7474:7474" \
                 "neo4j-bolt|cloudgraph|7687:7687" \
                 "qdrant|cloudgraph-qdrant|6333:6333" \
                 "orchestrator|cloudgraph-agent-orchestrator|8082:8082"; do
          IFS="|" read -r name svc ports <<< "$t"
          lp=${ports%%:*}
          if ! lsof -nP -iTCP:"$lp" -sTCP:LISTEN 2>/dev/null | grep -q kubectl; then
            nohup kubectl port-forward --address 0.0.0.0 -n "$NS" \
              "svc/$svc" "$ports" >>"$DIR/$name.log" 2>&1 </dev/null &
            echo "$(date +%T) restarted $name" >> "$DIR/watchdog.log"
          fi
        done
      done' ) >/dev/null 2>&1 &
  disown 2>/dev/null || true
}

status() {
  local a; a=$(ip)
  echo
  for t in "${TARGETS[@]}"; do
    IFS='|' read -r name svc ports <<< "$t"
    local lp=${ports%%:*} code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://$a:$lp/" 2>/dev/null)
    # Bolt is not HTTP, so a 000 there means "not HTTP", not "down".
    if [ "$name" = "neo4j-bolt" ]; then
      nc -z -G 2 "$a" "$lp" 2>/dev/null && code="open" || code="DOWN"
    fi
    printf "  %-11s %-28s %s\n" "$name" "http://$a:$lp" "$code"
  done
  echo
  echo "  Your LAN IP is $a — it CHANGES when you switch network or reboot."
  echo "  Always read the links from this command, never from memory."
  echo
  echo "  UI      http://$a:8080"
  echo "  Neo4j   http://$a:7474      (Connect URL: bolt://$a:7687)"
  echo "  Qdrant  http://$a:6333/dashboard"
}

case "${1:-status}" in
  start) start ;; stop) stop ;; status) status ;;
  watchdog) watchdog; echo "watchdog running" ;;
  *) echo "usage: $0 {start|stop|status|watchdog}"; exit 1 ;;
esac
