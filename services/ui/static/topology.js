/**
 * CloudGraph Topology Visualization component.
 * Responsible for SVG layered drawing, host node scheduling layouts,
 * and mouse zoom/drag offsets.
 */
document.addEventListener("DOMContentLoaded", () => {
  const svg = document.getElementById("topology-svg");
  const nodesGroup = document.getElementById("nodes-group");
  const edgesGroup = document.getElementById("edges-group");

  const nodePopup = document.getElementById("node-popup");
  const popupTitle = document.getElementById("popup-title");
  const popupContent = document.getElementById("popup-content");
  const btnClosePopup = document.getElementById("btn-close-popup");

  if (!svg) return; // Only execute on topology page

  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let viewOffset = { x: 50, y: 50 };
  let viewZoom = 1.0;

  // SVG drag-and-pan support
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

  // SVG Mouse wheel zoom support
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    if (e.deltaY < 0) {
      viewZoom = Math.min(3.0, viewZoom * zoomFactor);
    } else {
      viewZoom = Math.max(0.4, viewZoom / zoomFactor);
    }
    updateTransform();
  });

  if (btnClosePopup && nodePopup) {
    btnClosePopup.addEventListener("click", () =>
      nodePopup.classList.add("hidden"),
    );
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

  // Hierarchical Layout Calculations for SVG Node Drawing
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

    const containerWidth = svg.parentElement
      ? svg.parentElement.clientWidth
      : 800;
    const maxLayerCount = Math.max(
      ...Object.values(layers).map((l) => l.length),
    );
    const width = Math.max(containerWidth, maxLayerCount * 110 + 100);
    svg.setAttribute("viewBox", `0 0 ${width} 520`);
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
    assignPositions(layers["Commit"], 50);
    assignPositions(layers["Deployment"], 130);
    assignPositions(layers["Service"], 210);
    assignPositions(layers["Incident"], 280);
    assignPositions(layers["Pod"], 360);
    assignPositions(layers["Node"], 450);

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
          fillColor = "#dc2626";
          strokeColor = "#ef4444";
          circle.setAttribute("class", "node-circle node-failed");
        }
      }

      circle.setAttribute("fill", fillColor);
      circle.setAttribute("stroke", strokeColor);
      nodeG.appendChild(circle);

      // Truncate display name for node label text to prevent collisions
      let displayName = node.name || "";
      if (node.label === "Incident" && displayName.length > 12) {
        displayName = "inc-" + displayName.substring(0, 8) + "…";
      } else if (displayName.length > 16) {
        displayName = displayName.substring(0, 14) + "…";
      }

      // Node Label text (shown below node)
      const label = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text",
      );
      label.setAttribute("y", 28);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("class", "node-text");
      label.textContent = displayName;

      // Add label background container
      const bbox = { width: displayName.length * 6.5 + 10, height: 16 };
      const labelBg = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect",
      );
      labelBg.setAttribute("x", -bbox.width / 2);
      labelBg.setAttribute("y", 16);
      labelBg.setAttribute("width", bbox.width);
      labelBg.setAttribute("height", bbox.height);
      labelBg.setAttribute("class", "node-label-bg");

      nodeG.appendChild(labelBg);
      nodeG.appendChild(label);

      // Inner Symbol for node type identification
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
    popupTitle.textContent = `${node.label} Node Details`;
    nodePopup.classList.remove("hidden");

    let propsHtml = '<div class="prop-list">';
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

  // Register rendering capability globally
  window.CloudGraph.renderGraph = renderGraph;
});
