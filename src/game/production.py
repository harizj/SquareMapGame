from src.game.items import ITEM_REGISTRY
from src.game.buildings import BUILDING_REGISTRY

PRODUCTION_CATEGORIES = ['extraction', 'manufacturing', 'construction']

PRODUCTION_SUBTYPES = {
    'extraction':    ['wood', 'iron'],
    'manufacturing': ['swords', 'spears', 'bows'],
    'construction':  ['workcamp', 'workshop', 'wooden walls', 'stone walls'],
}

EXTRACTION_LABELS = {
    'wood': 'Chop Wood',
    'iron': 'Mine Iron',
}


class ProductionTarget:
    def __init__(self):
        self.type = None
        self.target = None
        self.target_item = None
        self.target_building = None
        self.progress = 0.0
        self.unfinished_items = []
        self.unfinished_buildings = []

    def _resolve_manufacturing_item(self, item_cls):
        for i, entry in enumerate(self.unfinished_items):
            if entry['item'] is item_cls:
                self.unfinished_items.pop(i)
                self.target_item = item_cls
                self.progress = entry['progress']
                return
        self.target_item = item_cls
        self.progress = 0.0

    def _resolve_construction(self, building_cls):
        for i, entry in enumerate(self.unfinished_buildings):
            if entry['building'] is building_cls:
                self.unfinished_buildings.pop(i)
                self.target_building = building_cls
                self.progress = entry['progress']
                return
        self.target_building = building_cls
        self.progress = 0.0

    def set(self, type, target):
        self.type = type
        self.target = target
        if type == 'manufacturing':
            item_cls = ITEM_REGISTRY.get(target)
            if item_cls:
                self._resolve_manufacturing_item(item_cls)
            else:
                self.target_item = None
                self.progress = 0.0
            self.target_building = None
        elif type == 'construction':
            building_cls = BUILDING_REGISTRY.get(target)
            if building_cls:
                self._resolve_construction(building_cls)
            else:
                self.target_building = None
                self.progress = 0.0
            self.target_item = None
        else:
            self.target_item = None
            self.target_building = None
            self.progress = 0.0

    def get_unfinished_progress(self, item_cls):
        for entry in self.unfinished_items:
            if entry['item'] is item_cls:
                return entry['progress']
        return None

    def clear(self):
        self.type = None
        self.target = None
        self.target_item = None
        self.target_building = None
        self.progress = 0.0

    @property
    def label(self):
        if self.type == 'manufacturing' and self.target_item:
            item = self.target_item
            return f"{item.name.capitalize()} ({int(self.progress)}/{item.production_needed})"
        if self.type == 'construction' and self.target_building:
            b = self.target_building
            return f"{b.name.title()} ({int(self.progress)}/{b.production_needed})"
        if self.type == 'extraction' and self.target:
            return EXTRACTION_LABELS.get(self.target, self.target.capitalize())
        if self.type and self.target:
            return f"{self.target.capitalize()} ({self.type.capitalize()})"
        return "None"
