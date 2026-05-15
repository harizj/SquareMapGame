import random
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
FARM_YIELD_BY_DISTANCE = {
    0.00: 1.40,
    0.50: 1.39,
    1.00: 1.37,
    1.50: 1.36,
    2.00: 1.34,
    2.50: 1.33,
    3.00: 1.33,
    3.50: 1.32,
    4.00: 1.30,
    4.50: 1.29,
    5.00: 1.28,
}

TILE_FARM_SLOTS = {
    'river':    6,
    'hills':    3,
    'desert':   0,
    'forest':   2,
    'mountain': 0,
}


class Tile:
    def __init__(self, row, col, terrain):
        self.row = row
        self.col = col
        self.terrain = terrain  # 'desert', 'hills', 'river'
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
        self.jobs = []
        self._init_jobs()
        self.food_allocated_from_routes = 0.0

    @property
    def worked_farms(self):
        farm_job = next((j for j in self.jobs if j.job_type == 'farm'), None)
        return farm_job.assigned if farm_job else 0

    @property
    def farm_yield(self):
        if self.city_distance is None:
            return FarmJob.YIELD_PER_POP
        key = round(round(self.city_distance / 0.25) * 0.25, 2)
        return FARM_YIELD_BY_DISTANCE.get(key, FarmJob.YIELD_PER_POP)

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

    def _init_jobs(self):
        if self.raided or self.restricted:
            self.jobs = []
            return
        slots = TILE_FARM_SLOTS.get(self.terrain, 0)
        self.jobs = [FarmJob(slots)] if slots > 0 else []

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
        self._init_jobs()
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
                self._init_jobs()
                city = self.owning_city
                if city is not None:
                    city._build_cumulative_farm_yield()
                    city.update_cumulative_farm_yield_net()
                    city.rebalance_pops()
        if self._restricted_ticker > 0:
            self._restricted_ticker -= 1

    def update_after_movement(self):
        self._update_city_with_movement()
        self.update_unit_allocations()
        # TO DO: update unit groups allocations

    def _food_from_routes(self):
        return sum(
            r.export_amount for r in self.trade_routes
            if r.established and not r.missing_caravans and r.export_material == 'food'
        )

    def update_unit_allocations(self):
        print('Updating unit allocations')
        remaining = self._food_from_routes()
        self.food_allocated_from_routes = 0.0
        for g in self.unit_groups:
            allocated = g.allocate_food(food_from_routes=remaining)
            print('Allocated:', allocated)
            self.food_allocated_from_routes += allocated
            remaining = max(0.0, remaining - allocated)
        print('Food allocated from routes:', self.food_allocated_from_routes)

        # Later on will need to handle the leftover food
