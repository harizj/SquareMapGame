import random

LETHALITY = 0.20


def drop_unit_items(units, tile):
    """Drop items carried by upgraded units onto a tile's item stockpile."""
    from src.game.items import ITEM_REGISTRY
    unit_to_item = {cls.upgrades_to: cls.name for cls in ITEM_REGISTRY.values()}
    for unit in units:
        item = unit_to_item.get(unit.unit_type)
        if item:
            tile.item_stockpiles[item] = tile.item_stockpiles.get(item, 0) + 1
WOODEN_WALL_MODIFIER = .5
STONE_WALL_MODIFIER = 1


def _attacker_modifier(unit, attacker_tile, defender_tile, spearmen_count=0):
    """Returns the total combat modifier multiplier for an attacking unit."""
    mod = 0.0
    if unit.unit_type == 'Spearmen' and spearmen_count > 4:
        mod += 0.25
    return mod


def _defender_modifier(unit, defender_tile, attacker_tile, spearmen_count=0):
    """Returns the total combat modifier multiplier for a defending unit."""
    features = defender_tile.terrain_features
    is_archer = unit.unit_type == 'Archers'
    mod = 0.0
    if 'hills' in features:
        mod += 0.50 if is_archer else 0.25
    elif 'forest' in features:
        mod += 0.50 if is_archer else 0.25
    elif 'river' in features and 'river' not in attacker_tile.terrain_features:
        mod += 0.50 if is_archer else 0.25
    if unit.unit_type == 'Spearmen' and spearmen_count > 4:
        mod += 0.25
    return mod


def compute_battle_preview(attacker_groups, defender, attacker_tile, defender_tile):
    """Computes combat strengths and modifiers for both sides before resolution.

    attacker_groups: list of UnitGroup
    defender: list of UnitGroup or a City
    attacker_tile, defender_tile: Tile objects (for terrain modifiers)

    Returns a dict with keys:
      attacker_units      -- total unit count on attacking side
      defender_units      -- total unit count on defending side
      attacker_strength   -- base combat strength
      defender_strength   -- base combat strength
      modifiers           -- list of (label, side, value) describing active modifiers
      attacker_total      -- final adjusted strength
      defender_total      -- final adjusted strength
    """
    from src.game.city import City

    attacker_units_list = [u for g in attacker_groups for u in g.units]
    attacker_units = len(attacker_units_list)
    attacker_strength = sum(u.combat_strength for u in attacker_units_list)

    defending_city = defender if isinstance(defender, City) else None
    defender_groups = [] if defending_city else defender
    if defending_city:
        defender_units_list = []
        defender_units = len(defending_city.pops)
        defender_strength = defender_units
    else:
        defender_units_list = [u for g in defender_groups for u in g.units]
        defender_units = len(defender_units_list)
        defender_strength = sum(u.combat_strength for u in defender_units_list)

    modifiers = []

    # Terrain modifier for display (non-stacking, hills takes priority)
    terrain_mod_applies = False
    if 'hills' in defender_tile.terrain_features:
        modifiers.append(('Hills Defence', 'defender', .25))
        terrain_mod_applies = True
    elif 'forest' in defender_tile.terrain_features:
        modifiers.append(('Forest Defence', 'defender', .25))
        terrain_mod_applies = True
    elif 'river' in defender_tile.terrain_features and 'river' not in attacker_tile.terrain_features:
        modifiers.append(('River Crossing Defence', 'defender', .25))
        terrain_mod_applies = True

    if defending_city:
        modifiers.append(('City Walls', 'defender', .5))
    elif terrain_mod_applies and any(u.unit_type == 'Archers' for u in defender_units_list):
        modifiers.append(('Archer Terrain Defence', 'defender', .25))

    atk_spearmen = sum(1 for u in attacker_units_list if u.unit_type == 'Spearmen')
    def_spearmen = sum(1 for u in defender_units_list if u.unit_type == 'Spearmen')
    if atk_spearmen > 4:
        modifiers.append(('Spear Wall', 'attacker', .25))
    if def_spearmen > 4:
        modifiers.append(('Spear Wall', 'defender', .25))

    # Wall counts from the defender's tile
    wooden_walls = defender_tile.building_list.get('wooden walls', 0)
    stone_walls  = defender_tile.building_list.get('stone walls',  0)
    if stone_walls > 0:
        modifiers.append((f'Stone Walls Defence x{stone_walls}', 'defender', STONE_WALL_MODIFIER))
    if wooden_walls > 0:
        modifiers.append((f'Wooden Walls Defence x{wooden_walls}', 'defender', WOODEN_WALL_MODIFIER))

    # Units ranked by effective strength (modifiers applied), strongest first
    attacker_units_ranked = sorted(
        attacker_units_list,
        key=lambda u: u.combat_strength * (1 + _attacker_modifier(u, attacker_tile, defender_tile, atk_spearmen)),
        reverse=True,
    )
    if not defending_city:
        defender_units_ranked = sorted(
            defender_units_list,
            key=lambda u: u.combat_strength * (1 + _defender_modifier(u, defender_tile, attacker_tile, def_spearmen)),
            reverse=True,
        )
    else:
        defender_units_ranked = []

    def _wall_mod(rank):
        if rank < stone_walls:
            return STONE_WALL_MODIFIER
        if rank < stone_walls + wooden_walls:
            return WOODEN_WALL_MODIFIER
        return 0.0

    attacker_total = sum(
        u.combat_strength * (1 + _attacker_modifier(u, attacker_tile, defender_tile, atk_spearmen))
        for u in attacker_units_list
    )
    if defending_city:
        defender_mult = sum(v for _, side, v in modifiers if side == 'defender')
        defender_total = defender_strength * (1 + defender_mult)
    else:
        defender_total = sum(
            u.combat_strength * (1 + _defender_modifier(u, defender_tile, attacker_tile, def_spearmen) + _wall_mod(rank))
            for rank, u in enumerate(defender_units_ranked)
        )

    return {
        'attacker_groups':        attacker_groups,
        'defender':               defender,
        'attacker_tile':          attacker_tile,
        'defender_tile':          defender_tile,
        'attacker_units':         attacker_units,
        'defender_units':         defender_units,
        'attacker_strength':      attacker_strength,
        'defender_strength':      defender_strength,
        'modifiers':              modifiers,
        'attacker_total':         attacker_total,
        'defender_total':         defender_total,
        'wooden_walls':           wooden_walls,
        'stone_walls':            stone_walls,
        'attacker_units_ranked':  attacker_units_ranked,
        'defender_units_ranked':  defender_units_ranked,
        'attacker_unit_strength': attacker_total / attacker_units,
        'defender_unit_strength': defender_total / defender_units,
    }


