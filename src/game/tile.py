class Tile:
    def __init__(self, row, col, terrain):
        self.row = row
        self.col = col
        self.terrain = terrain  # 'desert', 'hills', 'river'
        self.river_edges = set()  # subset of {'NW','NE','E','SE','SW','W'}
