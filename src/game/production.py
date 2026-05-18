from src.game.items import ITEM_REGISTRY

PRODUCTION_CATEGORIES = ['extraction', 'manufacturing', 'construction']

PRODUCTION_SUBTYPES = {
    'extraction':    ['wood', 'iron'],
    'manufacturing': ['sword', 'spear', 'bow'],
    'construction':  [],
}


class ProductionTarget:
    def __init__(self):
        self.type = None
        self.target = None
        self.target_item = None
        self.progress = 0.0
        self.unfinished_items = []

    def _resolve_manufacturing_item(self, item_cls):
        for i, entry in enumerate(self.unfinished_items):
            if entry['item'] is item_cls:
                self.unfinished_items.pop(i)
                self.target_item = item_cls
                self.progress = entry['progress']
                return
        self.target_item = item_cls
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
        else:
            self.target_item = None
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
        self.progress = 0.0

    @property
    def label(self):
        if self.type == 'manufacturing' and self.target_item:
            item = self.target_item
            return f"{item.name.capitalize()} ({int(self.progress)}/{item.production_needed})"
        if self.type and self.target:
            return f"{self.target.capitalize()} ({self.type.capitalize()})"
        return "None"
