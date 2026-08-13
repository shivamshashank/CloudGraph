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

    // Built as text nodes, never innerHTML: `message` is now real container
    // output, so a pod that logs "<img src=x onerror=...>" would otherwise
    // execute it in the operator's browser.
    const entry = document.createElement("div");
    entry.className = "log-entry";

    const timeEl = document.createElement("span");
    timeEl.className = "log-time";
    timeEl.textContent = `[${timestamp}]`;

    const levelEl = document.createElement("span");
    levelEl.className = `log-level log-level-${level}`;
    levelEl.textContent = String(source).toUpperCase();

    const msgEl = document.createElement("span");
    msgEl.className = "log-msg";
    msgEl.textContent = message;

    entry.append(timeEl, document.createTextNode(" "), levelEl);
    entry.append(document.createTextNode(" "), msgEl);
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

  // Every line already rendered, so a poll that re-reads the same tail does
  // not duplicate it. Keyed on timestamp+source+message.
  const seenLines = new Set();

  // ── Public: poll the cluster for real pod stdout/stderr ──────────────────
  //
  // This used to invent its own log lines: it picked a random string from a
  // hardcoded list based on the pod's status, so a pod that was not "Running"
  // produced fabricated "Failed to pull image" and "OutOfMemory" text. Nothing
  // was ever read from a container. It now reads what the pods actually wrote,
  // via GET /api/v1/logs/pods, so the feed can be checked against kubectl logs.
  async function streamLogs() {
    if (!logsFeed) return;
    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/logs/pods?tail=20`,
      );
      if (!res.ok) return;
      const data = await res.json();
      if (data.status !== "success" || !Array.isArray(data.logs)) return;

      const fresh = data.logs.filter((e) => {
        const key = `${e.timestamp}|${e.source}|${e.message}`;
        if (seenLines.has(key)) return false;
        seenLines.add(key);
        return true;
      });
      if (fresh.length === 0) return;

      if (logsFeed.querySelector(".empty-state")) logsFeed.innerHTML = "";
      fresh.forEach((e) =>
        renderLogEntry(
          {
            timestamp: e.timestamp
              ? new Date(e.timestamp).toLocaleString()
              : new Date().toLocaleString(),
            source: e.source,
            level: (e.level || "INFO").toLowerCase(),
            message: e.message,
          },
          // Not persisted: these lines already live in the cluster and are
          // re-read on every poll. Saving them would grow LiveLog without
          // bound and duplicate the feed after a reload.
          false,
        ),
      );
      logsFeed.scrollTop = logsFeed.scrollHeight;
    } catch (err) {
      console.error("Failed to fetch pod logs:", err);
    }
  }

  // Load full history from storage on page open
  loadPersistedLogs();

  // Register logger capabilities globally
  window.CloudGraph.streamLogs = streamLogs;
  window.CloudGraph.addLogLine = addLogLine;
});
