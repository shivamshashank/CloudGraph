// Drives the CloudGraph UI and captures the walkthrough screenshots.
//
// Scripted so the image set in docs/guides/UI_WALKTHROUGH.md can be regenerated
// after a UI change with the same viewport, order and waits.
//
//   node scripts/capture_ui_walkthrough.mjs [baseUrl] [outDir]
//
// Needs the UI on baseUrl (default http://localhost:3000), and for shots 12-15
// the two data stores, each via kubectl port-forward -n cloudgraph-system:
//   svc/cloudgraph-ui 3000:3000 | svc/cloudgraph 7474:7474 7687:7687 |
//   svc/cloudgraph-qdrant 6333:6333
//
// NEO4J_PASSWORD is read from the environment, never hardcoded (get it from the
// cloudgraph-neo4j-auth secret). Either data-store section is skipped with a
// warning if unreachable, so a UI-only run still succeeds.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = process.argv[2] || "http://localhost:3000";
const OUT = process.argv[3] || "docs/guides/images/ui";
const NEO4J_URL = process.env.NEO4J_URL || "http://localhost:7474";
const QDRANT_URL = process.env.QDRANT_URL || "http://localhost:6333";
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || "";
const VIEWPORT = { width: 1440, height: 900 };

let seq = 0;
const shots = [];

async function shot(page, slug, { full = false } = {}) {
  seq += 1;
  const name = `${String(seq).padStart(2, "0")}-${slug}.png`;
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: full });
  shots.push(name);
  console.log(`  captured ${name}`);
}

// The shell polls /health and /graph/data on a timer; give it a beat so the
// sidebar shows real values instead of the initial zeros.
const settle = (page, ms = 2500) => page.waitForTimeout(ms);

async function goto(page, path) {
  await page.goto(`${BASE}/${path}`, { waitUntil: "networkidle" });
  await settle(page);
}

async function reachable(page, url) {
  try {
    const res = await page.request.get(url, { timeout: 5000 });
    return res.ok();
  } catch {
    return false;
  }
}

