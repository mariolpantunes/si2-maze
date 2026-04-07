"""
Abstract base class for simulation agents in the SI2 - Maze environment.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import websockets

# Configure standard logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - AGENT - %(levelname)s - %(message)s")


class BaseAgent:
    """
    Abstract base class for simulation agents.
    Handles all WebSocket communications, state updates, routing, and UI telemetry.
    Subclasses MUST implement the deliberate_maze and deliberate_room methods.
    """

    def __init__(self, server_uri: str = "ws://localhost:8765") -> None:
        """Initialize the agent.

        Args:
            server_uri (str): URI of the simulation server.
        """
        self.server_uri: str = server_uri
        self.current_state: Optional[Dict[str, Any]] = None
        self.step_delay: float = 0.15  # Configurable delay between moves
        self.idle_logged: bool = False

    async def run(self) -> None:
        """Main connection loop.

        Do not override this unless modifying network protocols.
        """
        try:
            async with websockets.connect(self.server_uri) as websocket:
                await websocket.send(json.dumps({"client": "agent"}))
                logging.info(f"Connected to {self.server_uri}")

                async for message in websocket:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    data = json.loads(message)

                    if data.get("type") == "error":
                        logging.error(f"Server Error: {data.get('message')}")
                        continue

                    if data.get("type") == "state":
                        self.current_state = data

                        if self.current_state and self.current_state.get("objective_reached"):
                            if not self.idle_logged:
                                await self.deliberate()
                                await self.send_telemetry(websocket)
                                logging.info("Objective reached. Idling...")
                                self.idle_logged = True
                            continue
                        else:
                            self.idle_logged = False

                        action = await self.deliberate()

                        if action:
                            await self.send_telemetry(websocket)
                            await websocket.send(json.dumps({"action": "move", "direction": action}))
                            await asyncio.sleep(self.step_delay)

                    elif data.get("type") == "reset":
                        self.reset_memory()
                        logging.info("Memory wiped due to simulation reset.")

        except Exception as e:
            logging.error(f"Connection error: {e}")

    async def deliberate(self) -> Optional[str]:
        """Routes the deliberation based on the presence of a target (Maze vs Room).

        Returns:
            Optional[str]: The chosen direction ('N', 'S', 'E', 'W') or None.
        """
        if not self.current_state:
            return None

        if self.current_state.get("target") is not None:
            return await self.deliberate_maze()
        else:
            return await self.deliberate_room()

    async def deliberate_maze(self) -> Optional[str]:
        """Logic for maze navigation.

        Raises:
            NotImplementedError: Subclasses must implement this.

        Returns:
            Optional[str]: The chosen direction ('N', 'S', 'E', 'W') or None.
        """
        raise NotImplementedError("Subclasses must implement deliberate_maze()")

    async def deliberate_room(self) -> Optional[str]:
        """Logic for room exploration.

        Raises:
            NotImplementedError: Subclasses must implement this.

        Returns:
            Optional[str]: The chosen direction ('N', 'S', 'E', 'W') or None.
        """
        raise NotImplementedError("Subclasses must implement deliberate_room()")

    def reset_memory(self) -> None:
        """Clears internal tracking variables when the simulation resets."""
        pass

    async def send_telemetry(self, websocket: Any) -> None:
        """Packages internal memory/probabilities and sends them to the frontend UI.

        Args:
            websocket (Any): The current WebSocket connection.
        """
        pass
