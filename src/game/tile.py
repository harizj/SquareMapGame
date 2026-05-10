from src.game.jobs import FarmJob

# Yield per assigned pop at each distance increment (fill in from LP results later)
FARM_YIELD_BY_DISTANCE = {
    0.00: 1.40,
    0.25: 1.375,
    0.50: 1.35,
    0.75: 1.325,
    1.00: 1.30,
    1.25: 1.275,
    1.50: 1.25,
    1.75: 1.225,
    2.00: 1.20,
    2.25: 1.175,
    2.50: 1.15,
    2.75: 1.125,
    3.00: 1.10,
}

TILE_FARM_SLOTS = {
    'river':    5,
    'hills':    2,
    'desert':   1,
    'forest':   1,
    'mountain': 0,
}


class Tile:
    def __init__(self, row, col, terrain):
        self.row = row
        self.col = col
        self.terrain = terrain  # 'desert', 'hills', 'river'
        self.river_edges = set()  # subset of {'NW','NE','E','SE','SW','W'}
        self.owning_city = None
        self.city_distance = None
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

    def _init_jobs(self):
        slots = TILE_FARM_SLOTS.get(self.terrain, 0)
        self.jobs = [FarmJob(slots)] if slots > 0 else []
