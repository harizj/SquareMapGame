import heapq
import random
from src.game.city import City
from src.game.constants import DEFAULT_MOVE_DISTANCE, BASE_TERRAIN_COST, DIFFICULT_TERRAIN_COST, MIN_TERRAIN_COST
from src.game.tile import Tile
from src.game.unit_group import UnitGroup
from src.game.unit import Unit
from src.game.pop import Pop

GRID_COLS = 14
GRID_ROWS = 14

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
        self.cols = GRID_COLS
        self.rows = GRID_ROWS
        half_r = self.rows // 2
        self.tiles = [
            [
                Tile(r, c, 'hills' if r >= half_r and random.random() < 0.25 else 'desert')
                for c in range(GRID_COLS)
            ]
            for r in range(GRID_ROWS)
        ]
        self._city_name_idx = 0
        self.cities = {(4, 4): City(4, 4, self._take_city_name())}
        for city in self.cities.values():
            self.setup_city(city)

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
        from_terrain = self.tiles[from_r][from_c].terrain
        to_terrain = self.tiles[to_r][to_c].terrain
        if from_terrain == 'river' and to_terrain == 'river':
            return MOVE_COSTS['with_river']
        elif from_terrain == 'river':
            return MOVE_COSTS['cross_river'] / 2 + MOVE_COSTS[to_terrain] / 2
        elif to_terrain == 'river':
            return MOVE_COSTS[from_terrain] / 2 + MOVE_COSTS['cross_river'] / 2
        return MOVE_COSTS[from_terrain] / 2 + MOVE_COSTS[to_terrain] / 2

    def get_reachable(self, group):
        """Dijkstra from group position. Returns {(row, col): cost} for all reachable tiles."""
        start = (group.row, group.col)
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
                if self.tiles[nr][nc].terrain in IMPASSABLE_TERRAINS:
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost <= group.moves_remaining and new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    heapq.heappush(queue, (new_cost, (nr, nc)))
        del best[start]
        return best

    def get_reachable_budget(self, row, col, budget, blocked=None):
        """Dijkstra from (row, col) with a fixed move budget. Returns {(row, col): cost}.
        blocked is a set of (row, col) tiles that can be reached as destinations but not
        pathed through (e.g. enemy-occupied tiles)."""
        blocked = blocked or set()
        start = (row, col)
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
                if self.tiles[nr][nc].terrain in IMPASSABLE_TERRAINS:
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost <= budget and new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    if (nr, nc) not in blocked:
                        heapq.heappush(queue, (new_cost, (nr, nc)))
        del best[start]
        return best

    def get_city_range(self, city):
        """Dijkstra from city position. Returns {(row, col): cost} for all tiles within range, including city tile."""
        start = (city.row, city.col)
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
                if self.tiles[nr][nc].terrain in IMPASSABLE_TERRAINS:
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost <= DEFAULT_MOVE_DISTANCE and new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    heapq.heappush(queue, (new_cost, (nr, nc)))
        return best

    def _is_passable(self, r, c, water=False):
        terrain = self.tiles[r][c].terrain
        if water:
            return terrain == 'river'
        return terrain not in IMPASSABLE_TERRAINS

    def get_travel_cost(self, from_r, from_c, to_r, to_c, water=False):
        """Uncapped Dijkstra between two tiles. Returns movement cost or None if unreachable."""
        goal = (to_r, to_c)
        start = (from_r, from_c)
        best = {start: 0}
        queue = [(0, start)]
        while queue:
            cost, (r, c) = heapq.heappop(queue)
            if (r, c) == goal:
                return cost
            if cost > best[(r, c)]:
                continue
            for dr, dc in _NEIGHBORS[r % 2]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._is_passable(nr, nc, water):
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc)
                if new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    heapq.heappush(queue, (new_cost, (nr, nc)))
        return None

    def get_path(self, from_r, from_c, to_r, to_c, water=False):
        """Dijkstra from start to goal. Returns (path, path_distances) where path is a list of
        (r, c) tiles inclusive and path_distances[i] is the cumulative cost to path[i], or ([], [])."""
        goal = (to_r, to_c)
        start = (from_r, from_c)
        best = {start: 0}
        prev = {start: None}
        queue = [(0, start)]
        while queue:
            cost, (r, c) = heapq.heappop(queue)
            if (r, c) == goal:
                path = []
                node = goal
                while node is not None:
                    path.append(node)
                    node = prev[node]
                path.reverse()
                path_distances = [best[node] for node in path]
                return path, path_distances
            if cost > best[(r, c)]:
                continue
            for dr, dc in _NEIGHBORS[r % 2]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._is_passable(nr, nc, water):
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
        city.owned_tiles = []
        city_range = self.get_city_range(city)
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
        self.tiles[city.row][city.col].city = None
        del self.cities[(city.row, city.col)]

    def setup_city(self, city):
        city_range = self.get_city_range(city)
        city.owned_tiles = []
        for (r, c), cost in city_range.items():
            tile = self.tiles[r][c]
            tile.cities_in_range.append(city)
            if tile.owning_city is None:
                tile.owning_city = city
                tile.city_distance = cost
                city.owned_tiles.append(tile)
        self.tiles[city.row][city.col].city = city
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
        print('Calling dst tile after movement')

    def to_dict(self):
        return {
            'tiles': [
                [{'terrain': t.terrain, 'river_edges': list(t.river_edges)} for t in row]
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
                    terrain = _TERRAIN_MIGRATION.get(cell, cell)
                    t = Tile(r, c, terrain)
                else:
                    terrain = _TERRAIN_MIGRATION.get(cell['terrain'], cell['terrain'])
                    t = Tile(r, c, terrain)
                    for edge in cell.get('river_edges', []):
                        t.river_edges.add(edge)
                row.append(t)
            m.tiles.append(row)
        m._city_name_idx = 0
        m.cities = {}
        return m
