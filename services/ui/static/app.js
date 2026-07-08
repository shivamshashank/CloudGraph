document.addEventListener("DOMContentLoaded", () => {
  // API client configuration
  const API_BASE = ""; // Relative paths since we reverse proxy in mock_service.py

  // Page Context Indicators
  const isTopologyPage = !!document.getElementById("topology-svg");
  const isDiagnosisPage = !!document.getElementById("rca-output");
  const isLogsPage = !!document.getElementById("logs-feed");
  const isEvidencePage = !!document.getElementById("retrieval-output");

  // DOM Elements (Sidebar)
  const btnDiscover = document.getElementById("btn-discover");
  const btnAnalyze = document.getElementById("btn-analyze");
  const btnReset = document.getElementById("btn-reset");
  const apiStatus = document.getElementById("api-status");
  const apiDot = document.getElementById("api-dot");
  const dbStatus = document.getElementById("db-status");
  const dbDot = document.getElementById("db-dot");

  const statNodes = document.getElementById("stat-nodes");
  const statPods = document.getElementById("stat-pods");
  const statDeployments = document.getElementById("stat-deployments");
  const statServices = document.getElementById("stat-services");

  // DOM Elements (Page-specific)
  const graphLoader = document.getElementById("graph-loader");
  const btnAnalyzePage = document.getElementById("btn-analyze-page");
  const rcaOutput = document.getElementById("rca-output");
  const logsFeed = document.getElementById("logs-feed");

  const graphragQuery = document.getElementById("graphrag-query");
  const graphragResults = document.getElementById("graphrag-results");
  const btnSearch = document.getElementById("btn-search");

  const retrievalOutput = document.getElementById("retrieval-output");
  const retrievalQuery = document.getElementById("retrieval-query");
  const btnRetrieve = document.getElementById("btn-retrieve");

  const nodePopup = document.getElementById("node-popup");
  const popupTitle = document.getElementById("popup-title");
  const popupContent = document.getElementById("popup-content");
  const btnClosePopup = document.getElementById("btn-close-popup");

  // SVG elements (Topology page only)
  const svg = document.getElementById("topology-svg");
  const nodesGroup = document.getElementById("nodes-group");
  const edgesGroup = document.getElementById("edges-group");

  // State Variables
  let graphData = { nodes: [], edges: [] };
  let selectedNode = null;
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let viewOffset = { x: 50, y: 50 };
  let viewZoom = 1.0;

  // Initialize Web App
  checkHealth();
  fetchGraph();

  // Set intervals for live updates
  setInterval(checkHealth, 5000);
  setInterval(fetchGraph, 8000);

  // Global Operations Listeners
  if (btnDiscover) {
    btnDiscover.addEventListener("click", async () => {
      // Trigger discovery
      await runDiscovery();
      // If not on topology page, redirect
      if (!isTopologyPage) {
        window.location.href = "index.html";
      }
    });
  }

  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", () => {
      if (!isDiagnosisPage) {
        // Redirect and request investigation run on load
        window.location.href = "diagnosis.html?run=true";
      } else {
        runInvestigation();
      }
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", resetGraph);
  }

  // Page-specific Listeners
  if (btnAnalyzePage) {
    btnAnalyzePage.addEventListener("click", runInvestigation);
  }

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

  if (btnClosePopup && nodePopup) {
    btnClosePopup.addEventListener("click", () =>
      nodePopup.classList.add("hidden"),
    );
  }

  // Trigger investigation on load if redirected with ?run=true
  if (isDiagnosisPage) {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("run") === "true") {
      // Clean up the URL parameters so reloading doesn't repeat the action
      window.history.replaceState({}, document.title, window.location.pathname);
      runInvestigation();
    }
  }

  // SVG drag-and-pan support (Topology page only)
  if (isTopologyPage && svg) {
    svg.addEventListener("mousedown", (e) => {
      if (e.target === svg || e.target.tagName === "rect") {
        isDragging = true;
        dragStart = {
          x: e.clientX - viewOffset.x,
          y: e.clientY - viewOffset.y,
        };
        svg.style.cursor = "grabbing";
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (isDragging) {
        viewOffset.x = e.clientX - dragStart.x;
        viewOffset.y = e.clientY - dragStart.y;
        updateTransform();
      }
    });

    window.addEventListener("mouseup", () => {
      isDragging = false;
      svg.style.cursor = "grab";
    });

    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = 1.1;
      if (e.deltaY < 0) {
        viewZoom *= zoomFactor;
      } else {
        viewZoom /= zoomFactor;
      }
      viewZoom = Math.min(Math.max(0.4, viewZoom), 2.5);
      updateTransform();
    });
  }

  function updateTransform() {
    if (nodesGroup && edgesGroup) {
      nodesGroup.setAttribute(
        "transform",
        `translate(${viewOffset.x}, ${viewOffset.y}) scale(${viewZoom})`,
      );
      edgesGroup.setAttribute(
        "transform",
        `translate(${viewOffset.x}, ${viewOffset.y}) scale(${viewZoom})`,
      );
    }
  }

  // Health Checks
  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      const data = await res.json();

      if (apiStatus && apiDot) {
        apiStatus.textContent = "Healthy";
        apiDot.className = "indicator-dot online";
      }

      if (dbStatus && dbDot) {
        if (data.neo4j === "connected") {
          dbStatus.textContent = "Live";
          dbDot.className = "indicator-dot online";
        } else {
          dbStatus.textContent = "Offline";
          dbDot.className = "indicator-dot offline";
        }
      }
    } catch (err) {
      if (apiStatus && apiDot) {
        apiStatus.textContent = "Unreachable";
        apiDot.className = "indicator-dot offline";
      }
      if (dbStatus && dbDot) {
        dbStatus.textContent = "Offline";
        dbDot.className = "indicator-dot offline";
      }
    }
  }

  // Trigger Kubernetes Discovery
  async function runDiscovery() {
    if (graphLoader) graphLoader.classList.remove("hidden");
    try {
      const res = await fetch(`${API_BASE}/api/v1/graph/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (data.status === "success") {
        if (isLogsPage) {
          addLogLine(
            "SYSTEM",
            "Kubernetes cluster discovery completed successfully.",
            "info",
          );
          addLogLine(
            "SYSTEM",
            `Found: ${data.discovered.nodes} Nodes, ${data.discovered.pods} Pods, ${data.discovered.services} Services.`,
            "info",
          );
        }
        await fetchGraph();
      } else {
        if (isLogsPage) {
          addLogLine(
            "SYSTEM",
            `Discovery skipped or failed: ${data.reason || "Unknown error"}`,
            "warn",
          );
        }
      }
    } catch (err) {
      if (isLogsPage) {
        addLogLine(
          "SYSTEM",
          `Error triggering discovery: ${err.message}`,
          "error",
        );
      }
    } finally {
      if (graphLoader) graphLoader.classList.add("hidden");
    }
  }

  // Reset Neo4j Database
  async function resetGraph() {
    if (!confirm("Are you sure you want to clear the entire graph database?"))
      return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/demo/reset`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.status === "success") {
        if (isLogsPage) {
          addLogLine("SYSTEM", "Graph database cleared.", "info");
          if (logsFeed) {
            logsFeed.innerHTML = `
                            <div class="empty-state">
                                <span class="empty-icon">📺</span>
                                <p>Discover the cluster to stream live pod stdout logs.</p>
                            </div>`;
          }
        }
        if (isDiagnosisPage && rcaOutput) {
          rcaOutput.innerHTML = `
                        <div class="empty-state">
                            <span class="empty-icon">🛡️</span>
                            <p>No investigations run yet. Trigger "Run AI Diagnosis" to begin analyzing anomalies.</p>
                        </div>`;
        }
        // Redirect if not on topology view
        if (!isTopologyPage) {
          window.location.href = "index.html";
        } else {
          fetchGraph();
        }
      }
    } catch (err) {
      if (isLogsPage) {
        addLogLine("SYSTEM", `Error resetting graph: ${err.message}`, "error");
      }
    }
  }

  // Trigger Investigation / Root Cause Analysis
  async function runInvestigation() {
    if (rcaOutput) {
      rcaOutput.innerHTML = `
                <div class="empty-state">
                    <div class="spinner"></div>
                    <p>Running multi-agent diagnostics... Scanning log history... Analyzing metrics correlation...</p>
                </div>`;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/investigations/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ namespace: "cloudgraph-system" }),
      });
      const data = await res.json();
      if (data.status === "success" && data.results.length > 0) {
        if (isDiagnosisPage) {
          renderRCA(data.results);
        }
        if (isLogsPage) {
          addLogLine("ENGINE", "Incident investigation completed.", "info");
        }
        fetchGraph();
      }
    } catch (err) {
      if (isDiagnosisPage && rcaOutput) {
        rcaOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">Investigation failed: ${err.message}</p></div>`;
      }
    }
  }

  // GraphRAG Search (Evidence page only)
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
        fetch(`${API_BASE}/api/v1/graphrag/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            namespace: "cloudgraph-system",
            method: "keyword",
          }),
        }),
        fetch(`${API_BASE}/api/v1/graphrag/search`, {
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

  // Relevant Evidence (Evidence page only)
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
      const res = await fetch(`${API_BASE}/api/v1/graphrag/retrieve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, namespace: "cloudgraph-system" }),
      });
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

  // Fetch and Draw Graph
  async function fetchGraph() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/graph/data`);
      const data = await res.json();
      if (data.status === "success") {
        graphData = data;
        updateStats(data.nodes);
        if (isTopologyPage) {
          renderGraph(data.nodes, data.edges);
        }
        if (isLogsPage) {
          streamLogs(data.nodes);
        }
      }
    } catch (err) {
      console.error("Error fetching graph data:", err);
    }
  }

  function updateStats(nodes) {
    let n = 0,
      p = 0,
      d = 0,
      s = 0;
    nodes.forEach((node) => {
      if (node.label === "Node") n++;
      else if (node.label === "Pod") p++;
      else if (node.label === "Deployment") d++;
      else if (node.label === "Service") s++;
    });
    if (statNodes) statNodes.textContent = n;
    if (statPods) statPods.textContent = p;
    if (statDeployments) statDeployments.textContent = d;
    if (statServices) statServices.textContent = s;
  }

  // Stream Pod logs to log feeds panel (Logs page only)
  function streamLogs(nodes) {
    if (!logsFeed) return;
    const podNodes = nodes.filter((n) => n.label === "Pod");
    if (podNodes.length === 0) return;

    // Find if logs console has empty state
    if (logsFeed.querySelector(".empty-state")) {
      logsFeed.innerHTML = "";
    }

    // Simulating log scroll from active pods
    podNodes.forEach((pod) => {
      if (pod.properties && pod.properties.status === "Running") {
        // Occasional dummy telemetry entries to feel active if there are no raw errors
        if (Math.random() > 0.85) {
          const messages = [
            "HTTP GET /health - 200 OK",
            "Prometheus metrics scraped",
            "Database connection pool active",
            "Task execution queue processed",
            "Internal event dispatched",
          ];
          const msg = messages[Math.floor(Math.random() * messages.length)];
          addLogLine(pod.name.split("-")[0], msg, "info");
        }
      } else if (
        pod.properties &&
        pod.properties.status !== "Running" &&
        pod.properties.status !== "Succeeded"
      ) {
        if (Math.random() > 0.6) {
          const warnings = [
            "Failed to pull image: tag not found",
            "Back-off restarting failed container",
            "Database connection handshake timeout after 10s",
            "Terminated due to OutOfMemory limits",
          ];
          const msg = warnings[Math.floor(Math.random() * warnings.length)];
          addLogLine(pod.name.split("-")[0], msg, "error");
        }
      }
    });
  }

  function addLogLine(source, message, level) {
    if (!logsFeed) return;
    const entry = document.createElement("div");
    entry.className = "log-entry";

    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `
            <span class="log-time">[${timestamp}]</span>
            <span class="log-level log-level-${level}">${source.toUpperCase()}</span>
            <span class="log-msg">${message}</span>
        `;

    logsFeed.appendChild(entry);
    logsFeed.scrollTop = logsFeed.scrollHeight;

    // Keep console size limited
    while (logsFeed.children.length > 100) {
      logsFeed.removeChild(logsFeed.firstChild);
    }
  }

  // Hierarchical Layout Calculations for SVG Node Drawing (Topology page only)
  function renderGraph(nodes, edges) {
    if (!nodesGroup || !edgesGroup) return;
    nodesGroup.innerHTML = "";
    edgesGroup.innerHTML = "";

    if (nodes.length === 0) return;

    // Group nodes by labels to map layouts
    const layers = {
      Commit: [],
      Deployment: [],
      Service: [],
      Pod: [],
      Node: [],
      Incident: [],
    };

    nodes.forEach((node) => {
      if (layers[node.label]) {
        layers[node.label].push(node);
      } else {
        layers["Node"].push(node);
      }
    });

    // Set dimensions & spacing
    const width = svg.clientWidth || 800;
    const positions = {};

    // Helper to space nodes horizontally
    const assignPositions = (nodesList, yCoord) => {
      const count = nodesList.length;
      if (count === 0) return;
      const segment = width / (count + 1);
      nodesList.forEach((node, index) => {
        positions[node.id] = {
          x: segment * (index + 1),
          y: yCoord,
        };
      });
    };

    // Assign layered coordinates
    assignPositions(layers["Commit"], 60);
    assignPositions(layers["Deployment"], 140);
    assignPositions(layers["Service"], 220);
    assignPositions(layers["Pod"], 320);
    assignPositions(layers["Node"], 440);
    assignPositions(layers["Incident"], 220);

    // Render Edges
    edges.forEach((edge) => {
      const start = positions[edge.source];
      const end = positions[edge.target];
      if (start && end) {
        const line = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "line",
        );
        line.setAttribute("x1", start.x);
        line.setAttribute("y1", start.y);
        line.setAttribute("x2", end.x);
        line.setAttribute("y2", end.y);
        line.setAttribute("class", "edge-line");

        // Group to enable label hover in future
        const edgeGroup = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "g",
        );
        edgeGroup.setAttribute("class", "edge-group");
        edgeGroup.appendChild(line);
        edgesGroup.appendChild(edgeGroup);
      }
    });

    // Render Nodes
    nodes.forEach((node) => {
      const pos = positions[node.id] || { x: Math.random() * width, y: 250 };

      const nodeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      nodeG.setAttribute("class", "node-group");
      nodeG.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
      nodeG.addEventListener("click", (e) => {
        e.stopPropagation();
        showNodeDetails(node);
      });

      // Draw Node Circle
      const circle = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle",
      );
      circle.setAttribute("r", 16);
      circle.setAttribute("class", "node-circle");

      // Assign color scheme based on node type and status
      let fillColor = "#6366f1"; // Indigo default
      let strokeColor = "rgba(255,255,255,0.4)";

      if (node.label === "Node") {
        fillColor = "#1e293b";
        strokeColor = "#3b82f6";
      } else if (node.label === "Service") {
        fillColor = "#8b5cf6";
        strokeColor = "#c084fc";
      } else if (node.label === "Deployment") {
        fillColor = "#0f766e";
        strokeColor = "#2dd4bf";
      } else if (node.label === "Commit") {
        fillColor = "#f59e0b";
        strokeColor = "#fbbf24";
      } else if (node.label === "Incident") {
        fillColor = "#dc2626";
        strokeColor = "#ef4444";
        circle.setAttribute("class", "node-circle node-failed");
      } else if (node.label === "Pod") {
        if (node.status === "Running") {
          fillColor = "#10b981";
          strokeColor = "#34d399";
        } else if (node.status === "Succeeded") {
          fillColor = "#059669";
          strokeColor = "#34d399";
        } else {
          // Pod crashed or pending
          fillColor = "#ef4444";
          strokeColor = "#f87171";
          circle.setAttribute("class", "node-circle node-failed");
        }
      }

      circle.setAttribute("fill", fillColor);
      circle.setAttribute("stroke", strokeColor);
      nodeG.appendChild(circle);

      // Draw Label text
      const text = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text",
      );
      // Clean up long names for graph labels
      let labelText = node.name;
      if (labelText.length > 18) {
        labelText =
          labelText.substring(0, 8) +
          "..." +
          labelText.substring(labelText.length - 6);
      }
      text.textContent = labelText;
      text.setAttribute("class", "node-text");
      text.setAttribute("y", 30);
      text.setAttribute("text-anchor", "middle");

      // Draw label background for better readability
      const bbox_width = Math.max(labelText.length * 7, 50);
      const rect = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect",
      );
      rect.setAttribute("class", "node-label-bg");
      rect.setAttribute("x", -bbox_width / 2);
      rect.setAttribute("y", 18);
      rect.setAttribute("width", bbox_width);
      rect.setAttribute("height", 16);

      nodeG.appendChild(rect);
      nodeG.appendChild(text);

      // Draw node inner symbol
      const symbol = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text",
      );
      symbol.setAttribute("text-anchor", "middle");
      symbol.setAttribute("y", 4);
      symbol.setAttribute("fill", "#ffffff");
      symbol.setAttribute("font-size", "12px");
      symbol.setAttribute("font-weight", "bold");
      symbol.setAttribute("pointer-events", "none");

      if (node.label === "Pod") symbol.textContent = "P";
      else if (node.label === "Node")
        symbol.textContent = "H"; // Host
      else if (node.label === "Service") symbol.textContent = "S";
      else if (node.label === "Deployment") symbol.textContent = "D";
      else if (node.label === "Commit") symbol.textContent = "C";
      else if (node.label === "Incident") symbol.textContent = "⚠️";

      nodeG.appendChild(symbol);
      nodesGroup.appendChild(nodeG);
    });
  }

  // Detail Drawer Sidebar (Topology page only)
  function showNodeDetails(node) {
    if (!nodePopup || !popupTitle || !popupContent) return;
    selectedNode = node;
    popupTitle.textContent = `${node.label} Node Details`;
    nodePopup.classList.remove("hidden");

    let propsHtml = '<div class="prop-list">';
    // Iterate through properties
    const ignoreProps = ["id", "uuid"];
    for (const [key, value] of Object.entries(node.properties || {})) {
      if (!ignoreProps.includes(key)) {
        propsHtml += `
                    <div class="prop-row">
                        <span class="prop-key">${key}</span>
                        <span class="prop-value">${value}</span>
                    </div>
                `;
      }
    }

    propsHtml += `
            <div class="prop-row">
                <span class="prop-key">Graph Database ID</span>
                <span class="prop-value" style="font-family: monospace; font-size: 11px;">${node.id}</span>
            </div>
        `;
    propsHtml += "</div>";
    popupContent.innerHTML = propsHtml;
  }

  // Render Retrieval results (Evidence page only)
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
                        ? `<div class="comparison-rationale"><div class="comparison-rationale-title">Why it ranked here</div><ul>${item.ranking_rationale.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul></div>`
                        : "";

                    return `
                        <div class="retrieval-item">
                            <div class="retrieval-item-header">
                                <span class="retrieval-label">${escapeHtml(item.label)}</span>
                                <span class="retrieval-name">${escapeHtml(item.name)}</span>
                            </div>
                            <div class="retrieval-status">${escapeHtml(item.status || "Unknown")}</div>
                            ${typeof item.score !== "undefined" ? `<div class="comparison-meta"><span class="comparison-pill">Score ${escapeHtml(item.score)}</span></div>` : ""}
                            <div class="comparison-evidence">${evidenceChain}</div>
                            ${rationale}
                            <div class="retrieval-related">
                                ${
                                  item.related && item.related.length > 0
                                    ? item.related
                                        .map(
                                          (rel) => `
                                    <span class="retrieval-chip">${escapeHtml(rel.rel || "RELATED_TO")} → ${escapeHtml(rel.related_name || "unknown")}</span>
                                `,
                                        )
                                        .join("")
                                    : '<span class="retrieval-chip">No adjacent context</span>'
                                }
                            </div>
                        </div>
                    `;
                  })
                  .join("")}
            </div>
        `;
    retrievalOutput.innerHTML = html;
  }

  // Render RCA report cards (Diagnosis page only)
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
              .map(
                (item) => `
                    <div class="evidence-item">
                        <div class="evidence-item-title">${item.label}</div>
                        <div class="evidence-item-detail">${item.detail}</div>
                        ${item.messages ? `<div class="evidence-item-messages">${item.messages.map((msg) => `<span class="evidence-msg">${msg}</span>`).join("")}</div>` : ""}
                    </div>
                `,
              )
              .join("")
          : '<div class="evidence-item"><div class="evidence-item-title">No graph evidence returned yet</div><div class="evidence-item-detail">The current topology does not have additional evidence for this incident.</div></div>';

      rcaHtml += `
                <div class="rca-header">
                    <span class="rca-badge ${severityClass}">${res.severity}</span>
                    <h3 class="rca-title">${res.title}</h3>
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
});
