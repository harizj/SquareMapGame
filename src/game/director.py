import random
from src.game.battles import compute_battle_preview, resolve_battle, apply_battle_result
from src.game.unit import Militia
from src.game.pop import Pop
from src.game.unit_group import UnitGroup

_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

ATTACK_THRESHOLD     = 1.2
SPAWN_INTERVAL       = 20  # turns between each spawn wave
SPAWN_COUNT_START    = 5  # units in the first wave's group
SPAWN_COUNT_INCREASE = 5  # additional units added per subsequent wave


class Director:
    """Base class for AI-controlled faction behavior."""

    def director_moves(self, faction, game_map):
        pass

    def spawn_tick(self, faction, game_map, turn):
        pass


class HordeDirector(Director):
    """Attacks enemies in range (weakest first); otherwise advances toward nearest enemy city.
    Spawns unit groups at faction cities on a fixed interval that grows over time."""

    def __init__(self, spawn_interval=5):
        self.spawn_interval = spawn_interval

    def director_moves(self, faction, game_map):
        friendly_groups = [
            g for groups in game_map.unit_groups.values()
            for g in groups
            if g.faction is faction and not g.move_exhausted and g.moves_remaining > 0
        ]

        # Horde doesn't consume food — top up every group before moving
        for g in friendly_groups:
            g.max_food_stockpile = g._carry_capacity()
            g.food_stockpile     = g.max_food_stockpile

        if not friendly_groups:
            return

        enemy_cities = [
            city for city in game_map.cities.values()
            if city.faction is not faction
        ]

        # Combined enemy unit strength per tile (0 for empty enemy city tiles)
        enemy_tile_strength = {}
        for (r, c), groups in game_map.unit_groups.items():
            enemy_groups = [g for g in groups if g.faction is not faction]
            if enemy_groups:
                s = sum(u.combat_strength for g in enemy_groups for u in g.units)
                enemy_tile_strength[(r, c)] = s
        for city in enemy_cities:
            pos = (city.row, city.col)
            if pos not in enemy_tile_strength:
                enemy_tile_strength[pos] = 0

        for group in friendly_groups:
            gr, gc = group.row, group.col
            reachable = game_map.get_reachable_from(gr, gc, group.moves_remaining)

            # --- Condition 1: act on enemy tiles reachable this turn ---
            # city_targets: undefended enemy city tiles — move directly onto to capture
            # group_targets: tiles with enemy unit groups — approach adjacent and fight
            group_strength = sum(u.combat_strength for u in group.units)
            city_targets  = []  # (strength, cost, er, ec)
            group_targets = []  # (strength, cost, er, ec, approach)

            for (er, ec), strength in enemy_tile_strength.items():
                tile = game_map.tiles[er][ec]
                has_enemy_groups = any(g.faction is not faction for g in tile.unit_groups)
                has_enemy_city   = tile.city is not None and tile.city.faction is not faction

                if has_enemy_groups:
                    best_approach = None
                    best_cost = float('inf')
                    if max(abs(er - gr), abs(ec - gc)) == 1:
                        best_approach = (gr, gc)
                        best_cost = 0
                    for dr, dc in _DIRS:
                        nr, nc = er + dr, ec + dc
                        if (nr, nc) in reachable and reachable[(nr, nc)] < best_cost:
                            best_approach = (nr, nc)
                            best_cost = reachable[(nr, nc)]
                    if best_approach is not None:
                        group_targets.append((strength, best_cost, er, ec, best_approach))
                elif has_enemy_city and (er, ec) in reachable:
                    city_targets.append((strength, reachable[(er, ec)], er, ec))

            # Prefer weakest undefended city below threshold; fall back to weakest enemy group
            viable_cities = [t for t in city_targets if t[0] < group_strength * ATTACK_THRESHOLD]
            if viable_cities:
                viable_cities.sort(key=lambda x: x[0])
                _, move_cost, er, ec = viable_cities[0]
                if (er, ec) != (gr, gc):
                    game_map.move_group(group, er, ec, move_cost)
                continue
            elif group_targets:
                group_targets.sort(key=lambda x: x[0])
                _, approach_cost, er, ec, (ar, ac) = group_targets[0]
                if (ar, ac) != (gr, gc):
                    game_map.move_group(group, ar, ac, approach_cost)
                attacker_tile = game_map.tiles[group.row][group.col]
                defender_tile = game_map.tiles[er][ec]
                enemy_groups  = [g for g in defender_tile.unit_groups if g.faction is not faction]
                if not enemy_groups:
                    continue
                preview = compute_battle_preview([group], enemy_groups, attacker_tile, defender_tile)
                result  = resolve_battle(preview)
                apply_battle_result(preview, result, game_map, defender_tile)
                continue

            # --- Condition 2: no enemies in range — advance toward nearest enemy city ---
            if not enemy_cities:
                continue

            nearest_path = None
            nearest_dists = None
            nearest_cost = float('inf')
            for city in enemy_cities:
                path, dists = game_map.get_path_to(gr, gc, city.row, city.col)
                if path and dists[-1] < nearest_cost:
                    nearest_cost = dists[-1]
                    nearest_path = path
                    nearest_dists = dists

            if nearest_path is None or len(nearest_path) < 2:
                continue

            target_r, target_c, target_cost = gr, gc, 0
            for (pr, pc), d in zip(nearest_path[1:], nearest_dists[1:]):
                if d <= group.moves_remaining:
                    target_r, target_c, target_cost = pr, pc, d
                else:
                    break
            if (target_r, target_c) != (gr, gc):
                game_map.move_group(group, target_r, target_c, target_cost)

    def spawn_tick(self, faction, game_map, turn):
        if turn == 0 or turn % SPAWN_INTERVAL != 0:
            return
        spawn_tiles = [
            tile
            for row in game_map.tiles
            for tile in row
            if 'spawn_point' in tile.terrain_features
        ]
        if not spawn_tiles:
            return
        wave       = turn // SPAWN_INTERVAL
        unit_count = SPAWN_COUNT_START + (wave - 1) * SPAWN_COUNT_INCREASE
        tile       = random.choice(spawn_tiles)
        units      = [Militia(Pop()) for _ in range(unit_count)]
        group      = UnitGroup(tile.row, tile.col, units=units, faction=faction)
        group.max_food_stockpile = group._carry_capacity()
        group.food_stockpile     = group.max_food_stockpile
        tile.unit_groups.append(group)
