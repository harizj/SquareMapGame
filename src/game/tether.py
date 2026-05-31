from src.game.trade_route import TradeRoute
from src.game.constants import LAND_CARRY_CAPACITY, DEFAULT_MOVE_DISTANCE


class Tether:
    def __init__(self, city, unit_group, food_amount, tether_pops=None):
        self.city = city
        self.unit_group = unit_group
        self.food_amount = food_amount
        self.tether_pops = tether_pops or []
        self.route = None
        print(f"[Tether] city={city.name} units={len(unit_group.units)} food_amount={food_amount} tether_pops={len(self.tether_pops)}")

    def update_supply_pops(self, distance):
        supply_pops = self.food_amount * (LAND_CARRY_CAPACITY + 1 - 2 * distance / DEFAULT_MOVE_DISTANCE) / (LAND_CARRY_CAPACITY + 1)
        return supply_pops

    def unit_movement(self, game_map, dst_tile):
        if self.route is not None:
            self.route.detach()
            self.route = None

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
        )
        route.established = True
        route.establish_progress = route.distance
        self.route = route
        print(f"[Tether] route created city={self.city.name} -> ({dst_tile.row},{dst_tile.col}) distance={route.distance} food={self.food_amount}")
