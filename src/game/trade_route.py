class TradeRoute:
    def __init__(self, city_a, city_b, pops,
                 export_material, export_amount, max_export,
                 import_material, import_amount, max_import):
        self.city_a = city_a          # origin — allocates pops
        self.city_b = city_b          # destination
        self.pops = pops
        self.export_material = export_material  # city_a sends this
        self.export_amount = export_amount
        self.max_export = max_export
        self.import_material = import_material  # city_a receives this
        self.import_amount = import_amount
        self.max_import = max_import
        self.city_a.update_cumulative_farm_yield_net()
        self.city_b.update_cumulative_farm_yield_net()
