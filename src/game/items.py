class Item:
    name: str = ''
    production_needed: int = 10
    resource_cost: dict = {}

    @classmethod
    def requires_resource(cls, resource):
        return resource in cls.resource_cost


class Sword(Item):
    name = 'sword'
    production_needed = 10
    resource_cost = {'iron': 5}
    upgrades_to = 'Swordsmen'


class Spear(Item):
    name = 'spear'
    production_needed = 6
    resource_cost = {'wood': 5}
    upgrades_to = 'Spearmen'


class Bow(Item):
    name = 'bow'
    production_needed = 10
    resource_cost = {'wood': 5}
    upgrades_to = 'Archers'


ITEM_REGISTRY = {cls.name: cls for cls in [Sword, Spear, Bow]}
