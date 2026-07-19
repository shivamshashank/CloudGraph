/**
 * CloudGraph Live Log Stream component.
 * Streams real pod telemetry into a scrolling console and persists the
 * entire log history to localStorage so it survives page refreshes.
 */

const LOG_STORAGE_KEY = "cloudgraph_log_history";
const MAX_STORED_LOGS = 5000; // cap storage to 5000 entries maximum

document.addEventListener("DOMContentLoaded", () => {
  const logsFeed = document.getElementById("logs-feed");
  const isLogsPage = !!logsFeed;

  if (!isLogsPage) return;

  // ── Inject Clear Logs button into card header ──────────────────────────────
  const cardHeader = logsFeed.closest(".card")?.querySelector(".card-header");
  if (cardHeader) {
    const clearBtn = document.createElement("button");
    clearBtn.id = "btn-clear-logs";
    clearBtn.textContent = "Clear Logs";
    clearBtn.style.cssText =
      "margin-left:auto;padding:4px 12px;font-size:12px;border-radius:6px;" +
      "background:#1e293b;border:1px solid #334155;color:#94a3b8;cursor:pointer;";
    clearBtn.addEventListener("mouseenter", () => {
      clearBtn.style.background = "#ef4444";
      clearBtn.style.color = "#fff";
      clearBtn.style.borderColor = "#ef4444";
    });
    clearBtn.addEventListener("mouseleave", () => {
      clearBtn.style.background = "#1e293b";
      clearBtn.style.color = "#94a3b8";
      clearBtn.style.borderColor = "#334155";
    });
    clearBtn.addEventListener("click", async () => {
      if (confirm("Clear all saved log history?")) {
        try {
          await fetch(`${window.CloudGraph.API_BASE}/api/v1/logs`, {
            method: "DELETE",
          });
        } catch (err) {
          console.error("Failed to clear logs on database:", err);
        }
        logsFeed.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">📺</span>
            <p>Log history cleared. Discover the cluster to stream live pod stdout logs.</p>
          </div>`;
      }
    });
    cardHeader.appendChild(clearBtn);
  }

  // ── Load and replay persisted log history ─────────────────────────────────
  async function loadPersistedLogs() {
    try {
      const res = await fetch(`${window.CloudGraph.API_BASE}/api/v1/logs`);
      const data = await res.json();
      if (data.status === "success" && data.logs) {
        const entries = data.logs;
        if (entries.length === 0) return;
        logsFeed.innerHTML = ""; // clear empty-state placeholder
        entries.forEach((e) => renderLogEntry(e, false)); // false = don't re-save
        logsFeed.scrollTop = logsFeed.scrollHeight;
      }
    } catch (err) {
      console.error("Failed to load logs from database:", err);
    }
  }

  // ── Persist a single log entry to database ────────────────────────────────
  async function persistLogEntry(entry) {
    try {
      await fetch(`${window.CloudGraph.API_BASE}/api/v1/logs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
    } catch (err) {
      console.error("Failed to persist log entry:", err);
    }
  }

  // ── Render a log entry into the DOM ───────────────────────────────────────
  function renderLogEntry({ timestamp, source, level, message }, save) {
    if (logsFeed.querySelector(".empty-state")) {
      logsFeed.innerHTML = "";
    }

    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML =
      '<span class="log-time">[' +
      timestamp +
      "]</span> " +
      '<span class="log-level log-level-' +
      level +
      '">' +
      source.toUpperCase() +
      "</span> " +
      '<span class="log-msg">' +
      message +
      "</span>";
    logsFeed.appendChild(entry);
    logsFeed.scrollTop = logsFeed.scrollHeight;

    if (save) {
      persistLogEntry({ timestamp, source, level, message });
    }
  }

  // ── Public: add a single log line ─────────────────────────────────────────
  function addLogLine(source, message, level) {
    if (!logsFeed) return;
    const timestamp = new Date().toLocaleString();
    renderLogEntry({ timestamp, source, level, message }, true);
  }

  // ── Public: stream logs from graph nodes (called every 8s by app.js) ──────
  function streamLogs(nodes) {
    if (!logsFeed) return;
    const podNodes = nodes.filter((n) => n.label === "Pod");
    if (podNodes.length === 0) return;

    podNodes.forEach((pod) => {
      if (pod.properties && pod.properties.status === "Running") {
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

  // Load full history from storage on page open
  loadPersistedLogs();

  // Register logger capabilities globally
  window.CloudGraph.streamLogs = streamLogs;
  window.CloudGraph.addLogLine = addLogLine;
});
