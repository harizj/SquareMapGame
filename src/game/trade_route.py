from src.game.jobs import CaravanJob
from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY
import math
import random


def calculate_supply_pops(amount, travel_time, one_way=True):
    """Return the number of caravan pops needed to sustain a supply route."""
    denom = LAND_CARRY_CAPACITY + 1 - (2 * travel_time if one_way else travel_time)
    if denom <= 0 or travel_time <= 0:
        return 0
    return max(1, math.ceil((amount * 2 * travel_time) / denom))


class TradeRoute:
    def __init__(self, city_a, dest_tile,
                 pops_a, pops_b,
                 partial_pops_a, partial_pops_b,
                 export_resource, export_amount, max_amount,
                 import_resource, import_amount,
                 path=None, path_distances=None,
                 one_way=True,
                 establish_progress=None, established=None,
                 establish_distance=None,
                 tether=False):
        self.city_a = city_a          # origin — allocates pops
        self.dest_tile = dest_tile    # destination tile (may or may not have a city)
        self.tether = tether
        self.faction = city_a.faction
        self.pops_a = pops_a
        self.pops_b = pops_b
        self.partial_pops_a = partial_pops_a
        self.partial_pops_b = partial_pops_b
        self.export_resource = export_resource  # city_a sends this
        self.export_amount = export_amount
        self.max_amount = max_amount
        self.import_resource = import_resource  # city_a receives this
        self.import_amount = import_amount
        self.caravan_job_a = CaravanJob(slots=pops_a, trade_route=self) if pops_a > 0 else None
        self.caravan_job_b = CaravanJob(slots=pops_b, trade_route=self) if pops_b > 0 else None
        self.path = path or []
        self.path_distances = path_distances or []
        self.distance = path_distances[-1] if path_distances else 0.0
        self.travel_time = self.distance / DEFAULT_MOVE_DISTANCE if self.distance > 0 else 0.0
        self.one_way = one_way
        self.missing_caravans = False
        self.establish_distance = establish_distance if establish_distance is not None else self.distance
        self.establish_progress = establish_progress if establish_progress is not None else DEFAULT_MOVE_DISTANCE
        self.established = established if established is not None else (self.establish_progress >= self.establish_distance)
        if not self.tether:
            print(f"[TradeRoute init] {city_a.name} -> {dest_tile.city.name if dest_tile.city else (dest_tile.row, dest_tile.col)}")
            print(f"  supply_distance={self.distance:.2f}  establish_distance={self.establish_distance:.2f}  establish_progress={self.establish_progress:.2f}  established={self.established}")

        # Register with both endpoints
        self.city_a.trade_routes.append(self)
        dest_city = dest_tile.city
        if dest_city is not None:
            dest_city.trade_routes.append(self)
            dest_city.update_cumulative_farm_yield_net()
            dest_city.rebalance_pops()
        else:
            dest_tile.trade_routes.append(self)
            dest_tile.update_unit_allocations()
        self.city_a.update_cumulative_farm_yield_net()
        self.city_a.rebalance_pops()
        self.update_resource_amounts()

        # print(f"\n=== New TradeRoute ===")
        # print(f"  city_a={self.city_a.name}  dest={self.destination_name}")
        # print(f"  pops_a={self.pops_a}  pops_b={self.pops_b}")
        # print(f"  partial_pops_a={self.partial_pops_a}  partial_pops_b={self.partial_pops_b}")
        # print(f"  export_resource={self.export_resource}  max_amount={self.max_amount}")
        # print(f"  import_resource={self.import_resource}  import_amount={self.import_amount}")
        # print(f"  caravan_job_a={self.caravan_job_a}  caravan_job_b={self.caravan_job_b}")
        # print(f"  path_distances={self.path_distances}")

    @property
    def city_b(self):
        """The destination city, or None if the destination is a cityless tile."""
        return self.dest_tile.city

    @property
    def destination_name(self):
        city = self.dest_tile.city
        return city.name if city is not None else "Supply Line"

    def destination_is(self, city):
        """Return True if the given city is the destination of this route."""
        return self.dest_tile.city is city

    def detach(self, rebalance=False):
        """Remove this route from both endpoints and update cumulative yields.

        Pass rebalance=True to also call rebalance_pops on city endpoints
        (omit when already inside rebalance_pops to avoid recursion).
        """
        self.city_a.trade_routes.remove(self)
        self.city_a.update_cumulative_farm_yield_net()
        dest_city = self.dest_tile.city
        if dest_city is not None:
            dest_city.trade_routes.remove(self)
            dest_city.update_cumulative_farm_yield_net()
        else:
            self.dest_tile.trade_routes.remove(self)
            self.dest_tile.update_unit_allocations()
        if rebalance:
            self.city_a.rebalance_pops()
            if dest_city is not None:
                dest_city.rebalance_pops()

    def end_turn(self):
        if self.established == False:
            self.establish_progress += DEFAULT_MOVE_DISTANCE
            if self.establish_progress >= self.establish_distance:
                # print('Trade route established!')
                self.establish_progress = self.establish_distance
                self.established = True
                self.city_a.update_cumulative_farm_yield_net()
                self.city_a.rebalance_pops()
                dest_city = self.dest_tile.city
                if dest_city is not None:
                    dest_city.update_cumulative_farm_yield_net()
                    dest_city.rebalance_pops()
                
        self.dest_tile.update_unit_allocations()
        self.update_resource_amounts()

    def get_pops_from_city(self, city):
        return self.pops_a if self.city_a is city else self.pops_b

    def turns_until_established(self):
        return math.ceil((self.establish_distance - self.establish_progress) / DEFAULT_MOVE_DISTANCE)

    def check_if_established(self):
        return self.established

    def get_visual_path(self):
        if self.established:
            return self.path
        if self.establish_distance > 0:
            supply_cutoff = (self.establish_progress / self.establish_distance) * self.distance
        else:
            supply_cutoff = 0.0
        result = [node for node, d in zip(self.path, self.path_distances) if d <= supply_cutoff]
        return result

    def update_resource_amounts(self):
        if self.export_resource and self.export_resource != 'food':
            city_tile = next(
                (t for t in self.city_a.owned_tiles if t.row == self.city_a.row and t.col == self.city_a.col),
                None
            )
            available = city_tile.resource_stockpiles.get(self.export_resource, 0) if city_tile else 0
            allocated = self.city_a.resources_allocated_to_production.get(self.export_resource, 0)
            available = max(0, available - allocated)
            self.export_amount = min(available, self.max_amount)

        if self.import_resource and self.import_resource != 'food':
            available = self.dest_tile.resource_stockpiles.get(self.import_resource, 0)
            self.import_amount = min(available, self.max_amount)

    def get_plunder_resources(self):
        """Take resources in transit on this route, returning {resource: amount_taken}.

        One-way: always plunders the export side from city_a.
        Two-way: randomly chooses export (from city_a) or import (from dest_tile, non-food only).
        """
        if self.one_way:
            if not self.export_resource:
                return {}
            taken = self.city_a.take_resource(self.export_resource, self.export_amount)
            return {self.export_resource: taken} if taken > 0 else {}

        # Two-way: randomly pick a side
        plunder_export = random.random() < 0.5

        if plunder_export:
            if not self.export_resource:
                return {}
            taken = self.city_a.take_resource(self.export_resource, self.export_amount)
            return {self.export_resource: taken} if taken > 0 else {}
        else:
            if not self.import_resource or self.import_resource == 'food':
                return {}
            available = self.dest_tile.resource_stockpiles.get(self.import_resource, 0.0)
            taken = min(self.import_amount, available)
            if taken > 0:
                remaining = available - taken
                if remaining > 0:
                    self.dest_tile.resource_stockpiles[self.import_resource] = remaining
                else:
                    self.dest_tile.resource_stockpiles.pop(self.import_resource, None)
            return {self.import_resource: taken} if taken > 0 else {}

    def reduce_export_amount(self):
        if self.max_amount <= 1:
            self.detach(rebalance=True)
            return

        self.max_amount -= 1
        total_pops = calculate_supply_pops(self.max_amount, self.travel_time, self.one_way)
        if total_pops > 0:
            if not self.one_way:
                self.pops_a = (total_pops + 1) // 2
                self.pops_b = total_pops // 2
            else:
                self.pops_a = total_pops
            if self.caravan_job_a is not None:
                self.caravan_job_a.slots = self.pops_a
            if self.caravan_job_b is not None:
                self.caravan_job_b.slots = self.pops_b

        self.city_a.update_cumulative_farm_yield_net()
        self.city_a.rebalance_pops()
        dest_city = self.dest_tile.city
        if dest_city is not None:
            dest_city.update_cumulative_farm_yield_net()
            dest_city.rebalance_pops()
        self.update_resource_amounts()
