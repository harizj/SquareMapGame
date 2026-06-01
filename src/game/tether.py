import math
from src.game.trade_route import TradeRoute
from src.game.constants import LAND_CARRY_CAPACITY, DEFAULT_MOVE_DISTANCE


class Tether:
    def __init__(self, city, unit_group, food_amount, tether_units=None):
        self.city = city
        self.unit_group = unit_group
        self.food_amount = food_amount
        self.tether_units = tether_units or []  # list of Unit objects
        self.route = None
        print(f"[Tether] city={city.name} units={len(unit_group.units)} food_amount={food_amount} tether_units={len(self.tether_units)}")

    def update_supply_pops(self, distance):
        units_in_field = math.ceil(
            self.food_amount * (LAND_CARRY_CAPACITY + 1 - 2 * distance / DEFAULT_MOVE_DISTANCE) / (LAND_CARRY_CAPACITY + 1)
        )
        travel_time = 2 * distance / DEFAULT_MOVE_DISTANCE
        supply_pops = self.food_amount - units_in_field
        supply_pops = math.ceil((self.food_amount * travel_time)/(LAND_CARRY_CAPACITY + 1 - travel_time))
        supply_pops = max(1, math.ceil((travel_time*self.food_amount)/(LAND_CARRY_CAPACITY + 1)))
        needed = supply_pops - len(self.tether_units)
        print(f"[Tether] supply_pops={supply_pops} distance={distance} pops needed={needed} units_in_field={units_in_field}")
        if needed > 0:
            transferred = self.unit_group.remove_pops(needed)
            self.tether_units.extend(transferred)
        elif needed < 0:
            returning = self.tether_units[:abs(needed)]
            self.tether_units = self.tether_units[abs(needed):]
            self.unit_group.units.extend(returning)
            self.unit_group.max_food_stockpile = self.unit_group._carry_capacity()
        return supply_pops

    def _city_return(self, game_map, dst_tile):
        self.unit_group.units.extend(self.tether_units)
        self.unit_group.max_food_stockpile = self.unit_group._carry_capacity()
        self.tether_units.clear()

    def unit_movement(self, game_map, src_tile, dst_tile):
        if self.route is not None:
            self.route.detach()
            self.route = None

        if dst_tile.city is self.city:
            self._city_return(game_map, dst_tile)
            return

        _, prev_distances = game_map.get_path_to(
            self.city.row, self.city.col,
            src_tile.row, src_tile.col,
        )
        prev_distance = prev_distances[-1] if prev_distances else 0.0

        path, distances = game_map.get_path_to(
            self.city.row, self.city.col,
            dst_tile.row, dst_tile.col,
        )
        distance = distances[-1] if distances else 0.0

        supply_pops = self.update_supply_pops(distance)

        route = TradeRoute(
            city_a=self.city,
            dest_tile=dst_tile,
            pops_a=0,
            pops_b=0,
            partial_pops_a=0,
            partial_pops_b=0,
            export_resource='food',
            export_amount=self.food_amount,
            max_amount=self.food_amount,
            import_resource=None,
            import_amount=0,
            path=path,
            path_distances=distances,
            water=False,
            one_way=True,
            establish_progress=distances[-1] if distances else 0.0,
            established=True,
        )
        self.route = route
        print(f"[Tether] route created city={self.city.name} -> ({dst_tile.row},{dst_tile.col}) distance={route.distance} food={self.food_amount}")
