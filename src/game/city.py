import math
from src.game.pop import Pop
from src.game.jobs import FarmJob, ProductionJob, AdminJob

STOCKPILE_MAX = 20
STOCKPILE_PER_ADMIN = 20
GROWTH_NEEDED_FOR_NEW_POP = 100
POP_FOOD_CONSUMPTION = 1
GROWTH_FOOD_REQUIREMENT = .2
GROWTH_RATE = 2


class City:
    def __init__(self, row, col, name='City'):
        self.row = row
        self.col = col
        self.name = name
        self.pops = [Pop() for _ in range(20)]
        self.jobs = []
        self.owned_tiles = []
        self.food_stockpile = 0.0
        self.growth_progress = 0.0
        self.construction_progress = 0.0
        self.city_focus = 'Growth'

    @property
    def unassigned_pops(self):
        return sum(1 for p in self.pops if p.assigned_job is None)

    @property
    def total_farm_assigned(self):
        return sum(j.assigned for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    @property
    def total_farm_slots(self):
        return sum(j.slots for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    def _food_target(self):
        num_pops = len(self.pops)
        consumption = num_pops * POP_FOOD_CONSUMPTION
        min_stockpile = min(consumption, self._stockpile_max())
        food_needed_for_min_stockpile = min_stockpile - self.food_stockpile
        if self.city_focus == 'Production':
            growth_food = 0
        else:
            growth_food = num_pops * GROWTH_FOOD_REQUIREMENT
        return consumption + food_needed_for_min_stockpile + growth_food

    def _stockpile_max(self):
        admin_job = next((j for j in self.jobs if j.job_type == 'administrator'), None)
        admin_count = admin_job.assigned if admin_job else 0
        return admin_count * STOCKPILE_PER_ADMIN

    def _tile_farm_jobs(self):
        return [
            j
            for tile in sorted(self.owned_tiles, key=lambda t: t.city_distance or 0)
            for j in tile.jobs
            if j.job_type == 'farm'
        ]

    def rebalance_pops(self):
        admin_job = next((j for j in self.jobs if j.job_type == 'administrator'), None)
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        tile_farm_jobs = self._tile_farm_jobs()

        # Preserve player-set admin count before reset
        admin_count = admin_job.assigned if admin_job else 0
        if admin_count == 0 and admin_job and self.pops:
            admin_count = 1

        for pop in self.pops:
            pop.assigned_job = None
        for job in self.jobs:
            job.assigned = 0
        for j in tile_farm_jobs:
            j.assigned = 0

        # Admin first (player-controlled)
        if admin_job:
            count = 0
            for pop in self.pops:
                if count >= admin_count or admin_job.available_slots == 0:
                    break
                pop.assigned_job = admin_job
                admin_job.assigned += 1
                count += 1

        # Farm: fill nearest tiles first
        remaining_pops = len(self.pops) - (admin_job.assigned if admin_job else 0)
        total_farm_slots = sum(j.slots for j in tile_farm_jobs)
        if total_farm_slots > 0:
            if self.city_focus == 'Stockpile':
                pops_for_farm = min(remaining_pops, total_farm_slots)
            else:
                pops_for_farm = min(
                    math.ceil(self._food_target() / FarmJob.YIELD_PER_POP),
                    min(total_farm_slots, remaining_pops)
                )
            assigned_to_farm = 0
            for j in tile_farm_jobs:
                if assigned_to_farm >= pops_for_farm:
                    break
                for pop in self.pops:
                    if assigned_to_farm >= pops_for_farm:
                        break
                    if pop.assigned_job is None and j.available_slots > 0:
                        pop.assigned_job = j
                        j.assigned += 1
                        assigned_to_farm += 1

        # Rest to production
        if prod_job:
            for pop in self.pops:
                if pop.assigned_job is None and prod_job.available_slots > 0:
                    pop.assigned_job = prod_job
                    prod_job.assigned += 1

    def setup_jobs(self):
        if not any(j.job_type == 'administrator' for j in self.jobs):
            self.jobs.insert(0, AdminJob())
        if not any(j.job_type == 'production' for j in self.jobs):
            self.jobs.append(ProductionJob())
        self.rebalance_pops()

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
        self.rebalance_pops()
        num_pops = len(self.pops)
        log = []
        log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 1: total food production from tile farm jobs
        food = sum(j.food_yield() for tile in self.owned_tiles for j in tile.jobs if hasattr(j, 'food_yield'))
        log.insert(0, f"{self.name}: {food:.0f} food produced")

        # Step 2: basic consumption — 1 per pop, from production then stockpile
        needed = num_pops * POP_FOOD_CONSUMPTION
        from_production = min(food, needed)
        log.insert(0, f"{self.name}: {from_production:.0f} food consumed")
        food -= from_production
        self.food_stockpile = max(0.0, self.food_stockpile - (needed - from_production))

        # Step 3: replenish stockpile to minimum threshold
        min_stockpile = min(num_pops * POP_FOOD_CONSUMPTION, self._stockpile_max())
        if food > 0 and self.food_stockpile < min_stockpile:
            top_up = min(food, min_stockpile - self.food_stockpile)
            log.insert(0, f"{self.name}: {top_up:.0f} food added to stockpile")
            self.food_stockpile += top_up
            food -= top_up

        # Step 4: growth
        if food > 0:
            fed_pops = min(int(food // GROWTH_FOOD_REQUIREMENT), min(num_pops, self.food_stockpile / POP_FOOD_CONSUMPTION))
            log.insert(0, f"{self.name}: {fed_pops * GROWTH_FOOD_REQUIREMENT:.0f} additional food consumed")
            self.growth_progress += fed_pops * GROWTH_RATE
            log.insert(0, f"{self.name}: {fed_pops * GROWTH_RATE:.0f} added to growth bar")
            food -= fed_pops * GROWTH_FOOD_REQUIREMENT

        # Step 5: remaining food to stockpile
        self.food_stockpile = min(self.food_stockpile + food, self._stockpile_max())
        log.insert(0, f"{self.name}: {food:.0f} leftover food, added to stockpile")
        log.insert(0, f"{self.name}: {self.food_stockpile:.0f} food in stockpile")

        # Step 6: construction from laborers
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        if prod_job:
            self.construction_progress = min(self.construction_progress + prod_job.production_yield(), 1000)

        # Step 7: spawn new pops
        spawned = 0
        while self.growth_progress >= GROWTH_NEEDED_FOR_NEW_POP:
            self.growth_progress -= GROWTH_NEEDED_FOR_NEW_POP
            self.pops.append(Pop())
            spawned += 1
        if spawned:
            self.rebalance_pops()
            log.append(f"{self.name}: {spawned} new pop(s)! ({len(self.pops)} total)")

        return log
