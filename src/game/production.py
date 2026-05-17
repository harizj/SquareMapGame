PRODUCTION_CATEGORIES = ['extraction', 'manufacturing', 'construction']

PRODUCTION_SUBTYPES = {
    'extraction':    ['wood', 'iron'],
    'manufacturing': [],
    'construction':  [],
}


class ProductionTarget:
    def __init__(self):
        self.type = None
        self.target = None

    def set(self, type, target):
        self.type = type
        self.target = target

    def clear(self):
        self.type = None
        self.target = None

    @property
    def label(self):
        if self.type and self.target:
            return f"{self.target.capitalize()} ({self.type.capitalize()})"
        return "None"
