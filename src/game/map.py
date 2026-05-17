import heapq
import random
from src.game.city import City
from src.game.constants import DEFAULT_MOVE_DISTANCE, BASE_TERRAIN_COST, DIFFICULT_TERRAIN_COST, MIN_TERRAIN_COST
from src.game.tile import Tile
from src.game.unit_group import UnitGroup
from src.game.unit import Unit
from src.game.pop import Pop

GRID_COLS = 16
GRID_ROWS = 16

MAP_CONFIG = {
    'rows': 16,
    'cols': 16,
}

#MOVE_COSTS = {'desert': 1.0, 'hills': 1.5, 'forest': 1.5, 'with_river': 1.0, 'cross_river': 2.0}
MOVE_COSTS = {'desert': BASE_TERRAIN_COST, 'hills': DIFFICULT_TERRAIN_COST, 'forest': DIFFICULT_TERRAIN_COST, 'with_river': BASE_TERRAIN_COST, 'cross_river': DIFFICULT_TERRAIN_COST}

IMPASSABLE_TERRAINS = {'mountain'}
TERRAIN_TYPES = ['desert', 'hills', 'forest', 'river', 'mountain']

# Neighbor offsets (dr, dc) for odd-r offset hex grid, keyed by row parity.
_NEIGHBORS = {
    0: [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)],
    1: [(-1,  0), (-1, 1), (0, -1), (0, 1), (1,  0), (1, 1)],
}

_TERRAIN_MIGRATION = {'plains': 'desert'}

CITY_NAMES = [
    'Babylon', 'Nippur', 'Kish', 'Sippar', 'Uruk', 'Ur', 'Lagash',
    'Eridu', 'Akkad', 'Adab', 'Umma', 'Girsu', 'Eshnunna', 'Isin',
    'Larsa', 'Mari', 'Assur', 'Nineveh', 'Calah', 'Dur-Kurigalzu',
]


