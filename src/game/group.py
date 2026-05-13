from src.game.constants import DEFAULT_MOVE_DISTANCE


class Group:
    def __init__(self, row, col, units=None, unit_type='warrior'):
        self.row = row
        self.col = col
        self.units = units or []
        self.unit_type = unit_type
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE
        self.food_stockpile = 0.0
        self.max_food_stockpile = self._carry_capacity()

    def add_food(self, amount):
        before = self.food_stockpile
        self.food_stockpile = min(self.food_stockpile + amount, self.max_food_stockpile)
        return self.food_stockpile - before

    def _carry_capacity(self):
        return sum(u.carry_capacity for u in self.units)

    def update_moves_remaining(self):
        if self.units:
            self.moves_remaining = min(u.moves_remaining for u in self.units)

    def reset_moves(self):
        self.moves_remaining = self.max_moves
