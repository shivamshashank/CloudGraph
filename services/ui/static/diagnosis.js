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
    let settings = {};
    try {
      const res = await fetch(`${window.CloudGraph.API_BASE}/api/v1/settings`);
      const data = await res.json();
      if (data.status === "success" && data.settings) {
        settings = data.settings;
      }
    } catch (err) {
      console.error("Failed to fetch settings:", err);
    }

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

      const claimsHtml =
        res.claim_scoring && Array.isArray(res.claim_scoring.claims)
          ? res.claim_scoring.claims
              .map((claim) => {
                const claimStateClass = claim.unsupported
                  ? "claim-card-unsupported"
                  : "claim-card-supported";
                return `
                    <div class="claim-card ${claimStateClass}">
                        <div class="claim-card-title">${escapeHtml(claim.text)}</div>
                        <div class="claim-card-meta">
                            <span class="claim-pill">${escapeHtml(claim.claim_type)}</span>
                            <span class="claim-pill">Score ${escapeHtml(claim.trust_score)}</span>
                            ${claim.unsupported ? '<span class="claim-pill claim-pill-warning">Unsupported</span>' : ""}
                        </div>
                        <div class="claim-card-support">
                            ${
                              Array.isArray(claim.supporting_evidence) &&
                              claim.supporting_evidence.length > 0
                                ? claim.supporting_evidence
                                    .map(
                                      (evidence) => `
                                    <div class="claim-support-item">
                                        <span class="claim-support-label">${escapeHtml(evidence.label)}</span>
                                        <span class="claim-support-detail">Score ${escapeHtml(evidence.score)} • hop ${escapeHtml(evidence.hop_distance)}</span>
                                    </div>
                                `,
                                    )
                                    .join("")
                                : '<div class="claim-support-empty">No provenance evidence found.</div>'
                            }
                        </div>
                    </div>
                `;
              })
              .join("")
          : "<div class='empty-state'><p>No claim provenance available.</p></div>";

      const rcConf = res.root_cause_confidence
        ? Math.round(res.root_cause_confidence * 100)
        : 80;
      const recConf = res.recommendation_confidence
        ? Math.round(res.recommendation_confidence * 100)
        : 75;
      const unsupportedRate = res.claim_scoring
        ? Math.round((res.claim_scoring.unsupported_claim_rate || 0) * 100)
        : 0;

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

                <div class="rca-block">
                    <div class="rca-block-title" style="color: #a5b4fc;">Claim Provenance</div>
                    <div class="claim-list">
                        ${claimsHtml}
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

  // Context Explorer page behavior
  const contextQuery = document.getElementById("context-query");
  const btnContextCompare = document.getElementById("btn-context-compare");
  const contextOutput = document.getElementById("context-comparison-output");
  const tabInvestigation = document.getElementById("tab-investigation");
  const tabContextExplorer = document.getElementById("tab-context-explorer");
  const investigationPanel = document.getElementById("investigation-panel");
  const contextExplorerPanel = document.getElementById(
    "context-explorer-panel",
  );
  const viewToggle = document.getElementById("context-view-toggle");
  let activeContextView = "payload";

  function setActiveTab(tab) {
    if (!tabInvestigation || !tabContextExplorer) return;
    tabInvestigation.classList.toggle(
      "tab-button-active",
      tab === "investigation",
    );
    tabContextExplorer.classList.toggle(
      "tab-button-active",
      tab === "context-explorer",
    );
    if (investigationPanel && contextExplorerPanel) {
      investigationPanel.classList.toggle("hidden", tab !== "investigation");
      contextExplorerPanel.classList.toggle(
        "hidden",
        tab !== "context-explorer",
      );
    }
  }

  if (tabInvestigation) {
    tabInvestigation.addEventListener("click", () =>
      setActiveTab("investigation"),
    );
  }
  if (tabContextExplorer) {
    tabContextExplorer.addEventListener("click", () =>
      setActiveTab("context-explorer"),
    );
  }

  if (btnContextCompare) {
    btnContextCompare.addEventListener("click", runContextComparison);
  }
  if (contextQuery) {
    contextQuery.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runContextComparison();
    });
  }
  if (viewToggle) {
    viewToggle.addEventListener("click", (event) => {
      const button = event.target.closest(".view-toggle-button");
      if (!button) return;
      activeContextView = button.dataset.view || "payload";
      viewToggle.querySelectorAll(".view-toggle-button").forEach((btn) => {
        btn.classList.toggle("view-toggle-active", btn === button);
      });
      const currentData = window._contextComparisonData;
      if (currentData) {
        renderContextComparison(currentData);
      }
    });
  }

  async function runContextComparison() {
    if (!contextQuery || !contextOutput) return;
    const query = contextQuery.value.trim();
    if (!query) {
      contextOutput.innerHTML = `<div class="empty-state"><p>Enter a query to compare context payloads.</p></div>`;
      return;
    }

    contextOutput.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Requesting context comparison for '${escapeHtml(query)}'...</p>
            </div>`;

    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/investigations/context-comparison`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, namespace: "cloudgraph-system" }),
        },
      );
      const data = await res.json();
      if (data.status === "success") {
        window._contextComparisonData = data;
        renderContextComparison(data);
      } else {
        contextOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">${escapeHtml(data.detail || "Context comparison failed.")}</p></div>`;
      }
    } catch (err) {
      contextOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">${escapeHtml(err.message)}</p></div>`;
    }
  }

  function renderContextComparison(data) {
    if (!contextOutput) return;

    const blocks = data.comparisons.map((item) => {
      const isAgentContext = item.config === "agent-context";
      let detailHtml = "";

      if (activeContextView === "retrieval") {
        detailHtml = `<pre class="context-payload">${escapeHtml(JSON.stringify(item.payload.retrieval || {}, null, 2))}</pre>`;
      } else if (activeContextView === "evidence") {
        const evidenceList = Array.isArray(item.payload.evidence)
          ? item.payload.evidence
              .map(
                (evidence) => `
                        <div class="context-support-item">
                            <div class="context-support-label">${escapeHtml(evidence.label || evidence.type || "Evidence")}</div>
                            <div class="context-support-detail">${escapeHtml(evidence.detail || JSON.stringify(evidence, null, 0))}</div>
                        </div>
                    `,
              )
              .join("")
          : '<div class="empty-state"><p>No evidence payload available.</p></div>';
        detailHtml = `<div class="context-support-list">${evidenceList}</div>`;
      } else if (activeContextView === "prompts") {
        if (item.payload.prompts) {
          detailHtml = `<pre class="context-payload">${escapeHtml(JSON.stringify(item.payload.prompts, null, 2))}</pre>`;
        } else {
          detailHtml = `<div class="empty-state"><p>No prompt payload available for this configuration.</p></div>`;
        }
      } else {
        detailHtml = `<pre class="context-payload">${escapeHtml(JSON.stringify(item.payload || {}, null, 2))}</pre>`;
      }

      return `
                <div class="context-card ${item.unsupported ? "context-card-unsupported" : ""}">
                    <div class="context-card-header">
                        <div class="context-card-title">${escapeHtml(item.label)}</div>
                        <span class="context-card-pill">${escapeHtml(item.config)}</span>
                    </div>
                    <div class="context-card-detail">${escapeHtml(item.detail)}</div>
                    <div class="context-card-key">${activeContextView === "payload" ? "Payload" : activeContextView === "retrieval" ? "Retrieval Config" : activeContextView === "evidence" ? "Evidence" : "Prompts"}</div>
                    ${detailHtml}
                    ${isAgentContext && activeContextView === "evidence" && item.payload.raw_logs ? `<div class="context-card-key">Raw Logs</div><pre class="context-payload">${escapeHtml(JSON.stringify(item.payload.raw_logs, null, 2))}</pre>` : ""}
                    ${isAgentContext && activeContextView === "evidence" && item.payload.raw_metrics ? `<div class="context-card-key">Raw Metrics</div><pre class="context-payload">${escapeHtml(JSON.stringify(item.payload.raw_metrics, null, 2))}</pre>` : ""}
                </div>
            `;
    });

    contextOutput.innerHTML = `
            <div class="context-explorer-summary">
                <div>Compared ${data.comparisons.length} configuration payloads for query '<strong>${escapeHtml(data.query)}</strong>'.</div>
                <div>Unsupported claim rate: <strong>${Math.round(data.unsupported_claim_rate * 100)}%</strong></div>
            </div>
            <div class="context-comparison-grid">
                ${blocks.join("")}
            </div>
        `;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Trigger investigation on load if redirected with ?run=true
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("run") === "true") {
    window.history.replaceState({}, document.title, window.location.pathname);
    runInvestigation();
  }
});
