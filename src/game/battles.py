import random


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
    attacker_strength = attacker_units  # placeholder: 1 strength per unit

    defending_city = defender if isinstance(defender, City) else None
    defender_groups = [] if defending_city else defender
    defender_units = len(defending_city.pops) if defending_city else sum(len(g.units) for g in defender_groups)
    defender_strength = defender_units  # placeholder

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


def resolve_battle(preview):
    """Two-round battle. Attacker rolls first each round. Hits are 5s and 6s.
    Kills = floor(hits / enemy_unit_strength). Both sides' kills are applied
    simultaneously at the end of each round before the next begins.

    Returns a dict with keys:
      attacker_losses  -- total units lost by attacker
      defender_losses  -- total units lost by defender
      outcome          -- 'attacker_wins', 'defender_wins', or 'draw'
      log              -- list of result strings, one per side per round
    """
    import math
    from src.game.city import City

    attacker_unit_str = preview['attacker_unit_strength']
    defender_unit_str = preview['defender_unit_strength']

    attacker_groups = preview['attacker_groups']
    defender = preview['defender']
    attacker_name = (attacker_groups[0].faction.name
                     if attacker_groups and attacker_groups[0].faction else 'Attacker')
    if isinstance(defender, City):
        defender_name = defender.faction.name if defender.faction else defender.name
    else:
        defender_name = (defender[0].faction.name
                         if defender and defender[0].faction else 'Defender')

    remaining_attackers = preview['attacker_units']
    remaining_defenders = preview['defender_units']
    total_attacker_losses = 0
    total_defender_losses = 0
    log = []

    for round_num in range(1, 3):
        if remaining_attackers <= 0 or remaining_defenders <= 0:
            break

        # Attacker rolls
        a_dice = math.ceil(remaining_attackers * attacker_unit_str)
        a_hits = sum(1 for _ in range(a_dice) if random.randint(1, 6) >= 5)
        d_kills = min(math.floor(a_hits / defender_unit_str), remaining_defenders)

        # Defender rolls
        d_dice = math.ceil(remaining_defenders * defender_unit_str)
        d_hits = sum(1 for _ in range(d_dice) if random.randint(1, 6) >= 5)
        a_kills = min(math.floor(d_hits / attacker_unit_str), remaining_attackers)

        # Log attacker losses first, then defender losses
        if a_kills > 0:
            log.append(f"{a_kills} of {remaining_attackers} {attacker_name} were killed in round {round_num}.")
        else:
            log.append(f"No {attacker_name} were killed in round {round_num}.")
        if d_kills > 0:
            log.append(f"{d_kills} of {remaining_defenders} {defender_name} were killed in round {round_num}.")
        else:
            log.append(f"No {defender_name} were killed in round {round_num}.")

        # Apply kills simultaneously before next round
        remaining_attackers -= a_kills
        remaining_defenders -= d_kills
        total_attacker_losses += a_kills
        total_defender_losses += d_kills

    for line in log:
        print(line)

    if remaining_defenders <= 0 and remaining_attackers > 0:
        outcome = 'attacker_wins'
    elif remaining_attackers <= 0 and remaining_defenders > 0:
        outcome = 'defender_wins'
    elif remaining_defenders <= 0 and remaining_attackers <= 0:
        outcome = 'draw'
    elif total_defender_losses > total_attacker_losses:
        outcome = 'attacker_wins'
    elif total_attacker_losses > total_defender_losses:
        outcome = 'defender_wins'
    else:
        outcome = 'draw'

    return {
        'attacker_losses': total_attacker_losses,
        'defender_losses': total_defender_losses,
        'outcome':         outcome,
        'log':             log,
    }
