from src.game.pop import Pop
from src.game.jobs import FarmJob

STOCKPILE_MAX = 20
GROWTH_NEEDED_FOR_NEW_POP = 100
POP_FOOD_CONSUMPTION = 1
GROWTH_FOOD_REQUIREMENT = .1
GROWTH_RATE = 2


class City:
    def __init__(self, row, col, name='City'):
        self.row = row
        self.col = col
        self.name = name
        self.pops = [Pop() for _ in range(20)]
        self.jobs = []
        self.food_stockpile = 0.0
        self.growth_progress = 0.0

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
        num_pops = len(self.pops)
        log = []
        log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 1: total food production from all jobs
        food = sum(job.food_yield() for job in self.jobs if hasattr(job, 'food_yield'))
        log.insert(0, f"{self.name}: {food:.0f} food produced")
        #log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 2: basic consumption — 100 per pop, from production then stockpile
        needed = num_pops * POP_FOOD_CONSUMPTION
        from_production = min(food, needed)
        log.insert(0, f"{self.name}: {from_production:.0f} food consumed")
        food -= from_production
        self.food_stockpile = max(0.0, self.food_stockpile - (needed - from_production))
        #log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 3: replenish stockpile to minimum threshold (100 × num_pops)
        min_stockpile = min(num_pops * POP_FOOD_CONSUMPTION, STOCKPILE_MAX)
        if food > 0 and self.food_stockpile < min_stockpile:
            top_up = min(food, min_stockpile - self.food_stockpile)
            log.insert(0, f"{self.name}: {top_up:.0f} food added to stockpile")
            self.food_stockpile += top_up
            #log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")
            food -= top_up

        # Step 4: growth — each pop may consume 10 extra food for +2 growth
        # capped at GROWTH_POP_CAP pops regardless of city size
        if food > 0:
            fed_pops = min(int(food // GROWTH_FOOD_REQUIREMENT), min(num_pops,self.food_stockpile/POP_FOOD_CONSUMPTION))
            log.insert(0, f"{self.name}: {fed_pops*GROWTH_FOOD_REQUIREMENT:.0f} additional food consumed")
            self.growth_progress += fed_pops * GROWTH_RATE
            log.insert(0, f"{self.name}: {fed_pops*GROWTH_RATE:.0f} added to growth bar")
            food -= fed_pops * GROWTH_FOOD_REQUIREMENT

        # Step 5: any remaining food to stockpile, capped at STOCKPILE_MAX
        self.food_stockpile = min(self.food_stockpile + food, STOCKPILE_MAX)
        log.insert(0, f"{self.name}: {food:.0f} leftover food, added to stockpile")
        log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 6: spawn new pops for every 100 growth accumulated
        while self.growth_progress >= GROWTH_NEEDED_FOR_NEW_POP:
            self.growth_progress -= GROWTH_NEEDED_FOR_NEW_POP
            new_pop = Pop()
            farm_job = next((j for j in self.jobs if j.job_type == 'farm' and j.available_slots > 0), None)
            if farm_job:
                new_pop.assigned_job = farm_job
                farm_job.assigned += 1
            self.pops.append(new_pop)
            log.append(f"{self.name}: new pop! ({len(self.pops)} total)")

        return log
