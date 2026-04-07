# <img src="frontend/favicon.svg" alt="logo" width="128" height="128" align="middle"> SI2 - Maze

SI2 - Maze is a simulation platform designed for developing and testing autonomous agents in grid-based environments. The platform provides a real-time visualization of agent behavior, allowing researchers and students to observe how different algorithms navigate complex mazes or explore entire rooms. The system follows a client-server architecture, where a Python-based backend handles the simulation logic and WebSocket communication, while an HTML5 Canvas-based frontend provides the visual interface.

In this environment, agents are tasked with either reaching a specific target in "Maze Mode" or visiting every reachable tile in "Room Mode". The simulation supports various configurations, including teleportation mechanics that allow agents to wrap around the edges of the grid. This flexibility enables the creation of diverse challenges, from simple pathfinding to exhaustive exploration in topologically complex environments.

## Game Rules

The simulation environment operates on a discrete grid where each cell can be either a floor tile or an obstacle.

### World State
The simulation state is communicated to agents as a JSON object containing:
- `position`: The current `[x, y]` coordinates of the agent.
- `valid_actions`: A list of cardinal directions `['N', 'S', 'E', 'W']` that are currently traversable.
- `objective_reached`: A boolean indicating if the goal has been accomplished.
- `target`: The `[x, y]` coordinates of the goal (Maze mode only).
- `width` and `height`: The dimensions of the grid.

### Possible Actions
Agents can move in four cardinal directions:
- **North (N)**: Decrements the Y-coordinate.
- **South (S)**: Increments the Y-coordinate.
- **East (E)**: Increments the X-coordinate.
- **West (W)**: Decrements the X-coordinate.

If **Teleportation** is enabled, moving past the grid boundaries will wrap the agent to the opposite side.

## Setup

### Prerequisites
- Docker and Docker Compose
- Python 3.10+

### Launching the Simulation
The entire stack (backend and frontend viewer) can be started using Docker Compose:

```bash
docker compose up
```

The frontend will be available at `http://localhost:8080`, and the backend WebSocket server at `ws://localhost:8765`.

### Executing Agents Locally
It is recommended to use a virtual environment to run the agents:

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run an agent
python agents/dummy_agent.py
# OR
python agents/manual_agent.py
```

## Project Structure

- `agents/`: Contains the autonomous agent implementations.
  - `base_agent.py`: Abstract base class defining the agent interface.
  - `dummy_agent.py`: A simple random-walker agent.
  - `manual_agent.py`: A keyboard-controlled agent for testing.
- `backend/`: The simulation engine.
  - `server.py`: Handles map logic, agent movement, and WebSocket broadcasts.
- `frontend/`: The web-based visualization tool.
  - `index.html`, `script.js`, `styles.css`: Canvas rendering and UI logic.
- `maps/`: JSON files defining the maze and room layouts.

## Development

To develop a new agent, inherit from the `BaseAgent` class and implement the `deliberate_maze` and `deliberate_room` methods.

```python
from agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    async def deliberate_maze(self):
        # Implement your maze navigation logic here
        return "N"

    async def deliberate_room(self):
        # Implement your room exploration logic here
        return "S"
```

For more detailed information about the API and class structures, please refer to the [Project Documentation](https://mariolpantunes.github.io/si2-maze/).

## Authors

* **Mário Antunes** - [mariolpantunes](https://github.com/mariolpantunes)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
