import random

_WATER_BIOMES = {'ocean', 'coastal'}

# Hex neighbor offsets for odd-r offset grid, keyed by row parity
_HEX_NEIGHBORS = {
    0: [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)],
    1: [(-1,  0), (-1, 1), (0, -1), (0, 1), (1,  0), (1, 1)],
}

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

    def blend_border(self, biome_a, biome_b, probability=0.20):
        """Randomly flip border tiles between two biomes to soften the boundary.

        Each tile of biome_a adjacent to biome_b (and vice versa) has `probability`
        chance of switching to the other biome. All eligible tiles are collected
        before any flips so changes don't cascade within the same call.
        """
        border = set()
        for row in self._map.tiles:
            for t in row:
                if t.biome not in (biome_a, biome_b):
                    continue
                for dr, dc in _HEX_NEIGHBORS[t.row % 2]:
                    nr, nc = t.row + dr, t.col + dc
                    if 0 <= nr < self._map.rows and 0 <= nc < self._map.cols:
                        nb = self._map.tiles[nr][nc]
                        if nb.biome in (biome_a, biome_b) and nb.biome != t.biome:
                            border.add(t)
                            break

        for t in border:
            if random.random() >= probability:
                continue
            new_biome = biome_b if t.biome == biome_a else biome_a
            t.biome = new_biome
            if new_biome in _WATER_BIOMES:
                if 'water' not in t.terrain_features:
                    t.terrain_features = list(t.terrain_features) + ['water']
            else:
                t.terrain_features = [f for f in t.terrain_features if f != 'water']
            t.update_terrain_properties()
            t.build_deposits()

    def scatter_biome(self, biome, density=0.5, source_biome=None, cols=None, requires_neighbor=None):
        """Randomly reassign tiles to the given biome at the given probability.

        source_biome:     if set, only tiles with that biome are eligible.
        cols:             optional range/list to restrict which columns are eligible.
        requires_neighbor: if set, only tiles adjacent to a tile with that biome are eligible.
                           Candidates are collected before any flips to prevent cascade.
        """
        is_water_biome = biome in _WATER_BIOMES
        col_set = set(cols) if cols is not None else None

        candidates = []
        for row in self._map.tiles:
            for t in row:
                if col_set is not None and t.col not in col_set:
                    continue
                if source_biome is not None and t.biome != source_biome:
                    continue
                if t.biome == biome:
                    continue
                if requires_neighbor is not None:
                    neighbors = _HEX_NEIGHBORS[t.row % 2]
                    if not any(
                        0 <= t.row + dr < self._map.rows and
                        0 <= t.col + dc < self._map.cols and
                        self._map.tiles[t.row + dr][t.col + dc].biome == requires_neighbor
                        for dr, dc in neighbors
                    ):
                        continue
                candidates.append(t)

        for t in candidates:
            if random.random() >= density:
                continue
            t.biome = biome
            if is_water_biome:
                if 'water' not in t.terrain_features:
                    t.terrain_features = list(t.terrain_features) + ['water']
            else:
                t.terrain_features = [f for f in t.terrain_features if f != 'water']
            t.update_terrain_properties()
            t.build_deposits()

    def scatter(self, feature, biome=None, density=0.5, rows=None, cols=None, requires=None, requires_neighbor=None):
        """Randomly add a terrain feature to matching tiles at the given probability (0-1).

        biome:            if set, only tiles with that biome are eligible.
        density:          probability per tile of receiving the feature.
        rows:             optional range/list to restrict which rows are eligible.
        cols:             optional range/list to restrict which columns are eligible.
        requires:         terrain feature that must already be present on the tile.
        requires_neighbor: terrain feature that must be present on at least one neighbor.
        """
        incompatible = _INCOMPATIBLE.get(feature, set())
        requires_land = feature in _REQUIRES_LAND
        row_set = set(rows) if rows is not None else None
        col_set = set(cols) if cols is not None else None

        candidates = []
        for row in self._map.tiles:
            for t in row:
                if row_set is not None and t.row not in row_set:
                    continue
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
                if requires_neighbor is not None:
                    neighbors = _HEX_NEIGHBORS[t.row % 2]
                    if not any(
                        0 <= t.row + dr < self._map.rows and
                        0 <= t.col + dc < self._map.cols and
                        requires_neighbor in self._map.tiles[t.row + dr][t.col + dc].terrain_features
                        for dr, dc in neighbors
                    ):
                        continue
                candidates.append(t)

        for t in candidates:
            if random.random() >= density:
                continue
            if feature == 'mountain':
                t.terrain_features = [f for f in t.terrain_features if f not in incompatible]
            t.terrain_features = list(t.terrain_features) + [feature]
            t.update_terrain_properties()
            t.build_deposits()
