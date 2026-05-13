from src.game.jobs import CaravanJob
from src.game.constants import DEFAULT_MOVE_DISTANCE


class TradeRoute:
    def __init__(self, city_a, city_b, pops_a, pops_b,
                 partial_pops_a, partial_pops_b,
                 export_material, export_amount, max_export,
                 import_material, import_amount, max_import,
                 path=None, path_distances=None):
        self.city_a = city_a          # origin — allocates pops
        self.city_b = city_b          # destination
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
        self.missing_caravans = False
        self.established = False
        self.establish_progress = DEFAULT_MOVE_DISTANCE
        self.city_a.trade_routes.append(self)
        self.city_b.trade_routes.append(self)
        self.city_a.update_cumulative_farm_yield_net()
        self.city_b.update_cumulative_farm_yield_net()
        self.city_a.rebalance_pops()
        self.city_b.rebalance_pops()
        print(f"\n=== New TradeRoute ===")
        print(f"  city_a={self.city_a.name}  city_b={self.city_b.name}")
        print(f"  pops_a={self.pops_a}  pops_b={self.pops_b}")
        print(f"  partial_pops_a={self.partial_pops_a}  partial_pops_b={self.partial_pops_b}")
        print(f"  export_material={self.export_material}  export_amount={self.export_amount}  max_export={self.max_export}")
        print(f"  import_material={self.import_material}  import_amount={self.import_amount}  max_import={self.max_import}")
        print(f"  caravan_job_a={self.caravan_job_a}  caravan_job_b={self.caravan_job_b}")
        print(f"  path_distances={self.path_distances}")

    def end_turn(self):
        if self.established:
            return
        self.establish_progress += DEFAULT_MOVE_DISTANCE
        if self.establish_progress >= self.distance:
            self.establish_progress = self.distance
            self.established = True
            self.city_a.update_cumulative_farm_yield_net()
            self.city_b.update_cumulative_farm_yield_net()
            self.city_a.rebalance_pops()
            self.city_b.rebalance_pops()

    def check_if_established(self):
        return self.established

    def get_visual_path(self):
        if self.established:
            return self.path
        result = [node for node, d in zip(self.path, self.path_distances) if d <= self.establish_progress]
        return result
