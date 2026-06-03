from src.game.constants import DEFAULT_MOVE_DISTANCE, MILITARY_CARRY_CAPACITY, MOVE_CARRY_OVER


class Unit:
    unit_type = ''
    combat_strength = 0
    icon = ''
    icon_scale = 1.0
    icon_x_offset = 0

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
    combat_strength = 10
    icon = 'pitchfork'
    icon_scale = 1.5


class Swordsmen(Unit):
    unit_type = 'Swordsmen'
    combat_strength = 20
    icon = 'gladius'
    icon_scale = 1.0


class Archers(Unit):
    unit_type = 'Archers'
    combat_strength = 15
    icon = 'bow'
    icon_scale = 1.3


class Spearmen(Unit):
    unit_type = 'Spearmen'
    combat_strength = 15
    icon = 'spear'
    icon_scale = 1.4
    icon_x_offset = 0


class Skeleton(Unit):
    unit_type = 'Skeleton'
    combat_strength = 10
    icon = 'human-skull'
    icon_scale = 1.0


UNIT_REGISTRY = {cls.unit_type: cls for cls in [Swordsmen, Archers, Spearmen, Militia, Skeleton]}
unit_list = list(UNIT_REGISTRY.keys())
