"""
Backend server for the SI2 - Maze simulation environment.
Handles WebSocket connections, map management, and simulation state.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

# Configure standard logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class SimulationServer:
    """
    Main simulation engine.
    Handles map loading, agent movement, and state broadcasting.
    """

    def __init__(self) -> None:
        """Initialize the SimulationServer with default states."""
        self.frontend_ws: Optional[Any] = None
        self.agent_ws: Optional[Any] = None
        self.maps_dir: str = "maps"
        self.current_map: Optional[Dict[str, Any]] = None
        self.reachable_tiles: int = 0
        self.sim_state: Dict[str, Any] = {}
        self.running: bool = False

        if not os.path.exists(self.maps_dir):
            os.makedirs(self.maps_dir)
            logging.info(f"Created maps directory at: {os.path.abspath(self.maps_dir)}")

    def calculate_reachable_tiles(self) -> int:
        """
        Uses BFS to count floor tiles reachable from the start position.

        Returns:
            int: Number of reachable floor tiles.
        """
        if not self.current_map:
            return 0

        start_pos: Tuple[int, int] = tuple(self.current_map.get("start", [0, 0]))  # type: ignore
        width: int = self.current_map["width"]
        height: int = self.current_map["height"]
        is_teleport: bool = self.current_map.get("teleport", False)

        queue: List[Tuple[int, int]] = [start_pos]
        visited: set[Tuple[int, int]] = {start_pos}
        reachable_count: int = 0

        while queue:
            cx, cy = queue.pop(0)
            if self.current_map["grid"][cy][cx] != "obstacle":
                reachable_count += 1

                # Check 4-way neighbors
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = cx + dx, cy + dy

                    if is_teleport:
                        nx %= width
                        ny %= height
                    elif nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue

                    if (nx, ny) not in visited and self.current_map["grid"][ny][
                        nx
                    ] != "obstacle":
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        return reachable_count

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """
        Start the WebSocket server.

        Args:
            host (str): Host address to bind to.
            port (int): Port number to listen on.
        """
        import websockets

        logging.info(f"Starting websocket server on ws://{host}:{port}")
        async with websockets.serve(self.handle_client, host, port):
            await asyncio.Future()

    async def handle_client(self, websocket: Any) -> None:
        """
        Handle incoming WebSocket connections.

        Args:
            websocket: The WebSocket connection object.
        """
        client_type: str = "Unknown"
        try:
            init_msg = await websocket.recv()
            try:
                data = json.loads(init_msg)
            except json.JSONDecodeError:
                logging.warning("Received malformed initial message.")
                return

            client_type = data.get("client", "Unknown")

            if client_type == "frontend":
                if self.frontend_ws is not None:
                    logging.warning(
                        "Frontend already connected. Rejecting new connection."
                    )
                    await websocket.send(
                        json.dumps(
                            {"type": "error", "message": "Frontend already connected."}
                        )
                    )
                    await websocket.close()
                    return
                logging.info("Frontend connected.")
                self.frontend_ws = websocket
                await self.send_map_list()
                await self.frontend_loop(websocket)
            elif client_type == "agent":
                if self.agent_ws is not None:
                    logging.warning(
                        "Agent already connected. Rejecting new connection."
                    )
                    await websocket.send(
                        json.dumps(
                            {"type": "error", "message": "Agent already connected."}
                        )
                    )
                    await websocket.close()
                    return
                logging.info("Agent connected.")
                self.agent_ws = websocket
                if self.running and self.current_map:
                    await self.send_agent_state()
                await self.agent_loop(websocket)
            else:
                logging.warning(
                    f"Unknown client type attempted connection: {client_type}"
                )

        except Exception as e:
            logging.error(f"Error handling client {client_type}: {e}")
        finally:
            if websocket == self.frontend_ws:
                self.frontend_ws = None
                logging.info("Frontend session cleared.")
            elif websocket == self.agent_ws:
                self.agent_ws = None
                logging.info("Agent session cleared.")

    async def frontend_loop(self, websocket: Any) -> None:
        """
        Main loop for handling frontend messages.

        Args:
            websocket: The frontend WebSocket connection.
        """
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "load_map":
                    self.load_map(data.get("filename"))
                    await self.update_frontend()
                    if self.agent_ws and self.current_map:
                        await self.agent_ws.send(json.dumps({"type": "reset"}))
                        await self.send_agent_state()
                elif action == "save_map":
                    filename = data.get("filename")
                    map_data = data.get("map_data")
                    success, error = self.save_map(filename, map_data)

                    await websocket.send(
                        json.dumps(
                            {
                                "type": "save_response",
                                "success": success,
                                "error": error,
                            }
                        )
                    )

                    if success:
                        await self.send_map_list()
                elif action == "start_sim":
                    if self.current_map:
                        self.reset_sim()
                        self.running = True
                        logging.info("Simulation started via frontend.")
                        await self.update_frontend()
                        if self.agent_ws:
                            await self.send_agent_state()
                    else:
                        logging.warning("Attempted to start simulation without a map.")
                elif action == "stop_sim":
                    self.running = False
                    logging.info("Simulation stopped via frontend.")
                    await self.update_frontend()
                elif action == "reset_sim":
                    self.reset_sim()
                    await self.update_frontend()
                    if self.agent_ws and self.current_map:
                        await self.agent_ws.send(json.dumps({"type": "reset"}))
                        await self.send_agent_state()
            except Exception as e:
                logging.error(f"Error processing frontend message: {e}")

    async def agent_loop(self, websocket: Any) -> None:
        """
        Main loop for handling agent messages.

        Args:
            websocket: The agent WebSocket connection.
        """
        async for message in websocket:
            if not self.running or not self.current_map:
                continue
            try:
                data = json.loads(message)
                if data.get("action") == "move":
                    direction = data.get("direction")
                    self.process_move(direction)
                    self.check_objective()
                    await self.update_frontend()
                    await self.send_agent_state()
                elif data.get("action") == "telemetry":
                    if self.frontend_ws:
                        await self.frontend_ws.send(
                            json.dumps(
                                {"type": "agent_telemetry", "data": data.get("data")}
                            )
                        )
            except Exception as e:
                logging.error(f"Error processing agent message: {e}")

    def process_move(self, direction: str) -> None:
        """
        Process an agent movement request.

        Args:
            direction (str): Direction to move ('N', 'S', 'E', 'W').
        """
        if not self.current_map:
            return

        x, y = self.sim_state["agent_pos"]
        nx, ny = x, y

        if direction == "N":
            ny -= 1
        elif direction == "S":
            ny += 1
        elif direction == "E":
            nx += 1
        elif direction == "W":
            nx -= 1

        width = self.current_map["width"]
        height = self.current_map["height"]

        if self.current_map.get("teleport", False):
            nx = nx % width
            ny = ny % height
        else:
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                return

        cell = self.current_map["grid"][ny][nx]
        if cell == "obstacle":
            key = f"{nx},{ny}"
            self.sim_state["hits"][key] = self.sim_state["hits"].get(key, 0) + 1
        else:
            self.sim_state["agent_pos"] = [nx, ny]
            key = f"{nx},{ny}"
            self.sim_state["visits"][key] = self.sim_state["visits"].get(key, 0) + 1

    def get_valid_actions(self) -> List[str]:
        """
        Get a list of valid actions for the agent at its current position.

        Returns:
            List[str]: List of valid cardinal directions.
        """
        if not self.current_map:
            return []

        x, y = self.sim_state["agent_pos"]
        width = self.current_map["width"]
        height = self.current_map["height"]
        actions: List[str] = []

        is_teleport: bool = self.current_map.get("teleport", False)

        # Check North
        ny = (y - 1) % height if is_teleport else y - 1
        if (ny >= 0 or is_teleport) and self.current_map["grid"][ny][x] != "obstacle":
            actions.append("N")

        # Check South
        ny = (y + 1) % height if is_teleport else y + 1
        if (ny < height or is_teleport) and self.current_map["grid"][ny][
            x
        ] != "obstacle":
            actions.append("S")

        # Check East
        nx = (x + 1) % width if is_teleport else x + 1
        if (nx < width or is_teleport) and self.current_map["grid"][y][
            nx
        ] != "obstacle":
            actions.append("E")

        # Check West
        nx = (x - 1) % width if is_teleport else x - 1
        if (nx >= 0 or is_teleport) and self.current_map["grid"][y][nx] != "obstacle":
            actions.append("W")

        return actions

    def reset_sim(self) -> None:
        """Resets the map state and heatmaps to their initial conditions."""
        if self.current_map:
            start_pos = self.current_map.get("start", [0, 0])
            self.sim_state = {
                "agent_pos": start_pos,
                "visits": {f"{start_pos[0]},{start_pos[1]}": 1},
                "hits": {},
            }
            self.running = False
            logging.info("Simulation reset to start state.")

    def check_objective(self) -> None:
        """Checks if the simulation objective has been reached."""
        if not self.current_map:
            return

        if self.current_map["type"] == "maze":
            if self.sim_state["agent_pos"] == self.current_map.get("target"):
                self.running = False
                logging.info("Objective Reached: Maze target found!")
        elif self.current_map["type"] == "room":
            if len(self.sim_state["visits"]) >= self.reachable_tiles:
                self.running = False
                logging.info("Objective Reached: Room fully explored!")

    async def send_agent_state(self) -> None:
        """Sends the current simulation state to the agent."""
        if self.agent_ws and self.current_map:
            payload = {
                "type": "state",
                "position": self.sim_state["agent_pos"],
                "valid_actions": self.get_valid_actions(),
                "objective_reached": not self.running,
                "target": self.current_map.get("target")
                if self.current_map["type"] == "maze"
                else None,
                "start": self.current_map.get("start"),
                "width": self.current_map.get("width"),
                "height": self.current_map.get("height"),
            }
            await self.agent_ws.send(json.dumps(payload))

    async def update_frontend(self) -> None:
        """Sends the current simulation state to the frontend."""
        if self.frontend_ws:
            payload = {
                "type": "update",
                "map": self.current_map,
                "state": self.sim_state,
                "running": self.running,
                "agent_connected": self.agent_ws is not None,
            }
            await self.frontend_ws.send(json.dumps(payload))

    async def send_map_list(self) -> None:
        """Sends the list of available maps to the frontend."""
        if self.frontend_ws:
            try:
                maps = sorted(
                    [f for f in os.listdir(self.maps_dir) if f.endswith(".json")]
                )
                await self.frontend_ws.send(
                    json.dumps({"type": "map_list", "maps": maps})
                )
            except Exception as e:
                logging.error(f"Failed to read maps directory: {e}")

    def load_map(self, filename: str) -> None:
        """
        Load a map from a JSON file.

        Args:
            filename (str): Name of the map file to load.
        """
        try:
            filename = os.path.basename(filename)
            filepath = os.path.join(self.maps_dir, filename)
            with open(filepath, "r") as f:
                self.current_map = json.load(f)

            self.reachable_tiles = self.calculate_reachable_tiles()
            logging.info(
                f"Map loaded: {filename}. Reachable floor tiles: {self.reachable_tiles}"
            )

            start_pos = self.current_map.get("start", [0, 0])
            self.sim_state = {
                "agent_pos": start_pos,
                "visits": {f"{start_pos[0]},{start_pos[1]}": 1},
                "hits": {},
            }
            self.running = False
            logging.info(f"Successfully loaded map: {filename}")
        except Exception as e:
            logging.error(f"Failed to load map {filename}: {e}")

    def validate_map_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Basic schema validation for incoming map data.

        Args:
            data (Dict[str, Any]): Map data to validate.

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            required = ["width", "height", "type", "grid", "start"]
            if not all(k in data for k in required):
                return (
                    False,
                    "Missing required fields (width, height, type, grid, start).",
                )

            if (
                not isinstance(data["grid"], list)
                or len(data["grid"]) != data["height"]
            ):
                return False, f"Grid height mismatch. Expected {data['height']} rows."

            for row in data["grid"]:
                if not isinstance(row, list) or len(row) != data["width"]:
                    return (
                        False,
                        f"Grid width mismatch. Expected {data['width']} columns.",
                    )

            return True, None
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def save_map(
        self, filename: str, map_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Save map data to a JSON file.

        Args:
            filename (str): Name of the file to save.
            map_data (Dict[str, Any]): Map data to save.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            filename = os.path.basename(filename)
            if not filename.endswith(".json"):
                filename += ".json"

            is_valid, error_msg = self.validate_map_data(map_data)
            if not is_valid:
                logging.warning(f"Rejected invalid map save request: {error_msg}")
                return False, error_msg

            filepath = os.path.join(self.maps_dir, filename)
            with open(filepath, "w") as f:
                json.dump(map_data, f)

            logging.info(f"Successfully saved map: {filepath}")
            return True, None
        except PermissionError:
            err = "Permission denied when saving. Check Docker volume permissions."
            logging.error(err)
            return False, err
        except Exception as e:
            err = f"Unexpected error saving map: {str(e)}"
            logging.error(err)
            return False, err


if __name__ == "__main__":
    server = SimulationServer()
    asyncio.run(server.start())
