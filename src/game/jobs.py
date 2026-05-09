class Job:
    job_type = ''
    label = ''

    def __init__(self, slots=0):
        self.slots = slots
        self.assigned = 0

    @property
    def available_slots(self):
        return self.slots - self.assigned

    def assign(self, n):
        can = min(n, self.available_slots)
        self.assigned += can
        return can

    def on_turn(self, city):
        pass

    def yield_display(self):
        return ''


class FarmJob(Job):
    job_type = 'farm'
    label = 'Farm'
    YIELD_PER_POP = 1.3

    def __init__(self, slots=0):
        super().__init__(slots)

    def food_yield(self):
        return self.assigned * self.YIELD_PER_POP

    def yield_display(self):
        return f"{self.food_yield():.1f} food/turn"


class ProductionJob(Job):
    job_type = 'production'
    label = 'Production'

    def __init__(self):
        super().__init__(slots=100)
