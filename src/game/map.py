import heapq
import random
from src.game.city import City
from src.game.constants import DEFAULT_MOVE_DISTANCE, BASE_TERRAIN_COST, DIFFICULT_TERRAIN_COST, MIN_TERRAIN_COST, LAND_CARRY_CAPACITY, WATER_CARRY_CAPACITY
from src.game.tile import Tile
from src.game.unit_group import UnitGroup
from src.game.unit import Unit
from src.game.pop import Pop

GRID_COLS = 24
GRID_ROWS = 24

MAP_CONFIG = {
    'rows': 16,
    'cols': 16,
}

#MOVE_COSTS = {'desert': 1.0, 'hills': 1.5, 'forest': 1.5, 'with_river': 1.0, 'cross_river': 2.0}
MOVE_COSTS = {'desert': BASE_TERRAIN_COST, 'hills': DIFFICULT_TERRAIN_COST, 'forest': DIFFICULT_TERRAIN_COST, 'with_river': BASE_TERRAIN_COST, 'cross_river': DIFFICULT_TERRAIN_COST}

IMPASSABLE_TERRAINS = {'mountain'}
TERRAIN_TYPES = ['desert', 'hills', 'forest', 'river', 'mountain']

# Neighbor offsets (dr, dc) for 8-directional square grid.
_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

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

    @classmethod
    def make_plains(cls, rows=13, cols=11):
        """Create a blank map filled with temperate non-water plains tiles."""
        m = cls.__new__(cls)
        m.rows = rows
        m.cols = cols
        m.tiles = []
        for r in range(rows):
            row = []
            for c in range(cols):
                t = Tile(r, c, '', biome='temperate', terrain_features=[])
                t.update_terrain_properties()
                row.append(t)
            m.tiles.append(row)
        m._city_name_idx = 0
        m.cities = {}
        return m

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

    def _step_cost(self, from_r, from_c, to_r, to_c, scheme):
        from_tile = self.tiles[from_r][from_c]
        to_tile = self.tiles[to_r][to_c]
        if scheme == 'water':
            return BASE_TERRAIN_COST
        if abs(to_r - from_r) == 1 and abs(to_c - from_c) == 1:
            return to_tile.diagonal_movement_cost
        from_river = 'river' in from_tile.terrain_features
        to_river = 'river' in to_tile.terrain_features
        if from_river and to_river:
            if scheme == 'supply':
                return BASE_TERRAIN_COST * LAND_CARRY_CAPACITY / WATER_CARRY_CAPACITY
            return MOVE_COSTS['with_river']
        return to_tile.movement_cost

    def _tile_passable(self, r, c, scheme):
        tile = self.tiles[r][c]
        if scheme in ('land', 'supply'): return tile.passable and not tile.water
        if scheme == 'water': return tile.water or tile.water_access or 'river' in tile.terrain_features
        return tile.passable  # 'any': blocks mountains, crosses water freely

    def get_reachable_from(self, start_r, start_c, budget, scheme='land', blocked=None, include_start=False):
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
            for dr, dc in _NEIGHBORS:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._tile_passable(nr, nc, scheme):
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc, scheme)
                if new_cost <= budget and new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    if (nr, nc) not in blocked:
                        heapq.heappush(queue, (new_cost, (nr, nc)))
        if not include_start:
            del best[start]
        return best

    def path_distances(self, path, scheme):
        """Recompute cumulative distances along an existing path using the given scheme."""
        if not path:
            return []
        dists = [0.0]
        for i in range(1, len(path)):
            fr, fc = path[i - 1]
            tr, tc = path[i]
            dists.append(dists[-1] + self._step_cost(fr, fc, tr, tc, scheme))
        return dists

    def get_path_to(self, from_r, from_c, to_r, to_c, scheme='land'):
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
            for dr, dc in _NEIGHBORS:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if not self._tile_passable(nr, nc, scheme):
                    continue
                new_cost = cost + self._step_cost(r, c, nr, nc, scheme)
                if new_cost < best.get((nr, nc), float('inf')):
                    best[(nr, nc)] = new_cost
                    prev[(nr, nc)] = (r, c)
                    heapq.heappush(queue, (new_cost, (nr, nc)))
        return [], []

    def reassign_tile_owner(self, tile, new_city):
        """Move a tile from its current owning city to new_city and refresh both."""
        old_city = tile.owning_city
        if old_city is new_city:
            return
        if old_city is not None and tile in old_city.owned_tiles:
            old_city.owned_tiles.remove(tile)
        tile.owning_city = new_city
        if new_city is not None:
            _, distances = self.get_path_to(new_city.row, new_city.col, tile.row, tile.col, scheme='any')
            tile.city_distance = distances[-1] if distances else None
            if tile not in new_city.owned_tiles:
                new_city.owned_tiles.append(tile)
            new_city.refresh_owned_tile_jobs()
        else:
            tile.city_distance = None
        if old_city is not None:
            old_city.refresh_owned_tile_jobs()

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
        city_range = self.get_reachable_from(city.row, city.col, DEFAULT_MOVE_DISTANCE, scheme='any', include_start=True)
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
        # Minimal tether teardown: don't create replacement routes from a dying city
        for row in self.tiles:
            for tile in row:
                for group in tile.unit_groups:
                    if group.tether is not None and group.tether.city is city:
                        tether = group.tether
                        if tether.route is not None:
                            tether.route.detach()
                            tether.route = None
                        tether.tether_units.clear()
                        group.tether = None
        # Detach routes before clearing city_tile.city so detach() can still
        # resolve dest_tile.city correctly for routes where this is the destination.
        # Tether routes originating from another city are migrated to the tile
        # rather than detached, so they continue supplying the unit group.
        city_tile = self.tiles[city.row][city.col]
        for route in list(city.trade_routes):
            if route.tether and route.city_a is not city:
                city.trade_routes.remove(route)
                city_tile.trade_routes.append(route)
            else:
                route.detach()
        for tile in city.owned_tiles:
            tile.owning_city = None
            tile.city_distance = None
        for row in self.tiles:
            for tile in row:
                if city in tile.cities_in_range:
                    tile.cities_in_range.remove(city)
        city_tile.terrain_features = [f for f in city_tile.terrain_features if f not in ('city', 'water_access')]
        city_tile.update_terrain_properties()
        city_tile.city = None
        city.tile = None
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
            for dr, dc in _NEIGHBORS
            if 0 <= city.row + dr < self.rows and 0 <= city.col + dc < self.cols
        )
        if has_water_neighbor and 'water_access' not in features:
            features.append('water_access')
        city_tile.update_terrain_properties()

    def setup_city(self, city):
        city_tile = self.tiles[city.row][city.col]
        city_tile.city = city
        city.tile = city_tile
        self._apply_city_tile_features(city)
        city_range = self.get_reachable_from(city.row, city.col, DEFAULT_MOVE_DISTANCE, scheme='any', include_start=True)
        city.owned_tiles = []
        for (r, c), cost in city_range.items():
            tile = self.tiles[r][c]
            tile.cities_in_range.append(city)
            if tile.owning_city is None:
                tile.owning_city = city
                tile.city_distance = cost
                city.owned_tiles.append(tile)
        city.unit_groups = list(city_tile.unit_groups)
        for route in list(city_tile.trade_routes):
            city_tile.trade_routes.remove(route)
            city.trade_routes.append(route)
        city.update_cumulative_farm_yield_net()
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
        group.update_tether_after_movement(self, src_tile, dst_tile)
        dst_tile.update_after_movement()
        # print('Calling dst tile after movement')

    def plunder_routes(self, tile, raiding_faction):
        """Detach enemy trade routes whose visual path crosses tile.

        Returns a dict of {resource: total_amount} plundered across all hit routes.
        """
        target = (tile.row, tile.col)
        seen = set()
        plunder = {}
        for city in self.cities.values():
            for route in city.trade_routes:
                if id(route) in seen:
                    continue
                seen.add(id(route))
                if route.faction is raiding_faction:
                    continue
                if target in route.get_visual_path():
                    for resource, amount in route.get_plunder_resources().items():
                        plunder[resource] = plunder.get(resource, 0.0) + amount
                    route.detach(rebalance=True)
        return plunder

    def to_dict(self):
        return {
            'tiles': [
                [{'biome': t.biome, 'terrain_features': list(t.terrain_features), 'river_edges': list(t.river_edges)} for t in row]
                for row in self.tiles
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
                    if edge in {'N', 'S', 'E', 'W'}:
                        t.river_edges.add(edge)
                t.update_terrain_properties()
                row.append(t)
            m.tiles.append(row)
        m._city_name_idx = 0
        m.cities = {}
        return m
