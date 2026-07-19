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

  let benchmarkPayload = null;

  function renderSummary(data) {
    if (!datasetName || !datasetSplit || !benchmarkNotes || !benchmarkNotesList)
      return;
    datasetName.textContent = data.dataset || "Benchmark dataset";
    datasetSplit.textContent = data.split || "N/A";
    benchmarkNotes.textContent = "Experiment notes and dataset split summary.";
    benchmarkNotesList.innerHTML = (data.notes || [])
      .map(
        (note) => `<div class="benchmark-note-item">${escapeHtml(note)}</div>`,
      )
      .join("");
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
    if (!benchmarkPayload) return;
    const blob = new Blob([JSON.stringify(benchmarkPayload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    downloadFile(url, "cloudgraph-benchmark-results.json");
  }

  function downloadCSV() {
    if (!benchmarkPayload) return;
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

  async function loadBenchmarkSummary() {
    try {
      const res = await fetch(
        `${window.CloudGraph.API_BASE}/api/v1/benchmark/summary`,
      );
      const data = await res.json();
      if (data.status === "success") {
        benchmarkPayload = data;
        renderSummary(data);
        renderTable(data.baselines || []);
        renderChart(data.baselines || [], getCurrentMetric());
      } else {
        throw new Error(data.detail || "Failed to load benchmark summary.");
      }
    } catch (err) {
      benchmarkNotes.textContent = `Benchmark load error: ${escapeHtml(err.message)}`;
      benchmarkTable.querySelector("tbody").innerHTML = "";
      benchmarkChart.innerHTML = "";
    }
  }

  function initialize() {
    metricSelect?.addEventListener("change", () => {
      if (benchmarkPayload) {
        renderChart(benchmarkPayload.baselines || [], getCurrentMetric());
      }
    });

    exportJsonButton?.addEventListener("click", downloadJSON);
    exportCsvButton?.addEventListener("click", downloadCSV);

    loadBenchmarkSummary();
  }

  initialize();
});
