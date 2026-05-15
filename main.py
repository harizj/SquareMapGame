import json
import os
import pygame
from src.game.battles import compute_battle_preview, resolve_battle
from src.game.city import City
from src.game.faction import Faction, COLOR_SETS, CITY_NAME_SETS
from src.game.pop import Pop
from src.game.unit_group import UnitGroup
from src.game.map import Map
from src.game.save_load import load_map_data, save_map
from src.game.trade_route import TradeRoute
from src.game.unit import Unit
from src.ui.renderer import Renderer
from src.game.constants import DEFAULT_MOVE_DISTANCE

_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_CONFIG_PATH = os.path.join(_DIR, 'game_config.json')


def _load_game_config():
    if os.path.exists(GAME_CONFIG_PATH):
        with open(GAME_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def _apply_game_config(game_map, game_config):
    factions = {}
    for f_data in game_config.get('factions', []):
        faction = Faction(
            name=f_data['name'],
            colors=COLOR_SETS[f_data['colors']],
            city_names=CITY_NAME_SETS[f_data['city_names']],
        )
        factions[f_data['name']] = faction

    for city_data in game_config.get('cities', []):
        r, c = city_data['row'], city_data['col']
        faction = factions.get(city_data.get('faction'))
        name = city_data.get('name') or (faction.take_city_name() if faction else game_map._take_city_name())
        population = city_data.get('population', 20)
        city = City(r, c, name, faction=faction, population=population)
        game_map.cities[(r, c)] = city
        game_map.setup_city(city)

    for ug_data in game_config.get('unit_groups', []):
        r, c = ug_data['row'], ug_data['col']
        faction = factions.get(ug_data.get('faction'))
        group = UnitGroup(r, c, units=[Unit(Pop()) for _ in range(ug_data['num_units'])], faction=faction)
        group.add_food(ug_data['food'])
        group.allocate_food()
        game_map.tiles[r][c].unit_groups.append(group)

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
            return True, candidates, game_map.get_reachable_budget(selected_tile.row, selected_tile.col, budget, blocked=blocked)
    return False, [], {}


def main():
    pygame.init()

    game_config = _load_game_config()
    map_name = game_config.get('map', '').strip()
    if map_name:
        data = load_map_data(map_name)
        if data:
            game_map = Map.from_dict(data)
        else:
            print(f"Map '{map_name}' not found — starting fresh map.")
            game_map = Map()
    else:
        game_map = Map()
    factions = _apply_game_config(game_map, game_config)

    renderer = Renderer(game_map)
    clock = pygame.time.Clock()
    selected_tile = None
    move_mode = False
    move_mode_unit_groups = []
    reachable = {}
    move_hover_tile = None
    save_popup_active = False
    save_popup_text = ""
    terrain_popup_active = False
    river_popup_active = False
    battle_popup_active = False
    pending_combat_preview = None
    pending_combat_tile = None
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
                        print(f"Saved: {path}")
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
                if renderer._recruit_slider_dragging and renderer.recruit_popup_slider_rect and selected_tile and selected_tile.city:
                    sr = renderer.recruit_popup_slider_rect
                    max_recruit = min(8, len(selected_tile.city.pops) - 1)
                    t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                    renderer.recruit_popup_amount = max(1, min(max_recruit, round(1 + t * (max_recruit - 1))))
                if renderer._recruit_food_slider_dragging and renderer.recruit_popup_food_slider_rect and selected_tile and selected_tile.city:
                    from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                    sr = renderer.recruit_popup_food_slider_rect
                    max_food = int(min(selected_tile.city.food_stockpile, renderer.recruit_popup_amount * MCC))
                    t = max(0.0, min(1.0, (event.pos[0] - sr.x) / sr.width))
                    renderer.recruit_popup_food = max(0, min(max_food, round(t * max_food)))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if move_mode and event.pos[0] < renderer.map_w:
                    tile = renderer.get_tile_at(*event.pos)
                    if tile is not None and (tile.row, tile.col) in reachable:
                        controlling_faction = move_mode_unit_groups[0].faction if move_mode_unit_groups else None
                        enemy_groups = game_map.get_unit_groups(tile.row, tile.col)
                        is_enemy = bool(enemy_groups and enemy_groups[0].faction is not controlling_faction)
                        if is_enemy:
                            path, _ = game_map.get_path(selected_tile.row, selected_tile.col, tile.row, tile.col)
                            if len(path) >= 2:
                                stop_pos = path[-2]
                                if stop_pos != (selected_tile.row, selected_tile.col):
                                    stop_cost = reachable[stop_pos]
                                    for group in move_mode_unit_groups:
                                        game_map.move_group(group, stop_pos[0], stop_pos[1], stop_cost)
                                    selected_tile = game_map.tiles[stop_pos[0]][stop_pos[1]]
                                    renderer.selected_unit_groups = {g for g in move_mode_unit_groups}
                                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
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
                print(f"[LMB] pos={pos} battle={battle_popup_active} terrain={terrain_popup_active} river={river_popup_active} save={save_popup_active} recruit={renderer.recruit_popup_active} one_way_pending={renderer.one_way_route_pending is not None}")

                if battle_popup_active:
                    if renderer.battle_popup_confirm_rect and renderer.battle_popup_confirm_rect.collidepoint(pos):
                        result = resolve_battle(pending_combat_preview)
                        attacker_groups = pending_combat_preview['attacker_groups']
                        defender = pending_combat_preview['defender']
                        a_losses = result['attacker_losses']
                        for group in reversed(attacker_groups):
                            while a_losses > 0 and group.units:
                                group.units.pop()
                                a_losses -= 1
                        d_losses = result['defender_losses']
                        for group in reversed(defender):
                            while d_losses > 0 and group.units:
                                group.units.pop()
                                d_losses -= 1
                        if result['outcome'] == 'attacker_wins':
                            if pending_combat_tile:
                                pending_combat_tile.unit_groups = [g for g in pending_combat_tile.unit_groups if g.units]
                                if not pending_combat_tile.unit_groups:
                                    step_cost = game_map._step_cost(selected_tile.row, selected_tile.col, pending_combat_tile.row, pending_combat_tile.col)
                                    survivors = [g for g in attacker_groups if g.units]
                                    for group in survivors:
                                        game_map.move_group(group, pending_combat_tile.row, pending_combat_tile.col, step_cost)
                                    selected_tile = pending_combat_tile
                                    renderer.selected_unit_groups = {g for g in survivors}
                            game_log.append(f"Battle won! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        elif result['outcome'] == 'defender_wins':
                            game_log.append(f"Battle lost! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        else:
                            game_log.append(f"Battle drawn! Losses — us: {result['attacker_losses']}, them: {result['defender_losses']}")
                        for row in game_map.tiles:
                            for t in row:
                                t.unit_groups = [g for g in t.unit_groups if g.units]
                        move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        battle_popup_active = False
                        pending_combat_preview = None
                        pending_combat_tile = None
                    elif renderer.battle_popup_cancel_rect and renderer.battle_popup_cancel_rect.collidepoint(pos):
                        battle_popup_active = False
                        pending_combat_preview = None
                        pending_combat_tile = None

                elif terrain_popup_active:
                    for terrain, rect in renderer.terrain_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.terrain = terrain
                            if terrain in ('hills', 'desert'):
                                selected_tile.river_edges.clear()
                            if move_mode:
                                group = game_map.get_unit_group(selected_tile.row, selected_tile.col)
                                if group:
                                    reachable = game_map.get_reachable(group)
                            break
                    terrain_popup_active = False

                elif river_popup_active:
                    for direction, rect in renderer.river_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.river_edges.add(direction)
                            selected_tile.terrain = 'river'
                            if move_mode:
                                group = game_map.get_unit_group(selected_tile.row, selected_tile.col)
                                if group:
                                    reachable = game_map.get_reachable(group)
                            break
                    river_popup_active = False

                elif save_popup_active:
                    pass

                elif renderer.recruit_popup_active:
                    if renderer.recruit_popup_confirm_rect and renderer.recruit_popup_confirm_rect.collidepoint(pos):
                        if selected_tile and selected_tile.city:
                            from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                            city = selected_tile.city
                            n = renderer.recruit_popup_amount
                            food = renderer.recruit_popup_food
                            recruited_pops = city.pops[:n]
                            city.pops = city.pops[n:]
                            city.food_stockpile -= food
                            city.rebalance_pops()
                            new_group = UnitGroup(selected_tile.row, selected_tile.col, units=[Unit(p) for p in recruited_pops], faction=city.faction)
                            new_group.moves_remaining = 0
                            new_group.move_exhausted = True
                            new_group.add_food(food)
                            selected_tile.unit_groups.append(new_group)
                            selected_tile.update_after_movement()
                            city.rebalance_pops()
                            new_group.allocate_food()
                            renderer.selected_unit_groups.add(new_group)
                            move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                        renderer.recruit_popup_active = False
                        renderer.recruit_popup_food = 0
                    elif renderer.recruit_popup_cancel_rect and renderer.recruit_popup_cancel_rect.collidepoint(pos):
                        renderer.recruit_popup_active = False
                        renderer.recruit_popup_food = 0
                    elif renderer.recruit_popup_slider_rect and renderer.recruit_popup_slider_rect.collidepoint(pos):
                        renderer._recruit_slider_dragging = True
                        sr = renderer.recruit_popup_slider_rect
                        max_recruit = min(8, len(selected_tile.city.pops) - 1) if selected_tile and selected_tile.city else 1
                        t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                        renderer.recruit_popup_amount = max(1, min(max_recruit, round(1 + t * (max_recruit - 1))))
                    elif renderer.recruit_popup_food_slider_rect and renderer.recruit_popup_food_slider_rect.collidepoint(pos):
                        renderer._recruit_food_slider_dragging = True
                        from src.game.constants import MILITARY_CARRY_CAPACITY as MCC
                        sr = renderer.recruit_popup_food_slider_rect
                        max_food = int(min(selected_tile.city.food_stockpile, renderer.recruit_popup_amount * MCC)) if selected_tile and selected_tile.city else 0
                        t = max(0.0, min(1.0, (pos[0] - sr.x) / sr.width))
                        renderer.recruit_popup_food = max(0, min(max_food, round(t * max_food)))

                elif renderer.trade_route_import_slider_rect and renderer.trade_route_import_slider_rect.collidepoint(pos):
                    renderer.snap_import_amount(pos[0])
                    renderer._import_slider_dragging = True

                elif renderer.trade_route_amount_slider_rect and renderer.trade_route_amount_slider_rect.collidepoint(pos):
                    renderer.snap_export_amount(pos[0])
                    renderer._amount_slider_dragging = True

                elif renderer.trade_route_slider_rect and renderer.trade_route_slider_rect.collidepoint(pos):
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
                #         export_material=renderer.trade_route_export,
                #         export_amount=renderer.trade_route_export_amount,
                #         max_export=renderer.trade_route_max_export,
                #         import_material=renderer.trade_route_import,
                #         import_amount=renderer.trade_route_import_amount,
                #         max_import=renderer.trade_route_max_import,
                #     )
                #     renderer.trade_route_pending = None
                #     renderer.adding_trade_route = False

                elif any(r.collidepoint(pos) for r in renderer.one_way_route_type_rects.values()):
                    for label, rect in renderer.one_way_route_type_rects.items():
                        if rect.collidepoint(pos):
                            renderer.one_way_route_type = label.lower()
                            break

                elif renderer.one_way_confirm_rect and renderer.one_way_confirm_rect.collidepoint(pos) and renderer.one_way_route_pending:
                    city_a, dest_tile = renderer.one_way_route_pending
                    water = renderer.one_way_route_type == 'water'
                    path, path_distances = game_map.get_path(city_a.row, city_a.col, dest_tile.row, dest_tile.col, water=water)
                    TradeRoute(
                        city_a=city_a,
                        dest_tile=dest_tile,
                        pops_a=renderer.one_way_pops_required_whole,
                        pops_b=0,
                        partial_pops_a=renderer.one_way_partial_pops,
                        partial_pops_b=None,
                        export_material='food',
                        export_amount=renderer.one_way_amount,
                        max_export=renderer.one_way_amount,
                        import_material=None,
                        import_amount=0,
                        max_import=0,
                        path=path,
                        path_distances=path_distances,
                        water=water,
                    )
                    renderer.one_way_route_pending = None
                    renderer.one_way_route_type = 'land'

                elif renderer.one_way_cancel_rect and renderer.one_way_cancel_rect.collidepoint(pos):
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
                        renderer.selected_unit_groups.update(game_map.get_unit_groups(selected_tile.row, selected_tile.col))
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.unselect_all_button_rect and renderer.unselect_all_button_rect.collidepoint(pos):
                    if selected_tile:
                        for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col):
                            renderer.selected_unit_groups.discard(g)
                    move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
                    if not move_mode:
                        move_hover_tile = None

                elif renderer.recruit_unit_button_rect and renderer.recruit_unit_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city and len(selected_tile.city.pops) > 1:
                        renderer.recruit_popup_active = True
                        renderer.recruit_popup_amount = 1

                elif renderer.disband_button_rect and renderer.disband_button_rect.collidepoint(pos):
                    if selected_tile and selected_tile.city:
                        city = selected_tile.city
                        selected_on_tile = [g for g in game_map.get_unit_groups(selected_tile.row, selected_tile.col) if g in renderer.selected_unit_groups]
                        for group in selected_on_tile:
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

                elif renderer.one_way_slider_rect and renderer.one_way_slider_rect.collidepoint(pos):
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

                elif renderer.rebalance_pops_button_rect and renderer.rebalance_pops_button_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        city.rebalance_pops()

                elif renderer.restrict_tile_button_rect and renderer.restrict_tile_button_rect.collidepoint(pos):
                    if selected_tile:
                        selected_tile.restricted = not selected_tile.restricted
                        selected_tile._restricted_ticker = 5 if selected_tile.restricted else 0
                        selected_tile._init_jobs()
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

                elif renderer.admin_minus_rect and renderer.admin_minus_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        admin_job = next((j for j in city.jobs if j.job_type == 'administrator'), None)
                        if admin_job and admin_job.assigned > city.min_admin_count():
                            admin_job.assigned -= 1
                            city.rebalance_pops()

                elif renderer.admin_plus_rect and renderer.admin_plus_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        admin_job = next((j for j in city.jobs if j.job_type == 'administrator'), None)
                        if admin_job and admin_job.assigned < min(admin_job.slots, len(city.pops)):
                            admin_job.assigned += 1
                            city.rebalance_pops()

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
                            selected_tile.owning_city = friendly_city
                            selected_tile.city_distance = game_map.get_travel_cost(friendly_city.row, friendly_city.col, selected_tile.row, selected_tile.col)
                            friendly_city.owned_tiles.append(selected_tile)
                            friendly_city._build_cumulative_farm_yield()
                            friendly_city.update_cumulative_farm_yield_net()
                            friendly_city.rebalance_pops()
                            source_group = selected_on_tile[0]
                            detached_unit = source_group.units.pop(0)
                            source_group.max_food_stockpile = source_group._carry_capacity()
                            garrison = UnitGroup(selected_tile.row, selected_tile.col,
                                                 units=[detached_unit],
                                                 faction=attacker_faction)
                            garrison.moves_remaining = 0
                            garrison.move_exhausted = True
                            selected_tile.unit_groups.append(garrison)
                            selected_tile.update_after_movement()
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
                                                  units=[Unit(p) for p in captured_pops],
                                                  faction=attacker_faction)
                            new_group.moves_remaining = DEFAULT_MOVE_DISTANCE
                            new_group.move_exhausted = False
                            new_group.add_food(float(len(captured_pops)))
                            selected_tile.unit_groups.append(new_group)
                            selected_tile.update_after_movement()
                        game_log.append(f"Raid: {raided} farms, {result['food_gained']:.0f} food, {len(captured_pops)} captured.")

                elif renderer.end_turn_button_rect and renderer.end_turn_button_rect.collidepoint(pos):
                    do_end_turn = True

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
                    print(f"[CLICK] prev={prev} clicked={clicked} units_on_clicked={[str(g.faction.name if g.faction else '?') for g in (game_map.get_unit_groups(clicked_tile.row, clicked_tile.col) if clicked_tile else [])]}")
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

        if do_end_turn:
            turn += 1
            game_log.append("")
            for row in game_map.tiles:
                for tile in row:
                    for group in tile.unit_groups:
                        group.end_turn()
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
                    if tile.has_active_tickers():
                        tile.update_tickers()
            for (r, c) in game_map.unit_groups:
                game_map.tiles[r][c].update_unit_allocations()
            move_hover_tile = None
            move_mode, move_mode_unit_groups, reachable = _compute_move_state(renderer.selected_unit_groups, selected_tile, game_map)
            game_log.append(f"TURN {turn}")

        if not console_active and not save_popup_active:
            keys = pygame.key.get_pressed()
            pan_speed = 6
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
                      battle_popup_preview=pending_combat_preview)
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
