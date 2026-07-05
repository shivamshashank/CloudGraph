document.addEventListener('DOMContentLoaded', () => {
    // API client configuration
    const API_BASE = ""; // Relative paths since we reverse proxy in mock_service.py

    // DOM Elements
    const btnDiscover = document.getElementById('btn-discover');
    const btnAnalyze = document.getElementById('btn-analyze');
    const btnReset = document.getElementById('btn-reset');
    const btnRetrieve = document.getElementById('btn-retrieve');
    const graphLoader = document.getElementById('graph-loader');

    // Stats Elements
    const statNodes = document.getElementById('stat-nodes');
    const statPods = document.getElementById('stat-pods');
    const statDeployments = document.getElementById('stat-deployments');
    const statServices = document.getElementById('stat-services');

    // Health status
    const apiStatus = document.getElementById('api-status');
    const apiDot = document.getElementById('api-dot');
    const dbStatus = document.getElementById('db-status');
    const dbDot = document.getElementById('db-dot');

    // Panels
    const rcaOutput = document.getElementById('rca-output');
    const logsFeed = document.getElementById('logs-feed');
    const retrievalOutput = document.getElementById('retrieval-output');
    const retrievalQuery = document.getElementById('retrieval-query');
    const nodePopup = document.getElementById('node-popup');
    const popupTitle = document.getElementById('popup-title');
    const popupContent = document.getElementById('popup-content');
    const btnClosePopup = document.getElementById('btn-close-popup');

    // SVG elements
    const svg = document.getElementById('topology-svg');
    const nodesGroup = document.getElementById('nodes-group');
    const edgesGroup = document.getElementById('edges-group');

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

    // Event Listeners
    btnDiscover.addEventListener('click', runDiscovery);
    btnAnalyze.addEventListener('click', runInvestigation);
    btnReset.addEventListener('click', resetGraph);
    btnRetrieve.addEventListener('click', runRetrieval);
    btnClosePopup.addEventListener('click', () => nodePopup.classList.add('hidden'));

    // SVG drag-and-pan support
    svg.addEventListener('mousedown', (e) => {
        if (e.target === svg || e.target.tagName === 'rect') {
            isDragging = true;
            dragStart = { x: e.clientX - viewOffset.x, y: e.clientY - viewOffset.y };
            svg.style.cursor = 'grabbing';
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (isDragging) {
            viewOffset.x = e.clientX - dragStart.x;
            viewOffset.y = e.clientY - dragStart.y;
            updateTransform();
        }
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
        svg.style.cursor = 'grab';
    });

    svg.addEventListener('wheel', (e) => {
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

    function updateTransform() {
        nodesGroup.setAttribute('transform', `translate(${viewOffset.x}, ${viewOffset.y}) scale(${viewZoom})`);
        edgesGroup.setAttribute('transform', `translate(${viewOffset.x}, ${viewOffset.y}) scale(${viewZoom})`);
    }

    // Health Checks
    async function checkHealth() {
        try {
            const res = await fetch(`${API_BASE}/health`);
            const data = await res.json();

            apiStatus.textContent = "Healthy";
            apiDot.className = "indicator-dot online";

            if (data.neo4j === "connected") {
                dbStatus.textContent = "Live";
                dbDot.className = "indicator-dot online";
            } else {
                dbStatus.textContent = "Offline";
                dbDot.className = "indicator-dot offline";
            }
        } catch (err) {
            apiStatus.textContent = "Unreachable";
            apiDot.className = "indicator-dot offline";
            dbStatus.textContent = "Offline";
            dbDot.className = "indicator-dot offline";
        }
    }

    // Trigger Kubernetes Discovery
    async function runDiscovery() {
        graphLoader.classList.remove('hidden');
        try {
            const res = await fetch(`${API_BASE}/api/v1/graph/discover`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.status === "success") {
                addLogLine("SYSTEM", "Kubernetes cluster discovery completed successfully.", "info");
                addLogLine("SYSTEM", `Found: ${data.discovered.nodes} Nodes, ${data.discovered.pods} Pods, ${data.discovered.services} Services.`, "info");
                fetchGraph();
            } else {
                addLogLine("SYSTEM", `Discovery skipped or failed: ${data.reason || 'Unknown error'}`, "warn");
            }
        } catch (err) {
            addLogLine("SYSTEM", `Error triggering discovery: ${err.message}`, "error");
        } finally {
            graphLoader.classList.add('hidden');
        }
    }

    // Reset Neo4j Database
    async function resetGraph() {
        if (!confirm("Are you sure you want to clear the entire graph database?")) return;
        try {
            const res = await fetch(`${API_BASE}/api/v1/demo/reset`, { method: 'POST' });
            const data = await res.json();
            if (data.status === "success") {
                addLogLine("SYSTEM", "Graph database cleared.", "info");
                rcaOutput.innerHTML = `
                    <div class="empty-state">
                        <span class="empty-icon">🛡️</span>
                        <p>No investigations run yet. Trigger "Run AI Diagnosis" to begin analyzing anomalies.</p>
                    </div>`;
                logsFeed.innerHTML = `
                    <div class="empty-state">
                        <span class="empty-icon">📺</span>
                        <p>Discover the cluster to stream live pod stdout logs.</p>
                    </div>`;
                fetchGraph();
            }
        } catch (err) {
            addLogLine("SYSTEM", `Error resetting graph: ${err.message}`, "error");
        }
    }

    // Trigger Investigation / Root Cause Analysis
    async function runInvestigation() {
        rcaOutput.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Running multi-agent diagnostics... Scanning log history... Analyzing metrics correlation...</p>
            </div>`;
        try {
            const res = await fetch(`${API_BASE}/api/v1/investigations/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ namespace: "cloudgraph-system" })
            });
            const data = await res.json();
            if (data.status === "success" && data.results.length > 0) {
                renderRCA(data.results);
                addLogLine("ENGINE", "Incident investigation completed.", "info");
                fetchGraph();
            }
        } catch (err) {
            rcaOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">Investigation failed: ${err.message}</p></div>`;
        }
    }

    async function runRetrieval() {
        const query = retrievalQuery.value.trim();
        if (!query) {
            retrievalOutput.innerHTML = '<div class="empty-state"><p>Enter a term to retrieve evidence.</p></div>';
            return;
        }

        retrievalOutput.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Retrieving graph evidence...</p>
            </div>`;

        try {
            const res = await fetch(`${API_BASE}/api/v1/graphrag/retrieve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, namespace: 'cloudgraph-system' })
            });
            const data = await res.json();
            if (data.status === 'success') {
                renderRetrieval(data);
            } else {
                retrievalOutput.innerHTML = `<div class="empty-state"><p class="log-level-error">${data.detail || 'Retrieval failed.'}</p></div>`;
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
                renderGraph(data.nodes, data.edges);
                streamLogs(data.nodes);
            }
        } catch (err) {
            console.error("Error fetching graph data:", err);
        }
    }

    function updateStats(nodes) {
        let n = 0, p = 0, d = 0, s = 0;
        nodes.forEach(node => {
            if (node.label === "Node") n++;
            else if (node.label === "Pod") p++;
            else if (node.label === "Deployment") d++;
            else if (node.label === "Service") s++;
        });
        statNodes.textContent = n;
        statPods.textContent = p;
        statDeployments.textContent = d;
        statServices.textContent = s;
    }

    // Stream Pod logs to log feeds panel
    function streamLogs(nodes) {
        const podNodes = nodes.filter(n => n.label === "Pod");
        if (podNodes.length === 0) return;

        // Find if logs console has empty state
        if (logsFeed.querySelector('.empty-state')) {
            logsFeed.innerHTML = '';
        }

        // Simulating log scroll from active pods
        podNodes.forEach(pod => {
            if (pod.properties && pod.properties.status === "Running") {
                // Occasional dummy telemetry entries to feel active if there are no raw errors
                if (Math.random() > 0.85) {
                    const messages = [
                        "HTTP GET /health - 200 OK",
                        "Prometheus metrics scraped",
                        "Database connection pool active",
                        "Task execution queue processed",
                        "Internal event dispatched"
                    ];
                    const msg = messages[Math.floor(Math.random() * messages.length)];
                    addLogLine(pod.name.split('-')[0], msg, "info");
                }
            } else if (pod.properties && pod.properties.status !== "Running" && pod.properties.status !== "Succeeded") {
                if (Math.random() > 0.6) {
                    const warnings = [
                        "Failed to pull image: tag not found",
                        "Back-off restarting failed container",
                        "Database connection handshake timeout after 10s",
                        "Terminated due to OutOfMemory limits"
                    ];
                    const msg = warnings[Math.floor(Math.random() * warnings.length)];
                    addLogLine(pod.name.split('-')[0], msg, "error");
                }
            }
        });
    }

    function addLogLine(source, message, level) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';

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

    // Hierarchical Layout Calculations for SVG Node Drawing
    function renderGraph(nodes, edges) {
        nodesGroup.innerHTML = '';
        edgesGroup.innerHTML = '';

        if (nodes.length === 0) return;

        // Group nodes by labels to map layouts
        const layers = {
            "Commit": [],
            "Deployment": [],
            "Service": [],
            "Pod": [],
            "Node": [],
            "Incident": []
        };

        nodes.forEach(node => {
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
                    y: yCoord
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
        edges.forEach(edge => {
            const start = positions[edge.source];
            const end = positions[edge.target];
            if (start && end) {
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', start.x);
                line.setAttribute('y1', start.y);
                line.setAttribute('x2', end.x);
                line.setAttribute('y2', end.y);
                line.setAttribute('class', 'edge-line');

                // Group to enable label hover in future
                const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                edgeGroup.setAttribute('class', 'edge-group');
                edgeGroup.appendChild(line);
                edgesGroup.appendChild(edgeGroup);
            }
        });

        // Render Nodes
        nodes.forEach(node => {
            const pos = positions[node.id] || { x: Math.random() * width, y: 250 };

            const nodeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            nodeG.setAttribute('class', 'node-group');
            nodeG.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);
            nodeG.addEventListener('click', (e) => {
                e.stopPropagation();
                showNodeDetails(node);
            });

            // Draw Node Circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('r', 16);
            circle.setAttribute('class', 'node-circle');

            // Assign color scheme based on node type and status
            let fillColor = '#6366f1'; // Indigo default
            let strokeColor = 'rgba(255,255,255,0.4)';

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
                circle.setAttribute('class', 'node-circle node-failed');
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
                    circle.setAttribute('class', 'node-circle node-failed');
                }
            }

            circle.setAttribute('fill', fillColor);
            circle.setAttribute('stroke', strokeColor);
            nodeG.appendChild(circle);

            // Draw Label text
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            // Clean up long names for graph labels
            let labelText = node.name;
            if (labelText.length > 18) {
                labelText = labelText.substring(0, 8) + '...' + labelText.substring(labelText.length - 6);
            }
            text.textContent = labelText;
            text.setAttribute('class', 'node-text');
            text.setAttribute('y', 30);
            text.setAttribute('text-anchor', 'middle');

            // Draw label background for better readability
            const bbox_width = Math.max(labelText.length * 7, 50);
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('class', 'node-label-bg');
            rect.setAttribute('x', -bbox_width / 2);
            rect.setAttribute('y', 18);
            rect.setAttribute('width', bbox_width);
            rect.setAttribute('height', 16);

            nodeG.appendChild(rect);
            nodeG.appendChild(text);

            // Draw node inner symbol
            const symbol = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            symbol.setAttribute('text-anchor', 'middle');
            symbol.setAttribute('y', 4);
            symbol.setAttribute('fill', '#ffffff');
            symbol.setAttribute('font-size', '12px');
            symbol.setAttribute('font-weight', 'bold');
            symbol.setAttribute('pointer-events', 'none');

            if (node.label === "Pod") symbol.textContent = "P";
            else if (node.label === "Node") symbol.textContent = "H"; // Host
            else if (node.label === "Service") symbol.textContent = "S";
            else if (node.label === "Deployment") symbol.textContent = "D";
            else if (node.label === "Commit") symbol.textContent = "C";
            else if (node.label === "Incident") symbol.textContent = "⚠️";

            nodeG.appendChild(symbol);
            nodesGroup.appendChild(nodeG);
        });
    }

    // Detail Drawer Sidebar
    function showNodeDetails(node) {
        selectedNode = node;
        popupTitle.textContent = `${node.label} Node Details`;
        nodePopup.classList.remove('hidden');

        let propsHtml = '<div class="prop-list">';
        // Iterate through properties
        const ignoreProps = ['id', 'uuid'];
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

        // Add specific links/action items
        propsHtml += `
            <div class="prop-row">
                <span class="prop-key">Graph Database ID</span>
                <span class="prop-value" style="font-family: monospace; font-size: 11px;">${node.id}</span>
            </div>
        `;
        propsHtml += '</div>';
        popupContent.innerHTML = propsHtml;
    }

    function renderRetrieval(data) {
        if (!data.results || data.results.length === 0) {
            retrievalOutput.innerHTML = `<div class="empty-state"><p>${data.summary || 'No evidence found.'}</p></div>`;
            return;
        }

        const html = `
            <div class="retrieval-summary">${data.summary}</div>
            <div class="retrieval-list">
                ${data.results.map(item => `
                    <div class="retrieval-item">
                        <div class="retrieval-item-header">
                            <span class="retrieval-label">${item.label}</span>
                            <span class="retrieval-name">${item.name}</span>
                        </div>
                        <div class="retrieval-status">${item.status}</div>
                        <div class="retrieval-related">
                            ${item.related && item.related.length > 0 ? item.related.map(rel => `
                                <span class="retrieval-chip">${rel.rel || 'RELATED_TO'} → ${rel.related_name || 'unknown'}</span>
                            `).join('') : '<span class="retrieval-chip">No adjacent context</span>'}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        retrievalOutput.innerHTML = html;
    }

    // Render RCA report cards
    function renderRCA(results) {
        if (results.length === 0) return;

        let rcaHtml = '<div class="rca-report">';

        results.forEach(res => {
            const severityClass = res.severity === 'CRITICAL' ? 'rca-badge-critical' : (res.severity === 'HIGH' ? 'rca-badge-high' : 'rca-badge-healthy');
            const logsHtml = res.error_logs && res.error_logs.length > 0
                ? `<div class="rca-block">
                     <div class="rca-block-title">Anomalous Telemetry Signals</div>
                     <div class="rca-logs">
                       ${res.error_logs.map(log => `<div class="rca-log-item">${log}</div>`).join('')}
                     </div>
                   </div>`
                : '';

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

                <div class="rca-block rca-remediation">
                    <div class="rca-block-title" style="color: #a5b4fc;">Remediation Recommendation</div>
                    <div class="rca-block-body">${res.remediation}</div>
                </div>
            `;
        });

        rcaHtml += '</div>';
        rcaOutput.innerHTML = rcaHtml;
    }
});
