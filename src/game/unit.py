from src.game.constants import DEFAULT_MOVE_DISTANCE


class Unit:
    def __init__(self, row, col, unit_type='warrior'):
        self.row = row
        self.col = col
        self.unit_type = unit_type
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE

    def reset_moves(self):
        self.moves_remaining = self.max_moves
