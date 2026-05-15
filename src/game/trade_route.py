from src.game.jobs import CaravanJob
from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY, WATER_CARRY_CAPACITY
import math


class TradeRoute:
    def __init__(self, city_a, dest_tile,
                 pops_a, pops_b,
                 partial_pops_a, partial_pops_b,
                 export_material, export_amount, max_export,
                 import_material, import_amount, max_import,
                 path=None, path_distances=None,
                 water=False):
        self.city_a = city_a          # origin — allocates pops
        self.dest_tile = dest_tile    # destination tile (may or may not have a city)
        self.faction = city_a.faction
        self.pops_a = pops_a
        self.pops_b = pops_b
        self.partial_pops_a = partial_pops_a
        self.partial_pops_b = partial_pops_b
        self.export_material = export_material  # city_a sends this
        self.export_amount = export_amount
        self.max_export = max_export
        self.import_material = import_material  # city_a receives this
        self.import_amount = import_amount
        self.max_import = max_import
        self.caravan_job_a = CaravanJob(slots=pops_a, trade_route=self) if pops_a > 0 else None
        self.caravan_job_b = CaravanJob(slots=pops_b, trade_route=self) if pops_b > 0 else None
        self.path = path or []
        self.path_distances = path_distances or []
        self.distance = path_distances[-1] if path_distances else 0.0
        self.water = water
        self.travel_time = self.distance / DEFAULT_MOVE_DISTANCE if self.distance > 0 else 0.0
        self.missing_caravans = False
        self.establish_progress = DEFAULT_MOVE_DISTANCE
        self.established = self.establish_progress >= self.distance

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

        print(f"\n=== New TradeRoute ===")
        print(f"  city_a={self.city_a.name}  dest={self.destination_name}")
        print(f"  pops_a={self.pops_a}  pops_b={self.pops_b}")
        print(f"  partial_pops_a={self.partial_pops_a}  partial_pops_b={self.partial_pops_b}")
        print(f"  export_material={self.export_material}  export_amount={self.export_amount}  max_export={self.max_export}")
        print(f"  import_material={self.import_material}  import_amount={self.import_amount}  max_import={self.max_import}")
        print(f"  caravan_job_a={self.caravan_job_a}  caravan_job_b={self.caravan_job_b}")
        print(f"  path_distances={self.path_distances}")

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
        if rebalance:
            self.city_a.rebalance_pops()
            if dest_city is not None:
                dest_city.rebalance_pops()

    def end_turn(self):
        if self.established == False:
            self.establish_progress += DEFAULT_MOVE_DISTANCE
            if self.establish_progress >= self.distance:
                print('Trade route established!')
                self.establish_progress = self.distance
                self.established = True
                self.city_a.update_cumulative_farm_yield_net()
                self.city_a.rebalance_pops()
                dest_city = self.dest_tile.city
                if dest_city is not None:
                    dest_city.update_cumulative_farm_yield_net()
                    dest_city.rebalance_pops()
                
        self.dest_tile.update_unit_allocations()

    def get_pops_from_city(self, city):
        return self.pops_a if self.city_a is city else self.pops_b

    def turns_until_established(self):
        return math.ceil((self.distance - self.establish_progress) / DEFAULT_MOVE_DISTANCE)

    def check_if_established(self):
        return self.established

    def get_visual_path(self):
        if self.established:
            return self.path
        result = [node for node, d in zip(self.path, self.path_distances) if d <= self.establish_progress]
        return result

    def reduce_export_amount(self):
        if self.export_amount <= 1:
            self.detach(rebalance=True)
            return

        self.export_amount -= 1
        carry_capacity = WATER_CARRY_CAPACITY if self.water else LAND_CARRY_CAPACITY
        denom = carry_capacity + 1 - 2 * self.travel_time
        if denom > 0 and self.travel_time > 0:
            raw = (self.export_amount * 2 * self.travel_time) / denom
            self.pops_a = max(1, round(raw))
            if self.caravan_job_a is not None:
                self.caravan_job_a.slots = self.pops_a

        self.city_a.update_cumulative_farm_yield_net()
        self.city_a.rebalance_pops()
        dest_city = self.dest_tile.city
        if dest_city is not None:
            dest_city.update_cumulative_farm_yield_net()
            dest_city.rebalance_pops()
