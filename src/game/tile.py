import random
from src.game.constants import BASE_TERRAIN_COST, DIFFICULT_TERRAIN_COST, DEFAULT_MOVE_DISTANCE
from src.game.jobs import FarmJob

# Yield per assigned pop at each distance increment (fill in from LP results later)
# FARM_YIELD_BY_DISTANCE = {
#     0.00: 1.40,
#     0.25: 1.39,
#     0.50: 1.37,
#     0.75: 1.36,
#     1.00: 1.36,
#     1.25: 1.34,
#     1.50: 1.33,
#     1.75: 1.33,
#     2.00: 1.32,
#     2.25: 1.30,
#     2.50: 1.30,
#     2.75: 1.29,
#     3.00: 1.28,
# }
# FARM_YIELD_BY_DISTANCE = {
#     0.00: 1.40,
#     0.50: 1.39,
#     1.00: 1.37,
#     1.50: 1.36,
#     2.00: 1.34,
#     2.50: 1.33,
#     3.00: 1.33,
#     3.50: 1.32,
#     4.00: 1.30,
#     4.50: 1.29,
#     5.00: 1.28,
# }

FARM_YIELD_AT_MAX_DISTANCE = 1.3
# Derived: (YIELD_PER_POP - FARM_YIELD_AT_MAX_DISTANCE) / DEFAULT_MOVE_DISTANCE

EXTRACTION_YIELD_BASE = 1.0
EXTRACTION_YIELD_AT_MAX_DISTANCE = 0.80

TILE_FARM_SLOTS = {
    'river':    6,
    'hills':    3,
    'desert':   0,
    'forest':   2,
    'mountain': 0,
}
DEPOSIT_STARTING_WOOD = 40
DEPOSIT_STARTING_IRON = 20

BIOMES = ['temperate',
        'arid',
        'badlands',
        'tropical',
        'taiga',
        'tundra',
        'desert',
        'ice',
        'wetlands',
        'coastal',
        'ocean']

TERRAIN_FEATURES = ['hills',
                    'forest',
                    'river',
                    'floodplain',
                    'mountain',
                    'water',
                    'city',
                    'water_access']

BIOME_FARM_SLOTS = {'temperate': 4,
        'arid': 3,
        'badlands': 3,
        'tropical': 3,
        'taiga': 2,
        'tundra': 1,
        'desert': 0,
        'ice': 0,
        'wetlands': 1,
        'coastal': 1,
        'ocean': 0}

TERRAIN_FEATURE_FARM_SLOTS = {
    'hills': -1,
    'forest': -2,
    'floodplain': 1,
    'river': -1,
    'mountains': -5
}

BIOME_FEATURE_FARM_INTERACTIONS = {
    ('tropical', 'forest'): 1,
    ('arid', 'hills'): 1,
}

BIOME_COLORS = {
    'temperate': (105, 168,  88),
    'arid':      (165, 135,  80),
    'badlands':  (155,  70,  40),
    'tropical':  ( 75, 160,  80),
    'taiga':     ( 80, 120,  95),
    'tundra':    (148, 152, 130),
    'desert':    (200, 175, 115),
    'ice':       (195, 215, 230),
    'wetlands':  (110, 140, 100),
    'coastal':   (100, 150, 175),
    'ocean':     ( 55,  95, 155),
}

_MOUNTAIN_COLOR = (140, 140, 140)


