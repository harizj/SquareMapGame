from src.game.pop import Pop
from src.game.jobs import FarmJob


class City:
    def __init__(self, row, col, name='City'):
        self.row = row
        self.col = col
        self.name = name
        self.pops = [Pop() for _ in range(5)]
        self.jobs = []
        self.food_stockpile = 0.0

    @property
    def unassigned_pops(self):
        return sum(1 for p in self.pops if p.assigned_job is None)

    def setup_jobs(self, river_tile_count):
        farm_slots = river_tile_count * 5
        existing = next((j for j in self.jobs if j.job_type == 'farm'), None)
        if existing:
            existing.slots = farm_slots
        else:
            self.jobs.append(FarmJob(farm_slots))

    def set_job_assignment(self, job, target):
        for pop in self.pops:
            if pop.assigned_job is job:
                pop.assigned_job = None
        job.assigned = 0
        count = 0
        for pop in self.pops:
            if count >= target:
                break
            if pop.assigned_job is None:
                pop.assigned_job = job
                job.assigned += 1
                count += 1

    def end_turn(self):
        for job in self.jobs:
            job.on_turn(self)
