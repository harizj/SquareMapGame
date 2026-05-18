import math
from src.game.constants import DEFAULT_MOVE_DISTANCE, POP_FOOD_CONSUMPTION, MIN_TERRAIN_COST


class UnitGroup:
    def __init__(self, row, col, units=None, unit_type='warrior', faction=None):
        self.row = row
        self.col = col
        self.units = units or []
        self.unit_type = unit_type
        self.faction = faction
        self.max_moves = DEFAULT_MOVE_DISTANCE
        self.moves_remaining = DEFAULT_MOVE_DISTANCE
        self.food_stockpile = 0.0
        self.max_food_stockpile = self._carry_capacity()
        self.food_allocated_from_city = 0.0
        self.food_allocated_to_stockpile = 0.0
        self.food_allocated_from_routes = 0.0
        self.pending_pop_loss = 0
        self.move_exhausted = False
        self.can_capture_tile = False

    def get_color(self, color_type):
        if self.faction:
            return self.faction.colors[color_type]
        return None

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

    def allocate_food(self, food_from_routes=0.0):
        # print('Allocate food')
        # print(f"  food_from_city={self.food_allocated_from_city}")

        consumption = self.consumption_per_turn()
        # print(f"  consumption={consumption}")
        remainder = self.food_allocated_from_city - consumption
        # print(f"  remainder (after city alloc)={remainder}")
        # print(f"  carry capacity={self._carry_capacity()}")
        # print(f"  food_stockpile={self.food_stockpile}")

        food_to_fill_stockpile = self._carry_capacity() - remainder - self.food_stockpile
        # print(f"  food_to_fill_stockpile={food_to_fill_stockpile}")
        self.food_allocated_from_routes = min(food_to_fill_stockpile, food_from_routes)
        # print(f"  food_allocated_from_routes={self.food_allocated_from_routes}")
        remainder += self.food_allocated_from_routes
        # print(f"  remainder (after routes)={remainder}")
        remaining_route_food = food_from_routes - self.food_allocated_from_routes
        # print(f"  remaining_route_food={remaining_route_food}")

        # Separating this out for now until I'm sure the supply logic works
        if remainder >= 0:
            self.food_allocated_to_stockpile = remainder
            # print(f"  food_allocated_to_stockpile={self.food_allocated_to_stockpile}")
            self.pending_pop_loss = 0
        else:
            # If city can't cover food costs, -remainder will be the amount needed from stockpile
            # But can't be higher than current stockpile
            #self.food_allocated_to_stockpile = -min(-remainder, self.food_stockpile)
            #print(f"  food_allocated_to_stockpile={self.food_allocated_to_stockpile}")
            # print(f"  food_allocated_to_stockpile={self.food_allocated_to_stockpile}")
            self.food_allocated_to_stockpile = max(remainder, -self.food_stockpile)
            remainder -= self.food_allocated_to_stockpile
            # print(f"  remainder (after stockpile)={remainder}")
            if remainder < 0:
                self.pending_pop_loss = math.ceil(-remainder)
                # print(f"  pending_pop_loss={self.pending_pop_loss}")

        return self.food_allocated_from_routes

    def end_turn(self):
        # print(f"UnitGroup end_turn @ ({self.row},{self.col}): units={len(self.units)}, food_stockpile={self.food_stockpile}, food_allocated_from_city={self.food_allocated_from_city}, food_allocated_from_routes={self.food_allocated_from_routes}, food_allocated_to_stockpile={self.food_allocated_to_stockpile}, pending_pop_loss={self.pending_pop_loss}, moves_remaining={self.moves_remaining}, move_exhausted={self.move_exhausted}")
        # print('End turn, food allocated to stockpile is', self.food_allocated_to_stockpile)
        self.food_stockpile += self.food_allocated_to_stockpile
        if self.pending_pop_loss > 0:
            self.units = self.units[self.pending_pop_loss:]
            self.max_food_stockpile = self._carry_capacity()
        self._reset_moves()
        # self.food_allocated_from_routes = 0.0
        # self.food_allocated_to_stockpile = 0.0
        # self.food_allocated_from_city = 0.0

    def merge(self, other):
        self.units.extend(other.units)
        self.max_food_stockpile = self._carry_capacity()
        self.food_stockpile = min(self.food_stockpile + other.food_stockpile, self.max_food_stockpile)

    def _reset_moves(self):
        for unit in self.units:
            unit.reset_moves()
        self.update_moves_remaining()
        self.move_exhausted = False

    def equip_from_stockpile(self, item_stockpiles):
        from src.game.items import ITEM_REGISTRY
        from src.game.unit import UNIT_REGISTRY
        import collections
        def _summary(units):
            counts = collections.Counter(u.unit_type for u in units)
            return ', '.join(f"{v} {t}" for t, v in counts.items())
        print(f"[equip] before: units=[{_summary(self.units)}] stockpile={dict(item_stockpiles)}")
        militia = [u for u in self.units if u.is_militia]
        for item_name in ['sword', 'bow', 'spear']:
            if not militia:
                break
            count = item_stockpiles.get(item_name, 0)
            if count <= 0:
                continue
            item_cls = ITEM_REGISTRY.get(item_name)
            unit_cls = UNIT_REGISTRY.get(item_cls.upgrades_to) if item_cls else None
            if not unit_cls:
                continue
            while count > 0 and militia:
                old_unit = militia.pop(0)
                new_unit = unit_cls(old_unit.pop)
                new_unit.max_moves = old_unit.max_moves
                new_unit.moves_remaining = old_unit.moves_remaining
                self.units[self.units.index(old_unit)] = new_unit
                count -= 1
            if count > 0:
                item_stockpiles[item_name] = count
            else:
                del item_stockpiles[item_name]
        print(f"[equip] after:  units=[{_summary(self.units)}] stockpile={dict(item_stockpiles)}")

    def reset_after_movement(self):
        self.food_allocated_from_city = 0.0
        self.food_allocated_to_stockpile = 0.0
        self.food_allocated_from_routes = 0.0
