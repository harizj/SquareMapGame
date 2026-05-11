class TradeRoute:
    def __init__(self, city_a, city_b, pops_a, pops_b,
                 partial_pops_a, partial_pops_b,
                 export_material, export_amount, max_export,
                 import_material, import_amount, max_import):
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
        self.city_a.trade_routes.append(self)
        self.city_b.trade_routes.append(self)
        self.city_a.update_cumulative_farm_yield_net()
        self.city_b.update_cumulative_farm_yield_net()
        print(f"\n=== New TradeRoute ===")
        print(f"  city_a={self.city_a.name}  city_b={self.city_b.name}")
        print(f"  pops_a={self.pops_a}  pops_b={self.pops_b}")
        print(f"  partial_pops_a={self.partial_pops_a}  partial_pops_b={self.partial_pops_b}")
        print(f"  export_material={self.export_material}  export_amount={self.export_amount}  max_export={self.max_export}")
        print(f"  import_material={self.import_material}  import_amount={self.import_amount}  max_import={self.max_import}")
