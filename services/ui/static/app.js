/**
 * CloudGraph Application Entry Point.
 * Orchestrates shared layout elements, health polling, cluster discovery triggers,
 * and database resets. Delegates page-specific rendering (D3 topology, GraphRAG queries,
 * log streams) to modular component scripts.
 */

// Initialize global config namespace
window.CloudGraph = {
  API_BASE: "",
  fetchGraph: null,
  checkHealth: null,
  runInvestigation: null,
  streamLogs: null,
  addLogLine: null,
  renderGraph: null,
  showToast: null,
};

document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = window.CloudGraph.API_BASE;

  // Page Context Indicators
  const isTopologyPage = !!document.getElementById("topology-svg");
  const isDiagnosisPage = !!document.getElementById("rca-output");
  const isLogsPage = !!document.getElementById("logs-feed");

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

  const graphLoader = document.getElementById("graph-loader");

  // Initialize Web App
  checkHealth();
  fetchGraph();

  // Set intervals for live updates
  setInterval(checkHealth, 5000);
  setInterval(fetchGraph, 8000);

  // Global Operations Listeners
  if (btnDiscover) {
    btnDiscover.addEventListener("click", async () => {
      await runDiscovery();
      if (!isTopologyPage) {
        window.location.href = "index.html";
      }
    });
  }

  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", async () => {
      let settings = {};
      try {
        const res = await fetch(
          `${window.CloudGraph.API_BASE}/api/v1/settings`,
        );
        const data = await res.json();
        if (data.status === "success" && data.settings) {
          settings = data.settings;
        }
      } catch (err) {
        console.error("Failed to fetch settings:", err);
      }

      if (!settings.provider || !settings.model) {
        showToast(
          "No local model connected. Run `cloudgraph deploy llm` to set one up.",
          "error",
        );
        return;
      }
      if (!isDiagnosisPage) {
        window.location.href = "diagnosis.html?run=true";
      } else if (typeof window.CloudGraph.runInvestigation === "function") {
        window.CloudGraph.runInvestigation();
      }
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", resetGraph);
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
        if (isLogsPage && typeof window.CloudGraph.addLogLine === "function") {
          window.CloudGraph.addLogLine(
            "SYSTEM",
            "Kubernetes cluster discovery completed successfully.",
            "info",
          );
          window.CloudGraph.addLogLine(
            "SYSTEM",
            `Found: ${data.discovered.nodes} Nodes, ${data.discovered.pods} Pods, ${data.discovered.services} Services.`,
            "info",
          );
        }
        await fetchGraph();
      } else if (
        isLogsPage &&
        typeof window.CloudGraph.addLogLine === "function"
      ) {
        window.CloudGraph.addLogLine(
          "SYSTEM",
          `Discovery skipped or failed: ${data.reason || "Unknown error"}`,
          "warn",
        );
      }
    } catch (err) {
      if (isLogsPage && typeof window.CloudGraph.addLogLine === "function") {
        window.CloudGraph.addLogLine(
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
        if (isLogsPage && typeof window.CloudGraph.addLogLine === "function") {
          window.CloudGraph.addLogLine(
            "SYSTEM",
            "Graph database cleared.",
            "info",
          );
          const logsFeed = document.getElementById("logs-feed");
          if (logsFeed) {
            logsFeed.innerHTML = `
                            <div class="empty-state">
                                <span class="empty-icon">📺</span>
                                <p>Discover the cluster to stream live pod stdout logs.</p>
                            </div>`;
          }
        }
        const rcaOutput = document.getElementById("rca-output");
        if (isDiagnosisPage && rcaOutput) {
          rcaOutput.innerHTML = `
                        <div class="empty-state">
                            <span class="empty-icon">🛡️</span>
                            <p>No investigations run yet. Trigger "Run AI Diagnosis" to begin analyzing anomalies.</p>
                        </div>`;
        }
        if (!isTopologyPage) {
          window.location.href = "index.html";
        } else {
          fetchGraph();
        }
      }
    } catch (err) {
      if (isLogsPage && typeof window.CloudGraph.addLogLine === "function") {
        window.CloudGraph.addLogLine(
          "SYSTEM",
          `Error resetting graph: ${err.message}`,
          "error",
        );
      }
    }
  }

  // Fetch and Draw Graph
  async function fetchGraph() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/graph/data`);
      const data = await res.json();
      if (data.status === "success") {
        updateStats(data.nodes);
        if (
          isTopologyPage &&
          typeof window.CloudGraph.renderGraph === "function"
        ) {
          window.CloudGraph.renderGraph(data.nodes, data.edges);
        }
        if (isLogsPage && typeof window.CloudGraph.streamLogs === "function") {
          window.CloudGraph.streamLogs(data.nodes);
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

  // Toast Helper
  function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "ℹ️";
    if (type === "error") icon = "❌";
    else if (type === "success") icon = "✅";

    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${message}</span>`;
    container.appendChild(toast);

    // Trigger transition
    setTimeout(() => toast.classList.add("show"), 10);

    // Remove after 4s
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Register shared hooks
  window.CloudGraph.fetchGraph = fetchGraph;
  window.CloudGraph.checkHealth = checkHealth;
  window.CloudGraph.showToast = showToast;
});
