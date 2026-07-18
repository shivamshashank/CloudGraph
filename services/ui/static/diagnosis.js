/**
 * CloudGraph AI Investigation Diagnosis component.
 * Triggers backend investigations and parses the consensus recommendations.
 */
document.addEventListener("DOMContentLoaded", () => {
  const rcaOutput = document.getElementById("rca-output");
  const isDiagnosisPage = !!rcaOutput;

  if (!isDiagnosisPage) return;

  // Trigger Investigation / Root Cause Analysis
  async function runInvestigation() {
    const settings = JSON.parse(
      localStorage.getItem("cloudgraph_llm_settings") || "{}",
    );
    if (!settings.api_key) {
      if (typeof window.CloudGraph.showToast === "function") {
        window.CloudGraph.showToast(
          "Please add an AI API Key in LLM Settings before running AI Diagnosis.",
          "error",
        );
      }
      setTimeout(() => {
        window.location.href = "settings.html";
      }, 1500);
      return;
    }

    if (rcaOutput) {
      rcaOutput.innerHTML = `
                <div class="empty-state">
                    <div class="spinner"></div>
                    <p>Running multi-agent diagnostics... Scanning log history... Analyzing metrics correlation...</p>
                </div>`;
    }
    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/investigations/trigger`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            namespace: "cloudgraph-system",
            llm_provider: settings.provider || null,
            llm_api_key: settings.api_key || null,
            llm_model: settings.model || null,
          }),
        },
      );
      const data = await res.json();
      if (data.status === "success" && data.results.length > 0) {
        // Save to localStorage incidents
        const existingIncidents = JSON.parse(
          localStorage.getItem("cloudgraph_incidents") || "[]",
        );
        data.results.forEach((res) => {
          if (!existingIncidents.some((i) => i.title === res.title)) {
            existingIncidents.unshift({
              id:
                "incident-" +
                Date.now() +
                "-" +
                Math.random().toString(36).substr(2, 5),
              title: res.title,
              severity: res.severity || "HIGH",
              status: "Active",
              cause: res.cause || "Detected anomaly in logs/metrics.",
              remediation: res.recommendation || "Check pod details.",
              timestamp: Date.now(),
              assigned: "Unassigned",
              error_logs: res.evidence || [],
            });
          }
        });
        localStorage.setItem(
          "cloudgraph_incidents",
          JSON.stringify(existingIncidents),
        );

        renderRCA(data.results);
        window.CloudGraph.fetchGraph();
      }
    } catch (err) {
      if (rcaOutput) {
        rcaOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">Investigation failed: ${err.message}</p></div>`;
      }
    }
  }

  // Render RCA report cards
  function renderRCA(results) {
    if (!rcaOutput) return;
    if (results.length === 0) return;

    let rcaHtml = '<div class="rca-report">';

    results.forEach((res) => {
      const severityClass =
        res.severity === "CRITICAL"
          ? "rca-badge-critical"
          : res.severity === "HIGH"
            ? "rca-badge-high"
            : "rca-badge-healthy";
      const logsHtml =
        res.error_logs && res.error_logs.length > 0
          ? `<div class="rca-block">
                     <div class="rca-block-title">Anomalous Telemetry Signals</div>
                     <div class="rca-logs">
                       ${res.error_logs.map((log) => `<div class="rca-log-item">${log}</div>`).join("")}
                     </div>
                   </div>`
          : "";

      const evidenceItems =
        Array.isArray(res.relevant_evidence) && res.relevant_evidence.length > 0
          ? res.relevant_evidence
              .map((item) => {
                const confPercent = item.confidence
                  ? ` (Confidence: ${Math.round(item.confidence * 100)}%)`
                  : "";
                return `
                    <div class="evidence-item">
                        <div class="evidence-item-title">${item.label}${confPercent}</div>
                        <div class="evidence-item-detail">${item.detail}</div>
                        ${item.messages ? `<div class="evidence-item-messages">${item.messages.map((msg) => `<span class="evidence-msg">${msg}</span>`).join("")}</div>` : ""}
                    </div>
                `;
              })
              .join("")
          : '<div class="evidence-item"><div class="evidence-item-title">No graph evidence returned yet</div><div class="evidence-item-detail">The current topology does not have additional evidence for this incident.</div></div>';

      const rcConf = res.root_cause_confidence
        ? Math.round(res.root_cause_confidence * 100)
        : 80;
      const recConf = res.recommendation_confidence
        ? Math.round(res.recommendation_confidence * 100)
        : 75;

      rcaHtml += `
                <div class="rca-header">
                    <span class="rca-badge ${severityClass}">${res.severity}</span>
                    <h3 class="rca-title">${res.title}</h3>
                </div>

                <div class="rca-confidence-container">
                    <div class="rca-confidence-badge">
                        <span class="rca-conf-label">Root Cause Confidence:</span>
                        <div class="rca-conf-bar-bg">
                            <div class="rca-conf-bar-fill" style="width: ${rcConf}%; background: linear-gradient(90deg, #3b82f6, #60a5fa);"></div>
                        </div>
                        <span class="rca-conf-val">${rcConf}%</span>
                    </div>
                    <div class="rca-confidence-badge">
                        <span class="rca-conf-label">Remediation Confidence:</span>
                        <div class="rca-conf-bar-bg">
                            <div class="rca-conf-bar-fill" style="width: ${recConf}%; background: linear-gradient(90deg, #10b981, #34d399);"></div>
                        </div>
                        <span class="rca-conf-val">${recConf}%</span>
                    </div>
                </div>

                <div class="rca-block">
                    <div class="rca-block-title">Identified Root Cause</div>
                    <div class="rca-block-body">${res.cause}</div>
                </div>

                ${logsHtml}

                <div class="rca-block">
                    <div class="rca-block-title" style="color: #a5b4fc;">Relevant Evidence</div>
                    <div class="evidence-list">
                        ${evidenceItems}
                    </div>
                </div>

                <div class="rca-block rca-remediation">
                    <div class="rca-block-title" style="color: #a5b4fc;">Remediation Recommendation</div>
                    <div class="rca-block-body">${res.remediation}</div>
                </div>
            `;
    });

    rcaHtml += "</div>";
    rcaOutput.innerHTML = rcaHtml;
  }

  // Register investigation capability globally
  window.CloudGraph.runInvestigation = runInvestigation;

  // Trigger investigation on load if redirected with ?run=true
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("run") === "true") {
    window.history.replaceState({}, document.title, window.location.pathname);
    runInvestigation();
  }
});
