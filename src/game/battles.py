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
        modifiers.append(('Hills defence', 'defender', +1))
    if defender_tile.terrain == 'river':
        modifiers.append(('River crossing', 'attacker', -1))

    # City wall modifier (placeholder — city fortification not yet implemented)
    if defending_city:
        modifiers.append(('City walls', 'defender', +2))

    attacker_bonus = sum(v for _, side, v in modifiers if side == 'attacker')
    defender_bonus = sum(v for _, side, v in modifiers if side == 'defender')

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
        'attacker_total':   attacker_strength + attacker_bonus,
        'defender_total':   defender_strength + defender_bonus,
    }


def resolve_battle(preview):
    """Executes the dice roll sequence and returns the battle result.

    Returns a dict with keys:
      attacker_losses  -- number of attacker units lost
      defender_losses  -- number of defender units lost
      outcome          -- 'attacker_wins', 'defender_wins', or 'draw'
      rolls            -- list of (attacker_roll, defender_roll) per round
    """
    attacker_total = preview['attacker_total']
    defender_total = preview['defender_total']

    # Placeholder: one roll per unit on each side, highest roll wins each exchange
    attacker_rolls = [random.randint(1, 6) for _ in range(attacker_total)]
    defender_rolls = [random.randint(1, 6) for _ in range(defender_total)]

    attacker_rolls.sort(reverse=True)
    defender_rolls.sort(reverse=True)

    rounds = list(zip(attacker_rolls, defender_rolls))
    attacker_losses = sum(1 for a, d in rounds if a <= d)
    defender_losses = sum(1 for a, d in rounds if a > d)

    if defender_losses > attacker_losses:
        outcome = 'attacker_wins'
    elif attacker_losses > defender_losses:
        outcome = 'defender_wins'
    else:
        outcome = 'draw'

    return {
        'attacker_losses': attacker_losses,
        'defender_losses': defender_losses,
        'outcome':         outcome,
        'rolls':           rounds,
    }
