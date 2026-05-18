from src.game.constants import DEFAULT_MOVE_DISTANCE, MILITARY_CARRY_CAPACITY, MOVE_CARRY_OVER


class Unit:
    unit_type = ''
    combat_strength = 0

    def __init__(self, pop):
        self.pop = pop
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE
        self.carry_capacity = MILITARY_CARRY_CAPACITY

    @property
    def is_militia(self):
        return self.unit_type == 'Militia'

    def reset_moves(self):
        self.moves_remaining = self.max_moves + min(MOVE_CARRY_OVER, self.moves_remaining)


class Militia(Unit):
    unit_type = 'Militia'
    combat_strength = 1
    icon = 'pitchfork'


class Swordsmen(Unit):
    unit_type = 'Swordsmen'
    combat_strength = 3
    icon = 'gladius'


class Archers(Unit):
    unit_type = 'Archers'
    combat_strength = 2
    icon = 'bow'


class Spearmen(Unit):
    unit_type = 'Spearmen'
    combat_strength = 2
    icon = 'spear'


UNIT_REGISTRY = {cls.unit_type: cls for cls in [Swordsmen, Archers, Spearmen, Militia]}
unit_list = list(UNIT_REGISTRY.keys())  # display order: Swordsmen, Archers, Spearmen, Militia
