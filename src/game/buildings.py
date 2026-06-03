class Building:
    name: str = ''
    production_needed: int = 10
    resource_cost: dict = {}
    multiple = False
    survives_city = False

    @classmethod
    def requires_resource(cls, resource):
        return resource in cls.resource_cost


class Workcamp(Building):
    name = 'workcamp'
    production_needed = 6
    resource_cost = {'wood': 10, 'iron': 6}


class Workshop(Building):
    name = 'workshop'
    production_needed = 8
    resource_cost = {'wood': 10, 'iron': 4}


class WoodenWalls(Building):
    name = 'wooden walls'
    production_needed = 15
    resource_cost = {'wood': 10}
    multiple = True


class StoneWalls(Building):
    name = 'stone walls'
    production_needed = 30
    resource_cost = {'stone': 50}
    multiple = True
    survives_city = True


BUILDING_REGISTRY = {cls.name: cls for cls in [Workcamp, Workshop, WoodenWalls, StoneWalls]}
