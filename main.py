import json
import os
import pygame
from src.game.battles import compute_battle_preview, resolve_battle, apply_battle_result
from src.game.city import City
from src.game.faction import Faction, COLOR_SETS, CITY_NAME_SETS
from src.game.tether import Tether
from src.game.director import HordeDirector
from src.game.line_of_sight import LineOfSight
from src.game.pop import Pop
from src.game.unit_group import UnitGroup
from src.game.map import Map
from src.game.save_load import load_map_data, save_map
from src.game.trade_route import TradeRoute
from src.game.items import ITEM_REGISTRY
from src.game.unit import Militia, UNIT_REGISTRY
from src.ui.renderer import Renderer
from src.game.constants import DEFAULT_MOVE_DISTANCE, RESTRICTED_STARTING_TICKER

_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_CONFIG_PATH = os.path.join(_DIR, 'game_config.json')


def _load_game_config():
    if os.path.exists(GAME_CONFIG_PATH):
        with open(GAME_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def _apply_game_config(game_map, game_config):
    _director_map = {'horde': HordeDirector}

    factions = {}
    for f_data in game_config.get('factions', []):
        director_key = f_data.get('director')
        director = _director_map[director_key]() if director_key else None
        faction = Faction(
            name=f_data['name'],
            colors=COLOR_SETS[f_data['colors']],
            city_names=CITY_NAME_SETS[f_data['city_names']],
            director=director,
        )
        factions[f_data['name']] = faction

    for ug_data in game_config.get('unit_groups', []):
        r, c = ug_data['row'], ug_data['col']
        faction = factions.get(ug_data.get('faction'))
        unit_type_names = ug_data.get('units')
        if unit_type_names:
            units = [UNIT_REGISTRY.get(t, Militia)(Pop()) for t in unit_type_names]
        else:
            units = [Militia(Pop()) for _ in range(ug_data.get('num_units', 0))]
        group = UnitGroup(r, c, units=units, faction=faction)
        group.add_food(ug_data['food'])
        game_map.tiles[r][c].unit_groups.append(group)

    for city_data in game_config.get('cities', []):
        r, c = city_data['row'], city_data['col']
        faction = factions.get(city_data.get('faction'))
        name = city_data.get('name') or (faction.take_city_name() if faction else game_map._take_city_name())
        population = city_data.get('population', 20)
        city = City(r, c, name, faction=faction, population=population)
        game_map.cities[(r, c)] = city
        game_map.setup_city(city)

    return factions


def _build_blocked(controlling_faction, start, game_map):
    """Returns a set of (row, col) tiles occupied by enemy units or enemy cities."""
    if controlling_faction is None:
        return set()
    blocked = set()
    for (r, c), groups in game_map.unit_groups.items():
        if (r, c) == start:
            continue
        if groups and groups[0].faction is not controlling_faction:
            blocked.add((r, c))
    for (r, c), city in game_map.cities.items():
        if city.faction is not controlling_faction:
            blocked.add((r, c))
    return blocked


def _compute_move_state(selected_unit_groups, selected_tile, game_map):
    if selected_unit_groups and selected_tile:
        tile_groups = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
        candidates = [g for g in tile_groups if g in selected_unit_groups and g.moves_remaining > 0 and not g.move_exhausted]
        if candidates:
            budget = min(g.moves_remaining for g in candidates)
            controlling_faction = candidates[0].faction
            start = (selected_tile.row, selected_tile.col)
            blocked = _build_blocked(controlling_faction, start, game_map)
            return True, candidates, game_map.get_reachable_from(selected_tile.row, selected_tile.col, budget, blocked=blocked)
    return False, [], {}


_UNIT_TO_ITEM = {cls.upgrades_to: cls.name for cls in ITEM_REGISTRY.values()}

def _drop_items_for_units(units, tile):
    for unit in units:
        item = _UNIT_TO_ITEM.get(unit.unit_type)
        if item:
            tile.item_stockpiles[item] = tile.item_stockpiles.get(item, 0) + 1


def main():
    pygame.init()

    game_config = _load_game_config()
    map_name = game_config.get('map', '').strip()
    if map_name:
        data = load_map_data(map_name)
        if data:
            game_map = Map.from_dict(data)
        else:
            import importlib.util, os as _os
            script_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'map_generation', f'{map_name}.py')
            if _os.path.exists(script_path):
                spec = importlib.util.spec_from_file_location(map_name, script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                game_map = Map()
                module.generate(game_map)
            else:
                game_map = Map()
    else:
        game_map = Map()
    factions = _apply_game_config(game_map, game_config)

    renderer = Renderer(game_map)
    los = LineOfSight(game_map)
    clock = pygame.time.Clock()
    selected_tile = None
    move_mode = False
    move_mode_unit_groups = []
    reachable = {}
    move_hover_tile = None
    city_drag_active = False
    save_popup_active = False
    save_popup_text = ""
    terrain_popup_active = False
    terrain_popup_snapshot = None
    river_popup_active = False
    battle_popup_active = False
    pending_combat_preview = None
    pending_combat_tile = None
    battle_result_active = False
    pending_battle_result = None
    pending_battle_result_preview = None
    game_log = []
    turn = 0
    console_active = False
    console_input = ""

    running = True
    while running:
        do_end_turn = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                factor = 1.1 if event.y > 0 else (1 / 1.1)
                renderer.zoom_map(factor, *pygame.mouse.get_pos())

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKQUOTE:
                    console_active = not console_active
                    console_input = ""
                elif console_active:
                    if event.key == pygame.K_RETURN and console_input.strip():
                        cmd = console_input.strip()
                        try:
                            result = eval(cmd, {'game_map': game_map})
                            game_log.append(f"> {cmd}")
                            game_log.append(f"  {result}")
                        except Exception as e:
                            game_log.append(f"> {cmd}")
                            game_log.append(f"  Error: {e}")
                        console_input = ""
                        console_active = False
                    elif event.key == pygame.K_ESCAPE:
                        console_active = False
                        console_input = ""
                    elif event.key == pygame.K_BACKSPACE:
                        console_input = console_input[:-1]
                    elif event.unicode.isprintable():
                        console_input += event.unicode
                elif save_popup_active:
                    if event.key == pygame.K_RETURN and save_popup_text.strip():
                        name = save_popup_text.strip().replace(' ', '_')
                        path = save_map(game_map, name)
                        # print(f"Saved: {path}")
                        save_popup_active = False
                        save_popup_text = ""
                    elif event.key == pygame.K_ESCAPE:
                        save_popup_active = False
                        save_popup_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        save_popup_text = save_popup_text[:-1]
                    elif event.unicode.isprintable():
                        save_popup_text += event.unicode
                elif terrain_popup_active or river_popup_active:
                    if event.key == pygame.K_ESCAPE:
                        if terrain_popup_active and terrain_popup_snapshot:
                            selected_tile.biome, selected_tile.terrain_features, selected_tile.river_edges = terrain_popup_snapshot[0], list(terrain_popup_snapshot[1]), set(terrain_popup_snapshot[2])
                            selected_tile.update_terrain_properties()
                        terrain_popup_active = False
                        river_popup_active = False
                elif event.key == pygame.K_SPACE:
                    do_end_turn = True
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                                   pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9):
                    if selected_tile:
                        idx = event.key - pygame.K_1
                        unit_groups = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        if idx < len(unit_groups):
                            g = unit_groups[idx]
                            if g in renderer.selected_unit_groups:
                                renderer.selected_unit_groups.discard(g)
                            else:
                                renderer.selected_unit_groups.add(g)
                        move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        if not move_mode:
                            move_hover_tile = None
                elif event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                renderer._slider_dragging = False
                renderer._amount_slider_dragging = False
                renderer._import_slider_dragging = False
                renderer._one_way_slider_dragging = False
                renderer._recruit_slider_dragging = False
                renderer._recruit_food_slider_dragging = False
                renderer._recruit_supply_food_slider_dragging = False
                renderer._separate_slider_dragging = None
                renderer._separate_food_slider_dragging = False
                renderer._add_job_slider_dragging = False
                renderer._add_tether_food_slider_dragging = False
                if city_drag_active and renderer.adding_one_way_route:
                    tile = renderer.get_tile_at(*event.pos)
                    current_city = selected_tile.city if selected_tile else None
                    if tile is not None and current_city is not None:
                        origin_tile = game_map.tiles[current_city.row][current_city.col]
                        if tile is not origin_tile:
                            renderer.one_way_route_pending = (current_city, tile)
                            renderer.one_way_amount = 1
                            renderer.one_way_export_material = 'food'
                    renderer.adding_one_way_route = False
                    move_hover_tile = None
                city_drag_active = False

            elif event.type == pygame.MOUSEMOTION:
                if move_mode or renderer.adding_one_way_route:
                    move_hover_tile = renderer.get_tile_at(*event.pos)
                if renderer._slider_dragging and renderer.trade_route_slider_rect:
                    sr = renderer.trade_route_slider_rect
                    t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                    renderer.trade_route_pops = max(1, min(8, round(1 + t * 7)))
                if renderer._amount_slider_dragging:
                    renderer.snap_export_amount(event.pos[0])
                if renderer._import_slider_dragging:
                    renderer.snap_import_amount(event.pos[0])
                if renderer._one_way_slider_dragging and renderer.one_way_slider_rect:
                    sr = renderer.one_way_slider_rect
                    t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                    renderer.one_way_amount = max(1, min(8, round(1 + t * 7)))
                if renderer._recruit_supply_food_slider_dragging and renderer.recruit_popup_supply_food_slider_rect:
                    sr = renderer.recruit_popup_supply_food_slider_rect
                    n = renderer.recruit_popup_amount
                    max_supply_food = max(1, n * 2)
                    t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                    renderer.recruit_popup_supply_food = max(1, min(max_supply_food, round(1 + t * (max_supply_food - 1))))
                if renderer._separate_slider_dragging and renderer.separate_popup_active:
                    unit_type = renderer._separate_slider_dragging
                    sr = renderer.separate_popup_slider_rects.get(unit_type)
                    if sr and renderer.separate_popup_group:
                        import collections
                        type_counts = collections.Counter(u.unit_type for u in renderer.separate_popup_group.units)
                        max_val = type_counts.get(unit_type, 0)
                        t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                        renderer.separate_popup_counts[unit_type] = round(t * max_val)
                if renderer._separate_food_slider_dragging and renderer.separate_popup_active and renderer.separate_popup_group:
                    from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                    sr = renderer.separate_popup_food_slider_rect
                    if sr:
                        total = sum(renderer.separate_popup_counts.values())
                        max_food = min(total * MCC, int(renderer.separate_popup_group.food_stockpile)) if total > 0 else renderer.separate_popup_min_food
                        min_food = renderer.separate_popup_min_food
                        food_range = max_food - min_food
                        t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                        renderer.separate_popup_food = max(min_food, min(max_food, min_food + round(t * food_range)))
                if renderer._add_tether_food_slider_dragging and renderer.add_tether_popup_active and renderer.add_tether_popup_group:
                    sr = renderer.add_tether_popup_slider_rect
                    if sr:
                        n_units = len(renderer.add_tether_popup_group.units)
                        max_food = max(1, n_units * 2)
                        t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                        renderer.add_tether_popup_food = max(1, min(max_food, round(1 + t * (max_food - 1))))
                if renderer._add_job_slider_dragging and renderer.add_job_popup_active and renderer.add_job_popup_city:
                    sr = renderer.add_job_popup_slider_rect
                    if sr:
                        city = renderer.add_job_popup_city
                        max_count = city.free_pops
                        t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                        renderer.add_job_popup_count = round(t * max_count)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if move_mode and event.pos[0] < renderer.map_w:
                    tile = renderer.get_tile_at(*event.pos)
                    if tile is not None and (tile.row, tile.col) in reachable:
                        controlling_faction = move_mode_unit_groups[0].faction if move_mode_unit_groups else None
                        enemy_groups = game_map.get_unit_groups(tile.row, tile.col)
                        is_enemy = bool(enemy_groups and enemy_groups[0].faction is not controlling_faction)
                        if is_enemy:
                            path, _ = game_map.get_path_to(selected_tile.row, selected_tile.col, tile.row, tile.col)
                            if len(path) >= 2:
                                stop_pos = path[-2]
                                cost = reachable[(tile.row, tile.col)]
                                for group in move_mode_unit_groups:
                                    game_map.move_group(group, stop_pos[0], stop_pos[1], cost)
                                selected_tile = game_map.tiles[stop_pos[0]][stop_pos[1]]
                                renderer.selected_unit_groups = {g for g in move_mode_unit_groups}
                                attacker_tile = selected_tile
                                defender_tile = game_map.tiles[tile.row][tile.col]
                                pending_combat_preview = compute_battle_preview(list(move_mode_unit_groups), list(enemy_groups), attacker_tile, defender_tile)
                                pending_combat_tile = defender_tile
                                battle_popup_active = True
                                move_hover_tile = None
                        else:
                            cost = reachable[(tile.row, tile.col)]
                            for group in move_mode_unit_groups:
                                game_map.move_group(group, tile.row, tile.col, cost)
                            selected_tile = game_map.tiles[tile.row][tile.col]
                            renderer.selected_unit_groups = {g for g in move_mode_unit_groups}
                            move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                            if not move_mode:
                                move_hover_tile = None

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                # print(f"[LMB] pos={pos} battle={battle_popup_active} terrain={terrain_popup_active} river={river_popup_active} save={save_popup_active} recruit={renderer.recruit_popup_active} one_way_pending={renderer.one_way_route_pending is not None}")

                _section_clicked = False
                for key, rect in renderer.section_header_rects.items():
                    if rect.collidepoint(pos):
                        if key in renderer.collapsed_sections:
                            renderer.collapsed_sections.discard(key)
                        else:
                            renderer.collapsed_sections.add(key)
                        _section_clicked = True
                        break

                if _section_clicked:
                    pass
                elif any(rect.collidepoint(pos) for rect in renderer.los_button_rects.values()):
                    for key, rect in renderer.los_button_rects.items():
                        if rect.collidepoint(pos):
                            if key == 'all':
                                los.mode = 'all'
                                los.faction = None
                            elif key == 'none':
                                los.mode = 'none'
                                los.faction = None
                            else:
                                los.mode = 'faction'
                                los.faction = factions.get(key)
                            break

                elif renderer.notification_popup_active:
                    if renderer.notification_close_rect and renderer.notification_close_rect.collidepoint(pos):
                        renderer.notification_popup_active = False

                elif renderer.notification_bell_rect and renderer.notification_bell_rect.collidepoint(pos):
                    renderer.notification_popup_active = not renderer.notification_popup_active

                elif battle_result_active:
                    if renderer.battle_result_close_rect and renderer.battle_result_close_rect.collidepoint(pos):
                        battle_result_active = False
                        pending_battle_result = None
                        pending_battle_result_preview = None

                elif battle_popup_active:
                    if renderer.battle_popup_confirm_rect and renderer.battle_popup_confirm_rect.collidepoint(pos):
                        result = resolve_battle(pending_combat_preview)
                        survivors = apply_battle_result(pending_combat_preview, result, game_map, pending_combat_tile)
                        if result['outcome'] == 'attacker_wins':
                            survivors_on_combat_tile = (
                                pending_combat_tile and
                                any(g.row == pending_combat_tile.row and g.col == pending_combat_tile.col for g in survivors)
                            )
                            if survivors_on_combat_tile:
                                selected_tile = pending_combat_tile
                            renderer.selected_unit_groups = {g for g in survivors}
                            game_log.append(f"Battle won! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        elif result['outcome'] == 'defender_wins':
                            game_log.append(f"Battle lost! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        else:
                            game_log.append(f"Battle drawn! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        battle_result_active = True
                        pending_battle_result = result
                        pending_battle_result_preview = pending_combat_preview
                        battle_popup_active = False
                        pending_combat_preview = None
                        pending_combat_tile = None
                    elif renderer.battle_popup_cancel_rect and renderer.battle_popup_cancel_rect.collidepoint(pos):
                        battle_popup_active = False
                        pending_combat_preview = None
                        pending_combat_tile = None

                elif terrain_popup_active:
                    if renderer.terrain_confirm_rect and renderer.terrain_confirm_rect.collidepoint(pos):
                        terrain_popup_active = False
                    elif renderer.terrain_cancel_rect and renderer.terrain_cancel_rect.collidepoint(pos):
                        selected_tile.biome, selected_tile.terrain_features, selected_tile.river_edges = terrain_popup_snapshot[0], list(terrain_popup_snapshot[1]), set(terrain_popup_snapshot[2])
                        selected_tile.update_terrain_properties()
                        terrain_popup_active = False
                    else:
                        changed = False
                        for biome, rect in renderer.biome_option_rects.items():
                            if rect.collidepoint(pos):
                                selected_tile.biome = biome
                                changed = True
                                break
                        for feature, rect in renderer.feature_option_rects.items():
                            if rect.collidepoint(pos):
                                if feature in selected_tile.terrain_features:
                                    selected_tile.terrain_features = [f for f in selected_tile.terrain_features if f != feature]
                                else:
                                    selected_tile.terrain_features = [f for f in selected_tile.terrain_features if f != 'water'] + [feature]
                                if 'river' not in selected_tile.terrain_features:
                                    selected_tile.river_edges.clear()
                                changed = True
                                break
                        if changed:
                            selected_tile.update_terrain_properties()
                            selected_tile.build_deposits()
                            if move_mode:
                                group = game_map.get_unit_group(selected_tile.row, selected_tile.col)
                                if group:
                                    reachable = game_map.get_reachable_from(group.row, group.col, group.moves_remaining)

                elif river_popup_active:
                    for direction, rect in renderer.river_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.river_edges.add(direction)
                            if 'river' not in selected_tile.terrain_features:
                                selected_tile.terrain_features = selected_tile.terrain_features + ['river']
                            selected_tile.update_terrain_properties()
                            selected_tile.build_deposits()
                            if move_mode:
                                group = game_map.get_unit_group(selected_tile.row, selected_tile.col)
                                if group:
                                    reachable = game_map.get_reachable_from(group.row, group.col, group.moves_remaining)
                            break
                    river_popup_active = False

                elif save_popup_active:
                    pass

                elif renderer.production_popup_active:
                    hit = False
                    for (category, subtype), rect in renderer.production_popup_rects.items():
                        if rect.collidepoint(pos):
                            if selected_tile and selected_tile.city:
                                city = selected_tile.city
                                pt = city.production_target
                                if pt.type == 'manufacturing' and pt.target_item and pt.progress > 0:
                                    pt.unfinished_items.append({'item': pt.target_item, 'progress': pt.progress})
                                city.production_target.set(category, subtype)
                                city.rebalance_pops()
                            renderer.production_popup_active = False
                            hit = True
                            break
                    if not hit:
                        renderer.production_popup_active = False

                elif renderer.add_job_popup_active:
                    city = renderer.add_job_popup_city
                    if renderer.add_job_popup_confirm_rect and renderer.add_job_popup_confirm_rect.collidepoint(pos):
                        from src.game.jobs import JobQueue
                        if city and renderer.add_job_popup_selected_type and renderer.add_job_popup_count > 0:
                            city.job_queue.append(JobQueue(renderer.add_job_popup_selected_type, renderer.add_job_popup_count))
                            city.rebalance_pops()
                        renderer.add_job_popup_active = False
                        renderer.add_job_popup_city = None
                        renderer.add_job_popup_selected_type = None
                        renderer.add_job_popup_count = 0
                    elif renderer.add_job_popup_cancel_rect and renderer.add_job_popup_cancel_rect.collidepoint(pos):
                        renderer.add_job_popup_active = False
                        renderer.add_job_popup_city = None
                        renderer.add_job_popup_selected_type = None
                        renderer.add_job_popup_count = 0
                    else:
                        for jtype, rect in renderer.add_job_popup_type_rects.items():
                            if rect.collidepoint(pos):
                                renderer.add_job_popup_selected_type = jtype
                                break
                        if renderer.add_job_popup_slider_rect and renderer.add_job_popup_slider_rect.collidepoint(pos):
                            renderer._add_job_slider_dragging = True
                            sr = renderer.add_job_popup_slider_rect
                            max_count = city.free_pops if city else 0
                            t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                            renderer.add_job_popup_count = round(t * max_count)

                elif renderer.separate_popup_active:
                    if renderer.separate_popup_confirm_rect and renderer.separate_popup_confirm_rect.collidepoint(pos):
                        group = renderer.separate_popup_group
                        if group and selected_tile:
                            from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                            counts = renderer.separate_popup_counts
                            new_units = []
                            kept_units = []
                            type_taken = {ut: 0 for ut in counts}
                            for u in group.units:
                                want = counts.get(u.unit_type, 0)
                                if type_taken.get(u.unit_type, 0) < want:
                                    new_units.append(u)
                                    type_taken[u.unit_type] += 1
                                else:
                                    kept_units.append(u)
                            group.units = kept_units
                            food = renderer.separate_popup_food
                            group.food_stockpile = max(0.0, group.food_stockpile - food)
                            group.max_food_stockpile = group._carry_capacity()
                            new_group = UnitGroup(selected_tile.row, selected_tile.col, units=new_units, faction=group.faction)
                            new_group.moves_remaining = group.moves_remaining
                            new_group.move_exhausted = group.move_exhausted
                            new_group.add_food(food)
                            selected_tile.unit_groups.append(new_group)
                            selected_tile.update_after_movement()
                            selected_tile.update_unit_allocations()
                            renderer.selected_unit_groups.discard(group)
                            renderer.selected_unit_groups.add(new_group)
                        renderer.separate_popup_active = False
                        renderer.separate_popup_group = None
                        renderer.separate_popup_counts = {}
                        renderer.separate_popup_food = 0
                    elif renderer.separate_popup_cancel_rect and renderer.separate_popup_cancel_rect.collidepoint(pos):
                        renderer.separate_popup_active = False
                        renderer.separate_popup_group = None
                        renderer.separate_popup_counts = {}
                        renderer.separate_popup_food = 0
                    else:
                        for unit_type, sr in renderer.separate_popup_slider_rects.items():
                            if sr.collidepoint(pos):
                                renderer._separate_slider_dragging = unit_type
                                import collections
                                type_counts = collections.Counter(u.unit_type for u in renderer.separate_popup_group.units)
                                max_val = type_counts.get(unit_type, 0)
                                t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                                renderer.separate_popup_counts[unit_type] = round(t * max_val)
                                break
                        if renderer.separate_popup_food_slider_rect and renderer.separate_popup_food_slider_rect.collidepoint(pos):
                            from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                            renderer._separate_food_slider_dragging = True
                            sr = renderer.separate_popup_food_slider_rect
                            total = sum(renderer.separate_popup_counts.values())
                            max_food = min(total * MCC, int(renderer.separate_popup_group.food_stockpile)) if total > 0 else renderer.separate_popup_min_food
                            min_food = renderer.separate_popup_min_food
                            food_range = max_food - min_food
                            t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                            renderer.separate_popup_food = max(min_food, min(max_food, min_food + round(t * food_range)))

                elif renderer.add_tether_popup_active and renderer.add_tether_popup_group:
                    if renderer.add_tether_popup_confirm_rect and renderer.add_tether_popup_confirm_rect.collidepoint(pos):
                        group = renderer.add_tether_popup_group
                        if selected_tile and selected_tile.city and group.tether is None:
                            city = selected_tile.city
                            tether = Tether(city=city, unit_group=group, food_amount=renderer.add_tether_popup_food)
                            group.tether = tether
                            current_tile = game_map.tiles[group.row][group.col]
                            tether.unit_movement(game_map, current_tile, current_tile)
                        renderer.add_tether_popup_active = False
                        renderer.add_tether_popup_group = None
                    elif renderer.add_tether_popup_cancel_rect and renderer.add_tether_popup_cancel_rect.collidepoint(pos):
                        renderer.add_tether_popup_active = False
                        renderer.add_tether_popup_group = None

                elif renderer.recruit_popup_active:
                    if renderer.recruit_popup_confirm_rect and renderer.recruit_popup_confirm_rect.collidepoint(pos):
                        if selected_tile and selected_tile.city:
                            from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                            city = selected_tile.city
                            n = renderer.recruit_popup_amount
                            # recruitment_cost = n  # upfront food cost per recruit (disabled)
                            stockpile_food   = renderer.recruit_popup_food * n
                            total_food       = stockpile_food
                            if total_food <= city.food_stockpile:
                                recruited_pops = city.pops[:n]
                                city.pops = city.pops[n:]
                                city.food_stockpile -= total_food
                                city.rebalance_pops()
                                new_group = UnitGroup(selected_tile.row, selected_tile.col, units=[Militia(p) for p in recruited_pops], faction=city.faction)
                                new_group.moves_remaining = 0
                                new_group.move_exhausted = True
                                new_group.add_food(stockpile_food)
                                if renderer.recruit_popup_supply_train:
                                    new_group.tether = Tether(
                                        city=city,
                                        unit_group=new_group,
                                        food_amount=renderer.recruit_popup_supply_food,
                                    )
                                selected_tile.unit_groups.append(new_group)
                                selected_tile.update_after_movement()
                                city.rebalance_pops()
                                new_group.allocate_food()
                                renderer.selected_unit_groups.add(new_group)
                                move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        renderer.recruit_popup_active = False
                        renderer.recruit_popup_food = 0
                        renderer.recruit_popup_supply_train = False
                        renderer.recruit_popup_supply_food = 1
                    elif renderer.recruit_popup_cancel_rect and renderer.recruit_popup_cancel_rect.collidepoint(pos):
                        renderer.recruit_popup_active = False
                        renderer.recruit_popup_food = 0
                        renderer.recruit_popup_supply_train = False
                        renderer.recruit_popup_supply_food = 1
                    elif renderer.recruit_all_free_rect and renderer.recruit_all_free_rect.collidepoint(pos):
                        if selected_tile and selected_tile.city:
                            renderer.recruit_popup_amount = max(0, selected_tile.city.free_pops)
                    elif renderer.recruit_dec2_rect and renderer.recruit_dec2_rect.collidepoint(pos):
                        from src.game.constants import SELECTION_INCREMENT as _SI
                        renderer.recruit_popup_amount = max(0, renderer.recruit_popup_amount - _SI)
                    elif renderer.recruit_dec1_rect and renderer.recruit_dec1_rect.collidepoint(pos):
                        renderer.recruit_popup_amount = max(0, renderer.recruit_popup_amount - 1)
                    elif renderer.recruit_inc1_rect and renderer.recruit_inc1_rect.collidepoint(pos):
                        max_recruit = max(0, len(selected_tile.city.pops) - selected_tile.city.total_farm_slots) if selected_tile and selected_tile.city else 0
                        renderer.recruit_popup_amount = min(max_recruit, renderer.recruit_popup_amount + 1)
                    elif renderer.recruit_inc2_rect and renderer.recruit_inc2_rect.collidepoint(pos):
                        from src.game.constants import SELECTION_INCREMENT as _SI
                        max_recruit = max(0, len(selected_tile.city.pops) - selected_tile.city.total_farm_slots) if selected_tile and selected_tile.city else 0
                        renderer.recruit_popup_amount = min(max_recruit, renderer.recruit_popup_amount + _SI)
                    elif renderer.recruit_food_dec_rect and renderer.recruit_food_dec_rect.collidepoint(pos):
                        renderer.recruit_popup_food = max(0, renderer.recruit_popup_food - 1)
                    elif renderer.recruit_food_inc_rect and renderer.recruit_food_inc_rect.collidepoint(pos):
                        from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                        renderer.recruit_popup_food = min(MCC, renderer.recruit_popup_food + 1)
                    elif renderer.recruit_popup_supply_checkbox_rect and renderer.recruit_popup_supply_checkbox_rect.collidepoint(pos):
                        renderer.recruit_popup_supply_train = not renderer.recruit_popup_supply_train
                        if renderer.recruit_popup_supply_train:
                            renderer.recruit_popup_supply_food = renderer.recruit_popup_amount
                    elif renderer.recruit_popup_supply_food_slider_rect and renderer.recruit_popup_supply_food_slider_rect.collidepoint(pos):
                        renderer._recruit_supply_food_slider_dragging = True
                        sr = renderer.recruit_popup_supply_food_slider_rect
                        n = renderer.recruit_popup_amount
                        max_supply_food = max(1, n * 2)
                        t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                        renderer.recruit_popup_supply_food = max(1, min(max_supply_food, round(1 + t * (max_supply_food - 1))))

                elif renderer.raise_levies_popup_active:
                    if renderer.recruit_popup_confirm_rect and renderer.recruit_popup_confirm_rect.collidepoint(pos):
                        if selected_tile and selected_tile.city:
                            city = selected_tile.city
                            n = renderer.recruit_popup_amount
                            if n > 0:
                                recruited_pops = city.pops[:n]
                                city.pops = city.pops[n:]
                                city.rebalance_pops()
                                new_group = UnitGroup(selected_tile.row, selected_tile.col, units=[Militia(p) for p in recruited_pops], faction=city.faction)
                                new_group.moves_remaining = 0
                                new_group.move_exhausted = True
                                new_group.levy = True
                                # stockpile fixed at 0; supply food = unit count
                                new_group.tether = Tether(
                                    city=city,
                                    unit_group=new_group,
                                    food_amount=n,
                                )
                                selected_tile.unit_groups.append(new_group)
                                selected_tile.update_after_movement()
                                city.rebalance_pops()
                                new_group.allocate_food()
                                renderer.selected_unit_groups.add(new_group)
                                move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        renderer.raise_levies_popup_active = False
                        renderer.recruit_popup_food = 0
                        renderer.recruit_popup_supply_food = 1
                    elif renderer.recruit_popup_cancel_rect and renderer.recruit_popup_cancel_rect.collidepoint(pos):
                        renderer.raise_levies_popup_active = False
                        renderer.recruit_popup_food = 0
                        renderer.recruit_popup_supply_food = 1
                    elif renderer.recruit_all_free_rect and renderer.recruit_all_free_rect.collidepoint(pos):
                        if selected_tile and selected_tile.city:
                            renderer.recruit_popup_amount = max(0, selected_tile.city.free_pops)
                    elif renderer.recruit_dec2_rect and renderer.recruit_dec2_rect.collidepoint(pos):
                        from src.game.constants import SELECTION_INCREMENT as _SI
                        renderer.recruit_popup_amount = max(0, renderer.recruit_popup_amount - _SI)
                    elif renderer.recruit_dec1_rect and renderer.recruit_dec1_rect.collidepoint(pos):
                        renderer.recruit_popup_amount = max(0, renderer.recruit_popup_amount - 1)
                    elif renderer.recruit_inc1_rect and renderer.recruit_inc1_rect.collidepoint(pos):
                        max_recruit = len(selected_tile.city.pops) - 1 if selected_tile and selected_tile.city else 0
                        renderer.recruit_popup_amount = min(max_recruit, renderer.recruit_popup_amount + 1)
                    elif renderer.recruit_inc2_rect and renderer.recruit_inc2_rect.collidepoint(pos):
                        from src.game.constants import SELECTION_INCREMENT as _SI
                        max_recruit = len(selected_tile.city.pops) - 1 if selected_tile and selected_tile.city else 0
                        renderer.recruit_popup_amount = min(max_recruit, renderer.recruit_popup_amount + _SI)
                    elif renderer.recruit_food_dec_rect and renderer.recruit_food_dec_rect.collidepoint(pos):
                        renderer.recruit_popup_food = max(0, renderer.recruit_popup_food - 1)
                    elif renderer.recruit_food_inc_rect and renderer.recruit_food_inc_rect.collidepoint(pos):
                        from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                        renderer.recruit_popup_food = min(MCC, renderer.recruit_popup_food + 1)
                    elif renderer.recruit_popup_supply_food_slider_rect and renderer.recruit_popup_supply_food_slider_rect.collidepoint(pos):
                        renderer._recruit_supply_food_slider_dragging = True
                        sr = renderer.recruit_popup_supply_food_slider_rect
                        n = renderer.recruit_popup_amount
                        max_supply_food = max(1, n * 2)
                        t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                        renderer.recruit_popup_supply_food = max(1, min(max_supply_food, round(1 + t * (max_supply_food - 1))))

                elif renderer.add_tether_popup_active and renderer.add_tether_popup_group:
                    if renderer.add_tether_popup_slider_rect and renderer.add_tether_popup_slider_rect.collidepoint(pos):
                        renderer._add_tether_food_slider_dragging = True
                        sr = renderer.add_tether_popup_slider_rect
                        n_units = len(renderer.add_tether_popup_group.units)
                        max_food = max(1, n_units * 2)
                        t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                        renderer.add_tether_popup_food = max(1, min(max_food, round(1 + t * (max_food - 1))))

                elif renderer.trade_route_pending and renderer.trade_route_import_slider_rect and renderer.trade_route_import_slider_rect.collidepoint(pos):
                    renderer.snap_import_amount(pos[0])
                    renderer._import_slider_dragging = True

                elif renderer.trade_route_pending and renderer.trade_route_amount_slider_rect and renderer.trade_route_amount_slider_rect.collidepoint(pos):
                    renderer.snap_export_amount(pos[0])
                    renderer._amount_slider_dragging = True

                elif renderer.trade_route_pending and renderer.trade_route_slider_rect and renderer.trade_route_slider_rect.collidepoint(pos):
                    sr = renderer.trade_route_slider_rect
                    t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                    renderer.trade_route_pops = max(1, min(8, round(1 + t * 7)))
                    renderer._slider_dragging = True

                elif any(r.collidepoint(pos) for r in renderer.trade_route_import_rects.values()):
                    for label, rect in renderer.trade_route_import_rects.items():
                        if rect.collidepoint(pos):
                            key = label.lower()
                            renderer.trade_route_import = key if renderer.trade_route_import != key else None
                            break

                elif any(r.collidepoint(pos) for r in renderer.trade_route_export_rects.values()):
                    for label, rect in renderer.trade_route_export_rects.items():
                        if rect.collidepoint(pos):
                            key = label.lower()
                            renderer.trade_route_export = key if renderer.trade_route_export != key else None
                            break

                # elif renderer.trade_route_confirm_rect and renderer.trade_route_confirm_rect.collidepoint(pos):
                #     city_a, city_b = renderer.trade_route_pending
                #     dest_tile = game_map.tiles[city_b.row][city_b.col]
                #     route = TradeRoute(
                #         city_a=city_a,
                #         dest_tile=dest_tile,
                #         pops_a=renderer.trade_route_pops,
                #         pops_b=renderer.trade_route_pops,
                #         partial_pops_a=None,
                #         partial_pops_b=None,
                #         export_resource=renderer.trade_route_export,
                #         export_amount=renderer.trade_route_export_amount,
                #         max_amount=renderer.trade_route_max_amount,
                #         import_resource=renderer.trade_route_import,
                #         import_amount=renderer.trade_route_import_amount,
                #     )
                #     renderer.trade_route_pending = None
                #     renderer.adding_trade_route = False

                elif renderer.one_way_route_pending and any(r.collidepoint(pos) for r in renderer.one_way_route_style_rects.values()):
                    for label, rect in renderer.one_way_route_style_rects.items():
                        if rect.collidepoint(pos):
                            renderer.one_way_route_style = label.lower().replace(' ', '_')
                            break

                elif renderer.one_way_route_pending and any(r.collidepoint(pos) for r in renderer.one_way_route_type_rects.values()):
                    for label, rect in renderer.one_way_route_type_rects.items():
                        if rect.collidepoint(pos):
                            renderer.one_way_route_type = label.lower()
                            break

                elif renderer.one_way_route_pending and any(r.collidepoint(pos) for r in renderer.one_way_export_rects.values()):
                    for label, rect in renderer.one_way_export_rects.items():
                        if rect.collidepoint(pos):
                            renderer.one_way_export_material = label.lower()
                            break

                elif renderer.one_way_route_pending and any(r.collidepoint(pos) for r in renderer.one_way_import_rects.values()):
                    for label, rect in renderer.one_way_import_rects.items():
                        if rect.collidepoint(pos):
                            renderer.one_way_import_material = label.lower()
                            break

                elif renderer.one_way_route_pending and renderer.one_way_confirm_rect and renderer.one_way_confirm_rect.collidepoint(pos):
                    city_a, dest_tile = renderer.one_way_route_pending
                    water = renderer.one_way_route_type == 'water'
                    two_way = renderer.one_way_route_style == 'two_way'
                    path, path_distances = game_map.get_path_to(city_a.row, city_a.col, dest_tile.row, dest_tile.col, mode='water' if water else 'land')
                    total_pops = renderer.one_way_pops_required_whole
                    if two_way:
                        pops_a = (total_pops + 1) // 2
                        pops_b = total_pops // 2
                    else:
                        pops_a = total_pops
                        pops_b = 0
                    TradeRoute(
                        city_a=city_a,
                        dest_tile=dest_tile,
                        pops_a=pops_a,
                        pops_b=pops_b,
                        partial_pops_a=renderer.one_way_partial_pops,
                        partial_pops_b=None,
                        export_resource=renderer.one_way_export_material,
                        export_amount=renderer.one_way_amount,
                        max_amount=renderer.one_way_amount,
                        import_resource=renderer.one_way_import_material if two_way else None,
                        import_amount=0,
                        path=path,
                        path_distances=path_distances,
                        water=water,
                        one_way=not two_way,
                    )
                    renderer.one_way_route_pending = None
                    renderer.one_way_route_type = 'land'

                elif renderer.one_way_route_pending and renderer.one_way_cancel_rect and renderer.one_way_cancel_rect.collidepoint(pos):
                    renderer.one_way_route_pending = None
                    renderer.one_way_route_type = 'land'

                elif any(r.collidepoint(pos) for r, _ in renderer.group_icon_rects):
                    for rect, group in renderer.group_icon_rects:
                        if rect.collidepoint(pos):
                            if group in renderer.selected_unit_groups:
                                renderer.selected_unit_groups.discard(group)
                            else:
                                renderer.selected_unit_groups.add(group)
                            break
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.select_all_button_rect and renderer.select_all_button_rect.collidepoint(pos):
                    if selected_tile:
                        tile_groups = set(game_map.get_unit_groups(selected_tile.row, selected_tile.col))
                        if tile_groups.issubset(renderer.selected_unit_groups):
                            renderer.selected_unit_groups -= tile_groups
                        else:
                            renderer.selected_unit_groups.update(tile_groups)
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                    if not move_mode:
                        move_hover_tile = None

                elif renderer.production_target_button_rect and renderer.production_target_button_rect.collidepoint(pos):
                    renderer.production_popup_active = True
                    renderer.selecting_extraction_city = None

                elif renderer.select_extraction_tile_button_rect and renderer.select_extraction_tile_button_rect.collidepoint(pos):
                    city = selected_tile.city if selected_tile else None
                    if city:
                        renderer.selecting_extraction_city = None if renderer.selecting_extraction_city is city else city

                elif renderer.recruit_unit_button_rect and renderer.recruit_unit_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city and len(selected_tile.city.pops) > selected_tile.city.total_farm_slots:
                        renderer.recruit_popup_active = True
                        renderer.recruit_popup_amount = 0

                elif renderer.raise_levies_button_rect and renderer.raise_levies_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city and len(selected_tile.city.pops) > 1:
                        renderer.raise_levies_popup_active = True
                        renderer.recruit_popup_amount = max(0, selected_tile.city.free_pops)
                        renderer.recruit_popup_supply_food = renderer.recruit_popup_amount

                elif renderer.disband_button_rect and renderer.disband_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city:
                        city = selected_tile.city
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        for group in selected_on_tile:
                            _drop_items_for_units(group.units, selected_tile)
                            city.pops.extend(unit.pop for unit in group.units)
                            transferable = min(group.food_stockpile, city._stockpile_max() - city.food_stockpile)
                            city.food_stockpile += max(0.0, transferable)
                            selected_tile.unit_groups.remove(group)
                            renderer.selected_unit_groups.discard(group)
                        city.rebalance_pops()
                        selected_tile.update_after_movement()
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.equip_button_rect and renderer.equip_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.item_stockpiles:
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        if not selected_on_tile:
                            selected_on_tile = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        if len(selected_on_tile) == 1:
                            selected_on_tile[0].equip_from_stockpile(selected_tile.item_stockpiles)
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.settle_button_rect and renderer.settle_button_rect.collidepoint(pos):
                    if selected_tile and not selected_tile.city:
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        if not selected_on_tile:
                            selected_on_tile = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        if selected_on_tile:
                            settle_faction = selected_on_tile[0].faction
                            all_pops = [unit.pop for g in selected_on_tile for unit in g.units]
                            starting_food = sum(g.food_stockpile for g in selected_on_tile)
                            city_name = settle_faction.take_city_name() if settle_faction else game_map._take_city_name()
                            new_city = City(selected_tile.row, selected_tile.col, city_name, faction=settle_faction, population=0)
                            new_city.pops = all_pops
                            game_map.cities[(selected_tile.row, selected_tile.col)] = new_city
                            for group in selected_on_tile:
                                selected_tile.unit_groups.remove(group)
                                renderer.selected_unit_groups.discard(group)
                            game_map.setup_city(new_city)
                            new_city.rebalance_pops()
                            new_city.food_stockpile = min(starting_food, new_city._stockpile_max())
                            selected_tile.update_after_movement()
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.separate_button_rect and renderer.separate_button_rect.collidepoint(pos):
                    if selected_tile:
                        all_unit_groups = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        selected_on_tile = [g for g in all_unit_groups if g in renderer.selected_unit_groups]
                        if len(selected_on_tile) == 1:
                            import collections
                            renderer.separate_popup_group = selected_on_tile[0]
                            renderer.separate_popup_counts = {
                                ut: 0 for ut in collections.Counter(
                                    u.unit_type for u in selected_on_tile[0].units
                                )
                            }
                            renderer.separate_popup_food = 0
                            renderer.separate_popup_active = True

                elif renderer.merge_button_rect and renderer.merge_button_rect.collidepoint(pos):
                    if selected_tile:
                        all_unit_groups = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        selected_on_tile = [g for g in all_unit_groups if g in renderer.selected_unit_groups]
                        if len(selected_on_tile) >= 2:
                            target = selected_on_tile[0]
                            for other in selected_on_tile[1:]:
                                target.merge(other)
                                selected_tile.unit_groups.remove(other)
                                renderer.selected_unit_groups.discard(other)
                            selected_tile.update_after_movement()
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.restock_button_rect and renderer.restock_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city:
                        from src.game.constants import POP_FOOD_CONSUMPTION
                        city = selected_tile.city
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        for group in selected_on_tile:
                            amount = len(group.units) * POP_FOOD_CONSUMPTION
                            transfer = min(amount, city.food_stockpile, group.max_food_stockpile - group.food_stockpile)
                            if transfer > 0:
                                city.food_stockpile -= transfer
                                group.add_food(transfer)

                elif renderer.drop_button_rect and renderer.drop_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city:
                        from src.game.constants import POP_FOOD_CONSUMPTION
                        city = selected_tile.city
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        for group in selected_on_tile:
                            amount = len(group.units) * POP_FOOD_CONSUMPTION
                            space = city._stockpile_max() - city.food_stockpile
                            transfer = min(amount, group.food_stockpile, space)
                            if transfer > 0:
                                group.food_stockpile -= transfer
                                city.food_stockpile += transfer

                elif renderer.add_tether_button_rect and renderer.add_tether_button_rect.collidepoint(pos):
                    selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                    if selected_on_tile:
                        group = selected_on_tile[0]
                        renderer.add_tether_popup_active = True
                        renderer.add_tether_popup_group = group
                        renderer.add_tether_popup_food = len(group.units)

                elif renderer.drop_tether_button_rect and renderer.drop_tether_button_rect.collidepoint(pos):
                    selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                    for group in selected_on_tile:
                        if group.tether is not None:
                            group.drop_tether(game_map)

                elif any(r.collidepoint(pos) for r, _ in renderer.trade_route_delete_rects):
                    for rect, route in renderer.trade_route_delete_rects:
                        if rect.collidepoint(pos):
                            route.detach(rebalance=True)
                            break

                elif any(r.collidepoint(pos) for r, _ in renderer.trade_route_reduce_rects):
                    for rect, route in renderer.trade_route_reduce_rects:
                        if rect.collidepoint(pos):
                            route.reduce_export_amount()
                            break

                elif renderer.one_way_route_pending and renderer.one_way_slider_rect and renderer.one_way_slider_rect.collidepoint(pos):
                    sr = renderer.one_way_slider_rect
                    t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                    renderer.one_way_amount = max(1, min(8, round(1 + t * 7)))
                    renderer._one_way_slider_dragging = True

                # elif renderer.add_trade_route_button_rect and renderer.add_trade_route_button_rect.collidepoint(pos):
                #     renderer.adding_trade_route = not renderer.adding_trade_route
                #     renderer.adding_one_way_route = False
                #     if not renderer.adding_trade_route:
                #         renderer.trade_route_pending = None

                elif renderer.add_one_way_route_button_rect and renderer.add_one_way_route_button_rect.collidepoint(pos):
                    renderer.adding_one_way_route = not renderer.adding_one_way_route
                    renderer.adding_trade_route = False
                    if not renderer.adding_one_way_route:
                        renderer.trade_route_pending = None
                        move_hover_tile = None

                elif renderer.draw_river_button_rect and renderer.draw_river_button_rect.collidepoint(pos):
                    river_popup_active = True

                elif renderer.change_terrain_button_rect and renderer.change_terrain_button_rect.collidepoint(pos):
                    terrain_popup_active = True
                    terrain_popup_snapshot = (selected_tile.biome, list(selected_tile.terrain_features), set(selected_tile.river_edges))

                elif renderer.rebalance_pops_button_rect and renderer.rebalance_pops_button_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        city.rebalance_pops()

                elif renderer.restrict_tile_button_rect and renderer.restrict_tile_button_rect.collidepoint(pos):
                    if selected_tile:
                        selected_tile.restricted = not selected_tile.restricted
                        selected_tile._restricted_ticker = RESTRICTED_STARTING_TICKER if selected_tile.restricted else 0
                        selected_tile.update_terrain_properties()
                        city = selected_tile.owning_city
                        if city:
                            city._build_cumulative_farm_yield()
                            city.update_cumulative_farm_yield_net()
                            city.rebalance_pops()

                elif any(r.collidepoint(pos) for r in renderer.city_focus_rects.values()):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for label, rect in renderer.city_focus_rects.items():
                            if rect.collidepoint(pos):
                                city.city_focus = label
                                city.rebalance_pops()
                                break

                elif renderer.halt_growth_rect and renderer.halt_growth_rect.collidepoint(pos):
                    city = selected_tile.city if selected_tile else None
                    if city:
                        city.growth_halted = not city.growth_halted
                        if city.growth_halted and city.city_focus == 'Growth':
                            city.city_focus = 'Production'
                        city.rebalance_pops()

                elif renderer.gates_closed_rect and renderer.gates_closed_rect.collidepoint(pos):
                    city = selected_tile.city if selected_tile else None
                    if city:
                        city.gates_closed = not city.gates_closed

                elif any(r.collidepoint(pos) for r in renderer.job_queue_up_rects):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for i, r in enumerate(renderer.job_queue_up_rects):
                            if r.collidepoint(pos) and i > 0:
                                city.job_queue[i], city.job_queue[i - 1] = city.job_queue[i - 1], city.job_queue[i]
                                city.rebalance_pops()
                                break

                elif any(r.collidepoint(pos) for r in renderer.job_queue_down_rects):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for i, r in enumerate(renderer.job_queue_down_rects):
                            if r.collidepoint(pos) and i < len(city.job_queue) - 1:
                                city.job_queue[i], city.job_queue[i + 1] = city.job_queue[i + 1], city.job_queue[i]
                                city.rebalance_pops()
                                break

                elif any(r.collidepoint(pos) for r in renderer.job_queue_minus_rects):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for i, r in enumerate(renderer.job_queue_minus_rects):
                            if r.collidepoint(pos):
                                if city.job_queue[i].count <= 1:
                                    city.job_queue.pop(i)
                                else:
                                    city.job_queue[i].count -= 1
                                city.rebalance_pops()
                                break

                elif any(r.collidepoint(pos) for r in renderer.job_queue_plus_rects):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for i, r in enumerate(renderer.job_queue_plus_rects):
                            if r.collidepoint(pos):
                                city.job_queue[i].count = min(city.free_pops, city.job_queue[i].count + 1)
                                city.rebalance_pops()
                                break

                elif any(r.collidepoint(pos) for r in renderer.job_queue_x_rects):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for i, r in enumerate(renderer.job_queue_x_rects):
                            if r.collidepoint(pos):
                                city.job_queue.pop(i)
                                city.rebalance_pops()
                                break

                elif renderer.add_job_button_rect and renderer.add_job_button_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        renderer.add_job_popup_active = True
                        renderer.add_job_popup_city = city
                        renderer.add_job_popup_selected_type = None
                        renderer.add_job_popup_count = 0

                elif renderer.save_map_button_rect and renderer.save_map_button_rect.collidepoint(pos):
                    save_popup_active = True
                    save_popup_text = ""

                elif renderer.move_button_rect and renderer.move_button_rect.collidepoint(pos):
                    if move_mode:
                        move_mode = False
                        move_mode_unit_groups = []
                        reachable = {}
                        move_hover_tile = None

                elif renderer.capture_button_rect and renderer.capture_button_rect.collidepoint(pos):
                    if selected_tile:
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        attacker_faction = selected_on_tile[0].faction if selected_on_tile else None
                        friendly_city = next((c for c in selected_tile.cities_in_range if c.faction is attacker_faction), None)
                        if friendly_city:
                            enemy_city = selected_tile.owning_city
                            if enemy_city is not None:
                                enemy_city.owned_tiles.remove(selected_tile)
                                enemy_city._build_cumulative_farm_yield()
                                enemy_city.update_cumulative_farm_yield_net()
                                enemy_city.rebalance_pops()
                            source_group = selected_on_tile[0]
                            detached_unit = source_group.units.pop(0)
                            source_group.max_food_stockpile = source_group._carry_capacity()
                            if not source_group.units:
                                selected_tile.unit_groups = [g for g in selected_tile.unit_groups if g.units]
                                renderer.selected_unit_groups.discard(source_group)
                            detached_unit.pop.assigned_job = None
                            friendly_city.pops.append(detached_unit.pop)
                            selected_tile.owning_city = friendly_city
                            _, dists = game_map.get_path_to(friendly_city.row, friendly_city.col, selected_tile.row, selected_tile.col, mode='any')
                            selected_tile.city_distance = dists[-1] if dists else None
                            friendly_city.owned_tiles.append(selected_tile)
                            friendly_city._build_cumulative_farm_yield()
                            friendly_city.update_cumulative_farm_yield_net()
                            friendly_city.rebalance_pops()
                            game_log.append(f"Captured tile ({selected_tile.row},{selected_tile.col}) for {friendly_city.name}.")

                elif renderer.raid_button_rect and renderer.raid_button_rect.collidepoint(pos):
                    if selected_tile:
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        num_units = sum(len(g.units) for g in selected_on_tile)
                        result = selected_tile.raid(num_units)
                        for group in selected_on_tile:
                            group.moves_remaining = max(0, group.moves_remaining - 2)
                            if group.moves_remaining == 0:
                                group.move_exhausted = True
                        raided = result['raided_farms']
                        captured_pops = result['captured_pops']
                        remaining_food = result['food_gained']
                        for group in selected_on_tile:
                            if remaining_food <= 0:
                                break
                            remaining_food -= group.add_food(remaining_food)
                        if captured_pops:
                            attacker_faction = selected_on_tile[0].faction if selected_on_tile else None
                            new_group = UnitGroup(selected_tile.row, selected_tile.col,
                                                  units=[Militia(p) for p in captured_pops],
                                                  faction=attacker_faction)
                            new_group.moves_remaining = DEFAULT_MOVE_DISTANCE
                            new_group.move_exhausted = False
                            new_group.add_food(float(len(captured_pops)))
                            selected_tile.unit_groups.append(new_group)
                            selected_tile.update_after_movement()
                        game_log.append(f"Raid: {raided} farms, {result['food_gained']:.0f} food, {len(captured_pops)} captured.")

                elif renderer.plunder_route_button_rect and renderer.plunder_route_button_rect.collidepoint(pos):
                    if selected_tile:
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        for group in selected_on_tile:
                            group.moves_remaining = max(0, group.moves_remaining - 2)
                            if group.moves_remaining == 0:
                                group.move_exhausted = True
                        plundering_faction = selected_on_tile[0].faction if selected_on_tile else None
                        plunder = game_map.plunder_routes(selected_tile, plundering_faction)
                        for resource, amount in plunder.items():
                            if resource == 'food':
                                remaining = amount
                                for group in selected_on_tile:
                                    if remaining <= 0:
                                        break
                                    remaining -= group.add_food(remaining)
                            else:
                                selected_tile.add_resources_to_stockpile(amount, resource)
                        game_log.append(f"Plunder: {', '.join(f'{v:.0f} {k}' for k, v in plunder.items()) or 'nothing found'}.")

                elif renderer.end_turn_button_rect and renderer.end_turn_button_rect.collidepoint(pos):
                    do_end_turn = True

                elif renderer.selecting_extraction_city and renderer.map_start_x <= pos[0] < renderer.map_w:
                    clicked_tile = renderer.get_tile_at(*pos)
                    city = renderer.selecting_extraction_city
                    pt = city.production_target
                    if clicked_tile and pt.type == 'extraction' and pt.target:
                        if clicked_tile in city.get_eligible_extraction_tiles(pt.target):
                            city.selected_extraction_tile = clicked_tile
                            city.rebalance_pops()
                    renderer.selecting_extraction_city = None

                elif renderer.adding_one_way_route and renderer.map_start_x <= pos[0] < renderer.map_w:
                    tile = renderer.get_tile_at(*pos)
                    current_city = selected_tile.owning_city if selected_tile else None
                    if tile is not None and current_city is not None:
                        origin_tile = game_map.tiles[current_city.row][current_city.col]
                        if tile is not origin_tile:
                            renderer.one_way_route_pending = (current_city, tile)
                            renderer.one_way_amount = 1
                    renderer.adding_one_way_route = False
                    move_hover_tile = None

                elif renderer.map_start_x <= pos[0] < renderer.map_w:
                    clicked_tile = renderer.get_tile_at(*pos)
                    prev = f"({selected_tile.row},{selected_tile.col})" if selected_tile else "None"
                    clicked = f"({clicked_tile.row},{clicked_tile.col}) city={clicked_tile.city.name if clicked_tile and clicked_tile.city else None}" if clicked_tile else "None"
                    # print(f"[CLICK] prev={prev} clicked={clicked} units_on_clicked={[str(g.faction.name if g.faction else '?') for g in (game_map.get_unit_groups(clicked_tile.row, clicked_tile.col) if clicked_tile else [])]}")
                    if clicked_tile and selected_tile and clicked_tile.row == selected_tile.row and clicked_tile.col == selected_tile.col:
                        unit_groups = game_map.get_unit_groups(selected_tile.row, selected_tile.col)
                        if unit_groups and all(g in renderer.selected_unit_groups for g in unit_groups):
                            renderer.selected_unit_groups.clear()
                        else:
                            renderer.selected_unit_groups.update(unit_groups)
                    else:
                        selected_tile = clicked_tile
                        renderer.selected_unit_groups.clear()
                        if selected_tile:
                            renderer.selected_unit_groups.update(game_map.get_unit_groups(selected_tile.row, selected_tile.col))
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None
                    if clicked_tile and clicked_tile.city:
                        renderer.adding_one_way_route = True
                        city_drag_active = True

        if do_end_turn:
            turn += 1
            game_log.append("")
            renderer.notification_popup_active = False
            for faction in factions.values():
                faction.notification_log.clear()
                faction.do_turn(game_map, turn)
            for row in game_map.tiles:
                for tile in row:
                    for group in tile.unit_groups:
                        group.end_turn(tile, game_map)
                    tile.unit_groups = [g for g in tile.unit_groups if g.units]
            for city in game_map.cities.values():
                for msg in city.end_turn():
                    game_log.append(f"T{turn} {msg}")
            collapsed = [city for city in game_map.cities.values() if not city.pops]
            for city in collapsed:
                game_log.append(f"T{turn} {city.name} has collapsed!")
                game_map.remove_city(city)
            seen = set()
            for city in game_map.cities.values():
                for route in city.trade_routes:
                    if id(route) not in seen:
                        seen.add(id(route))
                        route.end_turn()
            for row in game_map.tiles:
                for tile in row:
                    for group in tile.unit_groups:
                        if group.tether is not None:
                            group.tether.tether_catchup()
            for row in game_map.tiles:
                for tile in row:
                    if tile.has_active_tickers():
                        tile.update_tickers()
            for (r, c) in game_map.unit_groups:
                game_map.tiles[r][c].update_unit_allocations()
            move_hover_tile = None
            move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
            game_log.append(f"TURN {turn}")

        if not console_active and not save_popup_active:
            keys = pygame.key.get_pressed()
            pan_speed = 6 * renderer.zoom ** 2
            if keys[pygame.K_w]: renderer.offset_y += pan_speed
            if keys[pygame.K_s]: renderer.offset_y -= pan_speed
            if keys[pygame.K_a]: renderer.offset_x += pan_speed
            if keys[pygame.K_d]: renderer.offset_x -= pan_speed

        renderer.draw(selected_tile, reachable, move_mode,
                      save_popup_active, save_popup_text,
                      terrain_popup_active, river_popup_active,
                      moves_remaining=min(g.moves_remaining for g in move_mode_unit_groups) if move_mode_unit_groups else None,
                      game_log=game_log,
                      move_hover_tile=move_hover_tile,
                      console_active=console_active,
                      console_input=console_input,
                      battle_popup_active=battle_popup_active,
                      battle_popup_preview=pending_combat_preview,
                      battle_result_active=battle_result_active,
                      battle_result=pending_battle_result,
                      battle_result_preview=pending_battle_result_preview,
                      los=los,
                      factions=factions)
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
