from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY


class Unit:
    def __init__(self, pop, unit_type='Militia'):
        self.pop = pop
        self.unit_type = unit_type
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE
        self.carry_capacity = LAND_CARRY_CAPACITY

    def reset_moves(self):
        self.moves_remaining = self.max_moves