def _poisson(lam):
    """Knuth Poisson sampler — unbiased for small lambda."""
    import math
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def resolve_battle(preview):
    """Two-round battle using Poisson kill draws.

    Casualties are deducted at the end of each round (lowest-strength units
    die first). Round 2 uses the updated surviving counts and strengths.
    Attacker strikes first each round; defender counterattacks with the count
    from the start of that round.

    Returns a dict with keys:
      attacker_losses  -- total units lost by attacker
      defender_losses  -- total units lost by defender
      outcome          -- 'attacker_wins', 'defender_wins', or 'draw'
      log              -- flat list of result strings
      rounds           -- per-round list of {attacker, defender, log} dicts
    """
    from src.game.city import City

    attacker_groups = preview['attacker_groups']
    defender        = preview['defender']
    attacker_tile   = preview['attacker_tile']
    defender_tile   = preview['defender_tile']
    attacker_name = (attacker_groups[0].faction.name
                     if attacker_groups and attacker_groups[0].faction else 'Attacker')
    if isinstance(defender, City):
        defender_name = defender.faction.name if defender.faction else defender.name
    else:
        defender_name = (defender[0].faction.name
                         if defender and defender[0].faction else 'Defender')

    # Local sorted unit lists — lowest combat_strength first (casualties come from front)
    atk_units = sorted(
        [u for g in attacker_groups for u in g.units],
        key=lambda u: u.combat_strength
    )
    defending_city = isinstance(defender, City)
    if defending_city:
        def_remaining = preview['defender_units']
        def_base_str  = preview['defender_total']
    else:
        def_units = sorted(
            [u for g in defender for u in g.units],
            key=lambda u: u.combat_strength
        )

    total_a_kills = 0
    total_d_kills = 0
    flat_log = []
    rounds   = []

    for round_num in range(1, 5):
        num_atk = len(atk_units)
        atk_str = preview['attacker_total'] * (num_atk / preview['attacker_units']) if preview['attacker_units'] else 0
        if defending_city:
            num_def = def_remaining
            def_str = def_base_str * (num_def / preview['defender_units']) if preview['defender_units'] else 0
        else:
            num_def = len(def_units)
            def_str = preview['defender_total'] * (num_def / preview['defender_units']) if preview['defender_units'] else 0

        if num_atk <= 0 or num_def <= 0:
            break
        atk_adv = atk_str / def_str if def_str > 0 else 1.0
        def_adv = def_str / atk_str if atk_str > 0 else 1.0
        atk_lam = atk_adv * num_def * LETHALITY
        def_lam = def_adv * num_atk * LETHALITY

        # Attacker strikes; defender counterattacks with count from round start
        d_kills = min(_poisson(atk_lam), num_def)
        a_kills = min(_poisson(def_lam), num_atk)

        round_log = []
        if d_kills > 0:
            round_log.append(f"{attacker_name} killed {d_kills} of {num_def} {defender_name}.")
        else:
            round_log.append(f"{attacker_name} failed to kill any {defender_name}.")
        if a_kills > 0:
            round_log.append(f"{defender_name} killed {a_kills} of {num_atk} {attacker_name}.")
        else:
            round_log.append(f"{defender_name} failed to kill any {attacker_name}.")

        rounds.append({
            'attacker': {'units': num_atk, 'strength': atk_str, 'advantage': atk_adv, 'lam': atk_lam},
            'defender': {'units': num_def, 'strength': def_str, 'advantage': def_adv, 'lam': def_lam},
            'log': round_log,
        })
        flat_log.extend(round_log)

        # Deduct casualties — remove lowest-quality first
        atk_units = atk_units[a_kills:]
        if defending_city:
            def_remaining -= d_kills
        else:
            def_units = def_units[d_kills:]

        total_a_kills += a_kills
        total_d_kills += d_kills

        # Stop after round 2 if there were any kills; otherwise play a 3rd round
        # if round_num == 2 and (total_a_kills > 0 or total_d_kills > 0):
        #     break

    for line in flat_log:
        print(line)

    final_atk = len(atk_units)
    final_def = def_remaining if defending_city else len(def_units)
    if final_def <= 0 and final_atk <= 0:
        outcome = 'draw'
    elif final_def <= 0:
        outcome = 'attacker_wins'
    elif final_atk <= 0:
        outcome = 'defender_wins'
    elif total_d_kills > total_a_kills:
        outcome = 'attacker_wins'
    elif total_a_kills > total_d_kills:
        outcome = 'defender_wins'
    else:
        outcome = 'draw'

    return {
        'attacker_losses': total_a_kills,
        'defender_losses': total_d_kills,
        'outcome':         outcome,
        'log':             flat_log,
        'rounds':          rounds,
    }


