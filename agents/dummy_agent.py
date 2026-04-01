"""
Random Walker Agent implementation.
An agent that moves randomly among valid actions.
"""

import asyncio
import json
import random
from typing import Any, Dict, List, Optional

try:
    from base_agent import BaseAgent
except ImportError:
    from agents.base_agent import BaseAgent


class RandomWalkerAgent(BaseAgent):
    """
    A baseline agent that moves completely randomly among valid actions.
    Useful for testing server physics, map loading, and UI rendering.
    """

    def __init__(self, server_uri: str = "ws://localhost:8765") -> None:
        """
        Initialize the random walker agent.

        Args:
            server_uri (str): URI of the simulation server.
        """
        super().__init__(server_uri)
        self.visited_tiles: set[str] = set()

    def reset_memory(self) -> None:
        """Clears memory when the user resets the map from the UI."""
        self.visited_tiles.clear()

    async def deliberate_maze(self) -> Optional[str]:
        """
        Logic for maps where 'target' is defined.

        Returns:
            Optional[str]: The chosen direction or None.
        """
        if not self.current_state:
            return None

        # Record current position
        pos_str = (
            f"{self.current_state['position'][0]},{self.current_state['position'][1]}"
        )
        self.visited_tiles.add(pos_str)

        # Get valid actions from the server state
        valid_actions: List[str] = self.current_state.get("valid_actions", [])

        if not valid_actions:
            return None

        # Choose randomly
        return random.choice(valid_actions)

    async def deliberate_room(self) -> Optional[str]:
        """
        Logic for room clearing (no target).
        Uses the same random walking strategy as maze mode.

        Returns:
            Optional[str]: The chosen direction or None.
        """
        return await self.deliberate_maze()

    async def send_telemetry(self, websocket: Any) -> None:
        """
        Calculates arbitrary probabilities (since it's random)
        and sends internal map memory to the frontend UI.

        Args:
            websocket: The current WebSocket connection.
        """
        if not self.current_state:
            return

        valid_actions: List[str] = self.current_state.get("valid_actions", [])

        # Build equal probability distribution for valid moves
        prob_per_move: float = 1.0 / len(valid_actions) if valid_actions else 0.0
        probs: Dict[str, float] = {
            "N": prob_per_move if "N" in valid_actions else 0.0,
            "S": prob_per_move if "S" in valid_actions else 0.0,
            "E": prob_per_move if "E" in valid_actions else 0.0,
            "W": prob_per_move if "W" in valid_actions else 0.0,
        }

        telemetry_data = {
            "action": "telemetry",
            "data": {"visited": list(self.visited_tiles), "current_probs": probs},
        }

        await websocket.send(json.dumps(telemetry_data))


if __name__ == "__main__":
    agent = RandomWalkerAgent()
    asyncio.run(agent.run())
