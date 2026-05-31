class Tether:
    def __init__(self, city, unit_group, food_amount, tether_pops=None):
        self.city = city
        self.unit_group = unit_group
        self.food_amount = food_amount
        self.tether_pops = tether_pops or []
        print(f"[Tether] city={city.name} units={len(unit_group.units)} food_amount={food_amount} tether_pops={len(self.tether_pops)}")