def apply_battle_result(preview, result, game_map, combat_tile):
    """Apply the mechanical outcome of a resolved battle to unit groups and map state.

    Removes casualties, updates food stockpiles, advances surviving attackers onto
    the combat tile if they won and it is clear, then purges empty groups everywhere.
    Returns the list of surviving attacker groups.
    """
    from src.game.city import City

    attacker_groups = preview['attacker_groups']
    defender = preview['defender']

    atk_sorted = sorted(
        [(g, u) for g in attacker_groups for u in g.units],
        key=lambda x: x[1].combat_strength,
    )
    atk_deaths = {}
    for g, u in atk_sorted[:result['attacker_losses']]:
        if u in g.units:
            atk_deaths.setdefault(g, []).append(u)
    for g, dying in atk_deaths.items():
        g.unit_deaths(dying, combat_tile, game_map)
    for g in attacker_groups:
        g.food_stockpile = min(g.food_stockpile, g.max_food_stockpile)

    if not isinstance(defender, City):
        def_sorted = sorted(
            [(g, u) for g in defender for u in g.units],
            key=lambda x: x[1].combat_strength,
        )
        def_deaths = {}
        for g, u in def_sorted[:result['defender_losses']]:
            if u in g.units:
                def_deaths.setdefault(g, []).append(u)
        for g, dying in def_deaths.items():
            g.unit_deaths(dying, combat_tile, game_map)
        for g in defender:
            g.food_stockpile = min(g.food_stockpile, g.max_food_stockpile)

    survivors = [g for g in attacker_groups if g.units]

    if result['outcome'] == 'attacker_wins' and combat_tile:
        combat_tile.unit_groups = [g for g in combat_tile.unit_groups if g.units]
        if not combat_tile.unit_groups:
            for group in survivors:
                game_map.move_group(group, combat_tile.row, combat_tile.col, 0)

    for row in game_map.tiles:
        for t in row:
            t.unit_groups = [g for g in t.unit_groups if g.units]
            t.update_unit_allocations()

    return survivors
