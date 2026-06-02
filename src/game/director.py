from src.game.battles import compute_battle_preview, resolve_battle, apply_battle_result

_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

ATTACK_THRESHOLD = 1.2


class Director:
    """Base class for AI-controlled faction behavior."""

    def director_moves(self, faction, game_map):
        pass

    def spawn_tick(self, faction, game_map, turn):
        pass


class HordeDirector(Director):
    """Attacks enemies in range (weakest first); otherwise advances toward nearest enemy city."""

    def __init__(self, spawn_interval=5):
        self.spawn_interval = spawn_interval

    def director_moves(self, faction, game_map):
        friendly_groups = [
            g for groups in game_map.unit_groups.values()
            for g in groups
            if g.faction is faction and not g.move_exhausted and g.moves_remaining > 0
        ]
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

            # --- Condition 1: attack weakest enemy tile reachable this turn ---
            group_strength = sum(u.combat_strength for u in group.units)
            city_targets = []   # (strength, cost, er, ec, approach)
            group_targets = []
            for (er, ec), strength in enemy_tile_strength.items():
                best_approach = None
                best_cost = float('inf')
                # Already adjacent — no move needed
                if max(abs(er - gr), abs(ec - gc)) == 1:
                    best_approach = (gr, gc)
                    best_cost = 0
                # Find lowest-cost reachable neighbor of the enemy tile
                for dr, dc in _DIRS:
                    nr, nc = er + dr, ec + dc
                    if (nr, nc) in reachable and reachable[(nr, nc)] < best_cost:
                        best_approach = (nr, nc)
                        best_cost = reachable[(nr, nc)]
                if best_approach is None:
                    continue
                tile = game_map.tiles[er][ec]
                is_city = tile.city is not None and tile.city.faction is not faction
                if is_city:
                    city_targets.append((strength, best_cost, er, ec, best_approach))
                else:
                    group_targets.append((strength, best_cost, er, ec, best_approach))

            # Prefer weakest city tile below the attack threshold; fall back to weakest unit group
            viable_cities = [t for t in city_targets if t[0] < group_strength * ATTACK_THRESHOLD]
            if viable_cities:
                viable_cities.sort(key=lambda x: x[0])
                chosen = viable_cities[0]
            elif group_targets:
                group_targets.sort(key=lambda x: x[0])
                chosen = group_targets[0]
            else:
                chosen = None

            if chosen is not None:
                _, approach_cost, er, ec, (ar, ac) = chosen
                if (ar, ac) != (gr, gc):
                    game_map.move_group(group, ar, ac, approach_cost)
                attacker_tile = game_map.tiles[group.row][group.col]
                defender_tile = game_map.tiles[er][ec]
                enemy_groups = [g for g in defender_tile.unit_groups if g.faction is not faction]
                city = defender_tile.city if defender_tile.city and defender_tile.city.faction is not faction else None
                if enemy_groups:
                    defender = enemy_groups
                elif city:
                    defender = city
                else:
                    continue
                preview = compute_battle_preview([group], defender, attacker_tile, defender_tile)
                result = resolve_battle(preview)
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
        pass
