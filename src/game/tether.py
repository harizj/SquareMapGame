import math
from src.game.trade_route import TradeRoute, calculate_supply_pops
from src.game.constants import LAND_CARRY_CAPACITY, DEFAULT_MOVE_DISTANCE, TETHER_CATCHUP


class Tether:
    def __init__(self, city, unit_group, food_amount, tether_units=None):
        self.city = city
        self.unit_group = unit_group
        self.food_amount = food_amount
        self.tether_units = tether_units or []  # list of Unit objects
        self.route = None
        self.catchup = False
        self.pending_dst_tile = None
        self.pending_path = None
        self.pending_distances = None
        # print(f"[Tether] city={city.name} units={len(unit_group.units)} food_amount={food_amount} tether_units={len(self.tether_units)}")

    def calculate_supply_pops(self, distance):
        travel_time = 2 * distance / DEFAULT_MOVE_DISTANCE
        return max(1, math.ceil((travel_time * self.food_amount) / (LAND_CARRY_CAPACITY + 1)))

    def update_supply_pops(self, distance):
        supply_pops = self.calculate_supply_pops(distance)
        total_units = len(self.unit_group.units) + len(self.tether_units)
        if supply_pops >= total_units:
            # print(f"[Tether] collapse: supply_pops={supply_pops} >= total_units={total_units}, tether will be deleted")
            return None
        needed = supply_pops - len(self.tether_units)
        # print(f"[Tether] supply_pops={supply_pops} distance={distance} pops needed={needed}")
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

    def transfer_tether_units_to_city(self, n, game_map):
        from src.game.battles import drop_unit_items
        city_tile = game_map.tiles[self.city.row][self.city.col]
        returning = self.tether_units[:n]
        self.tether_units = self.tether_units[n:]
        drop_unit_items(returning, city_tile)
        self.city.pops.extend(u.pop for u in returning)
        self.city.update_cumulative_farm_yield_net()
        self.city.rebalance_pops()

    def update_with_unit_deaths(self, game_map):
        if not self.unit_group.units:
            self.unit_group.delete_tether(game_map)
            return
        distance = self.route.distance if self.route is not None else 0.0
        travel_time = distance / DEFAULT_MOVE_DISTANCE
        self.food_amount = len(self.unit_group.units) + calculate_supply_pops(len(self.unit_group.units), travel_time)
        supply_pops = self.calculate_supply_pops(distance)
        total_units = len(self.unit_group.units) + len(self.tether_units)
        if supply_pops >= total_units:
            self.tether_units.extend(self.unit_group.units)
            self.unit_group.units = []
            self.unit_group.max_food_stockpile = self.unit_group._carry_capacity()
            self.unit_group.delete_tether(game_map)
            return
        reduction = len(self.tether_units) - supply_pops
        if reduction > 0:
            self.transfer_tether_units_to_city(reduction, game_map)
        if not self.catchup:
            if self.route is not None:
                self.route.export_amount = self.food_amount
                self.route.max_amount = self.food_amount
                self.route.dest_tile.update_unit_allocations()
                self.city.update_cumulative_farm_yield_net()
                self.city.rebalance_pops()

    def tether_catchup(self):
        if not self.catchup:
            return
        self.catchup = False
        dst_tile = self.pending_dst_tile
        path = self.pending_path
        distances = self.pending_distances
        self.pending_dst_tile = None
        self.pending_path = None
        self.pending_distances = None
        if dst_tile is None or not distances:
            return
        if self.route is not None:
            self.route.detach()
            self.route = None
        self.route = TradeRoute(
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
            establish_progress=distances[-1],
            established=True,
            tether=True,
        )

    def unit_movement(self, game_map, src_tile, dst_tile):
        if dst_tile.city is self.city:
            if self.route is not None:
                self.route.detach()
                self.route = None
            self._city_return(game_map, dst_tile)
            return

        _, prev_distances = game_map.get_path_to(
            self.city.row, self.city.col,
            src_tile.row, src_tile.col,
            scheme='supply',
        )
        prev_distance = prev_distances[-1] if prev_distances else 0.0

        path, distances = game_map.get_path_to(
            self.city.row, self.city.col,
            dst_tile.row, dst_tile.col,
            scheme='supply',
        )
        distance = distances[-1] if distances else 0.0

        supply_pops = self.update_supply_pops(distance)
        if supply_pops is None:
            self.unit_group.delete_tether(game_map)
            return

        if distance < prev_distance or src_tile.city is self.city or not TETHER_CATCHUP:
            if self.route is not None:
                self.route.detach()
                self.route = None
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

                one_way=True,
                establish_progress=distances[-1] if distances else 0.0,
                established=True,
                tether=True,
            )
            self.route = route
            # print(f"[Tether] route created city={self.city.name} -> ({dst_tile.row},{dst_tile.col}) distance={route.distance} food={self.food_amount}")
        else:
            self.catchup = True
            self.pending_dst_tile = dst_tile
            self.pending_path = path
            self.pending_distances = distances
