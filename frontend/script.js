/**
 * Hex to RGB converter for color interpolation calculations.
 */
function hexToRgb(hex) {
  const bigint = parseInt(hex.replace("#", ""), 16);
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  };
}

/**
 * Interpolates between a base color and Nord Aurora Red based on intensity.
 */
function interpolateColor(baseHex, intensity, maxIntensity = 10) {
  const targetHex = "#BF616A";
  const base = hexToRgb(baseHex);
  const target = hexToRgb(targetHex);
  const factor = Math.min(intensity / maxIntensity, 1);

  const r = Math.round(base.r + factor * (target.r - base.r));
  const g = Math.round(base.g + factor * (target.g - base.g));
  const b = Math.round(base.b + factor * (target.b - base.b));

  return `rgb(${r}, ${g}, ${b})`;
}

class App {
  /** Initializes the frontend application state and websocket connection. */
  constructor() {
    const serverHost = window.location.hostname;
    this.ws = new WebSocket(`ws://${serverHost}:8765`);
    this.canvas = document.getElementById("sim-canvas");
    this.ctx = this.canvas.getContext("2d");
    this.cellSize = 40;

    // FIX 4: Performance - Layered Rendering
    this.bgCanvas = document.createElement("canvas");
    this.bgCtx = this.bgCanvas.getContext("2d");

    this.mode = "idle";
    this.mapData = null;
    this.simState = null;
    this.editTool = "floor";

    this.setupWebsocket();
    this.setupCanvasEvents();
    this.agentCanvas = document.getElementById("agent-canvas");
    this.agentCtx = this.agentCanvas.getContext("2d");
  }

