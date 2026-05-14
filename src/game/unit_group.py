import math
from src.game.constants import DEFAULT_MOVE_DISTANCE, POP_FOOD_CONSUMPTION, MIN_TERRAIN_COST


class UnitGroup:
    def __init__(self, row, col, units=None, unit_type='warrior'):
        self.row = row
        self.col = col
        self.units = units or []
        self.unit_type = unit_type
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE
        self.food_stockpile = 0.0
        self.max_food_stockpile = self._carry_capacity()
        self.food_allocated_from_city = 0.0
        self.food_allocated_from_stockpile = 0.0
        self.food_allocated_from_routes = 0.0
        self.pending_pop_loss = 0
        self.move_exhausted = False

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
        remainder = max(0.0, consumption - self.food_allocated_from_city)
        self.food_allocated_from_stockpile = min(self.food_stockpile, remainder)
        self.pending_pop_loss = math.ceil(remainder - self.food_allocated_from_stockpile)

    def end_turn(self):
        self.allocate_food()
        self.food_stockpile -= self.food_allocated_from_stockpile
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
        self.move_exhausted = False

    def reset_after_movement(self):
        self.food_allocated_from_city = 0.0
        self.food_allocated_from_stockpile = 0.0
        self.food_allocated_from_routes = 0.0
