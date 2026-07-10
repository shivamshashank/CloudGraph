/**
 * CloudGraph GraphRAG Evidence Retrieval component.
 * Allows comparison of raw keyword search vs. multi-hop hybrid GraphRAG.
 */
document.addEventListener("DOMContentLoaded", () => {
  const graphragQuery = document.getElementById("graphrag-query");
  const graphragResults = document.getElementById("graphrag-results");
  const btnSearch = document.getElementById("btn-search");

  const retrievalOutput = document.getElementById("retrieval-output");
  const retrievalQuery = document.getElementById("retrieval-query");
  const btnRetrieve = document.getElementById("btn-retrieve");

  const isEvidencePage = !!retrievalOutput;

  if (!isEvidencePage) return;

  if (btnSearch) {
    btnSearch.addEventListener("click", runGraphSearch);
  }
  if (graphragQuery) {
    graphragQuery.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runGraphSearch();
    });
  }

  if (btnRetrieve) {
    btnRetrieve.addEventListener("click", runRetrieval);
  }
  if (retrievalQuery) {
    retrievalQuery.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runRetrieval();
    });
  }

  // GraphRAG Search (Evidence page comparison)
  async function runGraphSearch() {
    if (!graphragQuery || !graphragResults) return;
    const query = graphragQuery.value.trim();
    if (!query) {
      graphragResults.innerHTML =
        '<div class="retrieval-result"><div class="retrieval-result-title">Enter a search term</div><div class="retrieval-result-detail">Try a pod, service, deployment, or incident keyword.</div></div>';
      return;
    }

    graphragResults.innerHTML =
      '<div class="retrieval-result"><div class="retrieval-result-title">Comparing keyword and hybrid GraphRAG results…</div></div>';
    try {
      const [keywordRes, hybridRes] = await Promise.all([
        fetch(`${window.CloudGraph.API_BASE}/api/v1/graphrag/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            namespace: "cloudgraph-system",
            method: "keyword",
          }),
        }),
        fetch(`${window.CloudGraph.API_BASE}/api/v1/graphrag/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            namespace: "cloudgraph-system",
            method: "hybrid",
          }),
        }),
      ]);

      const keywordData = await keywordRes.json();
      const hybridData = await hybridRes.json();
      const keywordResults =
        keywordData.status === "success" ? keywordData.results || [] : [];
      const hybridResults =
        hybridData.status === "success" ? hybridData.results || [] : [];

      if (keywordResults.length === 0 && hybridResults.length === 0) {
        graphragResults.innerHTML =
          '<div class="retrieval-result"><div class="retrieval-result-title">No matches</div><div class="retrieval-result-detail">Try a broader term such as checkout, timeout, or crash.</div></div>';
        return;
      }

      graphragResults.innerHTML = `
                <div class="comparison-summary">Comparing keyword matching with hybrid GraphRAG retrieval for “${escapeHtml(query)}”</div>
                <div class="comparison-grid">
                    <div class="comparison-column">
                        <div class="comparison-header">Keyword Search</div>
                        ${keywordResults.length > 0 ? keywordResults.map((result) => renderComparisonCard(result, "keyword")).join("") : '<div class="comparison-empty">No keyword results returned.</div>'}
                    </div>
                    <div class="comparison-column">
                        <div class="comparison-header comparison-header-hybrid">Hybrid GraphRAG</div>
                        ${hybridResults.length > 0 ? hybridResults.map((result) => renderComparisonCard(result, "hybrid")).join("") : '<div class="comparison-empty">No hybrid results returned.</div>'}
                    </div>
                </div>
            `;
    } catch (err) {
      graphragResults.innerHTML = `<div class="retrieval-result"><div class="retrieval-result-title">Search failed</div><div class="retrieval-result-detail">${escapeHtml(err.message)}</div></div>`;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderComparisonCard(result, mode) {
    const evidenceChain =
      Array.isArray(result.evidence_chain) && result.evidence_chain.length > 0
        ? result.evidence_chain
            .map(
              (item) => `
                <div class="evidence-chain-item">
                    <span class="evidence-chain-label">${escapeHtml(item.label || item.type || "Evidence")}</span>
                    <span class="evidence-chain-name">${escapeHtml(item.name || "unknown")}</span>
                </div>
            `,
            )
            .join("")
        : '<div class="comparison-empty">No evidence chain available.</div>';

    const rationale =
      Array.isArray(result.ranking_rationale) &&
      result.ranking_rationale.length > 0
        ? `<div class="comparison-rationale">
                <div class="comparison-rationale-title">Why it ranked here</div>
                <ul>${result.ranking_rationale.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </div>`
        : "";

    const contextItems =
      Array.isArray(result.context) && result.context.length > 0
        ? result.context
            .map(
              (item) =>
                `<span class="retrieval-context-item">${escapeHtml(item.relationship || "related")} → ${escapeHtml(item.name || "unknown")}</span>`,
            )
            .join("")
        : "";

    return `
            <div class="retrieval-result comparison-result">
                <div class="comparison-result-header">
                    <div class="retrieval-result-title">${escapeHtml(result.name || "Unknown result")}</div>
                    <span class="comparison-pill">${mode === "hybrid" ? "Hybrid" : "Keyword"}</span>
                </div>
                <div class="retrieval-result-detail">${escapeHtml(result.detail || result.status || "No detail available")}</div>
                <div class="comparison-meta">
                    <span class="comparison-pill">${escapeHtml(result.label || "Result")}</span>
                    ${typeof result.score !== "undefined" ? `<span class="comparison-pill">Score ${escapeHtml(result.score)}</span>` : ""}
                </div>
                <div class="comparison-evidence">
                    ${evidenceChain}
                </div>
                ${rationale}
                ${contextItems ? `<div class="retrieval-context">${contextItems}</div>` : ""}
            </div>
        `;
  }

  // Relevant Evidence retrieval execution
  async function runRetrieval() {
    if (!retrievalQuery || !retrievalOutput) return;
    const query = retrievalQuery.value.trim();
    if (!query) {
      retrievalOutput.innerHTML =
        '<div class="empty-state"><p>Enter a term to retrieve evidence.</p></div>';
      return;
    }

    retrievalOutput.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Retrieving graph evidence...</p>
            </div>`;

    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/graphrag/retrieve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, namespace: "cloudgraph-system" }),
        },
      );
      const data = await res.json();
      if (data.status === "success") {
        renderRetrieval(data);
      } else {
        retrievalOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">${data.detail || "Retrieval failed."}</p></div>`;
      }
    } catch (err) {
      retrievalOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">${err.message}</p></div>`;
    }
  }

  function renderRetrieval(data) {
    if (!retrievalOutput) return;
    if (!data.results || data.results.length === 0) {
      retrievalOutput.innerHTML = `<div class="empty-state"><p>${data.summary || "No evidence found."}</p></div>`;
      return;
    }

    const html = `
            <div class="retrieval-summary">${escapeHtml(data.summary)}</div>
            <div class="retrieval-list">
                ${data.results
                  .map((item) => {
                    const evidenceChain =
                      Array.isArray(item.evidence_chain) &&
                      item.evidence_chain.length > 0
                        ? item.evidence_chain
                            .map(
                              (chainItem) => `
                            <div class="evidence-chain-item">
                                <span class="evidence-chain-label">${escapeHtml(chainItem.label || chainItem.type || "Evidence")}</span>
                                <span class="evidence-chain-name">${escapeHtml(chainItem.name || "unknown")}</span>
                            </div>
                        `,
                            )
                            .join("")
                        : '<div class="comparison-empty">No evidence chain available.</div>';

                    const rationale =
                      Array.isArray(item.ranking_rationale) &&
                      item.ranking_rationale.length > 0
                        ? `<div class="comparison-rationale">
                                <div class="comparison-rationale-title">Why it ranked here</div>
                                <ul>${item.ranking_rationale.map((rItem) => `<li>${escapeHtml(rItem)}</li>`).join("")}</ul>
                            </div>`
                        : "";

                    const contextItems =
                      Array.isArray(item.context) && item.context.length > 0
                        ? item.context
                            .map(
                              (cItem) =>
                                `<span class="retrieval-context-item">${escapeHtml(cItem.relationship || "related")} → ${escapeHtml(cItem.name || "unknown")}</span>`,
                            )
                            .join("")
                        : "";

                    return `
                        <div class="retrieval-result">
                            <div class="retrieval-result-header">
                                <div class="retrieval-result-title">${escapeHtml(item.name || "Unknown evidence")}</div>
                                <span class="retrieval-score">Score ${escapeHtml(item.score)}</span>
                            </div>
                            <div class="retrieval-result-detail">${escapeHtml(item.detail || item.status || "No detail available")}</div>
                            <div class="comparison-meta">
                                <span class="comparison-pill">${escapeHtml(item.label || "Evidence")}</span>
                            </div>
                            <div class="comparison-evidence" style="margin-top: 10px;">
                                ${evidenceChain}
                            </div>
                            ${rationale}
                            ${contextItems ? `<div class="retrieval-context">${contextItems}</div>` : ""}
                        </div>
                    `;
                  })
                  .join("")}
            </div>
        `;
    retrievalOutput.innerHTML = html;
  }
});
