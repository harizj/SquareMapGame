from src.game.constants import DEFAULT_MOVE_DISTANCE, CITY_VISION_DISTANCE


class LineOfSight:
    """Controls which tiles are visible on the map.

    mode:
      'all'     -- all tiles visible (no fog)
      'none'    -- no tiles visible (full fog)
      'faction' -- only tiles visible to `faction`
    """

    def __init__(self, game_map):
        self.mode = 'all'
        self.faction = None
        self._game_map = game_map

    def get_visible(self):
        """Returns None (all visible), set() (none visible), or a set of (row, col) tuples."""
        if self.mode == 'all':
            return None
        if self.mode == 'none':
            return set()
        return self._compute_faction_visible()

    def _compute_faction_visible(self):
        game_map = self._game_map
        faction = self.faction
        visible = set()

        for (r, c), groups in game_map.unit_groups.items():
            for group in groups:
                if group.faction is faction:
                    reachable = game_map.get_reachable_from(
                        r, c, DEFAULT_MOVE_DISTANCE, scheme='any', include_start=True
                    )
                    visible.update(reachable.keys())

        seen_routes = set()
        for (r, c), city in game_map.cities.items():
            if city.faction is faction:
                reachable = game_map.get_reachable_from(
                    r, c, CITY_VISION_DISTANCE, scheme='any', include_start=True
                )
                visible.update(reachable.keys())
                for route in city.trade_routes:
                    if id(route) not in seen_routes:
                        seen_routes.add(id(route))
                        visible.update(route.get_visual_path())

        return visible
