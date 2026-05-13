import math
from src.game.constants import DEFAULT_MOVE_DISTANCE, POP_FOOD_CONSUMPTION


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
        self.food_allocated_to_consumption = 0.0
        self.pending_pop_loss = 0

    def add_food(self, amount):
        before = self.food_stockpile
        self.food_stockpile = min(self.food_stockpile + amount, self.max_food_stockpile)
        return self.food_stockpile - before

    def _carry_capacity(self):
        return sum(u.carry_capacity for u in self.units)

    def update_moves_remaining(self):
        if self.units:
            self.moves_remaining = min(u.moves_remaining for u in self.units)

    def consumption_per_turn(self):
        return len(self.units) * POP_FOOD_CONSUMPTION

    def allocate_food(self):
        consumption = self.consumption_per_turn()
        self.food_allocated_to_consumption = max(0.0, min(self.food_stockpile, consumption))
        self.pending_pop_loss = math.ceil(consumption - self.food_allocated_to_consumption)

    def end_turn(self):
        self.allocate_food()
        self.food_stockpile -= self.food_allocated_to_consumption
        if self.pending_pop_loss > 0:
            self.units = self.units[self.pending_pop_loss:]
            self.max_food_stockpile = self._carry_capacity()
        self._reset_moves()
        self.allocate_food()

    def merge(self, other):
        self.units.extend(other.units)
        self.max_food_stockpile = self._carry_capacity()
        self.food_stockpile = min(self.food_stockpile + other.food_stockpile, self.max_food_stockpile)

    def _reset_moves(self):
        for unit in self.units:
            unit.reset_moves()
        self.update_moves_remaining()
