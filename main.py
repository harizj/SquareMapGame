import json
import os
import pygame
from src.game.map import Map
from src.game.save_load import load_map_data, save_map
from src.game.trade_route import TradeRoute
from src.ui.renderer import Renderer

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, 'config.json')


def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {'load_map': ''}


def main():
    pygame.init()

    config = _load_config()
    map_name = config.get('load_map', '').strip()
    if map_name:
        data = load_map_data(map_name)
        game_map = Map.from_dict(data) if data else Map()
        if not data:
            print(f"Save '{map_name}' not found — starting fresh map.")
    else:
        game_map = Map()

    renderer = Renderer(game_map)
    clock = pygame.time.Clock()
    selected_tile = None
    move_mode = False
    move_mode_groups = []
    reachable = {}
    save_popup_active = False
    save_popup_text = ""
    terrain_popup_active = False
    river_popup_active = False
    game_log = []
    turn = 0
    console_active = False
    console_input = ""

    running = True
    while running:
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
                elif event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                renderer._slider_dragging = False
                renderer._amount_slider_dragging = False
                renderer._import_slider_dragging = False
                renderer._one_way_slider_dragging = False

            elif event.type == pygame.MOUSEMOTION:
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

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                if terrain_popup_active:
                    for terrain, rect in renderer.terrain_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.terrain = terrain
                            if terrain in ('hills', 'desert'):
                                selected_tile.river_edges.clear()
                            if move_mode:
                                group = game_map.get_group(selected_tile.row, selected_tile.col)
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
                                group = game_map.get_group(selected_tile.row, selected_tile.col)
                                if group:
                                    reachable = game_map.get_reachable(group)
                            break
                    river_popup_active = False

                elif save_popup_active:
                    pass

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
                #     route = TradeRoute(
                #         city_a=city_a,
                #         city_b=city_b,
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

                elif renderer.one_way_confirm_rect and renderer.one_way_confirm_rect.collidepoint(pos):
                    city_a, city_b = renderer.one_way_route_pending
                    water = renderer.one_way_route_type == 'water'
                    path, path_distances = game_map.get_path(city_a.row, city_a.col, city_b.row, city_b.col, water=water)
                    TradeRoute(
                        city_a=city_a,
                        city_b=city_b,
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
                    )
                    renderer.one_way_route_pending = None
                    renderer.one_way_route_type = 'land'

                elif renderer.one_way_cancel_rect and renderer.one_way_cancel_rect.collidepoint(pos):
                    renderer.one_way_route_pending = None
                    renderer.one_way_route_type = 'land'

                elif any(r.collidepoint(pos) for r, _ in renderer.group_icon_rects):
                    for rect, group in renderer.group_icon_rects:
                        if rect.collidepoint(pos):
                            if group in renderer.selected_groups:
                                renderer.selected_groups.discard(group)
                            else:
                                renderer.selected_groups.add(group)
                            break

                elif renderer.select_all_button_rect and renderer.select_all_button_rect.collidepoint(pos):
                    if selected_tile:
                        renderer.selected_groups.update(game_map.get_groups(selected_tile.row, selected_tile.col))

                elif renderer.unselect_all_button_rect and renderer.unselect_all_button_rect.collidepoint(pos):
                    if selected_tile:
                        for g in game_map.get_groups(selected_tile.row, selected_tile.col):
                            renderer.selected_groups.discard(g)

                elif renderer.merge_button_rect and renderer.merge_button_rect.collidepoint(pos):
                    if selected_tile:
                        all_groups = game_map.get_groups(selected_tile.row, selected_tile.col)
                        selected_on_tile = [g for g in all_groups if g in renderer.selected_groups]
                        if len(selected_on_tile) >= 2:
                            target = selected_on_tile[0]
                            for other in selected_on_tile[1:]:
                                target.merge(other)
                                game_map.groups[(selected_tile.row, selected_tile.col)].remove(other)
                                renderer.selected_groups.discard(other)

                elif any(r.collidepoint(pos) for r, _ in renderer.trade_route_delete_rects):
                    for rect, route in renderer.trade_route_delete_rects:
                        if rect.collidepoint(pos):
                            route.city_a.trade_routes.remove(route)
                            route.city_b.trade_routes.remove(route)
                            route.city_a.update_cumulative_farm_yield_net()
                            route.city_b.update_cumulative_farm_yield_net()
                            route.city_a.rebalance_pops()
                            route.city_b.rebalance_pops()
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

                elif renderer.draw_river_button_rect and renderer.draw_river_button_rect.collidepoint(pos):
                    river_popup_active = True

                elif renderer.change_terrain_button_rect and renderer.change_terrain_button_rect.collidepoint(pos):
                    terrain_popup_active = True

                elif renderer.rebalance_pops_button_rect and renderer.rebalance_pops_button_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        city.rebalance_pops()

                elif any(r.collidepoint(pos) for r in renderer.city_focus_rects.values()):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        for label, rect in renderer.city_focus_rects.items():
                            if rect.collidepoint(pos):
                                city.city_focus = label
                                city.rebalance_pops()
                                break

                elif renderer.admin_minus_rect and renderer.admin_minus_rect.collidepoint(pos):
                    city = selected_tile.owning_city if selected_tile else None
                    if city:
                        admin_job = next((j for j in city.jobs if j.job_type == 'administrator'), None)
                        if admin_job and admin_job.assigned > 0:
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
                        move_mode_groups = []
                        reachable = {}
                    else:
                        all_groups = game_map.get_groups(selected_tile.row, selected_tile.col)
                        candidates = [g for g in all_groups if g in renderer.selected_groups]
                        candidates = [g for g in candidates if g.moves_remaining > 0]
                        if candidates:
                            budget = min(g.moves_remaining for g in candidates)
                            move_mode = True
                            move_mode_groups = candidates
                            reachable = game_map.get_reachable_budget(selected_tile.row, selected_tile.col, budget)

                elif renderer.end_turn_button_rect and renderer.end_turn_button_rect.collidepoint(pos):
                    turn += 1
                    game_log.append("")
                    for grp_list in game_map.groups.values():
                        for group in grp_list:
                            group.end_turn()
                    game_map.groups = {
                        pos: [g for g in grp_list if g.units]
                        for pos, grp_list in game_map.groups.items()
                    }
                    game_map.groups = {pos: grp_list for pos, grp_list in game_map.groups.items() if grp_list}
                    for city in game_map.cities.values():
                        for msg in city.end_turn():
                            game_log.append(f"T{turn} {msg}")
                    seen = set()
                    for city in game_map.cities.values():
                        for route in city.trade_routes:
                            if id(route) not in seen:
                                seen.add(id(route))
                                route.end_turn()
                    move_mode = False
                    move_mode_groups = []
                    reachable = {}
                    game_log.append(f"TURN {turn}")

                elif renderer.adding_one_way_route and pos[0] < renderer.map_w:
                    tile = renderer.get_tile_at(*pos)
                    current_city = selected_tile.owning_city if selected_tile else None
                    if tile is not None:
                        clicked_city = tile.owning_city
                        if clicked_city and clicked_city is not current_city:
                            renderer.one_way_route_pending = (current_city, clicked_city)
                            renderer.one_way_amount = 1
                    renderer.adding_one_way_route = False

                elif move_mode:
                    tile = renderer.get_tile_at(*pos)
                    if tile is not None and (tile.row, tile.col) in reachable:
                        cost = reachable[(tile.row, tile.col)]
                        for group in move_mode_groups:
                            game_map.move_group(group, tile.row, tile.col, cost)
                        selected_tile = game_map.tiles[tile.row][tile.col]
                    move_mode = False
                    move_mode_groups = []
                    reachable = {}

                elif pos[0] < renderer.map_w:
                    selected_tile = renderer.get_tile_at(*pos)
                    renderer.selected_groups.clear()
                    if selected_tile:
                        renderer.selected_groups.update(game_map.get_groups(selected_tile.row, selected_tile.col))

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
                      moves_remaining=min(g.moves_remaining for g in move_mode_groups) if move_mode_groups else None,
                      game_log=game_log,
                      console_active=console_active,
                      console_input=console_input)
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
