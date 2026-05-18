import random

LETHALITY = 0.2


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

    attacker_units = sum(len(g.units) for g in attacker_groups)
    attacker_strength = sum(u.combat_strength for g in attacker_groups for u in g.units)

    defending_city = defender if isinstance(defender, City) else None
    defender_groups = [] if defending_city else defender
    defender_units = len(defending_city.pops) if defending_city else sum(len(g.units) for g in defender_groups)
    defender_strength = defender_units if defending_city else sum(u.combat_strength for g in defender_groups for u in g.units)

    modifiers = []

    # Terrain modifier for defender
    if defender_tile.terrain == 'hills':
        modifiers.append(('Hills defence', 'defender', .5))
    if defender_tile.terrain == 'forest':
        modifiers.append(('Forest defence', 'defender', .25))

    # City wall modifier (placeholder — city fortification not yet implemented)
    if defending_city:
        modifiers.append(('City walls', 'defender', .5))

    attacker_mult = sum(v for _, side, v in modifiers if side == 'attacker')
    defender_mult = sum(v for _, side, v in modifiers if side == 'defender')

    attacker_total = attacker_strength * (1 + attacker_mult)
    defender_total = defender_strength * (1 + defender_mult)

    return {
        'attacker_groups':  attacker_groups,
        'defender':         defender,
        'attacker_tile':    attacker_tile,
        'defender_tile':    defender_tile,
        'attacker_units':   attacker_units,
        'defender_units':   defender_units,
        'attacker_strength': attacker_strength,
        'defender_strength': defender_strength,
        'modifiers':        modifiers,
        'attacker_total':   attacker_total,
        'defender_total':   defender_total,
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
        def_base_str  = preview['defender_strength']
    else:
        def_units = sorted(
            [u for g in defender for u in g.units],
            key=lambda u: u.combat_strength
        )

    total_a_kills = 0
    total_d_kills = 0
    flat_log = []
    rounds   = []

    for round_num in range(1, 4):
        num_atk = len(atk_units)
        if defending_city:
            num_def = def_remaining
            def_str = def_base_str * (num_def / preview['defender_units']) if preview['defender_units'] else 0
        else:
            num_def = len(def_units)
            def_str = sum(u.combat_strength for u in def_units)

        if num_atk <= 0 or num_def <= 0:
            break

        atk_str = sum(u.combat_strength for u in atk_units)
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
        if round_num == 2 and (total_a_kills > 0 or total_d_kills > 0):
            break

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
