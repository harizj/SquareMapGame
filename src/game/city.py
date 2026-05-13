import bisect
import math
from src.game.pop import Pop
from src.game.jobs import FarmJob, ProductionJob, AdminJob, CaravanJob

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
        self.cumulative_farm_yield = [0.0]
        self.cumulative_farm_yield_net = [0.0]
        self.food_stockpile = 20.0
        self.growth_progress = 0.0
        self.construction_progress = 0.0
        self.city_focus = 'Growth'
        self.trade_routes = []
        self.food_allocated_to_consumption = 0.0
        self.food_allocated_to_min_stockpile = 0.0
        self.food_allocated_to_growth = 0.0
        self.food_allocated_to_stockpile = 0.0
        self.food_shortfall = 0.0
        self.growth_allocated = 0.0
        self.pending_pop_loss = 0.0

    @property
    def unassigned_pops(self):
        return sum(1 for p in self.pops if p.assigned_job is None)

    @property
    def total_farm_assigned(self):
        return sum(j.assigned for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    @property
    def total_farm_slots(self):
        return sum(j.slots for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    def _food_from_routes(self):
        """Net food change from all active (fully staffed) trade routes."""
        net = 0.0
        for route in self.trade_routes:
            if route.missing_caravans:
                continue
            if route.city_a is self:
                if route.export_material == 'food':
                    net -= route.export_amount
                if route.import_material == 'food':
                    net += route.import_amount
            else:
                if route.export_material == 'food':
                    net += route.export_amount
                if route.import_material == 'food':
                    net -= route.import_amount
        return net

    def _food_target(self):
        num_pops = len(self.pops)
        consumption = num_pops * POP_FOOD_CONSUMPTION
        min_stockpile = min(consumption, self._stockpile_max())
        food_needed_for_min_stockpile = min_stockpile - self.food_stockpile
        if self.city_focus == 'Production' or not self._space_for_new_pop():
            growth_food = 0
        else:
            growth_food = num_pops * GROWTH_FOOD_REQUIREMENT
        return consumption, food_needed_for_min_stockpile, growth_food

    def _stockpile_max(self):
        admin_job = next((j for j in self.jobs if j.job_type == 'administrator'), None)
        admin_count = admin_job.assigned if admin_job else 0
        return admin_count * STOCKPILE_PER_ADMIN

    def _sorted_tile_farm_jobs(self):
        """Tile farm jobs sorted nearest-first (matches cumulative_farm_yield order)."""
        return [
            (tile, j)
            for tile in sorted(self.owned_tiles, key=lambda t: t.city_distance or 0)
            for j in tile.jobs
            if j.job_type == 'farm'
        ]

    def _build_cumulative_farm_yield(self):
        """Precompute cumulative food yield for n pops assigned to the best available slots."""
        self.cumulative_farm_yield = [0.0]
        total = 0.0
        for tile in sorted(self.owned_tiles, key=lambda t: t.city_distance or 0):
            for j in tile.jobs:
                if j.job_type == 'farm':
                    for _ in range(j.slots):
                        total += tile.farm_yield
                        self.cumulative_farm_yield.append(total)

    def update_cumulative_farm_yield_net(self):
        net_food_from_routes = self._food_from_routes()
        print('Net food from routes:',net_food_from_routes)
        self.cumulative_farm_yield_net = [v + net_food_from_routes for v in self.cumulative_farm_yield]

    def _food_produced(self):
        food = sum(
            j.assigned * tile.farm_yield
            for tile in self.owned_tiles
            for j in tile.jobs
            if j.job_type == 'farm'
        )
        return food + self._food_from_routes()

    def _update_food_allocations(self):
        consumption, food_needed_for_min_stockpile, growth_food = self._food_target()
        remaining = self._food_produced()

        if self.food_stockpile + remaining - consumption < 0:
            self.food_allocated_to_consumption = self.food_stockpile + remaining 
            self.pending_pop_loss = math.ceil(-(self.food_stockpile + remaining - consumption))
        else:
            self.food_allocated_to_consumption = consumption
            self.pending_pop_loss = 0.0

        #self.food_shortfall = max(0.0, consumption - self.food_allocated_to_consumption)
        remaining -= self.food_allocated_to_consumption

        # if self.food_shortfall > 0:
        #     print(f"{math.ceil(self.food_shortfall)} pops in {self.name} will starve this turn!")

        alloc_stockpile = max(0.0, food_needed_for_min_stockpile)
        self.food_allocated_to_min_stockpile = min(remaining, alloc_stockpile)
        remaining -= self.food_allocated_to_min_stockpile

        # if self.food_allocated_to_min_stockpile < alloc_stockpile:
        #     print(f"Not enough food for stockpile in {self.name}")

        if self._space_for_new_pop():
            self.food_allocated_to_growth = min(remaining, growth_food)
            remaining -= self.food_allocated_to_growth
            self.growth_allocated = (self.food_allocated_to_growth / GROWTH_FOOD_REQUIREMENT) * GROWTH_RATE
        else:
            self.food_allocated_to_growth = 0
            self.growth_allocated = 0

        self.food_allocated_to_stockpile = remaining + self.food_allocated_to_min_stockpile
        # if self.food_stockpile + self.food_allocated_to_stockpile < 0:
        #     self.pending_pop_loss = math.ceil(-(self.food_stockpile + self.food_allocated_to_stockpile))
        #     self.food_allocated_to_stockpile = - self.food_stockpile

    def _get_pops_assigned_to_routes(self):
        total = 0
        for route in self.trade_routes:
            job = route.caravan_job_a if route.city_a is self else route.caravan_job_b
            if job is not None:
                total += job.assigned
        return total

    def _space_for_new_pop(self):
        max_yield = self.cumulative_farm_yield_net[-1]
        return len(self.pops) + 1 <= max_yield

    # No longer used
    def _food_shortfall(self):
        stockpile_used = min(self.food_shortfall, self.food_stockpile)
        self.food_stockpile -= stockpile_used
        remaining_shortfall = self.food_shortfall - stockpile_used
        if remaining_shortfall > 0:
            to_remove = min(math.ceil(remaining_shortfall), len(self.pops))
            del self.pops[:to_remove]
            self.growth_progress = 0.0

    def _collect_caravan_jobs(self):
        for route in self.trade_routes:
            job = route.caravan_job_a if route.city_a is self else route.caravan_job_b
            if job is not None:
                route.missing_caravans = False
        jobs = []
        for route in self.trade_routes:
            job = route.caravan_job_a if route.city_a is self else route.caravan_job_b
            if job is not None:
                job.assigned = 0
                jobs.append(job)
        return jobs, sum(j.slots for j in jobs)

    def _pop_loss_from_locked_jobs(self, locked_jobs):
        farm_pops = min(max(0, len(self.pops) - locked_jobs), len(self.cumulative_farm_yield_net) - 1)
        max_food = self.cumulative_farm_yield_net[farm_pops]
        consumption = len(self.pops) * POP_FOOD_CONSUMPTION
        return consumption > max_food + self.food_stockpile


    def rebalance_pops(self):
        admin_job = next((j for j in self.jobs if j.job_type == 'administrator'), None)
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        tile_farm_jobs = self._sorted_tile_farm_jobs()

        # Preserve player-set admin count before reset
        admin_count = admin_job.assigned if admin_job else 0
        if admin_count == 0 and admin_job and self.pops:
            admin_count = 1

        for pop in self.pops:
            pop.assigned_job = None
        for job in self.jobs:
            job.assigned = 0
        for _, j in tile_farm_jobs:
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
        admin_assigned = admin_job.assigned if admin_job else 0

        # Caravans (locked to trade routes)
        route_caravan_jobs, total_caravan_slots = self._collect_caravan_jobs()

        while total_caravan_slots > 0 and self._pop_loss_from_locked_jobs(total_caravan_slots + admin_assigned):
            route_to_drop = next(
                (r for r in reversed(self.trade_routes)
                 if (r.city_a is self and r.caravan_job_a is not None) or
                    (r.city_b is self and r.caravan_job_b is not None)),
                None
            )
            if route_to_drop is None:
                break
            route_to_drop.city_a.trade_routes.remove(route_to_drop)
            route_to_drop.city_b.trade_routes.remove(route_to_drop)
            route_to_drop.city_a.update_cumulative_farm_yield_net()
            route_to_drop.city_b.update_cumulative_farm_yield_net()
            dropped_job = route_to_drop.caravan_job_a if route_to_drop.city_a is self else route_to_drop.caravan_job_b
            if dropped_job in route_caravan_jobs:
                route_caravan_jobs.remove(dropped_job)
            total_caravan_slots = sum(j.slots for j in route_caravan_jobs)

        caravan_assigned = 0
        for job in route_caravan_jobs:
            for pop in self.pops:
                if job.available_slots == 0:
                    break
                if pop.assigned_job is None:
                    pop.assigned_job = job
                    job.assigned += 1
                    caravan_assigned += 1
            if job.assigned < job.slots:
                job.trade_route.missing_caravans = True
                print('Missing caravan!')

        if any(r.missing_caravans for r in self.trade_routes):
            self.update_cumulative_farm_yield_net()

        if total_caravan_slots > 0:
            if caravan_assigned < total_caravan_slots:
                print(f"{self.name}: only {caravan_assigned}/{total_caravan_slots} caravan slots filled — not enough pops")
            else:
                print(f"{self.name}: all {total_caravan_slots} caravan slots filled")
   
        # Farm: use cumulative yield list to find minimum pops needed
        remaining_pops = len(self.pops) - admin_assigned - caravan_assigned
        total_farm_slots = len(self.cumulative_farm_yield) - 1
        if total_farm_slots > 0:
            if self.city_focus == 'Stockpile':
                pops_for_farm = min(remaining_pops, total_farm_slots)
            else:
                consumption, food_needed_for_min_stockpile, growth_food = self._food_target()
                food_target = consumption + food_needed_for_min_stockpile + growth_food
                pops_for_farm = bisect.bisect_left(self.cumulative_farm_yield_net, food_target)
                pops_for_farm = min(pops_for_farm, total_farm_slots, remaining_pops)

            assigned_to_farm = 0
            for tile, j in tile_farm_jobs:
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

        self._update_food_allocations()

    def setup_jobs(self):
        if not any(j.job_type == 'administrator' for j in self.jobs):
            self.jobs.insert(0, AdminJob())
        if not any(j.job_type == 'production' for j in self.jobs):
            self.jobs.append(ProductionJob())
        self._build_cumulative_farm_yield()
        self.update_cumulative_farm_yield_net()
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

        # Drop routes that couldn't be staffed
        missing = [r for r in self.trade_routes if r.missing_caravans]
        if missing:
            for route in missing:
                route.city_a.trade_routes.remove(route)
                route.city_b.trade_routes.remove(route)
                route.city_a.update_cumulative_farm_yield_net()
                route.city_b.update_cumulative_farm_yield_net()
                print(f"{self.name}: trade route to {(route.city_b if route.city_a is self else route.city_a).name} cancelled — not enough caravans")
            self.rebalance_pops()

        log = []

        # print(f"\n=== {self.name} END TURN ===")
        # print(f"  pops={len(self.pops)}  stockpile={self.food_stockpile:.1f}/{self._stockpile_max():.0f}  growth={self.growth_progress:.1f}/{GROWTH_NEEDED_FOR_NEW_POP}")
        # print(f"  produced={self._food_produced():.1f}  consumption={self.food_allocated_to_consumption:.1f}  shortfall={self.food_shortfall:.1f}")
        # print(f"  [after rebalance] alloc_consumption={self.food_allocated_to_consumption:.1f}  alloc_min_stockpile={self.food_allocated_to_min_stockpile:.1f}  alloc_growth={self.food_allocated_to_growth:.1f}  alloc_surplus={self.food_allocated_to_stockpile:.1f}  growth_allocated={self.growth_allocated:.1f}")

        # Step 1: stockpile replenishment
        self.food_stockpile = min(self.food_stockpile + self.food_allocated_to_stockpile, self._stockpile_max())

        # Step 2: growth
        self.growth_progress += self.growth_allocated
        if self.growth_allocated > 0:
            log.append(f"{self.name}: {self.growth_allocated:.0f} added to growth bar")

        # Step 3: starvation if shortfall exceeded stockpile
        if self.pending_pop_loss > 0:
            del self.pops[:self.pending_pop_loss]
            self.growth_progress = 0.0
            self.pending_pop_loss = 0.0
            # print(f"  [shortfall] {self.food_shortfall:.1f} shortfall, stockpile={self.food_stockpile:.1f}, pops={len(self.pops)}")
            #self._food_shortfall()
            # print(f"  [shortfall] after -> stockpile={self.food_stockpile:.1f}, pops={len(self.pops)}")

        # Step 4: construction from laborers
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        if prod_job:
            self.construction_progress = min(self.construction_progress + prod_job.production_yield(), 1000)

        # Step 5: spawn new pops
        spawned = 0
        if self.growth_progress >= GROWTH_NEEDED_FOR_NEW_POP:
            if self._space_for_new_pop():
                self.growth_progress -= GROWTH_NEEDED_FOR_NEW_POP
                self.pops.append(Pop())
                spawned += 1
        if spawned:
            self.rebalance_pops()
            log.append(f"{self.name}: {spawned} new pop(s)! ({len(self.pops)} total)")
            # print(f"  [spawn] +{spawned} pop(s), total={len(self.pops)}")

        self.rebalance_pops()
        # print(f"  === end: stockpile={self.food_stockpile:.1f}  growth={self.growth_progress:.1f}  pops={len(self.pops)} ===")
        return log