  /** Configures websocket event listeners and message routing. */
  setupWebsocket() {
    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({ client: "frontend" }));
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "map_list") {
        const select = document.getElementById("map-select");
        select.innerHTML = "";
        data.maps.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.innerText = m;
          select.appendChild(opt);
        });
      } else if (data.type === "error") {
        alert("Server Error: " + data.message);
      } else if (data.type === "save_response") {
        // FIX 3: Confirmation Save Logic
        if (data.success) {
          alert("Map saved successfully!");
        } else {
          alert("Error saving map: " + data.error);
        }
      } else if (data.type === "update") {
        const oldMap = JSON.stringify(this.mapData);
        this.mapData = data.map;
        this.simState = data.state;

        // Only redraw background if map structure changed
        if (oldMap !== JSON.stringify(this.mapData)) {
          this.resizeCanvas();
          this.drawBackground();
        }

        document.getElementById("sim-controls").classList.remove("hidden");
        document.getElementById("agent-status").innerText = data.agent_connected
          ? "Agent: Connected"
          : "Agent: Waiting...";
        this.draw();
      } else if (data.type === "agent_telemetry") {
        document.getElementById("agent-brain-panel").style.display = "flex";
        this.updateAgentBrainUI(data.data);
      }
    };
  }

  updateAgentBrainUI(telemetry) {
    if (!this.mapData) return;

    // Match canvas sizes only if needed to avoid flicker and redundant state resets
    if (this.agentCanvas.width !== this.canvas.width || this.agentCanvas.height !== this.canvas.height) {
        this.agentCanvas.width = this.canvas.width;
        this.agentCanvas.height = this.canvas.height;
    }
    
    this.agentCtx.clearRect(
      0,
      0,
      this.agentCanvas.width,
      this.agentCanvas.height,
    );

    // Draw the agent's memory map
    const visited = new Set(telemetry.visited);
    for (let y = 0; y < this.mapData.height; y++) {
      for (let x = 0; x < this.mapData.width; x++) {
        const cx = x * this.cellSize;
        const cy = y * this.cellSize;

        if (visited.has(`${x},${y}`)) {
          this.agentCtx.fillStyle = "#81A1C1"; // Explored
        } else {
          this.agentCtx.fillStyle = "#2E3440"; // Unknown (Fog of war)
        }
        this.agentCtx.fillRect(cx, cy, this.cellSize, this.cellSize);
        this.agentCtx.strokeStyle = "#3B4252";
        this.agentCtx.strokeRect(cx, cy, this.cellSize, this.cellSize);
      }
    }

    // Draw agent pos on memory map
    const [ax, ay] = this.simState.agent_pos;
    this.agentCtx.fillStyle = "#EBCB8B"; // Yellow dot for self
    this.agentCtx.beginPath();
    this.agentCtx.arc(
      ax * this.cellSize + this.cellSize / 2,
      ay * this.cellSize + this.cellSize / 2,
      this.cellSize / 3,
      0,
      Math.PI * 2,
    );
    this.agentCtx.fill();

    // Update probability bars
    const probs = telemetry.current_probs;
    ["N", "S", "E", "W"].forEach((dir) => {
      const p = probs[dir] || 0;
      const pct = Math.round(p * 100);
      document.getElementById(`prob-${dir}`).style.width = `${pct}%`;
      document.getElementById(`txt-${dir}`).innerText = `${pct}%`;

      // Color coding based on probability
      const bar = document.getElementById(`prob-${dir}`);
      if (p === 0)
        bar.style.backgroundColor = "var(--nord11)"; // Red (Invalid/Dead)
      else if (p > 0.4)
        bar.style.backgroundColor = "var(--nord14)"; // Green (Preferred)
      else bar.style.backgroundColor = "var(--nord13)"; // Yellow (Standard)
    });
  }

  /** Manages DOM visibility for navigation menus. */
  showMenu(menuId) {
    document
      .querySelectorAll(".panel")
      .forEach((p) => p.classList.add("hidden"));
    document.getElementById(menuId).classList.remove("hidden");
    this.mode = menuId === "edit-menu" ? "edit" : "idle";
    if (menuId === "main-menu") this.mapData = null;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  /** Dispatches a request to load a specific map from the server. */
  loadMap() {
    const filename = document.getElementById("map-select").value;
    if (filename) {
      this.mode = "run";
      this.ws.send(JSON.stringify({ action: "load_map", filename }));
    }
  }

  /** Dispatches a request to begin the simulation sequence. */
  startSimulation() {
    this.ws.send(JSON.stringify({ action: "start_sim" }));
  }

  /** Dispatches a request to halt the simulation sequence. */
  stopSimulation() {
    this.ws.send(JSON.stringify({ action: "stop_sim" }));
  }

  resetSimulation() {
    this.ws.send(JSON.stringify({ action: "reset_sim" }));
  }

  /** Initializes a blank grid structure for the map editor. */
  createNewMap() {
    const w = parseInt(document.getElementById("new-map-w").value);
    const h = parseInt(document.getElementById("new-map-h").value);
    const type = document.getElementById("new-map-type").value;
    const isTeleport = document.getElementById("new-map-teleport").checked;

    const grid = Array(h)
      .fill()
      .map(() => Array(w).fill("floor"));
    this.mapData = {
      width: w,
      height: h,
      type: type,
      teleport: isTeleport,
      grid: grid,
      start: [0, 0],
      target: [w - 1, h - 1],
    };
    this.simState = null;

    document.getElementById("editor-tools").classList.remove("hidden");
    this.resizeCanvas();
    this.drawBackground();
    this.draw();
  }

  /** Updates the active drawing tool for the map editor. */
  setEditTool(tool) {
    this.editTool = tool;
  }

  /** Compiles editor data and dispatches save request to server. */
  saveMap() {
    const name = document.getElementById("new-map-name").value || "new_map";
    this.ws.send(
      JSON.stringify({
        action: "save_map",
        filename: name,
        map_data: this.mapData,
      }),
    );
  }

  /** Adapts the HTML5 Canvas dimensions to fit the active grid. */
  resizeCanvas() {
    if (!this.mapData) return;
    const w = this.mapData.width * this.cellSize;
    const h = this.mapData.height * this.cellSize;
    this.canvas.width = w;
    this.canvas.height = h;
    this.bgCanvas.width = w;
    this.bgCanvas.height = h;
  }

  /** Registers mouse interaction listeners for map editing functionality. */
  setupCanvasEvents() {
    this.canvas.addEventListener("mousedown", (e) => {
      if (this.mode !== "edit" || !this.mapData) return;
      const rect = this.canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - rect.left) / this.cellSize);
      const y = Math.floor((e.clientY - rect.top) / this.cellSize);

      if (
        x >= 0 &&
        x < this.mapData.width &&
        y >= 0 &&
        y < this.mapData.height
      ) {
        if (this.editTool === "floor" || this.editTool === "obstacle") {
          this.mapData.grid[y][x] = this.editTool;
          this.drawBackground();
        } else if (this.editTool === "start") {
          this.mapData.start = [x, y];
          this.mapData.grid[y][x] = "floor";
          this.drawBackground();
        } else if (this.editTool === "target") {
          this.mapData.target = [x, y];
          this.mapData.grid[y][x] = "floor";
          this.drawBackground();
        }
        this.draw();
      }
    });
  }

  /** Renders the static parts of the map (floor, walls) once. */
  drawBackground() {
    if (!this.mapData) return;
    this.bgCtx.clearRect(0, 0, this.bgCanvas.width, this.bgCanvas.height);

    for (let y = 0; y < this.mapData.height; y++) {
      for (let x = 0; x < this.mapData.width; x++) {
        const cell = this.mapData.grid[y][x];
        const cx = x * this.cellSize;
        const cy = y * this.cellSize;

        if (cell === "floor") {
          this.bgCtx.fillStyle = "#D8DEE9"; // Default Nord 4
          this.bgCtx.fillRect(cx, cy, this.cellSize, this.cellSize);
          this.bgCtx.strokeStyle = "#E5E9F0";
          this.bgCtx.strokeRect(cx, cy, this.cellSize, this.cellSize);

          const isEdge =
            x === 0 ||
            x === this.mapData.width - 1 ||
            y === 0 ||
            y === this.mapData.height - 1;
          if (this.mapData.teleport && isEdge) {
            this.bgCtx.beginPath();
            this.bgCtx.moveTo(cx + this.cellSize / 2, cy + 10);
            this.bgCtx.lineTo(cx + this.cellSize - 10, cy + this.cellSize / 2);
            this.bgCtx.lineTo(cx + this.cellSize / 2, cy + this.cellSize - 10);
            this.bgCtx.lineTo(cx + 10, cy + this.cellSize / 2);
            this.bgCtx.closePath();
            this.bgCtx.strokeStyle = "rgba(180, 142, 173, 0.9)";
            this.bgCtx.lineWidth = 2;
            this.bgCtx.stroke();
            this.bgCtx.lineWidth = 1;
          }
        } else if (cell === "obstacle") {
          this.bgCtx.fillStyle = "#4C566A";
          this.bgCtx.fillRect(cx, cy, this.cellSize, this.cellSize);

          this.bgCtx.fillStyle = "rgba(255,255,255,0.1)";
          this.bgCtx.beginPath();
          this.bgCtx.moveTo(cx, cy);
          this.bgCtx.lineTo(cx + this.cellSize, cy);
          this.bgCtx.lineTo(cx + this.cellSize - 5, cy + 5);
          this.bgCtx.lineTo(cx + 5, cy + 5);
          this.bgCtx.fill();
        }
      }
    }
  }

  /** Renders the map grid, entities, and shading effects onto the canvas. */
  draw() {
    if (!this.mapData) return;

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Draw the pre-rendered static background
    this.ctx.drawImage(this.bgCanvas, 0, 0);

    // Only draw dynamic elements (Heatmaps, Start, Target, Agent)
    for (let y = 0; y < this.mapData.height; y++) {
      for (let x = 0; x < this.mapData.width; x++) {
        const cx = x * this.cellSize;
        const cy = y * this.cellSize;
        const key = `${x},${y}`;

        // 1. Draw Heatmaps (Visits/Hits)
        if (
          this.simState &&
          this.simState.visits[key] &&
          this.simState.visits[key] > 1
        ) {
          this.ctx.fillStyle = interpolateColor(
            "#D8DEE9",
            this.simState.visits[key],
            15,
          );
          this.ctx.globalAlpha = 0.5;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
          this.ctx.globalAlpha = 1.0;
        }

        if (this.simState && this.simState.hits[key]) {
          this.ctx.fillStyle = interpolateColor(
            "#4C566A",
            this.simState.hits[key],
            5,
          );
          this.ctx.globalAlpha = 0.7;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
          this.ctx.globalAlpha = 1.0;
        }

        // 2. Draw Points of Interest
        if (
          this.mapData.start &&
          x === this.mapData.start[0] &&
          y === this.mapData.start[1]
        ) {
          this.ctx.fillStyle = "rgba(235, 203, 139, 0.5)";
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
        }
        if (
          this.mapData.type === "maze" &&
          this.mapData.target &&
          x === this.mapData.target[0] &&
          y === this.mapData.target[1]
        ) {
          this.ctx.fillStyle = "rgba(163, 190, 140, 0.5)";
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
        }
      }
    }

    if (this.simState && this.simState.agent_pos) {
      const [ax, ay] = this.simState.agent_pos;
      const centerX = ax * this.cellSize + this.cellSize / 2;
      const centerY = ay * this.cellSize + this.cellSize / 2;
      const radius = this.cellSize / 2 - 4;

      this.ctx.beginPath();
      this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      this.ctx.fillStyle = "#88C0D0";
      this.ctx.shadowColor = "rgba(0,0,0,0.5)";
      this.ctx.shadowBlur = 5;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
    }
  }
}

const app = new App();
