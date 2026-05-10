from src.game.jobs import FarmJob

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

    def _init_jobs(self):
        slots = TILE_FARM_SLOTS.get(self.terrain, 0)
        self.jobs = [FarmJob(slots)] if slots > 0 else []
