import asyncio
import random

from base_agent import BaseAgent


class RandomWalkerAgent(BaseAgent):
    """
    A baseline agent that moves completely randomly among valid actions.
    Useful for testing server physics, map loading, and UI rendering.
    """

    def __init__(self, server_uri="ws://localhost:8765"):
        super().__init__(server_uri)
        self.visited_tiles = set()

    def reset_memory(self):
        """Clears memory when the user resets the map from the UI."""
        self.visited_tiles.clear()

    async def deliberate_maze(self):
        """Logic for maps where 'target' is defined."""
        # Record current position
        pos_str = (
            f"{self.current_state['position'][0]},{self.current_state['position'][1]}"
        )
        self.visited_tiles.add(pos_str)

        # Get valid actions from the server state
        valid_actions = self.current_state.get("valid_actions", [])

        if not valid_actions:
            return None

        # Choose randomly
        return random.choice(valid_actions)

    async def deliberate_room(self):
        """Logic for room clearing (no target). We'll use the same logic for now."""
        return await self.deliberate_maze()

    async def send_telemetry(self, websocket):
        """
        Calculates arbitrary probabilities (since it's random)
        and sends internal map memory to the frontend UI.
        """
        valid_actions = self.current_state.get("valid_actions", [])

        # Build equal probability distribution for valid moves
        prob_per_move = 1.0 / len(valid_actions) if valid_actions else 0
        probs = {
            "N": prob_per_move if "N" in valid_actions else 0.0,
            "S": prob_per_move if "S" in valid_actions else 0.0,
            "E": prob_per_move if "E" in valid_actions else 0.0,
            "W": prob_per_move if "W" in valid_actions else 0.0,
        }

        telemetry_data = {
            "action": "telemetry",
            "data": {"visited": list(self.visited_tiles), "current_probs": probs},
        }

        import json

        await websocket.send(json.dumps(telemetry_data))


if __name__ == "__main__":
    agent = RandomWalkerAgent()
    asyncio.run(agent.run())
