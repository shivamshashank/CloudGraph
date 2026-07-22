document.addEventListener("DOMContentLoaded", () => {
  const metricSelect = document.getElementById("metric-select");
  const benchmarkTable = document.getElementById("benchmark-table");
  const benchmarkChart = document.getElementById("benchmark-chart");
  const datasetName = document.getElementById("dataset-name");
  const datasetSplit = document.getElementById("dataset-split");
  const benchmarkNotes = document.getElementById("benchmark-notes");
  const benchmarkNotesList = document.getElementById("benchmark-notes-list");
  const exportJsonButton = document.getElementById("btn-export-json");
  const exportCsvButton = document.getElementById("btn-export-csv");
  const runBenchmarkButton = document.getElementById("btn-run-benchmark");
  const emptyStateContainer = document.getElementById("benchmark-empty-state");
  const resultsContainer = document.getElementById(
    "benchmark-results-container",
  );

  let benchmarkPayload = null;

  function showEmptyState() {
    if (emptyStateContainer) emptyStateContainer.classList.remove("hidden");
    if (resultsContainer) resultsContainer.classList.add("hidden");
  }

  function showResultsContainer() {
    if (emptyStateContainer) emptyStateContainer.classList.add("hidden");
    if (resultsContainer) resultsContainer.classList.remove("hidden");
  }

  function renderLogs(logs) {
    const logsContainer = document.getElementById("benchmark-calculation-logs");
    if (!logsContainer) return;
    if (!logs || !logs.length) {
      logsContainer.innerHTML =
        '<div class="log-entry"><span class="log-msg">No calculation logs available for this run.</span></div>';
      return;
    }
    logsContainer.innerHTML = logs
      .map(
        (log) =>
          `<div class="log-entry"><span class="log-msg">${escapeHtml(log)}</span></div>`,
      )
      .join("");
  }

  function renderSummary(data) {
    if (!datasetName || !datasetSplit || !benchmarkNotes || !benchmarkNotesList)
      return;
    datasetName.textContent = data.dataset || "Benchmark dataset";
    const splitText = data.split || "70/30";
    const timeText = data.last_run_timestamp
      ? ` • ${data.last_run_timestamp}`
      : "";
    datasetSplit.textContent = `${splitText}${timeText}`;
    benchmarkNotes.textContent = "Experiment notes and dataset split summary.";
    benchmarkNotesList.innerHTML = (data.notes || [])
      .map(
        (note) => `<div class="benchmark-note-item">${escapeHtml(note)}</div>`,
      )
      .join("");
    renderLogs(data.logs || []);
  }

  function renderTable(data) {
    if (!benchmarkTable) return;
    const tbody = benchmarkTable.querySelector("tbody");
    if (!tbody) return;
    tbody.innerHTML = data
      .map(
        (row) => `
          <tr>
            <td>${escapeHtml(row.baseline)}</td>
            <td>${formatPercent(row.accuracy)}</td>
            <td>${formatPercent(row.precision)}</td>
            <td>${formatPercent(row.recall)}</td>
            <td>${formatPercent(row.f1)}</td>
            <td>${formatPercent(row.hallucination_rate)}</td>
            <td>${escapeHtml(row.latency)} ms</td>
          </tr>
        `,
      )
      .join("");
  }

  function renderChart(data, metric) {
    if (!benchmarkChart) return;
    const rows = (data || [])
      .map(
        (row) => `
          <div class="benchmark-chart-row">
            <div class="benchmark-chart-label">${escapeHtml(row.baseline)}</div>
            <div class="benchmark-chart-bar" style="width: ${calculateBarWidth(
              row[metric],
            )}%">
              <span>${formatMetric(row[metric], metric)}</span>
            </div>
          </div>
        `,
      )
      .join("");
    benchmarkChart.innerHTML = rows;
  }

  function formatMetric(value, metric) {
    if (metric === "latency") {
      return `${escapeHtml(value)} ms`;
    }
    return `${formatPercent(value)}`;
  }

  function calculateBarWidth(value) {
    if (typeof value !== "number") return 0;
    if (value <= 1) return Math.round(value * 100);
    return Math.min(100, Math.round(value));
  }

  function formatPercent(value) {
    if (typeof value !== "number") return "-";
    return `${Math.round(value * 100)}%`;
  }

  function getCurrentMetric() {
    return metricSelect?.value || "accuracy";
  }

  function downloadJSON() {
    if (!benchmarkPayload || !benchmarkPayload.baselines?.length) return;
    const blob = new Blob([JSON.stringify(benchmarkPayload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    downloadFile(url, "cloudgraph-benchmark-results.json");
  }

  function downloadCSV() {
    if (!benchmarkPayload || !benchmarkPayload.baselines?.length) return;
    const rows = [
      [
        "baseline",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "hallucination_rate",
        "latency_ms",
      ],
      ...(benchmarkPayload.baselines || []).map((row) => [
        row.baseline,
        row.accuracy,
        row.precision,
        row.recall,
        row.f1,
        row.hallucination_rate,
        row.latency,
      ]),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    downloadFile(url, "cloudgraph-benchmark-results.csv");
  }

  function downloadFile(url, filename) {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function runBenchmarkTest() {
    if (!runBenchmarkButton) return;
    const originalText = runBenchmarkButton.innerHTML;
    runBenchmarkButton.disabled = true;
    runBenchmarkButton.innerHTML = `<span class="btn-icon">⚡</span> Running Test...`;

    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/benchmark/run`,
        { method: "POST" },
      );
      const data = await res.json();
      if (data.status === "success" && data.baselines?.length) {
        benchmarkPayload = data;
        renderSummary(data);
        renderTable(data.baselines);
        renderChart(data.baselines, getCurrentMetric());
        showResultsContainer();
        runBenchmarkButton.innerHTML = `<span class="btn-icon">⚡</span> Re-run Benchmark Test`;
        if (window.CloudGraph?.showToast) {
          window.CloudGraph.showToast(
            "Benchmark evaluation test completed successfully!",
            "success",
          );
        }
      } else {
        throw new Error(data.detail || "Failed to execute benchmark test.");
      }
    } catch (err) {
      if (window.CloudGraph?.showToast) {
        window.CloudGraph.showToast(`Benchmark error: ${err.message}`, "error");
      }
      runBenchmarkButton.innerHTML = originalText;
    } finally {
      runBenchmarkButton.disabled = false;
    }
  }

  async function loadBenchmarkSummary() {
    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/benchmark/summary`,
      );
      const data = await res.json();
      if (data.status === "success" && data.has_run && data.baselines?.length) {
        benchmarkPayload = data;
        renderSummary(data);
        renderTable(data.baselines);
        renderChart(data.baselines, getCurrentMetric());
        showResultsContainer();
        if (runBenchmarkButton) {
          runBenchmarkButton.innerHTML = `<span class="btn-icon">⚡</span> Re-run Benchmark Test`;
        }
      } else {
        showEmptyState();
        if (runBenchmarkButton) {
          runBenchmarkButton.innerHTML = `<span class="btn-icon">⚡</span> Run Benchmark Test`;
        }
      }
    } catch (err) {
      showEmptyState();
    }
  }

  function initialize() {
    metricSelect?.addEventListener("change", () => {
      if (benchmarkPayload && benchmarkPayload.baselines?.length) {
        renderChart(benchmarkPayload.baselines, getCurrentMetric());
      }
    });

    runBenchmarkButton?.addEventListener("click", runBenchmarkTest);
    exportJsonButton?.addEventListener("click", downloadJSON);
    exportCsvButton?.addEventListener("click", downloadCSV);

    loadBenchmarkSummary();
  }

  initialize();
});
