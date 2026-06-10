import bisect
import math
from src.game.pop import Pop
from src.game.jobs import FarmJob, ProductionJob, CaravanJob, JobQueue
from src.game.constants import POP_FOOD_CONSUMPTION, FOOD_YIELD, GAME_SCALE

STOCKPILE_MAX = 20
GROWTH_NEEDED_FOR_NEW_POP = 100
GROWTH_FOOD_REQUIREMENT = .20
GROWTH_RATE = 10.0
GROWTH_SLOWDOWN = GROWTH_RATE / 20.0
POPS_PER_GROWTH_SLOWDOWN = 5*GAME_SCALE
GROWTH_SLOWDOWN_POP_THRESHOLD = 20*GAME_SCALE
# TURNS_WITH_STOCKPILE_LOSS_THRESHOLD = 5
BASE_WOOD_EXTRACTION_MODIFIER = 2
BASE_IRON_EXTRACTION_MODIFIER = 2
FARM_YIELD = FOOD_YIELD
WORKSHOP_WOOD_CONSUMPTION = 0.5
WORKSHOP_PRODUCTION_MODIFIER = 1.5
WORKCAMP_EXTRACTION_MODIFIER = 1.5
STOCKPILE_JOB_YIELD = 1.35


from src.game.production import ProductionTarget
from src.game.tile import DEPOSIT_STARTING_WOOD, DEPOSIT_STARTING_IRON, DEPOSIT_STARTING_STONE

_DEPOSIT_STARTING = {'wood': DEPOSIT_STARTING_WOOD, 'iron': DEPOSIT_STARTING_IRON, 'stone': DEPOSIT_STARTING_STONE}


