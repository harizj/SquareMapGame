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
        self.jobs = []
        self._init_jobs()

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
            self.city.rebalance_pops()

    def _init_jobs(self):
        slots = TILE_FARM_SLOTS.get(self.terrain, 0)
        self.jobs = [FarmJob(slots)] if slots > 0 else []

    def update_after_movement(self):
        self._update_city_with_movement()
        # TO DO: update unit groups allocations