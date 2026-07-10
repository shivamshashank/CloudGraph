/**
 * CloudGraph Live Log Stream component.
 * Appends simulated and real pod stdout streams into a scrolling logger console.
 */
document.addEventListener("DOMContentLoaded", () => {
  const logsFeed = document.getElementById("logs-feed");
  const isLogsPage = !!logsFeed;

  if (!isLogsPage) return;

  function streamLogs(nodes) {
    if (!logsFeed) return;
    const podNodes = nodes.filter((n) => n.label === "Pod");
    if (podNodes.length === 0) return;

    if (logsFeed.querySelector(".empty-state")) {
      logsFeed.innerHTML = "";
    }

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

    while (logsFeed.children.length > 100) {
      logsFeed.removeChild(logsFeed.firstChild);
    }
  }

  // Register logger capabilities globally
  window.CloudGraph.streamLogs = streamLogs;
  window.CloudGraph.addLogLine = addLogLine;
});