class City:
    def __init__(self, row, col, name='City', faction=None, population=20):
        self.row = row
        self.col = col
        self.name = name
        self.faction = faction
        self.pops = [Pop() for _ in range(population)]
        self.unit_groups = []
        self.jobs = []
        self.owned_tiles = []
        self.cumulative_farm_yield = [0.0]
        self.cumulative_farm_yield_net = [0.0]
        self.food_stockpile = population
        self.growth_progress = 0.0
        self.construction_progress = 0.0
        self.city_focus = 'Growth'
        self.growth_halted = False
        self.gates_closed = False
        self.trade_routes = []
        self.food_allocated_to_units = 0.0
        self.food_allocated_to_consumption = 0.0
        self.food_allocated_to_min_stockpile = 0.0
        self.food_allocated_to_growth = 0.0
        self.food_allocated_to_stockpile = 0.0
        self.food_shortfall = 0.0
        self.growth_allocated = 0.0
        self.pending_pop_loss = 0
        # self.turns_with_stockpile_loss = 0.0
        self.tile = None
        self.production_target = ProductionTarget()
        self.production_yield = 0.0
        self.production_progress = 0.0
        self.production_complete = None
        self.extraction_tile = None
        self.selected_extraction_tile = None
        self.resources_allocated_to_production = {}
        self.production_limited_by = None
        self.production_workers = 0
        self.food_pops = 0
        self.non_food_pops = 0
        self.locked_pops = 0
        self.free_pops = 0
        self.job_queue = [JobQueue('stockpile', count=1)]
        self.pops_allocated_to_growth = 0
        self.pops_allocated_to_production = 0
        self.pops_allocated_to_stockpile = 0
        self.focus_unassigned_pops = 0
        self.remaining_free_pops = 0

    @property
    def unassigned_pops(self):
        return sum(1 for p in self.pops if p.assigned_job is None)

    @property
    def total_farm_assigned(self):
        return sum(j.assigned for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    @property
    def total_farm_slots(self):
        return sum(j.slots for tile in self.owned_tiles for j in tile.jobs if j.job_type == 'farm')

    @property
    def food_pop_limit(self):
        return self.total_farm_slots

    @property
    def food_pop_min(self):
        return math.ceil(self._get_population() / FARM_YIELD)

    @property
    def max_pops(self):
        return math.floor(self.food_pop_limit * FARM_YIELD)

    @property
    def non_food_pop_limit(self):
        return self.max_pops - self.food_pop_limit

    def _get_population(self):
        return len(self.pops)

    def _get_unit_consumption(self):
        return sum(g.consumption_per_turn() for g in self.unit_groups)

    def _food_from_routes(self):
        """Net food change from all active (fully staffed) trade routes."""
        net = 0.0
        for route in self.trade_routes:
            if route.missing_caravans or not route.established:
                continue
            if route.city_a is self:
                if route.export_resource == 'food':
                    net -= route.max_amount
                if route.import_resource == 'food':
                    net += route.import_amount
            else:
                if route.export_resource == 'food':
                    net += route.max_amount
                if route.import_resource == 'food':
                    net -= route.import_amount
        return net

    def _food_target(self):
        num_pops = self._get_population()
        pop_consumption = num_pops * POP_FOOD_CONSUMPTION
        unit_consumption = self._get_unit_consumption()
        min_stockpile = min(pop_consumption, self._stockpile_max())
        food_needed_for_min_stockpile = max(0,min_stockpile - self.food_stockpile)
        if self.city_focus == 'Production' or not self._space_for_new_pop():
            growth_food = 0
        else:
            growth_food = num_pops * GROWTH_FOOD_REQUIREMENT
        # print('stockpile_max',self._stockpile_max())
        # print('min_stockpile',min_stockpile)
        # print('stockpile',self.food_stockpile)
        # print('unit_consumption',unit_consumption)
        # print('pop_consumption',pop_consumption)
        # print('food_needed_for_min_stockpile',food_needed_for_min_stockpile)
        # print('growth_food',growth_food)
        return unit_consumption, pop_consumption, food_needed_for_min_stockpile, growth_food

    def change_faction(self, new_faction):
        self.faction = new_faction

    def get_city_color(self, color_type):
        if self.faction:
            return self.faction.colors[color_type]
        return None

    def _stockpile_max(self):
        return 4 * self._get_population()

    @property
    def growth_progress_display(self):
        return (self._get_population() * 100 + self.growth_progress) % 400

    def _stockpile_decay(self):
        pop = self._get_population()
        if pop == 0:
            return 0.0
        #return round(self.food_stockpile / pop, 1)
        return self.food_stockpile / pop

    def has_job_in_queue(self, job_type):
        return any(entry.job_type == job_type for entry in self.job_queue)

    def has_resource(self, resource):
        return self.tile is not None and self.tile.resource_stockpiles.get(resource, 0) > 0

    def has_deposit(self, resource):
        return any(resource in t.resource_deposits for t in self.owned_tiles if not t.is_disrupted)

    def has_accessible_deposit(self, resource):
        return any(
            resource in t.resource_deposits and
            not (resource == 'iron' and 'forest' in t.terrain_features)
            for t in self.owned_tiles if not t.is_disrupted
        )

    def get_eligible_extraction_tiles(self, resource):
        return [
            t for t in self.owned_tiles
            if not t.is_disrupted
            and resource in t.resource_deposits
            and not (resource == 'iron' and 'forest' in t.terrain_features)
        ]

    def update_production_bar(self):
        pt = self.production_target
        if not pt.type:
            self.production_complete = None
            self.production_progress = 0.0
            return
        if pt.type == 'extraction':
            if not pt.target:
                self.production_complete = None
                self.production_progress = 0.0
                return
            if self.extraction_tile:
                current = self.extraction_tile.resource_deposits.get(pt.target, 0)
                starting = _DEPOSIT_STARTING.get(pt.target, 1)
                self.production_complete = float(starting)
                self.production_progress = starting - current
            else:
                self.production_complete = None
                self.production_progress = 0.0
        elif pt.type == 'manufacturing':
            if pt.target_item:
                self.production_complete = float(pt.target_item.production_needed)
                self.production_progress = pt.progress
            else:
                self.production_complete = None
                self.production_progress = 0.0
        elif pt.type == 'construction':
            if pt.target_building:
                self.production_complete = float(pt.target_building.production_needed)
                self.production_progress = pt.progress
            else:
                self.production_complete = None
                self.production_progress = 0.0

    def check_additional_resources(self, resource):
        if not self.has_deposit(resource):
            self.production_target.clear()
            self.selected_extraction_tile = None

    def _move_resource(self, tile, resource, amount):
        current = tile.resource_stockpiles.get(resource, 0)
        tile.resource_stockpiles[resource] = max(0, current + amount)
        if tile.resource_stockpiles[resource] == 0:
            tile.resource_stockpiles.pop(resource, None)

    def take_resource(self, resource, amount):
        """Remove up to amount of resource from stockpile, returning what was taken."""
        if resource == 'food':
            taken = min(amount, self.food_stockpile)
            self.food_stockpile -= taken
            return taken
        if self.tile is None:
            return 0.0
        available = self.tile.resource_stockpiles.get(resource, 0.0)
        taken = min(amount, available)
        if taken > 0:
            self._move_resource(self.tile, resource, -taken)
        return taken

    def _process_resource_routes(self):
        if not self.tile:
            return
        for route in self.trade_routes:
            if not route.established or route.missing_caravans:
                continue
            if route.city_a is self:
                if route.export_resource and route.export_resource != 'food':
                    self._move_resource(self.tile, route.export_resource, -route.export_amount)
                    self._move_resource(route.dest_tile, route.export_resource, route.export_amount)
                if route.import_resource and route.import_resource != 'food':
                    self._move_resource(route.dest_tile, route.import_resource, -route.import_amount)
                    self._move_resource(self.tile, route.import_resource, route.import_amount)

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
        # print('Net food from routes:',net_food_from_routes)
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
        unit_consumption, pop_consumption, food_needed_for_min_stockpile, growth_food = self._food_target()
        remaining = self._food_produced()

        self.food_allocated_to_units = min(unit_consumption, max(0.0, self.food_stockpile + remaining))
        remaining -= self.food_allocated_to_units
        # print(f"[{self.name}] rebalance: food_allocated_to_units={self.food_allocated_to_units} unit_consumption={unit_consumption} groups={len(self.unit_groups)}")
        for g in self.unit_groups:
            g.food_allocated_from_city = (self.food_allocated_to_units * g.consumption_per_turn() / unit_consumption) if unit_consumption > 0 else 0.0
            g.allocate_food()

        _pop_loss_key = ('pending_pop_loss_city', self.name)
        if self.food_stockpile + remaining - pop_consumption < 0:
            self.food_allocated_to_consumption = self.food_stockpile + remaining
            self.pending_pop_loss = math.ceil(-(self.food_stockpile + remaining - pop_consumption))
            if self.faction:
                self.faction.notification_log.add(
                    f"{self.pending_pop_loss} pops don't have food in {self.name}!",
                    key=_pop_loss_key,
                    priority='Medium',
                )
        else:
            self.food_allocated_to_consumption = pop_consumption
            self.pending_pop_loss = 0
            if self.faction:
                self.faction.notification_log.remove(_pop_loss_key)

        #self.food_shortfall = max(0.0, consumption - self.food_allocated_to_consumption)
        remaining -= self.food_allocated_to_consumption

        # if self.food_shortfall > 0:
        #     print(f"{math.ceil(self.food_shortfall)} pops in {self.name} will starve this turn!")

        # alloc_stockpile = max(0.0, food_needed_for_min_stockpile)
        # self.food_allocated_to_min_stockpile = min(remaining, alloc_stockpile)
        # remaining -= self.food_allocated_to_min_stockpile

        # if self.food_allocated_to_min_stockpile < alloc_stockpile:
        #     print(f"Not enough food for stockpile in {self.name}")
        self.food_allocated_to_growth = 0
        self.growth_allocated = self.pops_allocated_to_growth * GROWTH_RATE
        # if self._space_for_new_pop():
        #     self.food_allocated_to_growth = min(remaining, growth_food)
        #     remaining -= self.food_allocated_to_growth
        #     self.growth_allocated = (self.food_allocated_to_growth / GROWTH_FOOD_REQUIREMENT) * self._effective_growth_rate()
        # else:
        #     self.food_allocated_to_growth = 0
        #     self.growth_allocated = 0
        #     self.growth_progress = 0
        if remaining < 0:
            self.food_allocated_to_stockpile = remaining
        else:
            self.food_allocated_to_stockpile = 0

        self.food_allocated_to_stockpile += self.pops_allocated_to_stockpile * STOCKPILE_JOB_YIELD
        self.food_allocated_to_stockpile -= self._stockpile_decay()
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
        if self.growth_halted:
            return False
        max_yield = self.cumulative_farm_yield_net[-1]
        return self._get_population() + 2 <= max_yield

    def _effective_growth_rate(self):
        if self._get_population() < GROWTH_SLOWDOWN_POP_THRESHOLD:
            return GROWTH_RATE
        steps = (self._get_population() - GROWTH_SLOWDOWN_POP_THRESHOLD) // POPS_PER_GROWTH_SLOWDOWN + 1
        return max(0.0, GROWTH_RATE - steps * GROWTH_SLOWDOWN)

    # No longer used
    def _food_shortfall(self):
        stockpile_used = min(self.food_shortfall, self.food_stockpile)
        self.food_stockpile -= stockpile_used
        remaining_shortfall = self.food_shortfall - stockpile_used
        if remaining_shortfall > 0:
            to_remove = min(math.ceil(remaining_shortfall), self._get_population())
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
        farm_pops = min(max(0, self._get_population() - locked_jobs), len(self.cumulative_farm_yield_net) - 1)
        max_food = self.cumulative_farm_yield_net[farm_pops]
        consumption = self._get_population() * POP_FOOD_CONSUMPTION + self._get_unit_consumption()
        return consumption > max_food + self.food_stockpile


    def rebalance_pops(self):
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        tile_farm_jobs = self._sorted_tile_farm_jobs()

        for pop in self.pops:
            pop.assigned_job = None
        for job in self.jobs:
            job.assigned = 0
        for _, j in tile_farm_jobs:
            j.assigned = 0

        # Caravans (locked to trade routes)
        route_caravan_jobs, total_caravan_slots = self._collect_caravan_jobs()

        food_caravan_jobs = [
            r.caravan_job_a for r in self.trade_routes
            if r.city_a is self and
               r.caravan_job_a is not None and r.export_resource == 'food'
        ]
        food_pop_slots = sum(j.slots for j in food_caravan_jobs)

        while food_pop_slots > 0 and self._pop_loss_from_locked_jobs(total_caravan_slots):
            route_to_drop = next(
                (r for r in reversed(self.trade_routes)
                 if r.city_a is self and r.caravan_job_a is not None and r.export_resource == 'food' and not r.tether),
                None
            )

            if route_to_drop is None:
                break
            # print('Route dropped due to pending pop loss!')
            route_to_drop.detach()
            dropped_job = route_to_drop.caravan_job_a
            if dropped_job in route_caravan_jobs:
                route_caravan_jobs.remove(dropped_job)
            if dropped_job in food_caravan_jobs:
                food_caravan_jobs.remove(dropped_job)
            total_caravan_slots = sum(j.slots for j in route_caravan_jobs)
            food_pop_slots = sum(j.slots for j in food_caravan_jobs)

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
                # print('Missing caravan!')

        if any(r.missing_caravans for r in self.trade_routes):
            self.update_cumulative_farm_yield_net()

        # Farm: use cumulative yield list to find minimum pops needed
        remaining_pops = self._get_population() - caravan_assigned
        total_farm_slots = len(self.cumulative_farm_yield) - 1
        # print('Farm slots',total_farm_slots)
        # print('Remaining pops',remaining_pops)
        if total_farm_slots > 0:
            unit_consumption, pop_consumption, food_needed_for_min_stockpile, growth_food = self._food_target()
            pops_for_farm = bisect.bisect_left(self.cumulative_farm_yield_net, unit_consumption + pop_consumption)
            pops_for_farm = min(pops_for_farm, total_farm_slots, remaining_pops)
            # print('pops_for_farm',pops_for_farm)

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

        self.food_pops = assigned_to_farm

        self.locked_pops = caravan_assigned if route_caravan_jobs else 0
        self.free_pops = remaining_pops - assigned_to_farm
        self.pops_allocated_to_growth = 0
        self.pops_allocated_to_production = 0
        self.pops_allocated_to_stockpile = 0

        # Job queue: allocate in priority order, track how many each entry receives
        free_pops = self.free_pops
        for entry in self.job_queue:
            want = min(entry.count, free_pops)
            if want <= 0:
                entry.filled = 0
                continue
            given = 0
            if entry.job_type == 'production':
                if prod_job:
                    for pop in self.pops:
                        if given >= want:
                            break
                        if pop.assigned_job is None and prod_job.available_slots > 0:
                            pop.assigned_job = prod_job
                            prod_job.assigned += 1
                            given += 1
                            self.pops_allocated_to_production += 1
            elif entry.job_type == 'growth':  # growth or stockpile → extra farm pops
                for _, j in tile_farm_jobs:
                    if given >= want:
                        break
                    for pop in self.pops:
                        if given >= want:
                            break
                        if pop.assigned_job is None and j.available_slots > 0:
                            pop.assigned_job = j
                            j.assigned += 1
                            given += 1
                            self.pops_allocated_to_growth += 1
            elif entry.job_type == 'stockpile':  # growth or stockpile → extra farm pops
                for _, j in tile_farm_jobs:
                    if given >= want:
                        break
                    for pop in self.pops:
                        if given >= want:
                            break
                        if pop.assigned_job is None and j.available_slots > 0:
                            pop.assigned_job = j
                            j.assigned += 1
                            given += 1
                            self.pops_allocated_to_stockpile += 1
            entry.filled = given
            free_pops -= given
        self.remaining_free_pops = free_pops

        # City focus: remaining free pops go to the focus destination
        focus_assigned = 0
        if self.city_focus == 'Production':
            if prod_job:
                for pop in self.pops:
                    if pop.assigned_job is None and prod_job.available_slots > 0:
                        pop.assigned_job = prod_job
                        prod_job.assigned += 1
                        focus_assigned += 1
        else:  # Growth or Stockpile → farm
            for _, j in tile_farm_jobs:
                for pop in self.pops:
                    if pop.assigned_job is None and j.available_slots > 0:
                        pop.assigned_job = j
                        j.assigned += 1
                        focus_assigned += 1
                        if self.city_focus == 'Growth':
                            self.pops_allocated_to_growth += 1
                        if self.city_focus == 'Stockpile':
                            self.pops_allocated_to_stockpile += 1
        self.focus_unassigned_pops = free_pops - focus_assigned

        _notif_key = ('not_enough_farm_slots', self.name)
        if self.focus_unassigned_pops > 0 and self.city_focus != 'Production':
            if self.faction:
                self.faction.notification_log.add(f"Not enough farm slots in {self.name}!", key=_notif_key, priority='High')
        else:
            if self.faction:
                self.faction.notification_log.remove(_notif_key)

        if self.focus_unassigned_pops > 0 and self.city_focus != 'Production':
            job_type = self.city_focus.lower()
            existing = next((e for e in self.job_queue if e.job_type == job_type), None)
            if existing:
                existing.count += self.remaining_free_pops
            else:
                self.job_queue.append(JobQueue(job_type, count=self.remaining_free_pops))
            self.city_focus = 'Production'
            self.rebalance_pops()
            return

        self.non_food_pops = self._get_population() - self.food_pops

        # Production yield
        self.production_yield = 0.0
        self.production_workers = prod_job.assigned if prod_job else 0
        _prod_notif_key = ('no_workers_for_production', self.name)
        if self.faction:
            if self.production_target.type and self.production_workers == 0:
                self.faction.notification_log.add(f"No workers assigned to production job in {self.name}!", key=_prod_notif_key, priority='High')
            else:
                self.faction.notification_log.remove(_prod_notif_key)
        self.resources_allocated_to_production = {}
        self.production_limited_by = None
        if self.extraction_tile:
            self.extraction_tile.clear_extraction_job()
        self.extraction_tile = None
        # pt = self.production_target
        # print(f"[extraction] {self.name} rebalance_pops: prod_job={prod_job} prod_job.assigned={prod_job.assigned if prod_job else 'N/A'} target={pt.type}/{pt.target}")
        # if prod_job and prod_job.assigned == 0:
        #     pt.clear()
        has_workcamp = self.tile and self.tile.building_list.get('workcamp', 0) > 0
        has_workshop = self.tile and self.tile.building_list.get('workshop', 0) > 0
        if prod_job and prod_job.assigned > 0:
            self.production_yield = prod_job.assigned
            pt = self.production_target
            if pt.type == 'extraction' and pt.target:
                if has_workcamp:
                    self.production_yield *= WORKCAMP_EXTRACTION_MODIFIER
                sel = self.selected_extraction_tile
                eligible = self.get_eligible_extraction_tiles(pt.target)
                if sel is not None and sel in eligible:
                    chosen = sel
                else:
                    deposit_tiles = sorted(eligible, key=lambda t: t.extraction_yield, reverse=True)
                    chosen = deposit_tiles[0] if deposit_tiles else None
                if chosen:
                    self.extraction_tile = chosen
                    self.extraction_tile.set_extraction_job(pt.target)
                    _modifiers = {'wood': BASE_WOOD_EXTRACTION_MODIFIER, 'iron': BASE_IRON_EXTRACTION_MODIFIER}
                    _modifier = _modifiers.get(pt.target, 1.0)
                    self.production_yield = self.production_yield * self.extraction_tile.extraction_yield * _modifier
                    # print(f"[extraction] {self.name}: extraction_tile=({self.extraction_tile.row},{self.extraction_tile.col}) production_yield={self.production_yield:.2f}")
                else:
                    print(f"[extraction] {self.name}: no deposit tiles found for {pt.target}")
            elif pt.type == 'manufacturing' and pt.target_item:
                if has_workshop:
                    work_done = prod_job.assigned * WORKSHOP_PRODUCTION_MODIFIER
                else:
                    work_done = prod_job.assigned
                item = pt.target_item
                if self.tile:
                    for resource, cost in item.resource_cost.items():
                        if resource == 'wood' and has_workshop:
                            rate = WORKSHOP_WOOD_CONSUMPTION + cost / item.production_needed
                        else:
                            rate = cost / item.production_needed
                        available = self.tile.resource_stockpiles.get(resource, 0.0)
                        resource_limit = available / rate if rate > 0 else work_done
                        if resource_limit < work_done:
                            work_done = resource_limit
                            self.production_limited_by = resource
                work_done = max(0.0, work_done)
                self.production_yield = work_done
                for resource, cost in item.resource_cost.items():
                    if resource == 'wood' and has_workshop:
                        rate = WORKSHOP_WOOD_CONSUMPTION + cost / item.production_needed
                    else:
                        rate = cost / item.production_needed
                    self.resources_allocated_to_production[resource] = work_done * rate
            elif pt.type == 'construction' and pt.target_building:
                building = pt.target_building
                if has_workshop:
                    work_done = prod_job.assigned * WORKSHOP_PRODUCTION_MODIFIER
                else:
                    work_done = prod_job.assigned
                if self.tile:
                    for resource, cost in building.resource_cost.items():
                        if resource == 'wood' and has_workshop:
                            rate = WORKSHOP_WOOD_CONSUMPTION + cost / building.production_needed
                        else:
                            rate = cost / building.production_needed
                        available = self.tile.resource_stockpiles.get(resource, 0.0)
                        resource_limit = available / rate if rate > 0 else work_done
                        if resource_limit < work_done:
                            work_done = resource_limit
                            self.production_limited_by = resource
                work_done = max(0.0, work_done)
                self.production_yield = work_done
                for resource, cost in building.resource_cost.items():
                    if resource == 'wood' and has_workshop:
                        rate = WORKSHOP_WOOD_CONSUMPTION + cost / building.production_needed
                    else:
                        rate = cost / building.production_needed
                    self.resources_allocated_to_production[resource] = work_done * rate

        self.update_production_bar()

        _limited_key = ('production_limited_by', self.name)
        if self.faction:
            if self.production_limited_by:
                self.faction.notification_log.add(
                    f"Production in {self.name} limited by {self.production_limited_by}!",
                    key=_limited_key,
                    priority='High',
                )
            else:
                self.faction.notification_log.remove(_limited_key)

        self._update_food_allocations()

    def setup_jobs(self):
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
                other_name = route.destination_name if route.city_a is self else route.city_a.name
                route.detach()
                # print(f"{self.name}: trade route to {other_name} cancelled — not enough caravans")
            self.rebalance_pops()

        log = []

        # print(f"\n=== {self.name} END TURN ===")
        # print(f"  pops={self._get_population()}  stockpile={self.food_stockpile:.1f}/{self._stockpile_max():.0f}  growth={self.growth_progress:.1f}/{GROWTH_NEEDED_FOR_NEW_POP}")
        # print(f"  produced={self._food_produced():.1f}  consumption={self.food_allocated_to_consumption:.1f}  shortfall={self.food_shortfall:.1f}")
        # print(f"  [after rebalance] alloc_consumption={self.food_allocated_to_consumption:.1f}  alloc_min_stockpile={self.food_allocated_to_min_stockpile:.1f}  alloc_growth={self.food_allocated_to_growth:.1f}  alloc_surplus={self.food_allocated_to_stockpile:.1f}  growth_allocated={self.growth_allocated:.1f}")

        # Step 1: stockpile replenishment
        self.food_stockpile = max(min(self.food_stockpile + self.food_allocated_to_stockpile, self._stockpile_max()),0)
        # if (self.food_allocated_to_stockpile < 0) and (self.food_stockpile < .5 * self._get_population() * POP_FOOD_CONSUMPTION):
        #     self.turns_with_stockpile_loss += 1
        #     if self.turns_with_stockpile_loss > TURNS_WITH_STOCKPILE_LOSS_THRESHOLD:
        #         self.pending_pop_loss += 1
        #         self.turns_with_stockpile_loss = 0
        # else:
        #     self.turns_with_stockpile_loss = 0

        # Step 2: growth
        if self._space_for_new_pop():
            self.growth_progress += self.growth_allocated
        if self.growth_allocated > 0:
            log.append(f"{self.name}: {self.growth_allocated:.0f} added to growth bar")

        # Step 3: starvation if shortfall exceeded stockpile
        if self.pending_pop_loss > 0:
            del self.pops[:self.pending_pop_loss]
            self.growth_progress = 0.0
            self.pending_pop_loss = 0
            if self.faction:
                self.faction.notification_log.remove(('pending_pop_loss_city', self.name))
            # print(f"  [shortfall] {self.food_shortfall:.1f} shortfall, stockpile={self.food_stockpile:.1f}, pops={self._get_population()}")
            #self._food_shortfall()
            # print(f"  [shortfall] after -> stockpile={self.food_stockpile:.1f}, pops={self._get_population()}")

        # Step 4: production
        prod_job = next((j for j in self.jobs if j.job_type == 'production'), None)
        if prod_job:
            self.construction_progress = min(self.construction_progress + prod_job.production_yield(), 1000)
        pt = self.production_target
        if pt.type == 'extraction' and pt.target and self.production_yield > 0 and self.extraction_tile:
            resource = pt.target
            # print(f"[extraction] {self.name} end_turn: extracting {self.production_yield:.2f} {resource} from ({self.extraction_tile.row},{self.extraction_tile.col}) deposit={self.extraction_tile.resource_deposits.get(resource, 0):.1f}")
            extracted = self.extraction_tile.extraction(self.production_yield, resource)
            if self.tile:
                self.tile.add_resources_to_stockpile(extracted, resource)
                # print(f"[extraction] {self.name} end_turn: extracted={extracted:.2f}, city_tile stockpile={self.tile.resource_stockpiles}")
        if pt.type == 'manufacturing' and pt.target_item and self.production_yield > 0:
            if self.tile:
                for resource, amount in self.resources_allocated_to_production.items():
                    current = self.tile.resource_stockpiles.get(resource, 0.0)
                    self.tile.resource_stockpiles[resource] = max(0.0, current - amount)
            pt.progress += self.production_yield
            if pt.progress >= pt.target_item.production_needed:
                if self.tile:
                    self.tile.item_stockpiles[pt.target_item.name] = self.tile.item_stockpiles.get(pt.target_item.name, 0) + 1
                item = pt.target_item
                if all(self.has_resource(r) for r in item.resource_cost):
                    pt.progress -= item.production_needed
                else:
                    pt.clear()
        if pt.type == 'construction' and pt.target_building and self.production_yield > 0:
            if self.tile:
                for resource, amount in self.resources_allocated_to_production.items():
                    current = self.tile.resource_stockpiles.get(resource, 0.0)
                    self.tile.resource_stockpiles[resource] = max(0.0, current - amount)
            pt.progress += self.production_yield
            if pt.progress >= pt.target_building.production_needed:
                if self.tile:
                    self.tile.building_list[pt.target_building.name] = self.tile.building_list.get(pt.target_building.name, 0) + 1
                building = pt.target_building
                if building.multiple and all(self.has_resource(r) for r in building.resource_cost):
                    pt.progress -= building.production_needed
                else:
                    pt.clear()

        # Step 5: spawn new pops
        spawned = 0
        while self.growth_progress >= GROWTH_NEEDED_FOR_NEW_POP and self._space_for_new_pop():
            self.growth_progress -= GROWTH_NEEDED_FOR_NEW_POP
            self.pops.append(Pop())
            spawned += 1
        if spawned:
            self.rebalance_pops()
            log.append(f"{self.name}: {spawned} new pop(s)! ({self._get_population()} total)")
            # print(f"  [spawn] +{spawned} pop(s), total={self._get_population()}")

        self._process_resource_routes()
        self.rebalance_pops()
        # print(f"  === end: stockpile={self.food_stockpile:.1f}  growth={self.growth_progress:.1f}  pops={self._get_population()} ===")
        return log
