import heapq
import random
from src.game.city import City
from src.game.constants import DEFAULT_MOVE_DISTANCE, BASE_TERRAIN_COST, DIFFICULT_TERRAIN_COST, MIN_TERRAIN_COST
from src.game.tile import Tile
from src.game.group import Group
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
    def groups(self):
        result = {}
        for row in self.tiles:
            for tile in row:
                if tile.groups:
                    result[(tile.row, tile.col)] = tile.groups
        return result

    def _take_city_name(self):
        name = CITY_NAMES[self._city_name_idx % len(CITY_NAMES)]
        self._city_name_idx += 1
        return name

    def get_groups(self, row, col):
        return self.tiles[row][col].groups

    def get_group(self, row, col):
        groups = self.tiles[row][col].groups
        return groups[0] if groups else None

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

    def get_reachable_budget(self, row, col, budget):
        """Dijkstra from (row, col) with a fixed move budget. Returns {(row, col): cost}."""
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
        self.tiles[group.row][group.col].groups.remove(group)
        group.row = row
        group.col = col
        group.moves_remaining -= cost
        if group.moves_remaining < MIN_TERRAIN_COST:
            group.move_exhausted = True
        self.tiles[row][col].groups.append(group)

    def to_dict(self):
        return {
            'tiles': [
                [{'terrain': t.terrain, 'river_edges': list(t.river_edges)} for t in row]
                for row in self.tiles
            ],
            'groups': [
                {
                    'row': u.row, 'col': u.col, 'unit_type': u.unit_type,
                    'max_moves': u.max_moves, 'moves_remaining': u.moves_remaining,
                }
                for u in self.groups.values()
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
        group_a = Group(5, 5, units=[Unit(Pop()) for _ in range(3)])
        group_a.add_food(12.0)
        group_b = Group(5, 5, units=[Unit(Pop()) for _ in range(2)])
        group_b.add_food(3.0)
        m.tiles[5][5].groups = [group_a, group_b]
        m._city_name_idx = 0
        m.cities = {(7, 2): City(7, 2, m._take_city_name()),
            (3, 6): City(3, 6, m._take_city_name()),
            (9, 4): City(9, 4, m._take_city_name())}
        for city in m.cities.values():
            m.setup_city(city)
        # m.groups = {}
        # for ud in data['groups']:
        #     u = Group(ud['row'], ud['col'], ud['unit_type'])
        #     u.max_moves = ud['max_moves']
        #     u.moves_remaining = ud['moves_remaining']
        #     m.groups[(u.row, u.col)] = u
        # m.cities = {}
        # for cd in data.get('cities', []):
        #     city = City(cd['row'], cd['col'], cd['name'])
        #     m.cities[(city.row, city.col)] = city
        return m