class Map:
    def __init__(self):
        self.rows = MAP_CONFIG['rows']
        self.cols = MAP_CONFIG['cols']
        self.tiles = [
            [
                self._make_empty_tile(r, c)
                for c in range(self.cols)
            ]
            for r in range(self.rows)
        ]
        self._city_name_idx = 0
        self.cities = {}

    @staticmethod
    def _make_empty_tile(r, c):
        t = Tile(r, c, '', biome='coastal', terrain_features=['water'])
        t.update_terrain_properties()
        return t

    @property
    def unit_groups(self):
        result = {}
        for row in self.tiles:
            for tile in row:
                if tile.unit_groups:
                    result[(tile.row, tile.col)] = tile.unit_groups
        return result

    def _take_city_name(self):
        name = CITY_NAMES[self._city_name_idx % len(CITY_NAMES)]
        self._city_name_idx += 1
        return name

    def get_unit_groups(self, row, col):
        return self.tiles[row][col].unit_groups

    def get_unit_group(self, row, col):
        unit_groups = self.tiles[row][col].unit_groups
        return unit_groups[0] if unit_groups else None

    def _step_cost(self, from_r, from_c, to_r, to_c):
        from_tile = self.tiles[from_r][from_c]
        to_tile = self.tiles[to_r][to_c]
        from_river = 'river' in from_tile.terrain_features
        to_river = 'river' in to_tile.terrain_features
        no_city = 'city' not in from_tile.terrain_features and 'city' not in to_tile.terrain_features
        if no_city and from_river and to_river:
            return MOVE_COSTS['with_river']
        elif no_city and from_river:
            return MOVE_COSTS['cross_river'] / 2 + to_tile.movement_cost / 2
        elif no_city and to_river:
            return from_tile.movement_cost / 2 + MOVE_COSTS['cross_river'] / 2
        return from_tile.movement_cost / 2 + to_tile.movement_cost / 2

    def _tile_passable(self, r, c, mode):
        tile = self.tiles[r][c]
        if mode == 'land':  return tile.passable and not tile.water
        if mode == 'water': return tile.water
        return tile.passable  # 'any': blocks mountains, crosses water freely

    def get_reachable_from(self, start_r, start_c, budget, mode='land', blocked=None, include_start=False):
        """Bounded Dijkstra. Returns {(row, col): cost} for all tiles reachable within budget.
        blocked tiles count as destinations but are not pathed through.
        include_start controls whether the origin tile is in the result."""
        blocked = blocked or set()
        start = (start_r, start_c)
        best = {start: 0}
        queue = [(0, start)]
        while queue:
            cost, (r, c) = heapq.heappop(queue)
            if cost > best[(r, c)]:
                continue
            for dr, dc in _NEIGHBORS[r % 2]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._tile_passable(nr, nc, mode):
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost <= budget and new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    if (nr, nc) not in blocked:
                        heapq.heappush(queue, (new_cost, (nr, nc)))
        if not include_start:
            del best[start]
        return best

    def get_path_to(self, from_r, from_c, to_r, to_c, mode='land'):
        """Unbounded Dijkstra from start to goal. Returns (path, distances) where path is a list of
        (r, c) tiles inclusive and distances[i] is the cumulative cost to path[i], or ([], []).
        Travel cost between two points is distances[-1] if path else None."""
        goal = (to_r, to_c)
        start = (from_r, from_c)
        best = {start: 0}
        prev = {start: None}
        queue = [(0, start)]
        while queue:
            cost, (r, c) = heapq.heappop(queue)
            if (r, c) == goal:
                path, node = [], goal
                while node is not None:
                    path.append(node)
                    node = prev[node]
                path.reverse()
                return path, [best[n] for n in path]
            if cost > best[(r, c)]:
                continue
            for dr, dc in _NEIGHBORS[r % 2]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._tile_passable(nr, nc, mode):
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    prev[(nr, nc)] = (r, c)
                    heapq.heappush(queue, (new_cost, (nr, nc)))
        return [], []

    def recalculate_city_tiles(self, city):
        for tile in city.owned_tiles:
            tile.owning_city = None
            tile.city_distance = None
        for row in self.tiles:
            for tile in row:
                if city in tile.cities_in_range:
                    tile.cities_in_range.remove(city)
        self._apply_city_tile_features(city)
        city.owned_tiles = []
        city_range = self.get_reachable_from(city.row, city.col, DEFAULT_MOVE_DISTANCE, mode='any', include_start=True)
        for (r, c), cost in city_range.items():
            tile = self.tiles[r][c]
            tile.cities_in_range.append(city)
            if tile.owning_city is None:
                tile.owning_city = city
                tile.city_distance = cost
                city.owned_tiles.append(tile)
        city._build_cumulative_farm_yield()
        city.update_cumulative_farm_yield_net()
        city.rebalance_pops()

    def remove_city(self, city):
        for tile in city.owned_tiles:
            tile.owning_city = None
            tile.city_distance = None
        for row in self.tiles:
            for tile in row:
                if city in tile.cities_in_range:
                    tile.cities_in_range.remove(city)
        city_tile = self.tiles[city.row][city.col]
        city_tile.terrain_features = [f for f in city_tile.terrain_features if f not in ('city', 'water_access')]
        city_tile.update_terrain_properties()
        city_tile.city = None
        del self.cities[(city.row, city.col)]

    def _apply_city_tile_features(self, city):
        city_tile = self.tiles[city.row][city.col]
        features = city_tile.terrain_features
        if 'city' not in features:
            features.append('city')
        water_adjacent = {'river', 'water'}
        has_water_neighbor = any(
            'river' in self.tiles[city.row + dr][city.col + dc].terrain_features or
            'water' in self.tiles[city.row + dr][city.col + dc].terrain_features
            for dr, dc in _NEIGHBORS[city.row % 2]
            if 0 <= city.row + dr < self.rows and 0 <= city.col + dc < self.cols
        )
        if has_water_neighbor and 'water_access' not in features:
            features.append('water_access')
        city_tile.update_terrain_properties()

    def setup_city(self, city):
        city_tile = self.tiles[city.row][city.col]
        city_tile.city = city
        self._apply_city_tile_features(city)
        city_range = self.get_reachable_from(city.row, city.col, DEFAULT_MOVE_DISTANCE, mode='any', include_start=True)
        city.owned_tiles = []
        for (r, c), cost in city_range.items():
            tile = self.tiles[r][c]
            tile.cities_in_range.append(city)
            if tile.owning_city is None:
                tile.owning_city = city
                tile.city_distance = cost
                city.owned_tiles.append(tile)
        city.unit_groups = list(city_tile.unit_groups)
        city.setup_jobs()

    def move_group(self, group, row, col, cost):
        src_tile = self.tiles[group.row][group.col]
        dst_tile = self.tiles[row][col]
        src_tile.unit_groups.remove(group)
        group.row = row
        group.col = col
        group.moves_remaining -= cost
        if group.moves_remaining < MIN_TERRAIN_COST:
            group.move_exhausted = True
        dst_tile.unit_groups.append(group)
        group.reset_after_movement()
        src_tile.update_after_movement()
        dst_tile.update_after_movement()
        # print('Calling dst tile after movement')

    def to_dict(self):
        return {
            'tiles': [
                [{'biome': t.biome, 'terrain_features': list(t.terrain_features), 'river_edges': list(t.river_edges)} for t in row]
                for row in self.tiles
            ],
            'unit_groups': [
                {
                    'row': u.row, 'col': u.col, 'unit_type': u.unit_type,
                    'max_moves': u.max_moves, 'moves_remaining': u.moves_remaining,
                }
                for u in self.unit_groups.values()
            ],
            'cities': [
                {'row': c.row, 'col': c.col, 'name': c.name}
                for c in self.cities.values()
            ],
        }

    @classmethod
    def from_dict(cls, data):
        m = cls.__new__(cls)
        rows_data = data['tiles']
        m.rows = len(rows_data)
        m.cols = len(rows_data[0])
        m.tiles = []
        for r in range(m.rows):
            row = []
            for c in range(m.cols):
                cell = rows_data[r][c]
                if isinstance(cell, str):
                    cell = {'terrain': cell}
                biome = cell.get('biome', 'coastal')
                terrain_features = cell.get('terrain_features', ['water'])
                t = Tile(r, c, '', biome=biome, terrain_features=terrain_features)
                for edge in cell.get('river_edges', []):
                    t.river_edges.add(edge)
                t.update_terrain_properties()
                row.append(t)
            m.tiles.append(row)
        m._city_name_idx = 0
        m.cities = {}
        return m
