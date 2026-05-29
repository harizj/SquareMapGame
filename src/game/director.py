from src.game.battles import compute_battle_preview, resolve_battle, apply_battle_result


class Director:
    """Base class for AI-controlled faction behavior."""

    def director_moves(self, faction, game_map):
        pass

    def spawn_tick(self, faction, game_map, turn):
        pass


class HordeDirector(Director):
    """Spawns unit groups at intervals and moves them toward the nearest enemy."""

    def __init__(self, spawn_interval=5):
        self.spawn_interval = spawn_interval

    def director_moves(self, faction, game_map):
        friendly_groups = [
            g for groups in game_map.unit_groups.values()
            for g in groups
            if g.faction is faction and not g.move_exhausted and g.moves_remaining > 0
        ]

        enemy_entries = [
            (r, c, g)
            for (r, c), groups in game_map.unit_groups.items()
            for g in groups
            if g.faction is not faction
        ]

        if not enemy_entries or not friendly_groups:
            return

        for group in friendly_groups:
            gr, gc = group.row, group.col

            # Find nearest enemy by path distance
            nearest_path = None
            nearest_dists = None
            nearest_pos = None
            nearest_cost = float('inf')

            for er, ec, _ in enemy_entries:
                path, dists = game_map.get_path_to(gr, gc, er, ec)
                if path and dists[-1] < nearest_cost:
                    nearest_cost = dists[-1]
                    nearest_pos = (er, ec)
                    nearest_path = path
                    nearest_dists = dists

            if nearest_path is None or len(nearest_path) < 2:
                continue

            er, ec = nearest_pos
            path, dists = nearest_path, nearest_dists

            can_attack = False

            if len(path) == 2:
                # Enemy is adjacent — no movement needed, attack in place
                can_attack = True
            else:
                stop_r, stop_c = path[-2]
                stop_cost = nearest_dists[-2]
                if stop_cost <= group.moves_remaining:
                    if (stop_r, stop_c) != (gr, gc):
                        game_map.move_group(group, stop_r, stop_c, stop_cost)
                    can_attack = True
                else:
                    # Move as far as possible along the path toward the enemy
                    target_r, target_c, target_cost = gr, gc, 0
                    for (pr, pc), d in zip(path[1:], dists[1:]):
                        if d <= group.moves_remaining:
                            target_r, target_c, target_cost = pr, pc, d
                        else:
                            break
                    if (target_r, target_c) != (gr, gc):
                        game_map.move_group(group, target_r, target_c, target_cost)

            if can_attack:
                attacker_tile = game_map.tiles[group.row][group.col]
                defender_tile = game_map.tiles[er][ec]
                defender_groups = [g for g in defender_tile.unit_groups if g.faction is not faction]
                if not defender_groups:
                    continue
                preview = compute_battle_preview([group], defender_groups, attacker_tile, defender_tile)
                result = resolve_battle(preview)
                apply_battle_result(preview, result, game_map, defender_tile)

    def spawn_tick(self, faction, game_map, turn):
        pass
