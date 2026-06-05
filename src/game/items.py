class Item:
    name: str = ''
    production_needed: int = 10
    resource_cost: dict = {}

    @classmethod
    def requires_resource(cls, resource):
        return resource in cls.resource_cost


class Sword(Item):
    name = 'swords'
    production_needed = 8
    resource_cost = {'iron': 4, 'wood': 2}
    upgrades_to = 'Swordsmen'


class Spear(Item):
    name = 'spears'
    production_needed = 4
    resource_cost = {'wood': 4, 'iron': 2}
    upgrades_to = 'Spearmen'


class Bow(Item):
    name = 'bows'
    production_needed = 6
    resource_cost = {'wood': 6, 'iron': 2}
    upgrades_to = 'Archers'


ITEM_REGISTRY = {cls.name: cls for cls in [Sword, Spear, Bow]}