class Tile:
    def __init__(self, row, col, terrain, biome='coastal', terrain_features=['water']):
        self.row = row
        self.col = col
        self.terrain = terrain  # 'desert', 'hills', 'river'
        self.biome = biome
        self.terrain_features = terrain_features
        self.river_edges = set()  # subset of {'NW','NE','E','SE','SW','W'}
        self.unit_groups = []
        self.city = None
        self.owning_city = None
        self.trade_routes = []
        self.city_distance = None
        self.cities_in_range = []
        self.raided = False
        self._raided_ticker = 0
        self.restricted = False
        self._restricted_ticker = 0
        self.movement_cost = BASE_TERRAIN_COST
        self.passable = True
        self.water = 'water' in self.terrain_features
        self.water_access = 'water_access' in self.terrain_features
        self.jobs = []
        self.current_extraction_job = None
        self.update_terrain_properties()
        self.food_allocated_from_routes = 0.0
        self.resource_stockpiles = {}
        self.resource_deposits = {}
        self.build_deposits()

    @property
    def worked_farms(self):
        farm_job = next((j for j in self.jobs if j.job_type == 'farm'), None)
        return farm_job.assigned if farm_job else 0

    @property
    def farm_yield(self):
        if self.city_distance is None:
            return FarmJob.YIELD_PER_POP
        decay_rate = (FarmJob.YIELD_PER_POP - FARM_YIELD_AT_MAX_DISTANCE) / DEFAULT_MOVE_DISTANCE
        return max(FARM_YIELD_AT_MAX_DISTANCE, FarmJob.YIELD_PER_POP - decay_rate * self.city_distance)

    @property
    def extraction_yield(self):
        if self.city_distance is None:
            return EXTRACTION_YIELD_BASE
        decay_rate = (EXTRACTION_YIELD_BASE - EXTRACTION_YIELD_AT_MAX_DISTANCE) / DEFAULT_MOVE_DISTANCE
        return max(EXTRACTION_YIELD_AT_MAX_DISTANCE, EXTRACTION_YIELD_BASE - decay_rate * self.city_distance)

    def _update_city_with_movement(self):
        if self.city is not None:
            self.city.unit_groups = list(self.unit_groups)
            if self.unit_groups:
                moving_faction = self.unit_groups[0].faction
                if moving_faction is not None and moving_faction is not self.city.faction:
                    self.city.change_faction(moving_faction)
            self.city._build_cumulative_farm_yield()
            self.city.update_cumulative_farm_yield_net()
            self.city.rebalance_pops()

    def set_extraction_job(self, resource):
        # print(f"[extraction] tile=({self.row},{self.col}) set_extraction_job: {resource}")
        self.current_extraction_job = resource

    def clear_extraction_job(self):
        # print(f"[extraction] tile=({self.row},{self.col}) clear_extraction_job (was: {self.current_extraction_job})")
        self.current_extraction_job = None

    def build_deposits(self):
        features = self.terrain_features
        if 'forest' in features:
            self.resource_deposits.setdefault('wood', DEPOSIT_STARTING_WOOD)
        elif 'hills' in features:
            self.resource_deposits.setdefault('iron', DEPOSIT_STARTING_IRON)

    _ART_PRIORITY = ['river', 'mountain', 'forest', 'hills', 'water']

    def get_terrain_color(self):
        if 'mountain' in self.terrain_features:
            return _MOUNTAIN_COLOR
        return BIOME_COLORS.get(self.biome, (150, 150, 150))

    def get_terrain_art(self):
        if self.biome == 'wetlands':
            return 'marsh'
        for feature in self._ART_PRIORITY:
            if feature in self.terrain_features:
                return feature
        if self.biome == 'desert':
            return 'desert'
        return 'grass'

    def update_terrain_properties(self):
        difficult = {'hills', 'forest'}
        if 'city' in self.terrain_features:
            self.movement_cost = BASE_TERRAIN_COST
        elif any(f in difficult for f in self.terrain_features) or self.biome == 'wetlands':
            self.movement_cost = DIFFICULT_TERRAIN_COST
        else:
            self.movement_cost = BASE_TERRAIN_COST
        self.passable = 'mountain' not in self.terrain_features
        self.water = 'water' in self.terrain_features
        self.water_access = 'water_access' in self.terrain_features
        if self.raided or self.restricted:
            self.jobs = []
            return
        base_slots = BIOME_FARM_SLOTS.get(self.biome, 0)
        feature_slots = sum(TERRAIN_FEATURE_FARM_SLOTS.get(f, 0) for f in self.terrain_features)
        bonuses = sum(BIOME_FEATURE_FARM_INTERACTIONS.get((self.biome, f), 0) for f in self.terrain_features)
        slots = max(0, base_slots + feature_slots + bonuses)
        self.jobs = [FarmJob(slots)] if slots > 0 else []

    def extraction(self, production_yield, resource):
        available = self.resource_deposits.get(resource, 0)
        extracted_amount = min(production_yield, available)
        remaining = available - extracted_amount
        if remaining <= 0:
            self.resource_deposits.pop(resource, None)
            if resource == 'wood' and 'forest' in self.terrain_features:
                self.terrain_features = [f for f in self.terrain_features if f != 'forest']
                self.update_terrain_properties()
                if self.owning_city:
                    self.owning_city._build_cumulative_farm_yield()
                    self.owning_city.update_cumulative_farm_yield_net()
                    self.owning_city.rebalance_pops()
            if self.owning_city:
                self.owning_city.check_additional_resources(resource)
        else:
            self.resource_deposits[resource] = remaining
        return extracted_amount

    def add_resources_to_stockpile(self, extracted_amount, resource):
        self.resource_stockpiles[resource] = self.resource_stockpiles.get(resource, 0) + extracted_amount

    def raid(self, num_units):
        """Raid worked farms on this tile.

        Returns dict with:
          raided_farms   -- number of farms raided
          food_gained    -- food to distribute to attacking units
          captured_pops  -- Pop objects removed from the defending city
        """
        result = {'raided_farms': 0, 'food_gained': 0.0, 'captured_pops': []}
        city = self.owning_city
        if not city or self.worked_farms == 0:
            return result

        raided_farms = min(num_units, self.worked_farms)
        result['raided_farms'] = raided_farms
        result['food_gained'] = raided_farms * self.farm_yield
        self.raided = True
        self._raided_ticker = 5
        self.jobs = []
        city.rebalance_pops()

        captured_count = sum(1 for _ in range(raided_farms) if random.random() < 0.5)
        if captured_count > 0:
            # Prefer pops already assigned to farm jobs on this tile
            farm_pops = [p for p in city.pops if p.assigned_job in self.jobs]
            other_pops = [p for p in city.pops if p.assigned_job not in self.jobs]
            to_capture = (farm_pops + other_pops)[:captured_count]
            for pop in to_capture:
                city.pops.remove(pop)
                pop.assigned_job = None
            if to_capture:
                city.rebalance_pops()
            result['captured_pops'] = to_capture

        return result

    @property
    def is_disrupted(self):
        return self.raided or self.restricted

    def has_active_tickers(self):
        return self._raided_ticker > 0 or self._restricted_ticker > 0

    def update_tickers(self):
        if self._raided_ticker > 0:
            self._raided_ticker -= 1
            if self._raided_ticker == 0:
                self.raided = False
                self.update_terrain_properties()
                city = self.owning_city
                if city is not None:
                    city._build_cumulative_farm_yield()
                    city.update_cumulative_farm_yield_net()
                    city.rebalance_pops()
        if self._restricted_ticker > 0:
            self._restricted_ticker -= 1

    def can_be_captured(self, faction):
        return any(c.faction is faction for c in self.cities_in_range)

    def update_after_movement(self):
        self._update_city_with_movement()
        self.update_unit_allocations()
        for group in self.unit_groups:
            result = self.can_be_captured(group.faction)
            # print(f"[capture check] tile=({self.row},{self.col}) city={self.city.name if self.city else None} city_faction={self.city.faction.name if self.city and self.city.faction else None} group_faction={group.faction.name if group.faction else None} -> {result}")
            group.can_capture_tile = result
        # TO DO: update unit groups allocations

    def _food_from_routes(self):
        return sum(
            r.max_amount for r in self.trade_routes
            if r.established and not r.missing_caravans and r.export_resource == 'food'
        )

    def update_unit_allocations(self):
        # print('Updating unit allocations')
        remaining = self._food_from_routes()
        self.food_allocated_from_routes = 0.0
        for g in self.unit_groups:
            allocated = g.allocate_food(food_from_routes=remaining)
            # print('Allocated:', allocated)
            self.food_allocated_from_routes += allocated
            remaining = max(0.0, remaining - allocated)
        # print('Food allocated from routes:', self.food_allocated_from_routes)

        # Later on will need to handle the leftover food
