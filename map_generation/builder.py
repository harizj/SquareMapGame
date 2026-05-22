import random

_WATER_BIOMES = {'ocean', 'coastal'}

# Features that cannot coexist with the key feature
_INCOMPATIBLE = {
    'mountain':   {'forest', 'hills', 'river', 'floodplain'},
    'forest':     {'mountain'},
    'hills':      {'mountain'},
    'river':      {'mountain'},
    'floodplain': {'mountain'},
}

# Features that require a land (non-water) tile
_REQUIRES_LAND = {'forest', 'hills', 'mountain', 'iron', 'floodplain'}


class MapBuilder:
    def __init__(self, game_map):
        self._map = game_map

    def resize(self, rows, cols):
        """Rebuild the map grid to the given dimensions (all tiles reset to water)."""
        from src.game.map import Map
        self._map.rows = rows
        self._map.cols = cols
        self._map.tiles = [
            [Map._make_empty_tile(r, c) for c in range(cols)]
            for r in range(rows)
        ]

    def zone(self, rows, biome, cols=None):
        """Set biome for all tiles in rows (range or list), optionally filtered to cols."""
        is_water_biome = biome in _WATER_BIOMES
        col_range = cols if cols is not None else range(self._map.cols)
        for r in rows:
            for c in col_range:
                t = self._map.tiles[r][c]
                t.biome = biome
                if is_water_biome:
                    if 'water' not in t.terrain_features:
                        t.terrain_features = list(t.terrain_features) + ['water']
                else:
                    t.terrain_features = [f for f in t.terrain_features if f != 'water']
                t.update_terrain_properties()
                t.build_deposits()

    def scatter(self, feature, biome=None, density=0.5, cols=None, requires=None):
        """Randomly add a terrain feature to matching tiles at the given probability (0-1).

        biome:    if set, only tiles with that biome are eligible.
        density:  probability per tile of receiving the feature.
        cols:     optional range/list to restrict which columns are eligible.
        requires: optional terrain feature that must already be present on the tile.
        """
        incompatible = _INCOMPATIBLE.get(feature, set())
        requires_land = feature in _REQUIRES_LAND
        col_set = set(cols) if cols is not None else None

        for row in self._map.tiles:
            for t in row:
                if col_set is not None and t.col not in col_set:
                    continue
                if biome is not None and t.biome != biome:
                    continue
                if requires_land and t.water:
                    continue
                if requires is not None and requires not in t.terrain_features:
                    continue
                if feature in t.terrain_features:
                    continue
                if any(f in t.terrain_features for f in incompatible):
                    continue
                if random.random() >= density:
                    continue
                if feature == 'mountain':
                    t.terrain_features = [f for f in t.terrain_features if f not in incompatible]
                t.terrain_features = list(t.terrain_features) + [feature]
                t.update_terrain_properties()
                t.build_deposits()
