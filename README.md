# ![logo](frontend/favicon.svg =128x128) SI2 - Maze Simulation Environment

A simulation platform for autonomous agents to navigate mazes and explore rooms. This project follows a client-server architecture using WebSockets for real-time visualization and agent control.

## Project Structure

- `backend/`: Python server using `websockets`. Handles map logic, movement, and simulation state.
- `frontend/`: HTML5 Canvas visualization and map editor (served via Nginx).
- `agents/`: Autonomous agents that connect to the backend via WebSockets.
- `maps/`: JSON files defining maze and room layouts.

## Rules of the Game

The simulation environment supports two primary game modes, both restricted to **one agent and one viewer** at a time.

### Movement & Interaction
- **Directions**: Agents move in four cardinal directions: **North (N)**, **South (S)**, **East (E)**, and **West (W)**.
- **Obstacles**: Dark grey tiles are walls. If an agent tries to move into an obstacle, the move is blocked and recorded as a **"hit"** (visualized in red on the heatmap).
- **Floor Tiles**: Light grey tiles are traversable. Each visit to a tile is recorded and visualized (in blue on the heatmap).
- **Teleportation**: If enabled in map settings, the grid wraps around. (See [Teleportation Mechanics](#teleportation-mechanics) for details).

### Objectives
- **Maze Mode**: The agent must navigate from the **Start** tile (yellow highlight) to the **Target** tile (green highlight). The simulation ends when the target is reached.
- **Room Mode**: The agent must explore the entire reachable area. The simulation ends only when **all reachable floor tiles** have been visited at least once. Reachability is determined by the server using a Breadth-First Search (BFS) from the starting position.

## Teleportation Mechanics

Teleportation is a map-level setting that fundamentally changes the topology of the grid:
- **Wrap-around Movement**: If an agent moves off an edge (e.g., West at `x=0`), it "teleports" to the opposite side of the same row (`x=width-1`). This applies to all four cardinal directions.
- **Reachability Impact**: When `teleport` is `true`, tiles that appear isolated by walls in a standard grid may become reachable via the edges. The server's BFS-based reachability check accounts for this wrapping, ensuring the **Room Mode** objective is always mathematically sound.
- **Visual Cues**: In the frontend, teleportation-enabled maps are often indicated by small purple arrow markers on the edges of the floor tiles.

## Map JSON Format

Maps are stored as JSON files in the `maps/` directory. Below is the schema:

```json
{
  "width": 10,        // Grid columns (integer)
  "height": 10,       // Grid rows (integer)
  "type": "maze",     // "maze" or "room"
  "teleport": false,  // Boolean toggle for edge-wrapping
  "start": [0, 0],    // Starting coordinates [x, y]
  "target": [9, 9],   // Target coordinates [x, y] (Required for "maze")
  "grid": [           // 2D array of tile types
    ["floor", "obstacle", "..."],
    ["...", "...", "..."]
  ]
}
```

### Tile Types
- `"floor"`: Traversable space.
- `"obstacle"`: Walls that block movement and record "hits".

## Getting Started

### Prerequisites
- Python 3.10+
- Docker

### Setup
The easiest way to run the full environment (Backend + Nginx Frontend) is via Docker Compose:

```bash
docker compose build
docker compose up
```

After the simulation is done, remember to stop the containers:

```bash
docker compose down
```

- **Frontend**: `http://localhost:8080` (served via Nginx)
- **Backend WebSocket**: `ws://localhost:8765`

## Development

- **Adding Agents**: Inherit from `BaseAgent` in `agents/base_agent.py` and implement `deliberate_maze` and `deliberate_room`.
- **Map Editor**: Use the "Create New Map" tool in the frontend to design custom levels. Maps are saved to the `maps/` directory.

It is recommended to use a virtual environment:
```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

With the backend running, start an autonomous or manual agent:

```bash
# Start a random walker
python agents/dummy_agent.py

# OR start a manual keyboard-controlled agent
python agents/manual_agent.py
```

## Authors

  * **Mário Antunes** - [mariolpantunes](https://github.com/mariolpantunes)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
