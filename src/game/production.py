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

    def set(self, type, target):
        self.type = type
        self.target = target
        self.target_item = ITEM_REGISTRY.get(target) if type == 'manufacturing' else None
        self.progress = 0.0

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
