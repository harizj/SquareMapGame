class Director:
    """Base class for AI-controlled faction behavior."""

    def plan_turn(self, faction, game_map):
        """Called once per end-turn to issue movement and attack orders."""
        pass

    def spawn_tick(self, faction, game_map, turn):
        """Called once per end-turn to handle unit spawning."""
        pass


class HordeDirector(Director):
    """Spawns unit groups at intervals and moves them toward the nearest enemy."""

    def __init__(self, spawn_interval=5):
        self.spawn_interval = spawn_interval

    def plan_turn(self, faction, game_map):
        pass  # movement logic to be implemented

    def spawn_tick(self, faction, game_map, turn):
        pass  # spawn logic to be implemented