// Neo4j Browser stacks every result as a "frame"; close the old ones so each
// screenshot shows the query it is meant to illustrate.
async function closeNeo4jFrames(page) {
  for (let i = 0; i < 8; i += 1) {
    const close = page
      .locator('button[title="Close"], [aria-label="Close"]')
      .last();
    if ((await close.count()) === 0) break;
    await close.click({ timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(250);
  }
}

async function runCypher(page, query) {
  const editor = page.locator(".cm-content, textarea").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+a").catch(() => {});
  await page.keyboard.type(query, { delay: 8 });
  await page.keyboard.press("Escape"); // dismiss the autocomplete popup
  await page.waitForTimeout(300);
  await page.keyboard.press("ControlOrMeta+Enter");
  await page.waitForTimeout(9000);
  await page.mouse.click(700, 880); // blur the editor
  await page.waitForTimeout(600);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`    [console error] ${m.text()}`);
  });

  // ── 1. Topology Map ────────────────────────────────────────────────────
  // Empty states are deliberately not captured: the walkthrough documents the
  // system doing its job, not its placeholders.
  await goto(page, "index.html");
  await page.click("#btn-discover").catch(() => {});

  // Discovery walks every namespace; wait for it to land, then reload so the
  // graph is drawn from the freshly written Neo4j state.
  await page.waitForTimeout(9000);
  await goto(page, "index.html");
  await shot(page, "topology-graph-rendered");

  // Open the details panel on whichever pod node is present.
  const podNode = page.locator("#nodes-group > g").nth(12);
  if (await podNode.count()) {
    await podNode.click({ force: true }).catch(() => {});
    await page.waitForTimeout(1200);
    await shot(page, "topology-node-details");
  }

  // ── 2. AI Diagnosis ────────────────────────────────────────────────────
  await goto(page, "diagnosis.html");

  // A real investigation runs five specialist agents plus a consensus call for
  // every pod with error logs, at high reasoning effort — measured at ~6.5 min.
  // Poll rather than guess a timeout.
  await page.click("#btn-analyze").catch(() => {});
  for (let i = 0; i < 90; i += 1) {
    await page.waitForTimeout(10000);
    const t = await page
      .locator("#rca-output")
      .innerText()
      .catch(() => "");
    if (t && !t.includes("Running multi-agent") && t.length > 200) break;
  }
  await shot(page, "diagnosis-run-result");

  await page.click("#tab-context-explorer").catch(() => {});
  await page.waitForTimeout(800);

  const ctxInput = page.locator("#context-query");
  if (await ctxInput.count()) {
    await ctxInput.fill("cloudgraph-api");
    await page.click("#btn-context-compare").catch(() => {});
    await page.waitForTimeout(9000);
    await shot(page, "diagnosis-context-payload");

    for (const tab of ["Retrieval", "Evidence", "Prompts"]) {
      await page
        .click(`#context-view-toggle [data-view="${tab.toLowerCase()}"]`)
        .catch(() => {});
      await page.waitForTimeout(700);
      await shot(page, `diagnosis-context-${tab.toLowerCase()}`);
    }
  }

  // ── 3. Log Stream ──────────────────────────────────────────────────────
  await goto(page, "logs.html");
  await page.waitForTimeout(11000); // one poll cycle of real pod logs
  await shot(page, "log-stream-real-pod-logs");

  // ── 4. Evidence & Search ───────────────────────────────────────────────
  await goto(page, "evidence.html");

  const searchBox = page.locator("#graphrag-query");
  if (await searchBox.count()) {
    await searchBox.fill("cloudgraph");
    await page.click("#btn-search").catch(() => {});
    await page.waitForTimeout(6000);
    await shot(page, "evidence-keyword-vs-hybrid", { full: true });
  }

  const evBox = page.locator("#retrieval-query");
  if (await evBox.count()) {
    await evBox.fill("cloudgraph");
    await page.click("#btn-retrieve").catch(() => {});
    await page.waitForTimeout(6000);
    await shot(page, "evidence-retrieved", { full: true });
  }

  // ── 5. Benchmark — intentionally not captured ─────────────────────────
  //
  // The Benchmark screen is hidden from the sidebar in this release and
  // deferred to the next version. Its code is retained, but it is not the
  // source of any published result and its design (point estimates, no CIs,
  // compute confounded with architecture) is not citable as it stands.
  // Capturing it would imply it is part of the evaluated system.

  // ── 6. LLM Settings ────────────────────────────────────────────────────
  await goto(page, "settings.html");
  await shot(page, "llm-settings-form");

  // ── 7. Data stores — Neo4j and Qdrant ─────────────────────────────────
  //
  // Separate consoles on their own ports, so each is probed first and skipped
  // rather than failing the whole run.
  if (!NEO4J_PASSWORD) {
    console.log("  [skip] Neo4j shots — NEO4J_PASSWORD not set");
  } else if (!(await reachable(page, NEO4J_URL))) {
    console.log(`  [skip] Neo4j shots — ${NEO4J_URL} unreachable`);
  } else {
    await page.goto(`${NEO4J_URL}/browser/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(5000);
    await page.locator('input[name="password"]').fill(NEO4J_PASSWORD);
    await page.getByRole("button", { name: /^Connect$/ }).click();
    await page.waitForTimeout(9000);
    await closeNeo4jFrames(page);

    const queries = [
      [
        "neo4j-incident-subgraph",
        "MATCH (i:Incident)-[r]-(x) RETURN i,r,x LIMIT 30",
      ],
      [
        "neo4j-label-counts",
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC",
      ],
    ];
    for (const [slug, query] of queries) {
      await runCypher(page, query);
      await shot(page, slug);
      await closeNeo4jFrames(page);
    }
  }

  if (!(await reachable(page, `${QDRANT_URL}/collections`))) {
    console.log(`  [skip] Qdrant shot — ${QDRANT_URL} unreachable`);
  } else {
    await page.goto(`${QDRANT_URL}/dashboard#/collections`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(5000);
    await shot(page, "qdrant-collections");
  }

  await browser.close();
  console.log(`\n${shots.length} screenshots written to ${OUT}`);
  shots.forEach((s) => console.log(`  ${s}`));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
