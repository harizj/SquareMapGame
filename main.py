import json
import os
import pygame
from src.game.map import Map
from src.game.save_load import load_map_data, save_map
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
    reachable = {}
    save_popup_active = False
    save_popup_text = ""
    terrain_popup_active = False
    river_popup_active = False
    assign_popup_active = False
    assign_popup_city = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if assign_popup_active:
                    if event.key == pygame.K_ESCAPE:
                        assign_popup_active = False
                        assign_popup_city = None
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

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                if assign_popup_active:
                    for job_type, rect in renderer.assign_input_rects.items():
                        if rect.collidepoint(pos):
                            job = next((j for j in assign_popup_city.jobs if j.job_type == job_type), None)
                            if job:
                                for pop in assign_popup_city.pops:
                                    if pop.assigned_job is None and job.available_slots > 0:
                                        pop.assigned_job = job
                                        job.assigned += 1
                            assign_popup_active = False
                            assign_popup_city = None
                            break

                elif terrain_popup_active:
                    for terrain, rect in renderer.terrain_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.terrain = terrain
                            if terrain in ('hills', 'desert'):
                                selected_tile.river_edges.clear()
                            if move_mode:
                                unit = game_map.get_unit(selected_tile.row, selected_tile.col)
                                if unit:
                                    reachable = game_map.get_reachable(unit)
                            break
                    terrain_popup_active = False

                elif river_popup_active:
                    for direction, rect in renderer.river_option_rects.items():
                        if rect.collidepoint(pos):
                            selected_tile.river_edges.add(direction)
                            selected_tile.terrain = 'river'
                            if move_mode:
                                unit = game_map.get_unit(selected_tile.row, selected_tile.col)
                                if unit:
                                    reachable = game_map.get_reachable(unit)
                            break
                    river_popup_active = False

                elif save_popup_active:
                    pass

                elif renderer.draw_river_button_rect and renderer.draw_river_button_rect.collidepoint(pos):
                    river_popup_active = True

                elif renderer.change_terrain_button_rect and renderer.change_terrain_button_rect.collidepoint(pos):
                    terrain_popup_active = True

                elif renderer.assign_pops_button_rect and renderer.assign_pops_button_rect.collidepoint(pos):
                    city = game_map.cities.get((selected_tile.row, selected_tile.col)) if selected_tile else None
                    if city and city.jobs:
                        assign_popup_active = True
                        assign_popup_city = city

                elif renderer.save_map_button_rect and renderer.save_map_button_rect.collidepoint(pos):
                    save_popup_active = True
                    save_popup_text = ""

                elif renderer.move_button_rect and renderer.move_button_rect.collidepoint(pos):
                    if move_mode:
                        move_mode = False
                        reachable = {}
                    else:
                        unit = game_map.get_unit(selected_tile.row, selected_tile.col)
                        if unit and unit.moves_remaining > 0:
                            move_mode = True
                            reachable = game_map.get_reachable(unit)

                elif renderer.end_turn_button_rect and renderer.end_turn_button_rect.collidepoint(pos):
                    for unit in game_map.units.values():
                        unit.reset_moves()
                    for city in game_map.cities.values():
                        city.end_turn()
                    move_mode = False
                    reachable = {}

                elif move_mode:
                    tile = renderer.get_tile_at(*pos)
                    if tile is not None and (tile.row, tile.col) in reachable:
                        unit = game_map.get_unit(selected_tile.row, selected_tile.col)
                        game_map.move_unit(unit, tile.row, tile.col, reachable[(tile.row, tile.col)])
                        selected_tile = game_map.tiles[tile.row][tile.col]
                    move_mode = False
                    reachable = {}

                elif pos[0] < renderer.map_w:
                    selected_tile = renderer.get_tile_at(*pos)

        moving_unit = game_map.get_unit(selected_tile.row, selected_tile.col) if move_mode and selected_tile else None
        assign_popup_data = {'city': assign_popup_city} if assign_popup_active and assign_popup_city else None
        renderer.draw(selected_tile, reachable, move_mode,
                      save_popup_active, save_popup_text,
                      terrain_popup_active, river_popup_active,
                      moves_remaining=moving_unit.moves_remaining if moving_unit else None,
                      assign_popup_data=assign_popup_data)
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
