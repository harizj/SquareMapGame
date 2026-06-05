import random

_WATER_BIOMES = {'ocean', 'coastal'}

# Neighbor offsets for 8-directional square grid
_SQUARE_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

# Features that cannot coexist with the key feature
_INCOMPATIBLE = {
    'mountain':   {'forest', 'hills', 'river', 'floodplain'},
    'forest':     {'mountain', 'river'},
    'hills':      {'mountain'},
    'river':      {'mountain', 'forest'},
    'floodplain': {'mountain'},
}

# Features that require a land (non-water) tile
_REQUIRES_LAND = {'forest', 'hills', 'mountain', 'iron', 'floodplain'}

# River flow config per direction.
# advance: (dr, dc) step each iteration
# straight: edges for a straight tile
# left / right: (current_edges, neighbor_dr, neighbor_dc, neighbor_edges)
#   "left" = decreasing lane index (col for N/S flow, row for E/W flow)
#   "right" = increasing lane index
_RIVER_FLOW = {
    'S': dict(advance=( 1,  0), straight={'N', 'S'},
              left=({'N', 'W'},  0, -1, {'S', 'E'}),
              right=({'N', 'E'}, 0,  1, {'S', 'W'})),
    'N': dict(advance=(-1,  0), straight={'N', 'S'},
              left=({'S', 'W'},  0, -1, {'N', 'E'}),
              right=({'S', 'E'}, 0,  1, {'N', 'W'})),
    'E': dict(advance=( 0,  1), straight={'W', 'E'},
              left=({'N', 'W'}, -1,  0, {'S', 'E'}),
              right=({'S', 'W'}, 1,  0, {'N', 'E'})),
    'W': dict(advance=( 0, -1), straight={'W', 'E'},
              left=({'N', 'E'}, -1,  0, {'S', 'W'}),
              right=({'S', 'E'}, 1,  0, {'N', 'W'})),
}


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
                for dr, dc in _SQUARE_NEIGHBORS:
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
                    neighbors = _SQUARE_NEIGHBORS
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

    def scatter(self, feature, biome=None, density=0.5, rows=None, cols=None, requires=None, requires_neighbor=None, neighbor_dirs=None):
        """Randomly add a terrain feature to matching tiles at the given probability (0-1).

        biome:            if set, only tiles with that biome are eligible.
        density:          probability per tile of receiving the feature.
        rows:             optional range/list to restrict which rows are eligible.
        cols:             optional range/list to restrict which columns are eligible.
        requires:         terrain feature that must already be present on the tile.
        requires_neighbor: terrain feature that must be present on at least one neighbor.
        neighbor_dirs:    list of (dr, dc) offsets to check for requires_neighbor;
                          defaults to all 8 directions if not specified.
        """
        incompatible = _INCOMPATIBLE.get(feature, set())
        requires_land = feature in _REQUIRES_LAND
        row_set = set(rows) if rows is not None else None
        col_set = set(cols) if cols is not None else None
        dirs = neighbor_dirs if neighbor_dirs is not None else _SQUARE_NEIGHBORS

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
                    if not any(
                        0 <= t.row + dr < self._map.rows and
                        0 <= t.col + dc < self._map.cols and
                        requires_neighbor in self._map.tiles[t.row + dr][t.col + dc].terrain_features
                        for dr, dc in dirs
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

    def generate_river(self, start_row, start_col, lanes, direction='S'):
        """Generate a river flowing in `direction` within the designated lanes.

        start_row, start_col: position of the first tile (gets a straight tile).
        lanes: list/range of valid lane values — columns for N/S flow, rows for E/W flow.
        direction: primary flow direction, one of 'N', 'S', 'E', 'W'.

        Each step the river either continues straight or turns one lane left/right.
        Turns are not available at the lane boundaries.
        """
        cfg = _RIVER_FLOW[direction]
        adv_r, adv_c = cfg['advance']
        straight = cfg['straight']
        l_tile, l_dr, l_dc, l_nb = cfg['left']
        r_tile, r_dr, r_dc, r_nb = cfg['right']

        min_lane = min(lanes)
        max_lane = max(lanes)
        use_col = direction in ('N', 'S')

        r, c = start_row, start_col
        self._river_tile(r, c, straight)
        r, c = r + adv_r, c + adv_c

        while 0 <= r < self._map.rows and 0 <= c < self._map.cols:
            lane = c if use_col else r
            options = ['straight']
            if lane > min_lane:
                options.append('left')
            if lane < max_lane:
                options.append('right')

            choice = random.choice(options)

            if choice == 'straight':
                self._river_tile(r, c, straight)
                r, c = r + adv_r, c + adv_c
            elif choice == 'left':
                self._river_tile(r, c, l_tile)
                nr, nc = r + l_dr, c + l_dc
                self._river_tile(nr, nc, l_nb)
                r, c = nr + adv_r, nc + adv_c
            else:
                self._river_tile(r, c, r_tile)
                nr, nc = r + r_dr, c + r_dc
                self._river_tile(nr, nc, r_nb)
                r, c = nr + adv_r, nc + adv_c

    def _river_tile(self, r, c, edges):
        if not (0 <= r < self._map.rows and 0 <= c < self._map.cols):
            return
        t = self._map.tiles[r][c]
        t.river_edges.update(edges)
        if 'river' not in t.terrain_features and 'mountain' not in t.terrain_features:
            t.terrain_features = list(t.terrain_features) + ['river']
            t.update_terrain_properties()
            t.build_deposits()
