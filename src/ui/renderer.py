import collections
import math
import os
import pygame
from src.game.city import STOCKPILE_MAX
from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY, MILITARY_CARRY_CAPACITY, WATER_CARRY_CAPACITY, MOVE_CARRY_OVER, GAME_SCALE
from src.game.map import TERRAIN_TYPES
from src.game.tile import BIOMES, TERRAIN_FEATURES, BIOME_COLORS
from src.game.unit import unit_list as UNIT_DISPLAY_ORDER, UNIT_REGISTRY

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets')

CELL_SIZE = 64
MARGIN = 40
PANEL_WIDTH = 220
DISPLAY_ROWS = 8
DISPLAY_COLS = 10
DISPLAY_FULL_BATTLE = False

COLOR_PARCHMENT = (240, 220, 185)

TERRAIN_COLORS = {
    # original
    # 'desert':   (210, 180, 100),
    # 'hills':    (139, 100,  60),
    # 'river':    (100, 180,  80),
    # 'mountain': (140, 140, 140),
    # 20% desaturated
    'desert':   (200, 175, 115),
    'hills':    (130, 102,  68),
    'forest':   (105, 168,  88),
    'river':    (105, 168,  88),
    'mountain': (140, 140, 140),
    # 'desert':   (255, 255, 255),
    # 'hills':    (255, 255, 255),
    # 'forest':   (255, 255, 255),
    # 'river':    (255, 255, 255),
    # 'mountain': (255, 255, 255),
    # 50% blended with parchment (240, 220, 185)
    # 'desert':   (220, 197, 150),
    # 'hills':    (185, 161, 126),
    # 'river':    (172, 194, 136),
    # 'mountain': (190, 180, 162),
}
TERRAIN_COLORS_DARK = {k: tuple(int(v * 0.68) for v in rgb) for k, rgb in TERRAIN_COLORS.items()}
COLOR_RIVER_LINE  = (60, 120, 200)
COLOR_RIVER_DARK  = (35, 80, 145)
COLOR_CITY        = (220, 200, 140)
COLOR_CITY_BORDER = (100,  80,  40)
COLOR_OUTLINE     = (50, 50, 50)
COLOR_SELECTED    = (255, 220, 50)
COLOR_REACHABLE   = (80, 160, 255)
COLOR_UNIT        = (240, 240, 240)
COLOR_UNIT_SHADOW = (30, 30, 30)
BG_COLOR          = (20, 20, 20)
PANEL_BG          = (35, 35, 45)
PANEL_DIVIDER     = (60, 60, 80)
TEXT_COLOR        = (210, 210, 210)
HEADER_TEXT_COLOR = (160, 190, 240)
BUTTON_NORMAL     = (60, 80, 110)
BUTTON_ACTIVE     = (40, 100, 180)
BUTTON_DISABLED   = (50, 50, 60)
BUTTON_TEXT       = (200, 210, 230)
BUTTON_TEXT_DISABLED = (90, 90, 100)

RIVER_DIR_GRID = [('N',), ('W', 'E'), ('S',)]

# Offset from cell center to edge midpoint for each cardinal river direction
_RIVER_EDGE_OFFSETS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}

# Square grid: cardinal neighbor (dr, dc) → (ci, cj) corner index pair for the shared edge
# Corners: 0=top-left, 1=top-right, 2=bottom-right, 3=bottom-left
_SQUARE_EDGE_CORNERS = {
    (-1, 0): (0, 1),  # N: top edge
    (0,  1): (1, 2),  # E: right edge
    (1,  0): (2, 3),  # S: bottom edge
    (0, -1): (3, 0),  # W: left edge
}

# Art names that get_terrain_art() can return — images loaded for each
_TERRAIN_ART_NAMES = ['river', 'mountain', 'forest', 'hills', 'water', 'floodplain', 'grass', 'desert', 'marsh']

# Biome sprite sheet tile dimensions (sheet is 256x256, tiles are 64 wide x 96 tall)
# The extra 32px height overhangs the row above, enabling 2.5D depth stacking.
_TILE_SPRITE_W = 64
_TILE_SPRITE_H = 96
# Maps get_terrain_art() return value → (file_stem, tile_col, tile_row) within a biome folder
# tile_col/tile_row are 0-indexed positions in the sprite sheet grid
_BIOME_ART_FILES = {
    'grass':           ('flat',        0, 0),
    'hills':           ('hills',       0, 0),
    'forest':          ('forests',     0, 0),
    'hillforest':      ('hillforest',  0, 0),
    'mountain':        ('mountains',   0, 0),
    'water':           ('water',       0, 0),
    'iron_hills':      ('iron',        0, 0),
    'iron_hillforest': ('iron',        1, 0),
}

# Maps frozenset of river edge directions → (col, row) in the river sprite sheet
# Sheet layout (64×96 tiles, 3 cols × 2 rows): NS WE NE / NW SE SW
_RIVER_TILE_MAP = {
    frozenset({'N', 'S'}): (0, 0),
    frozenset({'W', 'E'}): (1, 0),
    frozenset({'N', 'E'}): (2, 0),
    frozenset({'N', 'W'}): (3, 0),
    frozenset({'S', 'E'}): (0, 1),
    frozenset({'S', 'W'}): (1, 1),
}

# Per-art scale multipliers applied on top of the hex size (1.0 = fill hex)
_TERRAIN_ART_SCALE = {
    'grass': 0.7,
}

# Features excluded from the terrain editor — preserved on tiles but not user-togglable
_NON_SELECTABLE_FEATURES = {'water_access', 'city'}

# Maps art name → image filename stem when they differ
_TERRAIN_IMG_FILES = {
    'mountain': 'mountains',
}

ICON_SIZE      = 40
LOG_PANEL_WIDTH = 0
CITY_PANEL_WIDTH = 220
BOTTOM_PANEL_HEIGHT = 36
FOG_FACTOR = 0.75


class Renderer:
    def __init__(self, game_map):
        self.map = game_map
        map_area_w = DISPLAY_COLS * CELL_SIZE + 2 * MARGIN
        self.map_w = CITY_PANEL_WIDTH + map_area_w
        self.map_start_x = CITY_PANEL_WIDTH
        map_h = DISPLAY_ROWS * CELL_SIZE + 2 * MARGIN
        self.bottom_panel_y = map_h
        screen_h = map_h + BOTTOM_PANEL_HEIGHT
        self.offset_x = CITY_PANEL_WIDTH + MARGIN
        self.offset_y = MARGIN
        self.screen = pygame.display.set_mode((self.map_w + PANEL_WIDTH, screen_h))
        pygame.display.set_caption("SquareMapGame")
        self.font_header = pygame.font.SysFont('segoeui', 13, bold=True)
        self.font_body = pygame.font.SysFont('segoeui', 13)
        self.font_small = pygame.font.SysFont('segoeui', 10)
        self.font_city = pygame.font.SysFont('tempussansitc', 12, bold=True)
        _font_cinzel        = os.path.join(_ASSETS_DIR, 'fonts', 'Cinzel', 'static', 'Cinzel-Bold.ttf')
        _font_almendra      = os.path.join(_ASSETS_DIR, 'fonts', 'Almendra', 'Almendra-Bold.ttf')
        _font_caesar        = os.path.join(_ASSETS_DIR, 'fonts', 'Caesar_Dressing', 'CaesarDressing-Regular.ttf')
        _font_glass_antiqua = os.path.join(_ASSETS_DIR, 'fonts', 'Glass_Antiqua', 'GlassAntiqua-Regular.ttf')
        self.font_pop = pygame.font.Font(_font_cinzel, 13)
        self.font_unit_count = pygame.font.Font(_font_cinzel, 15)
        hex_w = CELL_SIZE
        hex_h = CELL_SIZE
        self._terrain_images_raw = {}
        terrain_dir = os.path.join(_ASSETS_DIR, 'terrain')
        for name in _TERRAIN_ART_NAMES:
            img_file = _TERRAIN_IMG_FILES.get(name, name)
            raw_variants = []
            for i in range(1, 5):
                path = os.path.join(terrain_dir, f'{img_file}{i}.png')
                if os.path.exists(path):
                    raw_variants.append(pygame.image.load(path).convert_alpha())
            if raw_variants:
                self._terrain_images_raw[name] = raw_variants
        self._biome_terrain_images_raw = {}
        self._river_images_raw = {}
        for biome_folder in os.listdir(terrain_dir):
            biome_path = os.path.join(terrain_dir, biome_folder)
            if not os.path.isdir(biome_path):
                continue
            for art_name, (file_stem, tile_col, tile_row) in _BIOME_ART_FILES.items():
                path = os.path.join(biome_path, f'{file_stem}.png')
                if os.path.exists(path):
                    sheet = pygame.image.load(path).convert_alpha()
                    x = tile_col * _TILE_SPRITE_W
                    y = tile_row * _TILE_SPRITE_H
                    tile_surf = sheet.subsurface((x, y, _TILE_SPRITE_W, _TILE_SPRITE_H)).copy()
                    self._biome_terrain_images_raw[(biome_folder, art_name)] = tile_surf
            river_path = os.path.join(biome_path, 'river.png')
            if os.path.exists(river_path):
                sheet = pygame.image.load(river_path).convert_alpha()
                for edge_key, (col, row) in _RIVER_TILE_MAP.items():
                    x = col * _TILE_SPRITE_W
                    y = row * _TILE_SPRITE_H
                    tile_surf = sheet.subsurface((x, y, _TILE_SPRITE_W, _TILE_SPRITE_H)).copy()
                    self._river_images_raw[(biome_folder, edge_key)] = tile_surf
        self._icons_raw = {}
        icons_dir = os.path.join(_ASSETS_DIR, 'icons')
        for icon_name, file_name in (('castle', 'city'), ('sword', 'gladius'), ('flag', 'flag'), ('torch', 'restriction'), ('wood', 'wood'), ('iron', 'iron'), ('hammer', 'hammer'), ('club', 'club'), ('spear', 'spear'), ('bow', 'bow'), ('gladius', 'gladius'), ('pitchfork', 'pitchfork'), ('wagon_wheel', 'wagon-wheel'), ('human-skull', 'human-skull')):
            path = os.path.join(icons_dir, f'{file_name}.png')
            if os.path.exists(path):
                self._icons_raw[icon_name] = pygame.image.load(path).convert_alpha()
        self.zoom = 1
        self.terrain_images = {}
        self.icons = {}
        self.icons_tinted = {}
        self.icons_dark = {}
        self.icons_light = {}
        self.icons_selected = {}
        self._faction_castle_icons = {}
        self._faction_sword_icons = {}
        self._faction_flag_icons = {}
        self._faction_torch_icons = {}
        self._faction_resource_icons = {}
        self._unit_map_icons = {}
        self._biome_terrain_images = {}
        self._river_images = {}
        self._river_images_fog = {}
        self._fog_overlay_cache = {}
        self._apply_zoom()
        self.move_button_rect = None
        self.capture_button_rect = None
        self.raid_button_rect = None
        self.plunder_route_button_rect = None
        self.end_turn_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.rebalance_pops_button_rect = None
        self.restrict_tile_button_rect = None
        self.halt_growth_rect = None
        self.gates_closed_rect = None
        self.city_focus_rects = {}
        self.trade_route_delete_rects = []
        self.trade_route_reduce_rects = []
        self.adding_trade_route = False
        self.adding_one_way_route = False
        self.add_one_way_route_button_rect = None
        self.one_way_route_pending = None
        self.one_way_route_style = 'one_way'
        self.one_way_route_style_rects = {}
        self.one_way_route_type = 'land'
        self.one_way_route_type_rects = {}
        self.one_way_export_material = 'food'
        self.one_way_export_rects = {}
        self.one_way_import_material = 'wood'
        self.one_way_import_rects = {}
        self.one_way_amount = 1
        self.one_way_pops_required_whole = 0
        self.one_way_partial_pops = None
        self.one_way_slider_rect = None
        self._one_way_slider_dragging = False
        self.one_way_confirm_rect = None
        self.one_way_cancel_rect = None
        self.trade_route_pending = None
        self.trade_route_confirm_rect = None
        self.trade_route_pops = 1
        self.trade_route_slider_rect = None
        self._slider_dragging = False
        self.trade_route_export = None
        self.trade_route_export_rects = {}
        self.trade_route_export_amount = 0
        self.trade_route_amount_slider_rect = None
        self._amount_slider_dragging = False
        self.trade_route_import = None
        self.trade_route_import_rects = {}
        self.trade_route_import_amount = 0
        self.trade_route_import_slider_rect = None
        self._import_slider_dragging = False
        self.trade_route_max_amount = 0.0
        self.terrain_option_rects = {}
        self.biome_option_rects = {}
        self.feature_option_rects = {}
        self.terrain_confirm_rect = None
        self.terrain_cancel_rect = None
        self.river_option_rects = {}
        self.selected_unit_groups = set()
        self.group_icon_rects = []
        self.select_all_button_rect = None
        self.merge_button_rect = None
        self.separate_button_rect = None
        self.restock_button_rect = None
        self.drop_button_rect = None
        self.add_tether_button_rect = None
        self.drop_tether_button_rect = None
        self.settle_button_rect = None
        self.recruit_unit_button_rect = None
        self.disband_button_rect = None
        self.raise_levies_button_rect = None
        self.recruit_popup_active = False
        self.raise_levies_popup_active = False
        self.recruit_popup_amount = 1
        self.production_popup_active = False
        self.production_target_button_rect = None
        self.select_extraction_tile_button_rect = None
        self.selecting_extraction_city = None
        self.production_popup_rects = {}
        self.recruit_popup_food = 0
        self.recruit_popup_slider_rect = None
        self.recruit_popup_food_slider_rect = None
        self.recruit_popup_confirm_rect = None
        self.recruit_popup_cancel_rect = None
        self.recruit_dec2_rect = None
        self.recruit_dec1_rect = None
        self.recruit_inc1_rect = None
        self.recruit_inc2_rect = None
        self.recruit_all_free_rect = None
        self.recruit_food_dec_rect = None
        self.recruit_food_inc_rect = None
        self.separate_popup_active = False
        self.separate_popup_group = None
        self.separate_popup_counts = {}
        self.separate_popup_food = 0
        self.separate_popup_min_food = 0
        self.separate_popup_slider_rects = {}
        self.separate_popup_food_slider_rect = None
        self.separate_popup_confirm_rect = None
        self.separate_popup_cancel_rect = None
        self._separate_slider_dragging = None
        self.add_job_popup_active = False
        self.add_job_popup_city = None
        self.add_job_popup_selected_type = None
        self.add_job_popup_count = 0
        self.add_job_popup_type_rects = {}
        self.add_job_popup_slider_rect = None
        self.add_job_popup_confirm_rect = None
        self.add_job_popup_cancel_rect = None
        self._add_job_slider_dragging = False
        self.add_job_button_rect = None
        self.job_queue_up_rects = []
        self.job_queue_down_rects = []
        self.job_queue_minus_rects = []
        self.job_queue_plus_rects = []
        self.job_queue_x_rects = []
        self._separate_food_slider_dragging = False
        self.battle_popup_confirm_rect = None
        self.battle_popup_cancel_rect = None
        self.battle_result_close_rect = None
        self.los_button_rects = {}
        self.collapsed_sections = set()
        self.section_header_rects = {}
        self._recruit_slider_dragging = False
        self._recruit_food_slider_dragging = False
        self.recruit_popup_supply_train = False
        self.recruit_popup_supply_food = 1
        self.recruit_popup_supply_checkbox_rect = None
        self.recruit_popup_supply_food_slider_rect = None
        self._recruit_supply_food_slider_dragging = False
        self.add_tether_popup_active = False
        self.add_tether_popup_food = 1
        self.add_tether_popup_group = None
        self.add_tether_popup_slider_rect = None
        self.add_tether_popup_confirm_rect = None
        self.add_tether_popup_cancel_rect = None
        self._add_tether_food_slider_dragging = False

    def _make_icon_pair(self, scaled, light_rgb, dark_rgb, outline_radius, pad=0):
        """Returns (tinted, dark, selected):
        tinted   = dark fill + light outline
        dark     = light fill + dark outline
        selected = white fill + dark outer outline
        pad expands the output surface so outlines don't clip at edges."""
        mask = scaled.copy()
        mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        lb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        lb.fill((*light_rgb, 255))
        lb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        db = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        db.fill((*dark_rgb, 255))
        db.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        wb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        wb.fill((255, 255, 255, 255))
        wb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        near_black = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        near_black.fill((20, 20, 20, 255))
        near_black.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        w, h = scaled.get_width() + 2 * pad, scaled.get_height() + 2 * pad
        result = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_radius, outline_radius + 1):
            for dy in range(-outline_radius, outline_radius + 1):
                if dx * dx + dy * dy <= outline_radius * 2:
                    result.blit(lb, (pad + dx, pad + dy))
        result.blit(db, (pad, pad))
        dark_result = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_radius, outline_radius + 1):
            for dy in range(-outline_radius, outline_radius + 1):
                if dx * dx + dy * dy <= outline_radius * 2:
                    dark_result.blit(db, (pad + dx, pad + dy))
        dark_result.blit(lb, (pad, pad))
        selected_result = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_radius, outline_radius + 1):
            for dy in range(-outline_radius, outline_radius + 1):
                if dx * dx + dy * dy <= outline_radius * 2:
                    selected_result.blit(db, (pad + dx, pad + dy))
        selected_result.blit(lb, (pad, pad))
        # outer_r = outline_radius + 2
        # inner_r = outline_radius // 2 - 1
        # for dx in range(-outer_r, outer_r + 1):
        #     for dy in range(-outer_r, outer_r + 1):
        #         if dx * dx + dy * dy <= outer_r * 2:
        #             selected_result.blit(lb, (pad + dx, pad + dy))
        # for dx in range(-inner_r, inner_r + 1):
        #     for dy in range(-inner_r, inner_r + 1):
        #         if dx * dx + dy * dy <= inner_r * 2:
        #             selected_result.blit(db, (pad + dx, pad + dy))
        return result, dark_result, selected_result

    def _get_fog_overlay(self, w, h):
        key = (w, h)
        if key not in self._fog_overlay_cache:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 64))
            self._fog_overlay_cache[key] = surf
        return self._fog_overlay_cache[key]

    @staticmethod
    def _make_fog_surf(surf):
        fogged = surf.copy()
        dark = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        dark.fill((192, 192, 192, 255))
        fogged.blit(dark, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return fogged

    def _apply_zoom(self):
        self._fog_overlay_cache = {}
        sz = CELL_SIZE * self.zoom
        hex_w = sz
        hex_h = sz
        self.terrain_images = {
            name: [
                pygame.transform.scale(v, (
                    int(hex_w * _TERRAIN_ART_SCALE.get(name, 1.0)),
                    int(hex_h * _TERRAIN_ART_SCALE.get(name, 1.0)),
                ))
                for v in variants
            ]
            for name, variants in self._terrain_images_raw.items()
        }
        self.terrain_images_fog = {
            name: [self._make_fog_surf(v) for v in variants]
            for name, variants in self.terrain_images.items()
        }
        tile_render_w = int(sz)
        tile_render_h = int(sz * _TILE_SPRITE_H / _TILE_SPRITE_W)
        self._biome_terrain_images = {
            key: pygame.transform.scale(raw, (tile_render_w, tile_render_h))
            for key, raw in self._biome_terrain_images_raw.items()
        }
        self._biome_terrain_images_fog = {
            key: self._make_fog_surf(surf)
            for key, surf in self._biome_terrain_images.items()
        }
        self._river_images = {
            key: pygame.transform.scale(raw, (tile_render_w, tile_render_h))
            for key, raw in self._river_images_raw.items()
        }
        self._river_images_fog = {
            key: self._make_fog_surf(surf)
            for key, surf in self._river_images.items()
        }
        castle_size = int(ICON_SIZE * 1.2 * self.zoom)
        sword_size = int(ICON_SIZE * 0.4 * self.zoom)
        self.icons = {}
        self.icons_tinted = {}
        if 'castle' in self._icons_raw:
            scaled = pygame.transform.scale(self._icons_raw['castle'], (castle_size, castle_size))
            self.icons['castle'] = scaled
            castle_outline_radius = 8
            tinted, dark_surf, sel_surf = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), castle_outline_radius)
            self.icons_tinted['castle'] = tinted
            self.icons_dark['castle'] = dark_surf
            self.icons_selected['castle'] = sel_surf
            self._faction_castle_icons = {}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_castle_icons:
                    t, d, s = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), castle_outline_radius)
                    self._faction_castle_icons[city.faction.name] = {'tinted': t, 'dark': d, 'selected': s}
        if 'sword' in self._icons_raw:
            scaled = pygame.transform.scale(self._icons_raw['sword'], (sword_size, sword_size))
            self.icons['sword'] = scaled
            sword_outline_radius = 5
            tinted, dark_surf, sel_surf = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), sword_outline_radius, pad=sword_outline_radius)
            self.icons_tinted['sword'] = tinted
            self.icons_dark['sword'] = dark_surf
            self.icons_selected['sword'] = sel_surf
            mask = scaled.copy()
            mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
            lb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            lb.fill((180, 210, 255, 255))
            lb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.icons_light['sword'] = lb
            self._faction_sword_icons = {}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_sword_icons:
                    t, d, s = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), sword_outline_radius, pad=sword_outline_radius)
                    self._faction_sword_icons[city.faction.name] = {'tinted': t, 'dark': d, 'selected': s}
        self._unit_map_icons = {}
        _unit_icon_r = 5
        for icon_name in {cls.icon for cls in UNIT_REGISTRY.values() if hasattr(cls, 'icon')}:
            raw = self._icons_raw.get(icon_name)
            if not raw:
                continue
            cls_scale = next((cls.icon_scale for cls in UNIT_REGISTRY.values() if getattr(cls, 'icon', None) == icon_name), 1.0)
            size = int(sword_size * cls_scale)
            scaled = pygame.transform.scale(raw, (size, size))
            tinted, _, sel_surf = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), _unit_icon_r, pad=_unit_icon_r)
            entry = {'plain': scaled, 'tinted': tinted, 'selected': sel_surf}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in entry:
                    t, _, s = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), _unit_icon_r, pad=_unit_icon_r)
                    entry[city.faction.name] = {'tinted': t, 'selected': s}
            self._unit_map_icons[icon_name] = entry
        if 'flag' in self._icons_raw:
            flag_size = int(ICON_SIZE * 0.4 * self.zoom)
            flag_outline_radius = 6
            scaled = pygame.transform.scale(self._icons_raw['flag'], (flag_size, flag_size))
            self.icons['flag'] = scaled
            tinted, dark_result, sel = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), flag_outline_radius)
            self.icons_tinted['flag'] = tinted
            self.icons_dark['flag'] = dark_result
            self.icons_selected['flag'] = sel
            self._faction_flag_icons = {}
        if 'torch' in self._icons_raw:
            torch_size = int(CELL_SIZE * self.zoom * 0.28)
            scaled_torch = pygame.transform.scale(self._icons_raw['torch'], (torch_size, torch_size))
            outline_r = 4
            torch_mask = scaled_torch.copy()
            torch_mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
            black_mask = scaled_torch.copy()
            black_mask.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MIN)
            tw, th = scaled_torch.get_size()
            outlined_torch = pygame.Surface((tw + outline_r * 2, th + outline_r * 2), pygame.SRCALPHA)
            for _odx in range(-outline_r, outline_r + 1):
                for _ody in range(-outline_r, outline_r + 1):
                    if _odx * _odx + _ody * _ody <= outline_r * 2:
                        outlined_torch.blit(black_mask, (outline_r + _odx, outline_r + _ody))
            outlined_torch.blit(torch_mask, (outline_r, outline_r))
            self.icons['torch'] = outlined_torch
            self._faction_torch_icons = {}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_torch_icons:
                    t, d, _ = self._make_icon_pair(scaled_torch, city.get_city_color('light'), city.get_city_color('dark'), outline_r, pad=outline_r)
                    self._faction_torch_icons[city.faction.name] = {'tinted': t, 'dark': d}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_flag_icons:
                    t, d, _ = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), flag_outline_radius)
                    self._faction_flag_icons[city.faction.name] = {'tinted': t, 'dark': d}

        resource_icon_size = int(CELL_SIZE * self.zoom * 0.28)
        outline_r = 4
        self._faction_resource_icons = {}
        self._deposit_icons = {}
        for resource in ('wood', 'iron', 'hammer'):
            if resource in self._icons_raw:
                scaled_res = pygame.transform.scale(self._icons_raw[resource], (resource_icon_size, resource_icon_size))
                res_mask = scaled_res.copy()
                res_mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                black_mask = scaled_res.copy()
                black_mask.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MIN)
                rw, rh = scaled_res.get_size()
                outlined = pygame.Surface((rw + outline_r * 2, rh + outline_r * 2), pygame.SRCALPHA)
                for _odx in range(-outline_r, outline_r + 1):
                    for _ody in range(-outline_r, outline_r + 1):
                        if _odx * _odx + _ody * _ody <= outline_r * 2:
                            outlined.blit(black_mask, (outline_r + _odx, outline_r + _ody))
                outlined.blit(res_mask, (outline_r, outline_r))
                self.icons[resource] = outlined
                if resource == 'iron':
                    dep_size = resource_icon_size
                    dep_raw = pygame.transform.scale(self._icons_raw['iron'], (dep_size, dep_size))
                    padded = dep_size + outline_r * 2
                    deposit_surf = pygame.Surface((padded, padded), pygame.SRCALPHA)
                    deposit_surf.blit(dep_raw, (outline_r, outline_r))
                    self._deposit_icons['iron'] = deposit_surf
                for city in self.map.cities.values():
                    if city.faction and (city.faction.name, resource) not in self._faction_resource_icons:
                        t, d, _ = self._make_icon_pair(scaled_res, city.get_city_color('light'), city.get_city_color('dark'), outline_r, pad=outline_r)
                        self._faction_resource_icons[(city.faction.name, resource)] = {'tinted': t, 'dark': d}

    def zoom_map(self, factor, mx, my):
        old_zoom = self.zoom
        new_zoom = max(1, min(3, old_zoom + (1 if factor > 1 else -1)))
        if new_zoom == old_zoom:
            return
        self.offset_x = mx + (self.offset_x - mx) * new_zoom / old_zoom
        self.offset_y = my + (self.offset_y - my) * new_zoom / old_zoom
        self.zoom = new_zoom
        self._apply_zoom()

    def _hex_to_pixel(self, row, col):
        sz = CELL_SIZE * self.zoom
        x = col * sz + sz / 2
        y = row * sz + sz / 2
        return x, y

    def _hex_corners(self, cx, cy):
        half = CELL_SIZE * self.zoom / 2
        return [
            (cx - half, cy - half),  # top-left
            (cx + half, cy - half),  # top-right
            (cx + half, cy + half),  # bottom-right
            (cx - half, cy + half),  # bottom-left
        ]

    def _draw_arrowhead(self, tip, from_pt, color, size=12):
        dx = tip[0] - from_pt[0]
        dy = tip[1] - from_pt[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        half_w = size * 0.5
        base_x = tip[0] - ux * size
        base_y = tip[1] - uy * size
        p1 = (int(base_x + px * half_w), int(base_y + py * half_w))
        p2 = (int(base_x - px * half_w), int(base_y - py * half_w))
        pygame.draw.polygon(self.screen, color, [(int(tip[0]), int(tip[1])), p1, p2])

    def _draw_dashed_line(self, start, end, color, width=2, dash_length=8, gap=6):
        x0, y0 = start
        x1, y1 = end
        length = math.hypot(x1 - x0, y1 - y0)
        if length == 0:
            return
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        d = 0.0
        on = True
        while d < length:
            step = dash_length if on else gap
            d2 = min(d + step, length)
            if on:
                p1 = (int(x0 + ux * d), int(y0 + uy * d))
                p2 = (int(x0 + ux * d2), int(y0 + uy * d2))
                pygame.draw.line(self.screen, color, p1, p2, width)
            d = d2
            on = not on

    def _draw_dashed_curve(self, p0, p1_through, p2, color, width=2, dash_length=8, gap=6):
        """Quadratic Bézier dashed curve that passes through p1_through at t=0.5."""
        cpx = 2 * p1_through[0] - 0.5 * (p0[0] + p2[0])
        cpy = 2 * p1_through[1] - 0.5 * (p0[1] + p2[1])
        steps = 200
        points = []
        for i in range(steps + 1):
            t = i / steps
            mt = 1 - t
            x = mt * mt * p0[0] + 2 * mt * t * cpx + t * t * p2[0]
            y = mt * mt * p0[1] + 2 * mt * t * cpy + t * t * p2[1]
            points.append((x, y))
        prev = points[0]
        accumulated = 0.0
        on = True
        dash_start = prev
        for pt in points[1:]:
            seg = math.hypot(pt[0] - prev[0], pt[1] - prev[1])
            accumulated += seg
            target = dash_length if on else gap
            while accumulated >= target:
                overshoot = accumulated - target
                frac = (seg - overshoot) / seg if seg > 0 else 0
                boundary = (prev[0] + frac * (pt[0] - prev[0]),
                            prev[1] + frac * (pt[1] - prev[1]))
                if on:
                    pygame.draw.line(self.screen, color,
                                     (int(dash_start[0]), int(dash_start[1])),
                                     (int(boundary[0]), int(boundary[1])), width)
                on = not on
                dash_start = boundary
                accumulated = overshoot
                target = dash_length if on else gap
            prev = pt
        if on:
            pygame.draw.line(self.screen, color,
                             (int(dash_start[0]), int(dash_start[1])),
                             (int(points[-1][0]), int(points[-1][1])), width)

    def _pixel_to_hex(self, px, py):
        sz = CELL_SIZE * self.zoom
        col = int((px - self.offset_x) / sz)
        row = int((py - self.offset_y) / sz)
        return row, col

    def get_tile_at(self, px, py):
        row, col = self._pixel_to_hex(px, py)
        if 0 <= row < self.map.rows and 0 <= col < self.map.cols:
            return self.map.tiles[row][col]
        return None

    def _draw_unit_marker(self, cx, cy):
        s = 7
        pygame.draw.line(self.screen, (30, 60, 120), (cx - s, cy - s), (cx + s, cy + s), 4)
        pygame.draw.line(self.screen, (30, 60, 120), (cx + s, cy - s), (cx - s, cy + s), 4)
        pygame.draw.line(self.screen, (180, 210, 255), (cx - s, cy - s), (cx + s, cy + s), 2)
        pygame.draw.line(self.screen, (180, 210, 255), (cx + s, cy - s), (cx - s, cy + s), 2)

    def _draw_button(self, x, y, w, h, text, active=False, disabled=False):
        if disabled:
            bg, fg = BUTTON_DISABLED, BUTTON_TEXT_DISABLED
        elif active:
            bg, fg = BUTTON_ACTIVE, BUTTON_TEXT
        else:
            bg, fg = BUTTON_NORMAL, BUTTON_TEXT
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, bg, rect, border_radius=3)
        surf = self.font_body.render(text, True, fg)
        self.screen.blit(surf, (x + (w - surf.get_width()) // 2, y + (h - surf.get_height()) // 2))
        return rect

    def _get_tile_job_icon(self, resource, tile):
        """Return the icon surface to display for a tile's active extraction job.
        Extend this to return resource-specific icons keyed by resource name."""
        faction = tile.owning_city.faction if tile.owning_city else None
        if faction:
            icon = self._faction_resource_icons.get((faction.name, resource), {}).get('tinted')
            if icon:
                return icon
        return self.icons.get(resource) or self.icons.get('torch')

    def _draw_city_bar_fill(self, city, bx, by, bar_w, bar_h, bar_type, tick_w=1, border_radius=0):
        if bar_type == 'food':
            food_max = city._stockpile_max()
            if food_max > 0:
                proj = min(city.food_stockpile + city.food_allocated_to_stockpile, food_max)
                proj_w = max(int(bar_w * proj / food_max), 0)
                fill_w = int(bar_w * min(city.food_stockpile, food_max) / food_max)
                if city.food_allocated_to_stockpile < 0:
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (220, 110, 60), (bx, by, fill_w, bar_h), border_radius=border_radius)
                    if proj_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (bx, by, proj_w, bar_h), border_radius=border_radius)
                else:
                    if proj_w > 0:
                        pygame.draw.rect(self.screen, (200, 240, 165), (bx, by, proj_w, bar_h), border_radius=border_radius)
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (bx, by, fill_w, bar_h), border_radius=border_radius)
                min_stockpile = min(len(city.pops), food_max)
                if 0 < min_stockpile < food_max:
                    tick_x = bx + int(bar_w * min_stockpile / food_max)
                    pygame.draw.line(self.screen, (255, 255, 255), (tick_x, by - 1), (tick_x, by + bar_h), tick_w)
        elif bar_type == 'growth':
            growth_display_max = 400
            proj = min(city.growth_progress_display + city.growth_allocated, growth_display_max)
            proj_w = max(int(bar_w * proj / growth_display_max), 0)
            if proj_w > 0:
                pygame.draw.rect(self.screen, (120, 210, 200), (bx, by, proj_w, bar_h), border_radius=border_radius)
            fill_w = max(int(bar_w * min(city.growth_progress_display, growth_display_max) / growth_display_max), 0)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (40, 160, 150), (bx, by, fill_w, bar_h), border_radius=border_radius)
            for tick_val in (100, 200, 300):
                tick_x = bx + int(bar_w * tick_val / growth_display_max)
                pygame.draw.line(self.screen, (30, 30, 40), (tick_x, by), (tick_x, by + bar_h - 1), tick_w)
        elif bar_type == 'construction':
            fill_w = max(int(bar_w * min(city.construction_progress, 1000) / 1000), 0)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (130, 130, 140), (bx, by, fill_w, bar_h), border_radius=border_radius)
        elif bar_type == 'production':
            total = city.production_complete
            if total and total > 0:
                proj = min(city.production_progress + city.production_yield, total)
                proj_w = max(int(bar_w * proj / total), 0)
                if proj_w > 0:
                    pygame.draw.rect(self.screen, (210, 175, 110), (bx, by, proj_w, bar_h), border_radius=border_radius)
                fill_w = max(int(bar_w * min(city.production_progress, total) / total), 0)
                if fill_w > 0:
                    pygame.draw.rect(self.screen, (170, 120, 55), (bx, by, fill_w, bar_h), border_radius=border_radius)

    def _draw_labeled_bar(self, city, label_text, value_text, bar_type, x, y, bar_w, bar_h, gap=8, **kwargs):
        label = self.font_small.render(label_text, True, TEXT_COLOR)
        val = self.font_small.render(value_text, True, TEXT_COLOR)
        self.screen.blit(label, (x, y))
        self.screen.blit(val, (x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (x, y, bar_w, bar_h), border_radius=2)
        self._draw_city_bar_fill(city, x, y, bar_w, bar_h, bar_type, border_radius=2, **kwargs)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (x, y, bar_w, bar_h), 1, border_radius=2)
        return y + bar_h + gap

    def _draw_section_header(self, key, label, x, y):
        collapsed = key in self.collapsed_sections
        indicator = '▶' if collapsed else '▼'
        surf = self.font_header.render(f"{indicator} {label}", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        self.section_header_rects[key] = pygame.Rect(x, y, surf.get_width(), surf.get_height())
        return y + surf.get_height() + 6, collapsed

    def draw(self, selected_tile=None, reachable=None, move_mode=False,
             save_popup_active=False, save_popup_text="",
             terrain_popup_active=False, river_popup_active=False,
             moves_remaining=None, game_log=None,
             move_hover_tile=None,
             console_active=False, console_input="",
             battle_popup_active=False, battle_popup_preview=None,
             battle_result_active=False, battle_result=None, battle_result_preview=None,
             los=None, factions=None):
        if reachable is None:
            reachable = {}
        self.section_header_rects.clear()
        self.screen.fill(BG_COLOR)

        all_corners = {}
        all_centers = {}
        apothem = CELL_SIZE * self.zoom / 2
        visible = los.get_visible() if los else None

        # Pass 1: cell fills
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                px, py = self._hex_to_pixel(r, c)
                cx, cy = px + self.offset_x, py + self.offset_y
                corners = self._hex_corners(cx, cy)
                all_corners[(r, c)] = corners
                all_centers[(r, c)] = (cx, cy)
                color = tile.get_terrain_color()
                if visible is not None and (r, c) not in visible:
                    color = tuple(int(v * FOG_FACTOR) for v in color)
                dark_color = tuple(int(v * 0.68) for v in color)
                sz = CELL_SIZE * self.zoom
                rect = pygame.Rect(int(cx - sz / 2), int(cy - sz / 2), int(sz), int(sz))
                pygame.draw.rect(self.screen, color, rect)

        # Pass 1b: terrain and river images top-to-bottom so tall sprites overlap the row above
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                cx, cy = all_centers[(r, c)]
                art_name = tile.get_terrain_art()
                sz = CELL_SIZE * self.zoom
                fogged = visible is not None and (r, c) not in visible
                img = self._biome_terrain_images_fog.get((tile.biome, art_name)) if fogged else self._biome_terrain_images.get((tile.biome, art_name))
                if img is None:
                    variants = self.terrain_images_fog.get(art_name) if fogged else self.terrain_images.get(art_name)
                    if variants:
                        img = variants[(r * 7 + c * 13) % len(variants)]
                if img:
                    blit_x = int(cx - img.get_width() / 2)
                    if img.get_height() > sz:
                        blit_y = int(cy + sz / 2 - img.get_height())
                    else:
                        blit_y = int(cy - img.get_height() / 2)
                    self.screen.blit(img, (blit_x, blit_y))
                if tile.river_edges:
                    edge_key = frozenset(tile.river_edges)
                    river_dict = self._river_images_fog if fogged else self._river_images
                    river_img = river_dict.get((tile.biome, edge_key))
                    if river_img:
                        blit_x = int(cx - river_img.get_width() / 2)
                        blit_y = int(cy + sz / 2 - river_img.get_height())
                        self.screen.blit(river_img, (blit_x, blit_y))
                    else:
                        for direction in tile.river_edges:
                            offset = _RIVER_EDGE_OFFSETS.get(direction)
                            if offset is None:
                                continue
                            ox, oy = offset
                            ex, ey = cx + ox * apothem, cy + oy * apothem
                            pygame.draw.line(self.screen, (0, 0, 0),
                                             (int(cx), int(cy)), (int(ex), int(ey)), 3)


        # Pass 2b: trade route dashed curves on intermediate path tiles (above rivers)
        seen_routes = set()
        for city in self.map.cities.values():
            for route in city.trade_routes:
                if id(route) in seen_routes or route.missing_caravans:
                    continue
                seen_routes.add(id(route))
                path = route.get_visual_path()
                # if len(path) < 1:
                #     continue

                def _edge_pt(r, c, nr, nc):
                    if (r, c) not in all_centers:
                        return None, None
                    cx, cy = all_centers[(r, c)]
                    dr, dc = nr - r, nc - c
                    return (cx + dc * apothem, cy + dr * apothem), (cx, cy)

                _ROUTE_DARK = route.faction.colors['dark'] if route.faction else (35, 65, 150)
                _ROUTE_LIGHT = route.faction.colors['light'] if route.faction else (180, 210, 255)
                _ROUTE_OUTLINE_W = 5
                _ROUTE_INNER_W = 3
                destination = route.path[-1]

                # Start city: center → edge toward path[1]
                ep, center = _edge_pt(path[0][0], path[0][1], path[1][0], path[1][1])
                if ep and center and (visible is None or path[0] in visible):
                    self._draw_dashed_line(center, ep, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_line(center, ep, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)

                # Intermediate tiles
                for i in range(1, len(path) - 1):
                    r, c = path[i]
                    if visible is not None and (r, c) not in visible:
                        continue
                    pr, pc = path[i - 1]
                    nr, nc = path[i + 1]
                    if (r, c) not in all_centers:
                        continue
                    cx, cy = all_centers[(r, c)]
                    dr_from, dc_from = pr - r, pc - c
                    dr_to,   dc_to   = nr - r, nc - c
                    from_pt = (cx + dc_from * apothem, cy + dr_from * apothem)
                    to_pt   = (cx + dc_to   * apothem, cy + dr_to   * apothem)
                    self._draw_dashed_curve(from_pt, (cx, cy), to_pt, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_curve(from_pt, (cx, cy), to_pt, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)

                # End city: edge toward path[-2] → center (only when destination reached)
                ep, center = _edge_pt(path[-1][0], path[-1][1], path[-2][0], path[-2][1])
                if ep and center and (visible is None or path[-1] in visible):
                    self._draw_dashed_line(ep, center, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_line(ep, center, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)
                    self._draw_arrowhead(center, ep, _ROUTE_LIGHT, size=8)

        # Pass 3b: city territory borders
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                if visible is not None and (r, c) not in visible:
                    continue
                tile = self.map.tiles[r][c]
                if tile.owning_city is None:
                    continue
                cx, cy = all_centers[(r, c)]
                corners = all_corners[(r, c)]
                border_lines = []
                for (dr, dc), (ci, cj) in _SQUARE_EDGE_CORNERS.items():
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.map.rows and 0 <= nc < self.map.cols):
                        neighbor_city = None
                    else:
                        neighbor_city = self.map.tiles[nr][nc].owning_city
                    if neighbor_city is not tile.owning_city:
                        border_lines.append((corners[ci], corners[cj]))
                if not border_lines:
                    continue
                sz = CELL_SIZE * self.zoom
                border_line_w = 8
                outline_radius = 4
                pad = outline_radius + border_line_w
                surf_w = int(sz) + pad * 2
                surf_h = int(sz) + pad * 2
                scx = surf_w // 2
                scy = surf_h // 2
                edge_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                for (p1, p2) in border_lines:
                    lp1 = (int(p1[0] - cx + scx), int(p1[1] - cy + scy))
                    lp2 = (int(p2[0] - cx + scx), int(p2[1] - cy + scy))
                    pygame.draw.line(edge_surf, (255, 255, 255, 255), lp1, lp2, border_line_w)
                border_dark  = tile.owning_city.get_city_color('dark')  or (35, 65, 150)
                border_light = tile.owning_city.get_city_color('light') or (160, 200, 255)
                lb_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                lb_surf.fill((*border_light, 170))
                lb_surf.blit(edge_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                base_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                base_surf.fill((*border_dark, 255))
                base_surf.blit(edge_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                result = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                r2 = outline_radius * outline_radius
                for dx in range(-outline_radius, outline_radius + 1):
                    for dy in range(-outline_radius, outline_radius + 1):
                        if (dx, dy) != (0, 0) and dx * dx + dy * dy <= r2:
                            result.blit(lb_surf, (dx, dy))
                result.blit(base_surf, (0, 0))
                half_sz = int(sz / 2)
                clip_mask = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                pygame.draw.rect(clip_mask, (255, 255, 255, 255),
                                 (scx - half_sz, scy - half_sz, int(sz), int(sz)))
                result.blit(clip_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                self.screen.blit(result, (int(cx) - scx, int(cy) - scy))

        # Pass 4: movement range borders
        if move_mode and selected_tile:
            in_range = set(reachable.keys())
            in_range.add((selected_tile.row, selected_tile.col))
            sz = CELL_SIZE * self.zoom
            border_line_w = 4
            outline_radius = 2
            pad = outline_radius + border_line_w + 1
            surf_w = int(sz) + pad * 2
            surf_h = int(sz) + pad * 2
            scx = surf_w // 2
            scy = surf_h // 2
            for (r, c) in in_range:
                if (r, c) not in all_corners:
                    continue
                cx, cy = all_centers[(r, c)]
                corners = all_corners[(r, c)]
                border_lines = []
                for (dr, dc), (ci, cj) in _SQUARE_EDGE_CORNERS.items():
                    nr, nc = r + dr, c + dc
                    if (nr, nc) not in in_range:
                        border_lines.append((corners[ci], corners[cj]))
                if not border_lines:
                    continue
                edge_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                for (p1, p2) in border_lines:
                    lp1 = (int(p1[0] - cx + scx), int(p1[1] - cy + scy))
                    lp2 = (int(p2[0] - cx + scx), int(p2[1] - cy + scy))
                    pygame.draw.line(edge_surf, (255, 255, 255, 255), lp1, lp2, border_line_w)
                self.screen.blit(edge_surf, (int(cx) - scx, int(cy) - scy))

        # Pass 4b: (move cost labels removed)

        # Pass 5: selected border (moved to pass 8 to draw over everything)

        # Pass 6b: worked farm dots (top-left of each tile, one dot per assigned pop)
        dot_radius = 1
        dot_spacing = 5
        dot_offset_x = int(apothem * 0.72)
        dot_start_y_offset = int(CELL_SIZE * self.zoom * 0.4)
        dot_positions = []  # (ddx, ddy, owning_city)
        torch_icon = self.icons.get('torch')
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                if visible is not None and (r, c) not in visible:
                    continue
                tile = self.map.tiles[r][c]
                cx, cy = all_centers[(r, c)]
                dx = int(cx) - dot_offset_x
                dy = int(cy) - dot_start_y_offset
                icon_y = dy - int(apothem * 0.3)
                if tile.is_disrupted and torch_icon:
                    faction = tile.owning_city.faction if tile.owning_city else None
                    faction_torch = self._faction_torch_icons.get(faction.name, {}).get('dark') if faction else None
                    icon = faction_torch or torch_icon
                    self.screen.blit(icon, (dx - int(apothem * 0.4), icon_y))
                if tile.current_extraction_job is not None:
                    icon = self._get_tile_job_icon(tile.current_extraction_job, tile)
                    if icon:
                        self.screen.blit(icon, (int(cx) + dot_offset_x - icon.get_width() + int(apothem * 0.4), icon_y))
                if tile.city is not None and tile.city.production_target.type == 'manufacturing':
                    icon = self._get_tile_job_icon('hammer', tile)
                    if icon:
                        self.screen.blit(icon, (int(cx) + dot_offset_x - icon.get_width() + int(apothem * 0.4), icon_y))
                if tile.is_disrupted:
                    continue
                if tile.worked_farms <= 0:
                    continue
                for i in range(max(1, tile.worked_farms // GAME_SCALE)):
                    col_i = i // 3
                    row_i = i % 3
                    dot_positions.append((dx + col_i * dot_spacing, dy + row_i * dot_spacing, tile.owning_city))
        for ddx, ddy, city in dot_positions:
            dot_dark = city.get_city_color('dark') if city else (30, 60, 120)
            pygame.draw.circle(self.screen, dot_dark, (ddx, ddy), dot_radius + 4)
        for ddx, ddy, city in dot_positions:
            dot_light = city.get_city_color('light') if city else (160, 200, 255)
            pygame.draw.circle(self.screen, dot_light, (ddx, ddy), dot_radius + 1)
            pygame.draw.circle(self.screen, (255, 255, 255), (ddx, ddy), dot_radius)

        # Pass 6: city icons (castle, drawn below units)
        selected_city_pos = (selected_tile.row, selected_tile.col) if selected_tile else None
        city_name_ys = {}
        for (r, c), city in self.map.cities.items():
            if visible is not None and (r, c) not in visible:
                continue
            cx, cy = all_centers[(r, c)]
            fname = city.faction.name if city.faction else None
            faction_icons = self._faction_castle_icons.get(fname)
            if faction_icons:
                icon = faction_icons['selected'] if (r, c) == selected_city_pos else faction_icons['tinted']
            else:
                icon = self.icons_selected.get('castle') if (r, c) == selected_city_pos else self.icons_tinted.get('castle')
            if icon:
                ix = int(cx) - icon.get_width() // 2 + 2
                iy = int(cy - CELL_SIZE * self.zoom / 2)
                self.screen.blit(icon, (ix, iy))
                city_name_ys[(r, c)] = iy + icon.get_height() - 12
            else:
                s = 6
                rect = pygame.Rect(int(cx) - s, int(cy) - s, s * 2, s * 2)
                pygame.draw.rect(self.screen, COLOR_CITY, rect)
                pygame.draw.rect(self.screen, COLOR_CITY_BORDER, rect, 1)
                city_name_ys[(r, c)] = int(cy) + s + 2

        # Pass 6b: flag icons for cityless trade route destinations
        if self.icons_tinted.get('flag') or self.icons_dark.get('flag'):
            seen_dest_tiles = set()
            for city in self.map.cities.values():
                for route in city.trade_routes:
                    if route.city_b is None:
                        dt = route.dest_tile
                        key = (dt.row, dt.col)
                        if key not in seen_dest_tiles and key in all_centers and (visible is None or key in visible):
                            seen_dest_tiles.add(key)
                            is_selected = selected_tile is not None and (selected_tile.row, selected_tile.col) == key
                            faction_name = route.faction.name if route.faction else None
                            faction_flag = self._faction_flag_icons.get(faction_name) if faction_name else None
                            if faction_flag:
                                flag_icon = faction_flag['tinted']
                            else:
                                flag_icon = self.icons_tinted.get('flag')
                            if flag_icon:
                                cx, cy = all_centers[key]
                                ix = int(cx) - flag_icon.get_width() // 2 - 2
                                iy = int(cy) - flag_icon.get_height() // 2 + 2
                                self.screen.blit(flag_icon, (ix, iy))

        # Pass 7: group markers (drawn over city icons)
        for (r, c) in self.map.unit_groups:
            if visible is not None and (r, c) not in visible:
                continue
            cx, cy = all_centers[(r, c)]
            unit_groups_here = self.map.unit_groups[(r, c)]
            any_selected = any(g in self.selected_unit_groups for g in unit_groups_here)
            first_faction = unit_groups_here[0].faction
            fname = first_faction.name if first_faction else None
            _utype_to_icon = {cls.unit_type: getattr(cls, 'icon', None) for cls in UNIT_REGISTRY.values()}
            _order = {t: i for i, t in enumerate(UNIT_DISPLAY_ORDER)}
            all_units = sorted(
                [u for g in unit_groups_here for u in g.units],
                key=lambda u: _order.get(u.unit_type, 99)
            )
            top_unit = all_units[0] if all_units else None
            icon_name = _utype_to_icon.get(top_unit.unit_type) if top_unit else None
            icon_data = self._unit_map_icons.get(icon_name, {})
            if fname and fname not in icon_data and first_faction and icon_name in self._unit_map_icons:
                _unit_icon_r = 5
                raw = self._icons_raw.get(icon_name)
                if raw:
                    cls_scale = next((cls.icon_scale for cls in UNIT_REGISTRY.values() if getattr(cls, 'icon', None) == icon_name), 1.0)
                    sword_size = int(ICON_SIZE * 0.4 * self.zoom)
                    size = int(sword_size * cls_scale)
                    scaled = pygame.transform.scale(raw, (size, size))
                    t, _, s = self._make_icon_pair(scaled, first_faction.colors['light'], first_faction.colors['dark'], _unit_icon_r, pad=_unit_icon_r)
                    self._unit_map_icons[icon_name][fname] = {'tinted': t, 'selected': s}
            faction_data = icon_data.get(fname, {})
            icon = (faction_data.get('selected') or icon_data.get('selected')) if any_selected else (faction_data.get('tinted') or icon_data.get('tinted'))
            total_units = sum(len(g.units) for g in unit_groups_here)
            total_tether = sum(len(g.tether.tether_units) for g in unit_groups_here if g.tether is not None)
            if icon:
                icon_y = int(cy) - icon.get_height() // 2
                icon_x = int(cx) - icon.get_width() // 2 + int(apothem * 0.3)
                self.screen.blit(icon, (icon_x, icon_y))
                has_tether = any(g.tether is not None for g in unit_groups_here)
                count_str = f"{total_units}/{total_tether}" if has_tether else str(total_units)
                outline_color = first_faction.colors['dark'] if first_faction else (35, 65, 150)
                count_outline = self.font_unit_count.render(count_str, True, outline_color)
                count_white   = self.font_unit_count.render(count_str, True, (255, 255, 255))
                pop_r = 3
                count_x_offset = 6 if has_tether else 0
                tx = icon_x - count_white.get_width() + count_x_offset
                ty = int(cy) - count_white.get_height() // 2
                for dx in range(-pop_r, pop_r + 1):
                    for dy in range(-pop_r, pop_r + 1):
                        if (dx, dy) != (0, 0) and dx * dx + dy * dy <= pop_r * pop_r:
                            self.screen.blit(count_outline, (tx + dx, ty + dy))
                self.screen.blit(count_white, (tx, ty))
            else:
                self._draw_unit_marker(int(cx), int(cy))
                icon_y = int(cy)
                icon_x = int(cx)
                icon_y = int(cy)

            if (r, c) in self.map.cities:
                continue

            bar_w = 30
            bar_h = 2
            bar_gap = 1
            mini_pad = 2
            bar_pad = 1
            inner_h = bar_h * 2 + bar_gap
            block_w = bar_w + mini_pad * 2
            block_h = inner_h + mini_pad * 2
            bar_x = int(cx) - bar_w // 2
            block_x = bar_x - mini_pad
            block_y = icon_y + (icon.get_height() if icon else 0) + 1
            unit_dark = unit_groups_here[0].get_color('dark') or (35, 65, 150)
            pygame.draw.rect(self.screen, unit_dark, (block_x - bar_pad, block_y - bar_pad, block_w + bar_pad * 2, block_h + bar_pad * 2))
            pygame.draw.rect(self.screen, (0, 0, 0), (bar_x, block_y + mini_pad, bar_w, inner_h))

            # food bar
            total_food = sum(g.food_stockpile for g in unit_groups_here)
            total_max = sum(g.max_food_stockpile for g in unit_groups_here)
            total_from_stockpile = sum(-g.food_allocated_to_stockpile for g in unit_groups_here)
            bar_y = block_y + mini_pad
            if total_max > 0:
                current = min(total_food, total_max)
                proj = max(0.0, min(current - total_from_stockpile, total_max))
                fill_w = max(int(bar_w * current / total_max), 0)
                proj_w = max(int(bar_w * proj / total_max), 0)
                if total_from_stockpile > 0:
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (220, 110, 60), (bar_x, bar_y, fill_w, bar_h))
                    if proj_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (bar_x, bar_y, proj_w, bar_h))
                else:
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (bar_x, bar_y, fill_w, bar_h))
                total_consumption = sum(g.consumption_per_turn() for g in unit_groups_here)
                if total_consumption > 0:
                    tick = total_consumption
                    while tick < total_max:
                        tx = bar_x + int(bar_w * tick / total_max)
                        pygame.draw.line(self.screen, (30, 30, 40), (tx, bar_y), (tx, bar_y + bar_h - 1))
                        tick += total_consumption

            # move bar
            move_bar_max = unit_groups_here[0].max_moves + MOVE_CARRY_OVER
            any_exhausted = any(g.move_exhausted for g in unit_groups_here)
            min_moves = min(g.moves_remaining for g in unit_groups_here)
            bar_y = block_y + mini_pad + bar_h + bar_gap
            if not any_exhausted and move_bar_max > 0:
                carryover_w = int(bar_w * min(min_moves, move_bar_max) / move_bar_max)
                if carryover_w > 0:
                    pygame.draw.rect(self.screen, (255, 240, 60), (bar_x, bar_y, carryover_w, bar_h))
                fill_w = int(bar_w * min(min_moves, unit_groups_here[0].max_moves) / move_bar_max)
                if fill_w > 0 and min_moves > MOVE_CARRY_OVER:
                    pygame.draw.rect(self.screen, (230, 195, 50), (bar_x, bar_y, fill_w, bar_h))

        # Pass 7b: city bars and population (drawn over everything)
        for (r, c), city in self.map.cities.items():
            if visible is not None and (r, c) not in visible:
                continue
            if los and los.mode == 'faction' and city.faction is not los.faction:
                continue
            cx, cy = all_centers[(r, c)]
            name_y = city_name_ys.get((r, c), int(cy))
            mini_bar_w = 30
            mini_bar_h = 3.5
            mini_gap = 1
            mini_pad = 2
            block_w = mini_bar_w + mini_pad * 2
            block_h = mini_bar_h * 3 + mini_gap * 2 + mini_pad * 2
            circle_r = 12
            overlap = 1
            total_w = circle_r * 2 + block_w - overlap
            start_x = int(cx) - total_w // 2
            circle_cy = name_y + circle_r
            by = circle_cy - block_h // 2
            circle_cx = start_x + circle_r
            bx = start_x + circle_r * 2 - overlap
            bar_pad = 1
            city_dark  = city.get_city_color('dark')  or (35, 65, 150)
            city_light = city.get_city_color('light') or (180, 210, 255)
            pygame.draw.rect(self.screen, city_dark, (bx - bar_pad, by - bar_pad, block_w + bar_pad * 2, block_h + bar_pad * 2))
            inner_h = mini_bar_h * 3 + mini_gap * 2
            pygame.draw.rect(self.screen, (0, 0, 0), (bx + mini_pad, by + mini_pad, mini_bar_w, inner_h))
            mbx = bx + mini_pad
            food_bar_y  = by + mini_pad
            growth_bar_y = food_bar_y + mini_bar_h + mini_gap
            constr_bar_y = growth_bar_y + mini_bar_h + mini_gap
            self._draw_city_bar_fill(city, mbx, food_bar_y,  mini_bar_w, mini_bar_h, 'food')
            self._draw_city_bar_fill(city, mbx, growth_bar_y, mini_bar_w, mini_bar_h, 'growth')
            self._draw_city_bar_fill(city, mbx, constr_bar_y, mini_bar_w, mini_bar_h, 'production')
            pop_fill_r = circle_r
            pop_ring_r = circle_r + 3
            pop_num_outline_r = 3
            pop = city._get_population()
            pop_pct = min(1.0, pop / city.max_pops) if city.max_pops > 0 else 0.0
            fill_h = int(pop_fill_r * 2 * pop_pct)
            pop_str = str(pop)
            pop_outline = self.font_pop.render(pop_str, True, city_dark)
            pop_white   = self.font_pop.render(pop_str, True, (255, 255, 255))
            pygame.draw.circle(self.screen, city_dark, (circle_cx, circle_cy), pop_ring_r)
            pygame.draw.circle(self.screen, (255, 255, 255), (circle_cx, circle_cy), pop_fill_r)
            if fill_h > 0:
                old_clip = self.screen.get_clip()
                self.screen.set_clip(pygame.Rect(
                    circle_cx - pop_fill_r,
                    circle_cy + pop_fill_r - fill_h,
                    pop_fill_r * 2,
                    fill_h,
                ))
                pygame.draw.circle(self.screen, city_light, (circle_cx, circle_cy), pop_fill_r)
                self.screen.set_clip(old_clip)
                y_off = pop_fill_r - fill_h
                if abs(y_off) < pop_fill_r:
                    chord_half = int(math.sqrt(pop_fill_r ** 2 - y_off ** 2))
                    line_y = int(circle_cy) + y_off
                    pygame.draw.line(self.screen, city_dark,
                                     (int(circle_cx) - chord_half, line_y),
                                     (int(circle_cx) + chord_half, line_y), 1)
            tx = circle_cx - pop_white.get_width() // 2
            ty = circle_cy - pop_white.get_height() // 2
            for dx in range(-pop_num_outline_r, pop_num_outline_r + 1):
                for dy in range(-pop_num_outline_r, pop_num_outline_r + 1):
                    if (dx, dy) != (0, 0) and dx * dx + dy * dy <= pop_num_outline_r * pop_num_outline_r:
                        self.screen.blit(pop_outline, (tx + dx, ty + dy))
            self.screen.blit(pop_white, (tx, ty))

        # Pass 8: selected tile border (drawn over all map content)
        if self.selecting_extraction_city:
            ec = self.selecting_extraction_city
            pt = ec.production_target
            if pt.type == 'extraction' and pt.target:
                for t in ec.get_eligible_extraction_tiles(pt.target):
                    key = (t.row, t.col)
                    if key in all_corners:
                        pygame.draw.polygon(self.screen, (255, 200, 0), all_corners[key], 3)
        if selected_tile is not None:
            pygame.draw.polygon(self.screen, (255, 220, 50),
                                all_corners[(selected_tile.row, selected_tile.col)], 4)
        if move_mode and move_hover_tile and (move_hover_tile.row, move_hover_tile.col) in reachable:
            pygame.draw.polygon(self.screen, (255, 220, 50),
                                all_corners[(move_hover_tile.row, move_hover_tile.col)], 4)
        if self.adding_one_way_route and move_hover_tile and (move_hover_tile.row, move_hover_tile.col) in all_corners:
            pygame.draw.polygon(self.screen, (255, 220, 50),
                                all_corners[(move_hover_tile.row, move_hover_tile.col)], 4)

        self._draw_city_panel(selected_tile)
        self._draw_panel(selected_tile, move_mode)
        # self._draw_trade_route_popup()
        self._draw_one_way_route_popup()

        self.terrain_option_rects = {}
        self.biome_option_rects = {}
        self.feature_option_rects = {}
        self.terrain_confirm_rect = None
        self.terrain_cancel_rect = None
        self.river_option_rects = {}
        if river_popup_active:
            self._draw_river_popup(selected_tile)
        elif terrain_popup_active:
            self._draw_terrain_popup(selected_tile)
        elif save_popup_active:
            self._draw_save_popup(save_popup_text)

        if self.recruit_popup_active and selected_tile and selected_tile.city:
            self._draw_recruit_popup(selected_tile.city)
        elif self.raise_levies_popup_active and selected_tile and selected_tile.city:
            self._draw_recruit_popup(selected_tile.city, levy_mode=True)

        if self.separate_popup_active and self.separate_popup_group:
            self._draw_separate_popup()

        if self.add_tether_popup_active and self.add_tether_popup_group:
            self._draw_add_tether_popup(self.add_tether_popup_group)

        if self.add_job_popup_active and self.add_job_popup_city:
            self._draw_add_job_popup()


        if self.production_popup_active and selected_tile and selected_tile.city:
            self._draw_production_popup(selected_tile.city)

        if battle_popup_active and battle_popup_preview:
            self._draw_battle_popup(battle_popup_preview)

        if battle_result_active and battle_result and battle_result_preview:
            self._draw_battle_result_popup(battle_result, battle_result_preview)

        if console_active:
            self._draw_console_overlay(console_input)

        self._draw_los_panel(los, factions or {})

        pygame.display.flip()

    def _amount_steps(self, dist, pops, travel_coeff):
        """Return (steps_list, max_amount). Steps are integers; max is floored to nearest 0.1."""
        if not dist or pops <= 0:
            return [0], 0.0
        travel_time = dist / DEFAULT_MOVE_DISTANCE
        if travel_time <= 0:
            return [0], 0.0
        raw_max = (LAND_CARRY_CAPACITY + 1 - travel_coeff * travel_time) * pops / (2 * travel_time)
        if raw_max <= 0:
            return [0], 0.0
        max_amount = math.floor(raw_max * 10) / 10
        steps = list(range(0, int(max_amount) + 1))
        if max_amount != int(max_amount):
            steps.append(max_amount)
        return steps, max_amount

    def _draw_route_slider(self, track_x, track_y, track_w, track_h, steps, max_amount, current_value):
        """Draw a step-snapping slider track. Returns the clickable Rect."""
        if max_amount > 0:
            pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
            for step in steps:
                tx = int(track_x + (step / max_amount) * track_w)
                pygame.draw.line(self.screen, PANEL_DIVIDER, (tx, track_y - 2), (tx, track_y + track_h + 2), 1)
            clamped = min(current_value, max_amount)
            hx = int(track_x + (clamped / max_amount) * track_w)
            hy = track_y + track_h // 2
            pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
            pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
            max_str = f"{max_amount:.1f}"
            self.screen.blit(self.font_small.render("0", True, PANEL_DIVIDER), (track_x, track_y + track_h + 3))
            ms = self.font_small.render(max_str, True, PANEL_DIVIDER)
            self.screen.blit(ms, (track_x + track_w - ms.get_width(), track_y + track_h + 3))
        else:
            pygame.draw.rect(self.screen, (40, 40, 50), (track_x, track_y, track_w, track_h), border_radius=2)
        return pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)

    def _snap_route_amount(self, pos_x, slider_rect, amount_attr, dist, travel_coeff):
        steps, max_amount = self._amount_steps(dist, self.trade_route_pops, travel_coeff)
        if max_amount <= 0 or not slider_rect:
            return
        t = max(0.0, min(1.0, (pos_x - slider_rect.x) / slider_rect.width))
        setattr(self, amount_attr, min(steps, key=lambda s: abs(s - t * max_amount)))

    def snap_export_amount(self, pos_x):
        if not self.trade_route_pending or not self.trade_route_amount_slider_rect:
            return
        city_a, city_b = self.trade_route_pending
        _, dists = self.map.get_path_to(city_a.row, city_a.col, city_b.row, city_b.col)
        dist = dists[-1] if dists else None
        self._snap_route_amount(pos_x, self.trade_route_amount_slider_rect, 'trade_route_export_amount', dist, 2)

    def snap_import_amount(self, pos_x):
        if not self.trade_route_pending or not self.trade_route_import_slider_rect:
            return
        city_a, city_b = self.trade_route_pending
        _, dists = self.map.get_path_to(city_a.row, city_a.col, city_b.row, city_b.col)
        dist = dists[-1] if dists else None
        self._snap_route_amount(pos_x, self.trade_route_import_slider_rect, 'trade_route_import_amount', dist, 1)

    def _draw_trade_route_popup(self):
        if not self.trade_route_pending:
            return
        city_a, city_b = self.trade_route_pending
        _, dists = self.map.get_path_to(city_a.row, city_a.col, city_b.row, city_b.col)
        dist = dists[-1] if dists else None

        pad = 16
        popup_w = 300
        label_h = self.font_small.size("0")[1]
        track_h = 4
        popup_h = 420
        sw, sh = self.screen.get_size()
        px = (sw - popup_w) // 2
        py = (sh - popup_h) // 2

        # Overlay + background
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, PANEL_BG, (px, py, popup_w, popup_h), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (px, py, popup_w, popup_h), 1, border_radius=6)

        x = px + pad
        y = py + pad
        inner_w = popup_w - pad * 2

        title = self.font_header.render(f"{city_a.name} <-> {city_b.name}", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (x, y))
        y += title.get_height() + 4

        dist_text = f"Distance: {dist:.1f}" if dist is not None else "Distance: N/A"
        surf = self.font_body.render(dist_text, True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 12

        # Pops slider
        surf = self.font_small.render(f"Pops allocated: {self.trade_route_pops}", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6
        track_x, track_y, track_w = x, y, inner_w
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
        t = (self.trade_route_pops - 1) / 7.0
        hx = int(track_x + t * track_w)
        hy = track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
        min_surf = self.font_small.render("1", True, PANEL_DIVIDER)
        max_surf = self.font_small.render("8", True, PANEL_DIVIDER)
        self.screen.blit(min_surf, (track_x, track_y + track_h + 3))
        self.screen.blit(max_surf, (track_x + track_w - max_surf.get_width(), track_y + track_h + 3))
        self.trade_route_slider_rect = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)
        y = track_y + track_h + min_surf.get_height() + 14

        # Export material
        surf = self.font_small.render("Export material", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        btn_w = (inner_w - 4) // 3
        self.trade_route_export_rects = {}
        bx = x
        for label in ('Food', 'Wood', 'Iron'):
            rect = self._draw_button(bx, y, btn_w, 20, label,
                                     active=(self.trade_route_export == label.lower()))
            self.trade_route_export_rects[label] = rect
            bx += btn_w + 2
        y += 28

        # Export amount slider
        ex_steps, ex_max = self._amount_steps(dist, self.trade_route_pops, 2)
        self.trade_route_max_amount = ex_max
        ex_val = min(self.trade_route_export_amount, ex_max)
        ex_str = str(int(ex_val)) if ex_val == int(ex_val) else f"{ex_val:.1f}"
        surf = self.font_small.render(f"Export amount: {ex_str}", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6
        self.trade_route_amount_slider_rect = self._draw_route_slider(
            x, y, inner_w, track_h, ex_steps, ex_max, ex_val)
        y += track_h + label_h + 14

        # Import material
        surf = self.font_small.render("Import material", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        self.trade_route_import_rects = {}
        bx = x
        for label in ('Food', 'Wood', 'Iron'):
            rect = self._draw_button(bx, y, btn_w, 20, label,
                                     active=(self.trade_route_import == label.lower()))
            self.trade_route_import_rects[label] = rect
            bx += btn_w + 2
        y += 28

        # Import amount slider
        im_steps, im_max = self._amount_steps(dist, self.trade_route_pops, 1)
        self.trade_route_max_amount = im_max
        im_val = min(self.trade_route_import_amount, im_max)
        im_str = str(int(im_val)) if im_val == int(im_val) else f"{im_val:.1f}"
        surf = self.font_small.render(f"Import amount: {im_str}", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6
        self.trade_route_import_slider_rect = self._draw_route_slider(
            x, y, inner_w, track_h, im_steps, im_max, im_val)
        y += track_h + label_h + 14

        self.trade_route_confirm_rect = self._draw_button(x, y, inner_w, 24, "Confirm")

    def _draw_one_way_route_popup(self):
        if not self.one_way_route_pending:
            return
        city_a, dest_tile = self.one_way_route_pending
        _, water_dists = self.map.get_path_to(city_a.row, city_a.col, dest_tile.row, dest_tile.col, mode='water')
        water_reachable = bool(water_dists)
        if not water_reachable and self.one_way_route_type == 'water':
            self.one_way_route_type = 'land'
        water = self.one_way_route_type == 'water'
        _, route_dists = self.map.get_path_to(city_a.row, city_a.col, dest_tile.row, dest_tile.col, mode='water' if water else 'land')
        dist = route_dists[-1] if route_dists else None

        pad = 16
        popup_w = 280
        two_way = self.one_way_route_style == 'two_way'
        popup_h = 420 if two_way else 370
        sw, sh = self.screen.get_size()
        px = (sw - popup_w) // 2
        py = (sh - popup_h) // 2

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, PANEL_BG, (px, py, popup_w, popup_h), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (px, py, popup_w, popup_h), 1, border_radius=6)

        x = px + pad
        y = py + pad
        inner_w = popup_w - pad * 2

        dest_name = dest_tile.city.name if dest_tile.city is not None else f"({dest_tile.row}, {dest_tile.col})"
        title = self.font_header.render(f"{city_a.name} -> {dest_name}", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (x, y))
        y += title.get_height() + 8

        # Route style: One Way / Two Way
        btn_w = (inner_w - 4) // 2
        self.one_way_route_style_rects = {}
        has_dest_city = dest_tile.city is not None
        for label in ('One Way', 'Two Way'):
            disabled = label == 'Two Way' and not has_dest_city
            if disabled and self.one_way_route_style == 'two_way':
                self.one_way_route_style = 'one_way'
            rect = self._draw_button(x, y, btn_w, 22, label,
                                     active=(self.one_way_route_style == label.lower().replace(' ', '_')),
                                     disabled=disabled)
            if not disabled:
                self.one_way_route_style_rects[label] = rect
            x += btn_w + 4
        x = px + pad
        y += 30

        # Transport type: Land / Water
        self.one_way_route_type_rects = {}
        for label in ('Land', 'Water'):
            is_water = label == 'Water'
            disabled = is_water and not water_reachable
            rect = self._draw_button(x, y, btn_w, 22, label,
                                     active=(self.one_way_route_type == label.lower()),
                                     disabled=disabled)
            if not disabled:
                self.one_way_route_type_rects[label] = rect
            x += btn_w + 4
        x = px + pad
        y += 30

        dist_text = f"Distance: {dist:.1f}" if dist is not None else "Distance: unreachable"
        surf = self.font_body.render(dist_text, True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 10

        # Export resource
        surf = self.font_body.render("Export Resource", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6
        self.one_way_export_rects = {}
        res_btn_w = (inner_w - 8) // 3
        for label in ('Wood', 'Iron', 'Food'):
            rect = self._draw_button(x, y, res_btn_w, 22, label,
                                     active=(self.one_way_export_material == label.lower()))
            self.one_way_export_rects[label] = rect
            x += res_btn_w + 4
        x = px + pad
        y += 30

        # Import resource (two-way only)
        self.one_way_import_rects = {}
        if two_way:
            surf = self.font_body.render("Import Resource", True, TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 6
            for label in ('Wood', 'Iron'):
                rect = self._draw_button(x, y, res_btn_w, 22, label,
                                         active=(self.one_way_import_material == label.lower()))
                self.one_way_import_rects[label] = rect
                x += res_btn_w + 4
            x = px + pad
            y += 30

        # Amount slider 1–8
        surf = self.font_body.render(f"Amount: {self.one_way_amount}", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6
        track_h = 4
        track_x, track_y, track_w = x, y, inner_w
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
        t = (self.one_way_amount - 1) / 7.0
        hx = int(track_x + t * track_w)
        hy = track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
        min_surf = self.font_small.render("1", True, PANEL_DIVIDER)
        max_surf = self.font_small.render("8", True, PANEL_DIVIDER)
        self.screen.blit(min_surf, (track_x, track_y + track_h + 3))
        self.screen.blit(max_surf, (track_x + track_w - max_surf.get_width(), track_y + track_h + 3))
        self.one_way_slider_rect = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)
        y = track_y + track_h + min_surf.get_height() + 14

        # Pops required calculation
        # Rounded to nearest whole number, min 1. Consider switching to ceil + partial_pops
        # in the future to eliminate arbitrage potential (players exploiting fractional rounding).
        pops_required_text = "Pops required: N/A"
        self.one_way_pops_required_whole = 0
        self.one_way_partial_pops = None
        if dist:
            travel_time = dist / DEFAULT_MOVE_DISTANCE
            carry_capacity = WATER_CARRY_CAPACITY if water else LAND_CARRY_CAPACITY
            denom = carry_capacity + 1 - travel_time if two_way else carry_capacity + 1 - 2 * travel_time
            if denom > 0 and travel_time > 0:
                raw = (self.one_way_amount * 2 * travel_time) / denom
                pops_required = max(1, math.ceil(raw))
                pops_required_text = f"Pops required: {pops_required}"
                self.one_way_pops_required_whole = pops_required
                # partial_pops = round(math.ceil(raw) - raw, 1)
                # self.one_way_partial_pops = partial_pops
        surf = self.font_body.render(pops_required_text, True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        # if self.one_way_partial_pops is not None:
        #     frac_str = str(int(self.one_way_partial_pops)) if self.one_way_partial_pops == int(self.one_way_partial_pops) else f"{self.one_way_partial_pops:.1f}"
        #     surf = self.font_body.render(f"{frac_str} remaining pops will work production", True, TEXT_COLOR)
        #     self.screen.blit(surf, (x, y))
        #     y += surf.get_height() + 10
        # else:
        #     y += 6
        y += 6

        btn_w = (inner_w - 8) // 2
        confirm_disabled = not dist or self.one_way_pops_required_whole == 0
        self.one_way_confirm_rect = self._draw_button(x, y, btn_w, 24, "Confirm", disabled=confirm_disabled)
        if confirm_disabled:
            self.one_way_confirm_rect = None
        self.one_way_cancel_rect = self._draw_button(x + btn_w + 8, y, btn_w, 24, "Cancel")

    def _draw_city_panel(self, tile):
        pad = 16
        self.add_trade_route_button_rect = None
        self.trade_route_confirm_rect = None
        pygame.draw.rect(self.screen, PANEL_BG, (0, 0, CITY_PANEL_WIDTH, self.screen.get_height()))
        pygame.draw.line(self.screen, PANEL_DIVIDER,
                         (CITY_PANEL_WIDTH - 1, 0), (CITY_PANEL_WIDTH - 1, self.screen.get_height()), 1)

        x = pad
        bar_w = CITY_PANEL_WIDTH - pad * 2
        bar_h = 8
        bar_x = pad
        y = 20

        city = tile.city if tile else None
        dest_routes = [r for r in tile.trade_routes if r.dest_tile is tile] if (tile and not city) else []

        if not city and not dest_routes:
            return

        if not city:
            def _fmt_amt(v):
                return str(int(v)) if v == int(v) else f"{v:.1f}"
            surf = self.font_header.render("TRADE ROUTES", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 6
            self.trade_route_delete_rects = []
            self.trade_route_reduce_rects = []
            btn_s = 16
            for route in dest_routes:
                base_name = f"Tether From {route.city_a.name}" if route.tether else route.city_a.name
                if not route.established:
                    t = route.turns_until_established()
                    name_line = f"{base_name} ({t} {'turn' if t == 1 else 'turns'})"
                else:
                    name_line = base_name
                name_surf = self.font_body.render(name_line, True, TEXT_COLOR)
                self.screen.blit(name_surf, (x + 4, y))
                if not route.tether:
                    del_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "x")
                    self.trade_route_delete_rects.append((del_rect, route))
                    red_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                    self.trade_route_reduce_rects.append((red_rect, route))
                y += name_surf.get_height() + 2
                net_food = route.max_amount if route.export_resource == 'food' else 0
                food_str = f"+{_fmt_amt(net_food)}" if net_food >= 0 else _fmt_amt(net_food)
                detail_surf = self.font_small.render(f"{food_str} food", True, TEXT_COLOR)
                self.screen.blit(detail_surf, (x + 4, y))
                y += detail_surf.get_height() + 6
            return

        surf = self.font_header.render(city.name.upper(), True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6

        # Food stockpile bar
        food_max = city._stockpile_max()
        y = self._draw_labeled_bar(city, "Food Stockpile", f"{int(city.food_stockpile)}/{food_max}", 'food', bar_x, y, bar_w, bar_h, gap=8, tick_w=2)

        # Growth bar
        y = self._draw_labeled_bar(city, "Growth", f"{int(city.growth_progress)}/100", 'growth', bar_x, y, bar_w, bar_h, gap=8)

        # Production bar
        pt = city.production_target
        prod_label = "Production"
        if city.production_complete is not None:
            prod_val = f"{int(city.production_progress)}/{int(city.production_complete)}"
        else:
            prod_val = "—"
        y = self._draw_labeled_bar(city, prod_label, prod_val, 'production', bar_x, y, bar_w, bar_h, gap=12)

        btn_w2 = CITY_PANEL_WIDTH - pad * 2
        btn_h2 = 22
        self.rebalance_pops_button_rect = self._draw_button(pad, y, btn_w2, btn_h2, "Rebalance Pops")
        y += btn_h2 + 10

        y, _city_focus_collapsed = self._draw_section_header('city_focus', 'CITY FOCUS', x, y)
        focus_btn_h = 20
        if not _city_focus_collapsed:
            half_w = (CITY_PANEL_WIDTH - pad * 2 - 4) // 2
            self.halt_growth_rect = self._draw_button(
                pad, y, half_w, focus_btn_h, "Halt Growth", active=city.growth_halted)
            self.gates_closed_rect = self._draw_button(
                pad + half_w + 4, y, half_w, focus_btn_h, "Close Gates", active=city.gates_closed)
            y += focus_btn_h + 10
        else:
            self.halt_growth_rect = None
            self.gates_closed_rect = None

        y, _pops_collapsed = self._draw_section_header('pops', 'POPS', x, y)

        def _jlabel(label, n):
            return label[:-1] if n == 1 else label

        if not _pops_collapsed:
            btn_s = 16
            total_caravans = city._get_pops_assigned_to_routes()
            if total_caravans > 0:
                surf = self.font_body.render(f"{total_caravans} {_jlabel('Caravans', total_caravans)}", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
            available_farms = city.total_farm_slots - city.total_farm_assigned
            surf = self.font_body.render(f"{available_farms} Available {_jlabel('Farms', available_farms)}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
            n_peasants = city.food_pops
            surf = self.font_body.render(f"{n_peasants} {_jlabel('Peasants', n_peasants)}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
            free = city.free_pops
            surf = self.font_body.render(f"{free} Free {_jlabel('Pops', free)}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 8
            alloc_surf = self.font_body.render("Allocations", True, HEADER_TEXT_COLOR)
            self.screen.blit(alloc_surf, (x + 4, y))
            y += alloc_surf.get_height() + 2
            _jq_labels = {'growth': 'Growth', 'stockpile': 'Stockpile', 'production': 'Production'}
            self.job_queue_up_rects = []
            self.job_queue_down_rects = []
            self.job_queue_minus_rects = []
            self.job_queue_plus_rects = []
            self.job_queue_x_rects = []
            row_h = btn_s + 2
            for entry in city.job_queue:
                label_text = f"{entry.filled}/{entry.count} {_jq_labels.get(entry.job_type, entry.job_type)}"
                surf = self.font_body.render(label_text, True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y + (row_h - surf.get_height()) // 2))
                rx = CITY_PANEL_WIDTH - pad - btn_s
                self.job_queue_x_rects.append(self._draw_button(rx, y, btn_s, btn_s, "x"))
                rx -= btn_s + 4
                self.job_queue_plus_rects.append(self._draw_button(rx, y, btn_s, btn_s, "+"))
                rx -= btn_s + 2
                self.job_queue_minus_rects.append(self._draw_button(rx, y, btn_s, btn_s, "-"))
                rx -= btn_s + 4
                self.job_queue_down_rects.append(self._draw_button(rx, y, btn_s, btn_s, "v"))
                rx -= btn_s + 2
                self.job_queue_up_rects.append(self._draw_button(rx, y, btn_s, btn_s, "^"))
                y += row_h + 2
            self.add_job_button_rect = self._draw_button(x + 4, y, CITY_PANEL_WIDTH - pad * 2 - 4, 18, "Add Priority")
            y += 22
            for job in city.jobs:
                if job.job_type == 'production':
                    focus_assigned = city.remaining_free_pops - city.focus_unassigned_pops
                    if city.focus_unassigned_pops > 0:
                        remaining_label = f"Remaining {focus_assigned}/{city.remaining_free_pops} To"
                    else:
                        remaining_label = f"Remaining {city.remaining_free_pops} To"
                    remaining_surf = self.font_body.render(remaining_label, True, TEXT_COLOR)
                    self.screen.blit(remaining_surf, (x + 4, y))
                    y += remaining_surf.get_height() + 4
                    focus_widths = [60, 52, 72]
                    focus_x = x + 4
                    self.city_focus_rects = {}
                    farm_full = city._get_population() > city.total_farm_slots
                    for label, fw in zip(("Stockpile", "Growth", "Production"), focus_widths):
                        disabled = (label == 'Growth' and city.growth_halted) or (label in ('Growth', 'Stockpile') and farm_full)
                        rect = self._draw_button(focus_x, y, fw, 20, label,
                                                 active=(label == city.city_focus),
                                                 disabled=disabled)
                        if not disabled:
                            self.city_focus_rects[label] = rect
                        focus_x += fw + 2
                    y += 24
                    if city.focus_unassigned_pops > 0:
                        warn_surf = self.font_body.render("Not Enough Farms!", True, (220, 80, 80))
                        self.screen.blit(warn_surf, (x + 4, y))
                        y += warn_surf.get_height() + 2
            y += 4
        else:
            self.add_job_button_rect = None
            self.job_queue_up_rects = []
            self.job_queue_down_rects = []
            self.job_queue_minus_rects = []
            self.job_queue_plus_rects = []
            self.job_queue_x_rects = []
            self.city_focus_rects = {}
        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
        y += 10
        y, _yields_collapsed = self._draw_section_header('yields', 'YIELDS', x, y)

        def _fmt_res(v):
            return str(int(v)) if v == int(v) else f"{v:.1f}"

        def _signed(v):
            return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"

        if not _yields_collapsed:
            surf = self.font_body.render("Food", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2

            farm_food  = city._food_produced() - city._food_from_routes()
            route_food = city._food_from_routes()

            positive_lines = [("Agriculture", farm_food)]
            if route_food >= 0:
                positive_lines.append(("Trade Routes", route_food))

            negative_lines = []
            if route_food < 0:
                negative_lines.append(("Trade Routes", route_food, None))
            unit_consumption = city._get_unit_consumption()
            if unit_consumption > 0:
                negative_lines.append(("Units", -unit_consumption, None))
            negative_lines.append((f"Pops", -city.food_allocated_to_consumption, None))
            negative_lines.append(("Growth", -city.food_allocated_to_growth, f"(Adds {round(city.growth_allocated)})"))

            for label, val in positive_lines:
                surf = self.font_body.render(f"{label}  {_signed(val)}", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 12, y))
                y += surf.get_height() + 2

            for label, val, suffix in negative_lines:
                text = f"{label}  {_signed(val)}"
                if suffix:
                    text += f"  {suffix}"
                surf = self.font_body.render(text, True, TEXT_COLOR)
                self.screen.blit(surf, (x + 12, y))
                y += surf.get_height() + 2

            net = city.food_allocated_to_stockpile
            net_surf = self.font_body.render(f"= {_signed(net)} Net Stockpile Change", True, HEADER_TEXT_COLOR)
            self.screen.blit(net_surf, (x + 12, y))
            y += net_surf.get_height() + 2

            y += 6
            pt = city.production_target
            pt_label = f"Production: {pt.label}"
            self.production_target_button_rect = self._draw_button(x, y, CITY_PANEL_WIDTH - pad * 2, 22, pt_label)
            self.select_extraction_tile_button_rect = None
            y += 22 + 4
            workers = city.production_workers
            if not pt.type:
                status_surf = self.font_body.render("No Production Target", True, TEXT_COLOR)
                self.screen.blit(status_surf, (x + 4, y))
                y += status_surf.get_height() + 4
            elif workers == 0:
                status_surf = self.font_body.render("No Workers", True, TEXT_COLOR)
                self.screen.blit(status_surf, (x + 4, y))
                y += status_surf.get_height() + 4
            elif pt.type == 'manufacturing':
                prod_line = f"Production: {city.production_yield:.1f}/{workers:.1f}"
                prod_surf = self.font_body.render(prod_line, True, TEXT_COLOR)
                self.screen.blit(prod_surf, (x + 4, y))
                y += prod_surf.get_height() + 2
                for resource, amount in city.resources_allocated_to_production.items():
                    res_surf = self.font_body.render(f"  {resource.capitalize()}: {amount:.1f}", True, TEXT_COLOR)
                    self.screen.blit(res_surf, (x + 4, y))
                    y += res_surf.get_height() + 2
                if city.production_limited_by:
                    lim_surf = self.font_body.render(f"  Limited By {city.production_limited_by.capitalize()}", True, TEXT_COLOR)
                    self.screen.blit(lim_surf, (x + 4, y))
                    y += lim_surf.get_height() + 2
                y += 2
            elif pt.type == 'construction':
                prod_line = f"Production: {city.production_yield:.1f}/{workers:.1f}"
                prod_surf = self.font_body.render(prod_line, True, TEXT_COLOR)
                self.screen.blit(prod_surf, (x + 4, y))
                y += prod_surf.get_height() + 2
                for resource, amount in city.resources_allocated_to_production.items():
                    res_surf = self.font_body.render(f"  {resource.capitalize()}: {amount:.1f}", True, TEXT_COLOR)
                    self.screen.blit(res_surf, (x + 4, y))
                    y += res_surf.get_height() + 2
                if city.production_limited_by:
                    lim_surf = self.font_body.render(f"  Limited By {city.production_limited_by.capitalize()}", True, TEXT_COLOR)
                    self.screen.blit(lim_surf, (x + 4, y))
                    y += lim_surf.get_height() + 2
                y += 2
            else:
                prod_line = f"Production: {city.production_yield:.1f}" if city.production_yield > 0 else "No Production"
                prod_surf = self.font_body.render(prod_line, True, TEXT_COLOR)
                self.screen.blit(prod_surf, (x + 4, y))
                y += prod_surf.get_height() + 2
                efficiency = city.production_yield / workers if workers > 0 else 0.0
                eff_line = f"Extraction Efficiency: {efficiency:.2f}"
                eff_surf = self.font_body.render(eff_line, True, TEXT_COLOR)
                self.screen.blit(eff_surf, (x + 4, y))
                y += eff_surf.get_height() + 4
                if pt.type == 'extraction':
                    active = self.selecting_extraction_city is city
                    self.select_extraction_tile_button_rect = self._draw_button(
                        x, y, CITY_PANEL_WIDTH - pad * 2, 22, "Select Location", active=active
                    )
                    y += 22 + 4
        else:
            self.production_target_button_rect = None

        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
        y += 10
        y, _trade_routes_collapsed = self._draw_section_header('trade_routes', 'TRADE ROUTES', x, y)

        self.trade_route_delete_rects = []
        self.trade_route_reduce_rects = []
        if _trade_routes_collapsed:
            self.trade_route_slider_rect = None
            self.trade_route_amount_slider_rect = None
            self.trade_route_import_slider_rect = None
            self.trade_route_export_rects = {}
            self.trade_route_import_rects = {}
            self.add_one_way_route_button_rect = None
            return
        btn_s = 16
        for route in city.trade_routes:
            is_origin = route.city_a is city
            other_name = route.destination_name if is_origin else route.city_a.name

            if route.established:
                name_line = other_name
            else:
                t = route.turns_until_established()
                name_line = f"{other_name} ({t} {'turn' if t == 1 else 'turns'})"
            surf = self.font_body.render(name_line, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            if not route.tether:
                del_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "x")
                self.trade_route_delete_rects.append((del_rect, route))
                red_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                self.trade_route_reduce_rects.append((red_rect, route))
            y += surf.get_height() + 2
            pops = route.get_pops_from_city(city)

            if is_origin:
                out_res, out_amt = route.export_resource, route.max_amount if route.export_resource == 'food' else route.export_amount
                in_res,  in_amt  = route.import_resource, route.max_amount if route.import_resource == 'food' else route.import_amount
            else:
                out_res, out_amt = route.import_resource, route.max_amount if route.import_resource == 'food' else route.import_amount
                in_res,  in_amt  = route.export_resource, route.max_amount if route.export_resource == 'food' else route.export_amount

            def _rstr(res, amt, sign):
                if not res:
                    return None
                if res == 'food':
                    return f"{sign}{amt:.1f} Food"
                return f"{sign}{amt:.1f}/{route.max_amount:.1f} {res.title()}"

            out_str = _rstr(out_res, out_amt, '-') or ''
            detail = f"{pops} Pops, {out_str}" if out_str else f"{pops} Pops"
            if route.missing_caravans:
                detail += " (ending)"
            surf = self.font_body.render(detail, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2

            in_str = _rstr(in_res, in_amt, '+')
            if in_str:
                surf = self.font_body.render(in_str, True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
            y += 4

        self.trade_route_slider_rect = None
        self.trade_route_amount_slider_rect = None
        self.trade_route_import_slider_rect = None
        self.trade_route_export_rects = {}
        self.trade_route_import_rects = {}
        # self.add_trade_route_button_rect = self._draw_button(
        #     pad, y, CITY_PANEL_WIDTH - pad * 2, 22, "Add New Route",
        #     active=self.adding_trade_route)
        # y += 28
        self.add_one_way_route_button_rect = self._draw_button(
            pad, y, CITY_PANEL_WIDTH - pad * 2, 22, "Add Trade Route",
            active=self.adding_one_way_route)
        y += 28

    def _draw_panel(self, tile, move_mode=False):
        self.move_button_rect = None
        self.capture_button_rect = None
        self.raid_button_rect = None
        self.plunder_route_button_rect = None
        self.restrict_tile_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.recruit_unit_button_rect = None
        self.disband_button_rect = None
        self.settle_button_rect = None
        self.equip_button_rect = None
        panel_x = self.map_w
        pad = 16
        pygame.draw.rect(self.screen, PANEL_BG, (panel_x, 0, PANEL_WIDTH, self.screen.get_height()))
        pygame.draw.line(self.screen, PANEL_DIVIDER, (panel_x, 0), (panel_x, self.screen.get_height()), 1)

        x = panel_x + pad
        y = 20

        # Terrain section
        btn_w = PANEL_WIDTH - pad * 2
        btn_h = 22
        if tile:
            y, _terrain_collapsed = self._draw_section_header('terrain', 'TILE', x, y)
            if _terrain_collapsed:
                self.change_terrain_button_rect = None
                self.draw_river_button_rect = None
                self.restrict_tile_button_rect = None
            else:
                row_h = 22
                dr_btn_w = 78
                t_surf = self.font_body.render(tile.terrain.capitalize(), True, TEXT_COLOR)
                self.screen.blit(t_surf, (x + 4, y + (row_h - t_surf.get_height()) // 2))
                no_river = tile.terrain in ('hills', 'mountain')
                self.draw_river_button_rect = self._draw_button(
                    panel_x + PANEL_WIDTH - pad - dr_btn_w, y, dr_btn_w, row_h,
                    "Draw River", disabled=no_river,
                )
                if no_river:
                    self.draw_river_button_rect = None
                y += row_h + 8
                coords_surf = self.font_body.render(f"Row {tile.row}, Col {tile.col}", True, TEXT_COLOR)
                self.screen.blit(coords_surf, (x + 4, y))
                y += coords_surf.get_height() + 4
                biome_surf = self.font_body.render(f"Biome: {tile.biome.capitalize()}", True, TEXT_COLOR)
                self.screen.blit(biome_surf, (x + 4, y))
                y += biome_surf.get_height() + 4
                features_text = ", ".join(
                    "Water Access" if f == "water_access" else f.capitalize()
                    for f in tile.terrain_features
                ) if tile.terrain_features else "None"
                features_surf = self.font_body.render(f"Features: {features_text}", True, TEXT_COLOR)
                self.screen.blit(features_surf, (x + 4, y))
                y += features_surf.get_height() + 4
                self.change_terrain_button_rect = self._draw_button(panel_x + pad, y, btn_w, btn_h, "Change Terrain")
                y += btn_h + 6
                if tile.owning_city:
                    owned_surf = self.font_body.render(f"Owned By {tile.owning_city.name}", True, TEXT_COLOR)
                    self.screen.blit(owned_surf, (x + 4, y))
                    y += owned_surf.get_height() + 2
                    dist_surf = self.font_body.render(f"Distance {tile.city_distance:.2f}", True, TEXT_COLOR)
                    self.screen.blit(dist_surf, (x + 4, y))
                    y += dist_surf.get_height() + 2
                    yield_surf = self.font_body.render(f"Food Yield: {tile.farm_yield:.2f}", True, TEXT_COLOR)
                    self.screen.blit(yield_surf, (x + 4, y))
                    y += yield_surf.get_height() + 2
                    extraction_surf = self.font_body.render(f"Extraction Rate: {tile.extraction_yield:.2f}", True, TEXT_COLOR)
                    self.screen.blit(extraction_surf, (x + 4, y))
                    y += extraction_surf.get_height() + 2
                    farms_surf = self.font_body.render(f"{tile.worked_farms} Farms", True, TEXT_COLOR)
                    self.screen.blit(farms_surf, (x + 4, y))
                    y += farms_surf.get_height() + 4
                if tile.cities_in_range:
                    surf = self.font_body.render("Cities In Range:", True, TEXT_COLOR)
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 2
                    for city in tile.cities_in_range:
                        faction_name = city.faction.name if city.faction else "none"
                        surf = self.font_body.render(f"  {city.name} ({faction_name})", True, TEXT_COLOR)
                        self.screen.blit(surf, (x + 4, y))
                        y += surf.get_height() + 2
                if tile.raided:
                    label = f"Raided ({tile._raided_ticker} turns left)" if tile._raided_ticker > 0 else "Raided"
                    surf = self.font_body.render(label, True, (200, 80, 80))
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 2
                if tile.restricted:
                    label = f"Restricted ({tile._restricted_ticker} turns left)" if tile._restricted_ticker > 0 else "Restricted"
                    surf = self.font_body.render(label, True, (200, 160, 60))
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 2
                btn_label = "Unrestrict Tile" if tile.restricted else "Restrict Tile"
                disabled = tile._restricted_ticker > 0
                self.restrict_tile_button_rect = self._draw_button(x, y, PANEL_WIDTH - pad * 2, 20, btn_label, disabled=disabled)
                if disabled:
                    self.restrict_tile_button_rect = None
                y += 26
            y += 6

        self.save_map_button_rect = self._draw_button(panel_x + pad, y, btn_w, btn_h, "Save Map")
        y += btn_h + 6

        # Resources section
        has_deposits = bool(tile and tile.resource_deposits)
        has_resources = bool(tile and tile.resource_stockpiles)
        has_items = bool(tile and tile.item_stockpiles)
        has_buildings = bool(tile and tile.building_list)
        if has_deposits or has_resources or has_items or has_buildings:
            y, _inventory_collapsed = self._draw_section_header('inventory', 'TILE INVENTORY', x, y)
            if not _inventory_collapsed:
                def _qty_label(name, count):
                    return name.title() if count == 1 else f"{name.title()} x{count}"

                def _draw_inv_section(label, entries):
                    nonlocal y
                    sub = self.font_body.render(label, True, HEADER_TEXT_COLOR)
                    self.screen.blit(sub, (x + 4, y))
                    y += sub.get_height() + 2
                    for entry in entries:
                        line = self.font_body.render(entry, True, TEXT_COLOR)
                        self.screen.blit(line, (x + 8, y))
                        y += line.get_height() + 2
                    y += 4

                if has_deposits:
                    _draw_inv_section("Resource Deposits", [f"{v:.1f} {k.capitalize()}" for k, v in tile.resource_deposits.items()])
                if has_resources:
                    inv_city = tile.city if tile else None
                    def _resource_label(res, val):
                        label = f"{val:.1f} {res.capitalize()}"
                        if not inv_city:
                            return label
                        parts = []
                        prod_use = inv_city.resources_allocated_to_production.get(res, 0.0)
                        if prod_use > 0:
                            parts.append(f"-{prod_use:.1f} To Production")
                        route_net = 0.0
                        for route in inv_city.trade_routes:
                            if not route.established or route.missing_caravans:
                                continue
                            if route.city_a is inv_city:
                                if route.export_resource == res and res != 'food':
                                    route_net -= route.export_amount
                                if route.import_resource == res and res != 'food':
                                    route_net += route.import_amount
                            elif route.city_b is inv_city:
                                if route.export_resource == res and res != 'food':
                                    route_net += route.export_amount
                                if route.import_resource == res and res != 'food':
                                    route_net -= route.import_amount
                        if route_net != 0.0:
                            sign = '+' if route_net > 0 else ''
                            direction = 'From' if route_net > 0 else 'To'
                            parts.append(f"{sign}{route_net:.1f} {direction} Routes")
                        if parts:
                            label += f" ({', '.join(parts)})"
                        return label
                    _draw_inv_section("Resource Stockpiles", [_resource_label(k, v) for k, v in tile.resource_stockpiles.items()])
                if has_items:
                    _draw_inv_section("Items", [_qty_label(k, v) for k, v in tile.item_stockpiles.items()])
                if has_buildings:
                    _draw_inv_section("Buildings", [_qty_label(k, v) for k, v in tile.building_list.items()])
                y += 2

        unit_groups = self.map.get_unit_groups(tile.row, tile.col) if tile else []
        has_city = tile and tile.city is not None
        _units_collapsed = False
        if unit_groups or has_city:
            pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (panel_x + PANEL_WIDTH - pad, y), 1)
            y += 16
            y, _units_collapsed = self._draw_section_header('units', 'UNITS', x, y)
            if not _units_collapsed:
                selected_on_tile = [g for g in unit_groups if g in self.selected_unit_groups]
                half_w = (PANEL_WIDTH - pad * 2 - 4) // 2
                recruit_disabled = not has_city or (has_city and len(tile.city.pops) <= tile.city.total_farm_slots)
                any_levy_away = any(
                    g.levy and g.tether is not None
                    and not (g.row == g.tether.city.row and g.col == g.tether.city.col)
                    for g in selected_on_tile
                )
                disband_disabled = not has_city or len(selected_on_tile) == 0 or any(g.move_exhausted for g in selected_on_tile) or any_levy_away
                recruit_label = "Recruit"
                if has_city:
                    _cur = max(0, len(tile.city.pops) - tile.city.total_farm_slots)
                    _max = tile.city.non_food_pop_limit
                    recruit_label = f"Recruit {_cur}/{_max}"
                self.recruit_unit_button_rect = self._draw_button(panel_x + pad, y, half_w, btn_h, recruit_label, disabled=recruit_disabled)
                self.disband_button_rect = self._draw_button(panel_x + pad + half_w + 4, y, half_w, btn_h, "Disband", disabled=disband_disabled)
                if recruit_disabled:
                    self.recruit_unit_button_rect = None
                if disband_disabled:
                    self.disband_button_rect = None
                y += btn_h + 6
                self.raise_levies_button_rect = self._draw_button(panel_x + pad, y, PANEL_WIDTH - pad * 2, btn_h, "Raise Levies", disabled=not has_city)
                if not has_city:
                    self.raise_levies_button_rect = None
                y += btn_h + 6

        first_group = unit_groups[0] if unit_groups else None
        if first_group and not _units_collapsed:
            btn_h = 20
            full_w = PANEL_WIDTH - pad * 2
            half_w = (full_w - 4) // 2
            selected_on_tile = [g for g in unit_groups if g in self.selected_unit_groups]
            min_moves = min(g.moves_remaining for g in unit_groups)
            any_exhausted = any(g.move_exhausted for g in selected_on_tile)
            self.move_button_rect = self._draw_button(
                x, y, full_w, btn_h, "Move",
                active=move_mode, disabled=min_moves == 0 or not selected_on_tile or any_exhausted,
            )
            y += btn_h + 4
            unit_faction = first_group.faction if first_group else None
            tile_faction = tile.owning_city.faction if tile and tile.owning_city else None
            tile_farm_jobs = [j for j in tile.jobs if j.job_type == 'farm'] if tile else []
            capture_enabled = (
                bool(selected_on_tile) and
                not any(g.move_exhausted for g in selected_on_tile) and
                any(g.can_capture_tile for g in selected_on_tile) and
                all(g.moves_remaining >= g.max_moves for g in selected_on_tile)
            )
            self.capture_button_rect = self._draw_button(x, y, half_w, btn_h, "Capture", disabled=not capture_enabled)
            if not capture_enabled:
                self.capture_button_rect = None
            raid_enabled = (
                bool(selected_on_tile) and
                unit_faction is not None and
                tile_faction is not None and
                tile_faction is not unit_faction and
                not any(g.move_exhausted for g in selected_on_tile) and
                all(g.moves_remaining >= 2 for g in selected_on_tile) and
                bool(tile_farm_jobs)
            )
            self.raid_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Raid", disabled=not raid_enabled)
            if not raid_enabled:
                self.raid_button_rect = None
            y += btn_h + 6
            plunder_enabled = (
                bool(selected_on_tile) and
                not any(g.move_exhausted for g in selected_on_tile) and
                all(g.moves_remaining >= 2 for g in selected_on_tile)
            )
            self.plunder_route_button_rect = self._draw_button(x, y, half_w, btn_h, "Plunder Route", disabled=not plunder_enabled)
            if not plunder_enabled:
                self.plunder_route_button_rect = None
            settle_group = selected_on_tile[0] if selected_on_tile else (first_group if first_group else None)
            settle_faction = settle_group.faction if settle_group else None
            tile_owned_by_other = (
                tile and tile.owning_city is not None and
                tile.owning_city.faction is not settle_faction
            )
            groups_for_settle = selected_on_tile if selected_on_tile else [first_group] if first_group else []
            has_full_moves = all(g.moves_remaining >= g.max_moves for g in groups_for_settle)
            settle_disabled = tile_owned_by_other or (tile and tile.city is not None) or not has_full_moves
            self.settle_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Settle", disabled=settle_disabled)
            if settle_disabled:
                self.settle_button_rect = None
            y += btn_h + 6

        icon_h = self.font_body.get_height()
        outline_r = 2
        # Build per-unit-type small icon surfaces: {icon_name: {'plain': surf, 'default': surf, fname: surf}}
        _unit_icon_names = {cls.unit_type: cls.icon for cls in UNIT_REGISTRY.values() if hasattr(cls, 'icon')}
        _unit_icon_scale = {cls.icon: cls.icon_scale for cls in UNIT_REGISTRY.values() if hasattr(cls, 'icon')}
        _unit_icon_x_offset = {cls.unit_type: cls.icon_x_offset for cls in UNIT_REGISTRY.values()}
        small_icons = {}
        for icon_name in set(_unit_icon_names.values()):
            icon_raw = self._icons_raw.get(icon_name)
            if not icon_raw:
                continue
            size = int(icon_h * _unit_icon_scale.get(icon_name, 1.0))
            scaled = pygame.transform.scale(icon_raw, (size, size))
            tinted, _, _ = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), outline_r, pad=outline_r)
            entry = {'plain': scaled, 'default': tinted}
            for group in unit_groups:
                if group.faction:
                    fname = group.faction.name
                    if fname not in entry:
                        t, _, _ = self._make_icon_pair(scaled, group.faction.colors['light'], group.faction.colors['dark'], outline_r, pad=outline_r)
                        entry[fname] = t
            small_icons[icon_name] = entry
        bar_w = PANEL_WIDTH - pad * 2
        bar_h = 6

        self.group_icon_rects = []
        for group in (unit_groups if not _units_collapsed else []):
            selected = group in self.selected_unit_groups
            fname = group.faction.name if group.faction else None
            type_counts = collections.Counter(u.unit_type for u in group.units)
            _order = {t: i for i, t in enumerate(UNIT_DISPLAY_ORDER)}
            sorted_types = sorted(type_counts.items(), key=lambda kv: _order.get(kv[0], 99))
            icon_overlap = 8       # overlap between icons of the same type
            icon_type_gap = 20     # center-to-center distance between last icon of one type and first of the next
            row_top_y = y
            row_h = int(icon_h * 2)
            cur_x = x + 4
            for i, (unit_type, count) in enumerate(sorted_types):
                icon_name = _unit_icon_names.get(unit_type)
                icon_data = small_icons.get(icon_name, {})
                icon_surf = (icon_data.get(fname) or icon_data.get('default')) if selected else icon_data.get('plain')
                icon_w = icon_surf.get_width() if icon_surf else icon_h
                icon_actual_h = icon_surf.get_height() if icon_surf else icon_h
                y_off = (row_h - icon_actual_h) // 2
                x_off = _unit_icon_x_offset.get(unit_type, 0)
                for j in range(count):
                    if icon_surf:
                        self.screen.blit(icon_surf, (cur_x + j * icon_overlap - x_off, y + y_off))
                if i < len(sorted_types) - 1:
                    last_center_x = cur_x + (count - 1) * icon_overlap + icon_w // 2
                    next_type, _ = sorted_types[i + 1]
                    next_icon_name = _unit_icon_names.get(next_type)
                    next_icon_data = small_icons.get(next_icon_name, {})
                    next_icon_surf = (next_icon_data.get(fname) or next_icon_data.get('default')) if selected else next_icon_data.get('plain')
                    next_icon_w = next_icon_surf.get_width() if next_icon_surf else icon_h
                    cur_x = last_center_x + icon_type_gap - next_icon_w // 2
            if group.tether is not None:
                ww_raw = self._icons_raw.get('wagon_wheel')
                if ww_raw:
                    ww_size = int(icon_h * 1.3)
                    ww_scaled = pygame.transform.scale(ww_raw, (ww_size, ww_size))
                    light = group.faction.colors['light'] if group.faction else (180, 210, 255)
                    dark = group.faction.colors['dark'] if group.faction else (35, 65, 150)
                    ww_tinted, _, _ = self._make_icon_pair(ww_scaled, light, dark, outline_r, pad=outline_r)
                    ww_surf = ww_tinted if selected else ww_scaled
                    tether_gap = icon_type_gap + 8
                    if sorted_types:
                        last_center_x = cur_x + (count - 1) * icon_overlap + icon_w // 2
                        ww_x = last_center_x + tether_gap - ww_size // 2
                    else:
                        ww_x = cur_x
                    ww_y = y + (row_h - ww_surf.get_height()) // 2
                    self.screen.blit(ww_surf, (ww_x, ww_y))
                    # Draw tether units after the wheel using same overlap/gap logic
                    tether_type_counts = collections.Counter(u.unit_type for u in group.tether.tether_units)
                    tether_sorted = sorted(tether_type_counts.items(), key=lambda kv: _order.get(kv[0], 99))
                    t_cur_x = ww_x + ww_size // 2 + tether_gap
                    for ti, (t_unit_type, t_count) in enumerate(tether_sorted):
                        t_icon_name = _unit_icon_names.get(t_unit_type)
                        t_icon_data = small_icons.get(t_icon_name, {})
                        t_icon_surf = (t_icon_data.get(fname) or t_icon_data.get('default')) if selected else t_icon_data.get('plain')
                        t_icon_w = t_icon_surf.get_width() if t_icon_surf else icon_h
                        t_icon_actual_h = t_icon_surf.get_height() if t_icon_surf else icon_h
                        t_y_off = (row_h - t_icon_actual_h) // 2
                        t_x_off = _unit_icon_x_offset.get(t_unit_type, 0)
                        t_cur_x -= t_icon_w // 2
                        for j in range(t_count):
                            if t_icon_surf:
                                self.screen.blit(t_icon_surf, (t_cur_x + j * icon_overlap - t_x_off, y + t_y_off))
                        if ti < len(tether_sorted) - 1:
                            last_t_center = t_cur_x + (t_count - 1) * icon_overlap + t_icon_w // 2
                            next_t_type, _ = tether_sorted[ti + 1]
                            next_t_icon_name = _unit_icon_names.get(next_t_type)
                            next_t_data = small_icons.get(next_t_icon_name, {})
                            next_t_surf = (next_t_data.get(fname) or next_t_data.get('default')) if selected else next_t_data.get('plain')
                            next_t_w = next_t_surf.get_width() if next_t_surf else icon_h
                            t_cur_x = last_t_center + icon_type_gap - next_t_w // 2
            y += row_h + 4
            icon_rect = pygame.Rect(x + 4, row_top_y, bar_w - 4, y - row_top_y)
            self.group_icon_rects.append((icon_rect, group))
            y += 2

            move_bar_max = group.max_moves + MOVE_CARRY_OVER
            food_bar_w = int(bar_w * group.max_moves / move_bar_max)
            pygame.draw.rect(self.screen, (30, 30, 40), (x, y, food_bar_w, bar_h), border_radius=2)
            if group.max_food_stockpile > 0:
                from_stockpile = -group.food_allocated_to_stockpile
                current = min(group.food_stockpile, group.max_food_stockpile)
                proj = max(0.0, min(current - from_stockpile, group.max_food_stockpile))
                fill_w = max(int(food_bar_w * current / group.max_food_stockpile), 0)
                proj_w = max(int(food_bar_w * proj / group.max_food_stockpile), 0)
                if from_stockpile > 0:
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (220, 110, 60), (x, y, fill_w, bar_h), border_radius=2)
                    if proj_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (x, y, proj_w, bar_h), border_radius=2)
                else:
                    if proj_w > 0:
                        pygame.draw.rect(self.screen, (200, 240, 165), (x, y, proj_w, bar_h), border_radius=2)
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (120, 190, 80), (x, y, fill_w, bar_h), border_radius=2)
                tick_interval = group.consumption_per_turn()
                if tick_interval > 0:
                    tick = tick_interval
                    while tick < group.max_food_stockpile:
                        tx = x + int(food_bar_w * tick / group.max_food_stockpile)
                        pygame.draw.line(self.screen, (30, 30, 40), (tx, y), (tx, y + bar_h - 1))
                        tick += tick_interval
            pygame.draw.rect(self.screen, PANEL_DIVIDER, (x, y, food_bar_w, bar_h), 1, border_radius=2)
            y += bar_h + 4

            move_rect_w = bar_w if group.moves_remaining > group.max_moves else int(bar_w * group.max_moves / move_bar_max)
            pygame.draw.rect(self.screen, (30, 30, 40), (x, y, move_rect_w, bar_h), border_radius=2)
            if move_bar_max > 0 and not group.move_exhausted:
                carryover_w = int(bar_w * min(group.moves_remaining, move_bar_max) / move_bar_max)
                if carryover_w > 0:
                    pygame.draw.rect(self.screen, (255, 240, 60), (x, y, carryover_w, bar_h), border_radius=2)
                fill_w = int(bar_w * min(group.moves_remaining, group.max_moves) / move_bar_max)
                if fill_w > 0 and group.moves_remaining > MOVE_CARRY_OVER:
                    pygame.draw.rect(self.screen, (230, 195, 50), (x, y, fill_w, bar_h), border_radius=2)
                for i in range(1, int(move_bar_max)):
                    tx = x + int(bar_w * i / move_bar_max)
                    pygame.draw.line(self.screen, (30, 30, 40), (tx, y), (tx, y + bar_h - 1))
            pygame.draw.rect(self.screen, PANEL_DIVIDER, (x, y, move_rect_w, bar_h), 1, border_radius=2)
            y += bar_h + 8

        if unit_groups and not _units_collapsed:
            btn_h = 20
            half_w = (bar_w - 4) // 2
            selected_on_tile = [g for g in unit_groups if g in self.selected_unit_groups]
            equip_groups = selected_on_tile if selected_on_tile else unit_groups
            equip_disabled = not (tile and tile.item_stockpiles) or len(equip_groups) != 1
            self.select_all_button_rect = self._draw_button(x, y, half_w, btn_h, "Select All")
            self.equip_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Equip", disabled=equip_disabled)
            if equip_disabled:
                self.equip_button_rect = None
            y += btn_h + 4
            any_levy = any(g.levy for g in selected_on_tile)
            merge_disabled = len(selected_on_tile) < 2 or any_levy
            self.merge_button_rect = self._draw_button(x, y, half_w, btn_h, "Merge", disabled=merge_disabled)
            if merge_disabled:
                self.merge_button_rect = None
            separate_disabled = len(selected_on_tile) != 1 or len(selected_on_tile[0].units) < 2 or any_levy
            self.separate_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Separate", disabled=separate_disabled)
            if separate_disabled:
                self.separate_button_rect = None
            y += btn_h + 4
            restock_disabled = not has_city or not selected_on_tile
            self.restock_button_rect = self._draw_button(x, y, half_w, btn_h, "Restock", disabled=restock_disabled)
            if restock_disabled:
                self.restock_button_rect = None
            drop_disabled = not has_city or not selected_on_tile
            self.drop_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Drop", disabled=drop_disabled)
            if drop_disabled:
                self.drop_button_rect = None
            y += btn_h + 4
            has_tether = bool(selected_on_tile) and any(g.tether is not None for g in selected_on_tile)
            add_tether_disabled = not has_city or not selected_on_tile or has_tether or any_levy
            self.add_tether_button_rect = self._draw_button(x, y, half_w, btn_h, "Add Tether", disabled=add_tether_disabled)
            if add_tether_disabled:
                self.add_tether_button_rect = None
            drop_tether_disabled = not selected_on_tile or not has_tether or any_levy
            self.drop_tether_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Drop Tether", disabled=drop_tether_disabled)
            if drop_tether_disabled:
                self.drop_tether_button_rect = None
            y += btn_h + 6

        # End Turn button anchored to bottom
        btn_w = PANEL_WIDTH - pad * 2
        btn_h = 28
        self.end_turn_button_rect = self._draw_button(
            panel_x + pad, self.screen.get_height() - BOTTOM_PANEL_HEIGHT - pad - btn_h, btn_w, btn_h, "End Turn"
        )

    def _draw_console_overlay(self, console_input):
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        bar_h = 38
        bar_y = sh - bar_h

        pygame.draw.rect(self.screen, (18, 18, 28), (0, bar_y, sw, bar_h))
        pygame.draw.line(self.screen, PANEL_DIVIDER, (0, bar_y), (sw, bar_y), 1)

        pad = 10
        prompt = self.font_body.render("> ", True, HEADER_TEXT_COLOR)
        self.screen.blit(prompt, (pad, bar_y + (bar_h - prompt.get_height()) // 2))

        input_x = pad + prompt.get_width()
        input_surf = self.font_body.render(console_input + "|", True, TEXT_COLOR)
        self.screen.blit(input_surf, (input_x, bar_y + (bar_h - input_surf.get_height()) // 2))

        hint = self.font_small.render(
            "Enter to run  •  Esc to close  •  e.g. len(list(game_map.cities.values())[0].pops)",
            True, (90, 90, 110)
        )
        self.screen.blit(hint, (sw - hint.get_width() - pad,
                                bar_y + (bar_h - hint.get_height()) // 2))

    def _draw_production_popup(self, city):
        from src.game.production import PRODUCTION_CATEGORIES, PRODUCTION_SUBTYPES, EXTRACTION_LABELS
        from src.game.items import ITEM_REGISTRY
        from src.game.buildings import BUILDING_REGISTRY
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        pad = 14
        btn_h = 18
        btn_w = 110
        row_h = btn_h + 4
        category_gap = 10
        W = 560

        n_rows = sum(max(1, len(PRODUCTION_SUBTYPES[c])) for c in PRODUCTION_CATEGORIES)
        H = pad + 20 + 6 + len(PRODUCTION_CATEGORIES) * (18 + 4 + category_gap) + n_rows * row_h + pad
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        desc_x = sx + pad + btn_w + 8

        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("PRODUCTION TARGET", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + pad, sy + pad))
        y = sy + pad + surf.get_height() + 6

        def _item_desc(cls):
            parts = [f"{cls.production_needed} Production"]
            for r, cost in cls.resource_cost.items():
                parts.append(f"{int(cost)} {r.capitalize()}")
            rate_parts = [f"{cost / cls.production_needed:.1f} {r.capitalize()}" for r, cost in cls.resource_cost.items()]
            return ", ".join(parts) + f" ({', '.join(rate_parts)} Per Production)"

        self.production_popup_rects = {}
        for category in PRODUCTION_CATEGORIES:
            cat_surf = self.font_body.render(category.capitalize(), True, HEADER_TEXT_COLOR)
            self.screen.blit(cat_surf, (sx + pad, y))
            y += cat_surf.get_height() + 4
            subtypes = PRODUCTION_SUBTYPES[category]
            if subtypes:
                for subtype in subtypes:
                    active = (city.production_target.type == category and
                              city.production_target.target == subtype)
                    desc = None
                    if category == 'extraction':
                        unavailable = not city.has_accessible_deposit(subtype)
                        label = EXTRACTION_LABELS.get(subtype, subtype.capitalize()) if active else subtype.capitalize()
                        total = sum(t.resource_deposits.get(subtype, 0) for t in city.get_eligible_extraction_tiles(subtype))
                        desc = f"{int(total)} {subtype.capitalize()} Accessible"
                    elif category == 'manufacturing':
                        item_cls = ITEM_REGISTRY.get(subtype)
                        unavailable = item_cls is None or any(
                            item_cls.requires_resource(r) and not city.has_resource(r)
                            for r in item_cls.resource_cost
                        )
                        unfinished = city.production_target.get_unfinished_progress(item_cls) if item_cls else None
                        label = f"{subtype.capitalize()} ({int(unfinished)}/{item_cls.production_needed})" if unfinished is not None else subtype.capitalize()
                        if item_cls:
                            desc = _item_desc(item_cls)
                    elif category == 'construction':
                        building_cls = BUILDING_REGISTRY.get(subtype)
                        already_built = city.tile is not None and city.tile.building_list.get(subtype, 0) > 0
                        unavailable = (
                            building_cls is None or
                            any(not city.has_resource(r) for r in building_cls.resource_cost) or
                            (not building_cls.multiple and already_built)
                        )
                        label = subtype.title()
                        if building_cls:
                            desc = _item_desc(building_cls)
                    else:
                        unavailable = False
                        label = subtype.capitalize()
                    rect = self._draw_button(sx + pad, y, btn_w, btn_h, label, active=active, disabled=unavailable)
                    if not unavailable:
                        self.production_popup_rects[(category, subtype)] = rect
                    if desc:
                        desc_color = TEXT_COLOR if not unavailable else PANEL_DIVIDER
                        desc_surf = self.font_body.render(desc, True, desc_color)
                        self.screen.blit(desc_surf, (desc_x, y + (btn_h - desc_surf.get_height()) // 2))
                    y += row_h
            else:
                placeholder = self.font_small.render("(none available)", True, PANEL_DIVIDER)
                self.screen.blit(placeholder, (sx + pad + 4, y + 4))
                y += row_h
            y += category_gap

    def _draw_recruit_popup(self, city, levy_mode=False):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        W = 280
        H = 140 if levy_mode else (294 if self.recruit_popup_supply_train else 246)
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pad = 16
        track_h = 6
        track_w = W - pad * 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        title = "RAISE LEVIES" if levy_mode else "RECRUIT UNITS"
        surf = self.font_header.render(title, True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + pad, sy + 12))

        from src.game.constants import SELECTION_INCREMENT as _SEL_INC
        max_recruit = len(city.pops) - 1 if levy_mode else max(0, len(city.pops) - city.total_farm_slots)
        amount = max(0, min(self.recruit_popup_amount, max_recruit))
        self.recruit_popup_amount = amount

        lbl_surf = self.font_body.render("Unit Count", True, TEXT_COLOR)
        self.screen.blit(lbl_surf, (sx + pad, sy + 36))
        all_free_w = 80
        self.recruit_all_free_rect = self._draw_button(sx + W - pad - all_free_w, sy + 32, all_free_w, 20, "All Free Pops")

        track_x = sx + pad
        btn_y   = sy + 54
        btn_h   = 22
        btn_w   = 30
        gap_sm  = 4
        self.recruit_popup_slider_rect = None
        self.recruit_dec2_rect = self._draw_button(track_x,                         btn_y, btn_w, btn_h, "--")
        self.recruit_dec1_rect = self._draw_button(track_x + btn_w + gap_sm,        btn_y, btn_w, btn_h, "-")
        self.recruit_inc2_rect = self._draw_button(track_x + track_w - btn_w,       btn_y, btn_w, btn_h, "++")
        self.recruit_inc1_rect = self._draw_button(track_x + track_w - btn_w*2 - gap_sm, btn_y, btn_w, btn_h, "+")
        count_surf = self.font_header.render(str(amount), True, TEXT_COLOR)
        cx = sx + W // 2
        self.screen.blit(count_surf, (cx - count_surf.get_width() // 2, btn_y + (btn_h - count_surf.get_height()) // 2))

        if levy_mode:
            # Stockpile fixed at 0, supply food = unit count — hidden from player
            self.recruit_popup_food = 0
            self.recruit_popup_food_slider_rect = None
            self.recruit_food_dec_rect = None
            self.recruit_food_inc_rect = None
            self.recruit_popup_supply_food = amount
            self.recruit_popup_supply_food_slider_rect = None
            self.recruit_popup_supply_checkbox_rect = None
            can_afford = amount > 0
        else:
            max_food_per_pop = MILITARY_CARRY_CAPACITY
            food_per_pop = max(0, min(self.recruit_popup_food, max_food_per_pop))
            self.recruit_popup_food = food_per_pop

            food_lbl_surf = self.font_body.render("Stockpile Per Unit", True, TEXT_COLOR)
            self.screen.blit(food_lbl_surf, (sx + pad, sy + 88))

            food_btn_y = sy + 106
            self.recruit_popup_food_slider_rect = None
            self.recruit_food_dec_rect = self._draw_button(track_x,                   food_btn_y, btn_w, btn_h, "-")
            self.recruit_food_inc_rect = self._draw_button(track_x + track_w - btn_w, food_btn_y, btn_w, btn_h, "+")
            food_count_surf = self.font_header.render(str(food_per_pop), True, TEXT_COLOR)
            self.screen.blit(food_count_surf, (cx - food_count_surf.get_width() // 2, food_btn_y + (btn_h - food_count_surf.get_height()) // 2))

            # Food cost summary
            recruitment_cost = amount
            stockpile_food   = food_per_pop * amount
            total_food       = recruitment_cost + stockpile_food
            food_ok          = amount == 0 or total_food <= city.food_stockpile
            can_afford       = amount > 0 and total_food <= city.food_stockpile
            cost_color       = TEXT_COLOR if food_ok else (220, 60, 60)
            total_surf  = self.font_body.render(f"Total Food Cost: {total_food}", True, cost_color)
            detail_surf = self.font_small.render(f"= {recruitment_cost} (Recruitment) + {stockpile_food} (Stockpile)", True, cost_color)
            self.screen.blit(total_surf,  (sx + pad, sy + 140))
            self.screen.blit(detail_surf, (sx + pad, sy + 156))

            # Supply Train checkbox
            cb_size = 14
            cb_x, cb_y = sx + pad, sy + 180
            cb_rect = pygame.Rect(cb_x, cb_y, cb_size, cb_size)
            pygame.draw.rect(self.screen, (60, 60, 80), cb_rect, border_radius=2)
            if self.recruit_popup_supply_train:
                pygame.draw.rect(self.screen, (160, 190, 240), cb_rect.inflate(-4, -4), border_radius=1)
            else:
                pygame.draw.rect(self.screen, PANEL_DIVIDER, cb_rect, 1, border_radius=2)
            label_surf = self.font_body.render("Supply Train", True, TEXT_COLOR)
            self.screen.blit(label_surf, (cb_x + cb_size + 6, cb_y - 1))
            self.recruit_popup_supply_checkbox_rect = pygame.Rect(cb_x, cb_y - 2, cb_size + 6 + label_surf.get_width(), cb_size + 4)

            if self.recruit_popup_supply_train:
                max_supply_food = max(1, amount * 2)
                supply_food = max(1, min(self.recruit_popup_supply_food, max_supply_food))
                self.recruit_popup_supply_food = supply_food
                sf_label = self.font_body.render(f"Food Per Turn: {supply_food}", True, TEXT_COLOR)
                self.screen.blit(sf_label, (sx + pad, sy + 202))
                sf_track_y = sy + 220
                pygame.draw.rect(self.screen, (60, 60, 80), (track_x, sf_track_y, track_w, track_h), border_radius=2)
                sfhx = track_x + int((supply_food - 1) / max(max_supply_food - 1, 1) * track_w)
                sfhy = sf_track_y + track_h // 2
                pygame.draw.circle(self.screen, (160, 190, 240), (sfhx, sfhy), 6)
                pygame.draw.circle(self.screen, (100, 130, 190), (sfhx, sfhy), 6, 1)
                self.screen.blit(self.font_small.render("1", True, PANEL_DIVIDER), (track_x, sf_track_y + track_h + 3))
                max_sf_surf = self.font_small.render(str(max_supply_food), True, PANEL_DIVIDER)
                self.screen.blit(max_sf_surf, (track_x + track_w - max_sf_surf.get_width(), sf_track_y + track_h + 3))
                self.recruit_popup_supply_food_slider_rect = pygame.Rect(track_x, sf_track_y - 6, track_w, track_h + 16)
            else:
                self.recruit_popup_supply_food_slider_rect = None

        btn_y = sy + H - 36
        btn_w = (W - pad * 2 - 8) // 2
        self.recruit_popup_confirm_rect = self._draw_button(sx + pad, btn_y, btn_w, 24, "Confirm", disabled=not can_afford)
        self.recruit_popup_cancel_rect  = self._draw_button(sx + pad + btn_w + 8, btn_y, btn_w, 24, "Cancel")

    def _draw_add_tether_popup(self, group):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        W, H = 280, 150
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pad = 16
        track_h = 6
        track_w = W - pad * 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("ADD TETHER", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + pad, sy + 12))

        n_units = len(group.units)
        max_food = max(1, n_units * 2)
        food = max(1, min(self.add_tether_popup_food, max_food))
        self.add_tether_popup_food = food

        track_x = sx + pad
        label = self.font_body.render(f"Food Per Turn: {food}", True, TEXT_COLOR)
        self.screen.blit(label, (track_x, sy + 36))

        track_y = sy + 54
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
        hx = track_x + int((food - 1) / max(max_food - 1, 1) * track_w)
        hy = track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
        self.screen.blit(self.font_small.render("1", True, PANEL_DIVIDER), (track_x, track_y + track_h + 3))
        max_surf = self.font_small.render(str(max_food), True, PANEL_DIVIDER)
        self.screen.blit(max_surf, (track_x + track_w - max_surf.get_width(), track_y + track_h + 3))
        self.add_tether_popup_slider_rect = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)

        btn_y = sy + H - 36
        btn_w = (W - pad * 2 - 8) // 2
        self.add_tether_popup_confirm_rect = self._draw_button(sx + pad, btn_y, btn_w, 24, "Confirm")
        self.add_tether_popup_cancel_rect = self._draw_button(sx + pad + btn_w + 8, btn_y, btn_w, 24, "Cancel")

    def _draw_separate_popup(self):
        import collections
        group = self.separate_popup_group
        if not group:
            return
        type_counts = collections.Counter(u.unit_type for u in group.units)
        unit_types = list(type_counts.keys())
        n_types = len(unit_types)

        track_h = 6
        pad = 16
        row_h = 44
        W = 300
        H = 32 + n_types * row_h + 52 + 40 + pad
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        track_w = W - pad * 2

        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        title = self.font_header.render("SEPARATE GROUP", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (sx + pad, sy + 10))

        self.separate_popup_slider_rects = {}
        track_x = sx + pad
        y = sy + 32

        for unit_type in unit_types:
            max_val = type_counts[unit_type]
            val = max(0, min(self.separate_popup_counts.get(unit_type, 0), max_val))
            self.separate_popup_counts[unit_type] = val

            label = self.font_body.render(f"{unit_type}: {val}/{max_val}", True, TEXT_COLOR)
            self.screen.blit(label, (track_x, y))
            y += label.get_height() + 4

            track_y = y
            pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
            hx = track_x + (int(val / max_val * track_w) if max_val > 0 else 0)
            hy = track_y + track_h // 2
            pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
            pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
            self.screen.blit(self.font_small.render("0", True, PANEL_DIVIDER), (track_x, track_y + track_h + 3))
            max_surf = self.font_small.render(str(max_val), True, PANEL_DIVIDER)
            self.screen.blit(max_surf, (track_x + track_w - max_surf.get_width(), track_y + track_h + 3))
            self.separate_popup_slider_rects[unit_type] = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)
            y += track_h + 18

        # Food slider
        total_selected = sum(self.separate_popup_counts.values())
        from src.game.constants import MILITARY_CARRY_CAPACITY
        type_kept = {ut: type_counts[ut] - self.separate_popup_counts.get(ut, 0) for ut in type_counts}
        kept_carry = 0
        type_seen = {ut: 0 for ut in type_counts}
        for u in group.units:
            if type_seen[u.unit_type] < type_kept[u.unit_type]:
                kept_carry += u.carry_capacity
                type_seen[u.unit_type] += 1
        min_food = max(0, int(group.food_stockpile) - kept_carry)
        max_food = min(total_selected * MILITARY_CARRY_CAPACITY, int(group.food_stockpile)) if total_selected > 0 else min_food
        self.separate_popup_min_food = min_food
        food_val = max(min_food, min(max_food, self.separate_popup_food))
        self.separate_popup_food = food_val

        food_label = self.font_body.render(f"Food: {food_val}", True, TEXT_COLOR)
        self.screen.blit(food_label, (track_x, y))
        y += food_label.get_height() + 4

        f_track_y = y
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, f_track_y, track_w, track_h), border_radius=2)
        food_range = max_food - min_food
        fhx = track_x + (int((food_val - min_food) / food_range * track_w) if food_range > 0 else 0)
        fhy = f_track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (fhx, fhy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (fhx, fhy), 6, 1)
        self.screen.blit(self.font_small.render(str(min_food), True, PANEL_DIVIDER), (track_x, f_track_y + track_h + 3))
        mf_surf = self.font_small.render(str(max_food), True, PANEL_DIVIDER)
        self.screen.blit(mf_surf, (track_x + track_w - mf_surf.get_width(), f_track_y + track_h + 3))
        self.separate_popup_food_slider_rect = pygame.Rect(track_x, f_track_y - 6, track_w, track_h + 16)
        y += track_h + 18

        btn_w = (W - pad * 2 - 8) // 2
        confirm_disabled = total_selected == 0
        self.separate_popup_confirm_rect = self._draw_button(sx + pad, y, btn_w, 24, "Confirm", disabled=confirm_disabled)
        if confirm_disabled:
            self.separate_popup_confirm_rect = None
        self.separate_popup_cancel_rect = self._draw_button(sx + pad + btn_w + 8, y, btn_w, 24, "Cancel")

    def _draw_add_job_popup(self):
        city = self.add_job_popup_city
        track_h = 6
        pad = 16
        W = 280
        H = 160
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        track_w = W - pad * 2

        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        title = self.font_header.render("ADD JOB", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (sx + pad, sy + 10))

        # Job type buttons
        y = sy + 34
        type_labels = [('stockpile', 'Stockpile'), ('growth', 'Growth'), ('production', 'Production')]
        btn_w = (track_w - 8) // 3
        self.add_job_popup_type_rects = {}
        for i, (jtype, jlabel) in enumerate(type_labels):
            bx = sx + pad + i * (btn_w + 4)
            already_queued = city.has_job_in_queue(jtype)
            if already_queued and self.add_job_popup_selected_type == jtype:
                self.add_job_popup_selected_type = None
            active = self.add_job_popup_selected_type == jtype
            rect = self._draw_button(bx, y, btn_w, 20, jlabel, active=active, disabled=already_queued)
            if not already_queued:
                self.add_job_popup_type_rects[jtype] = rect
        y += 28

        # Pop count slider
        max_count = city.free_pops
        count = max(0, min(self.add_job_popup_count, max_count))
        self.add_job_popup_count = count

        label = self.font_body.render(f"Pops: {count}", True, TEXT_COLOR)
        self.screen.blit(label, (sx + pad, y))
        y += label.get_height() + 4

        track_y = y
        pygame.draw.rect(self.screen, (60, 60, 80), (sx + pad, track_y, track_w, track_h), border_radius=2)
        hx = sx + pad + (int(count / max_count * track_w) if max_count > 0 else 0)
        hy = track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
        self.screen.blit(self.font_small.render("0", True, PANEL_DIVIDER), (sx + pad, track_y + track_h + 3))
        max_surf = self.font_small.render(str(max_count), True, PANEL_DIVIDER)
        self.screen.blit(max_surf, (sx + pad + track_w - max_surf.get_width(), track_y + track_h + 3))
        self.add_job_popup_slider_rect = pygame.Rect(sx + pad, track_y - 6, track_w, track_h + 16)
        y += track_h + 24

        btn_w2 = (track_w - 8) // 2
        confirm_disabled = self.add_job_popup_selected_type is None or count == 0
        self.add_job_popup_confirm_rect = self._draw_button(sx + pad, y, btn_w2, 24, "Confirm", disabled=confirm_disabled)
        if confirm_disabled:
            self.add_job_popup_confirm_rect = None
        self.add_job_popup_cancel_rect = self._draw_button(sx + pad + btn_w2 + 8, y, btn_w2, 24, "Cancel")

    def _draw_los_panel(self, los, factions):
        sw = self.map_w + PANEL_WIDTH
        y = self.bottom_panel_y
        h = BOTTOM_PANEL_HEIGHT
        pygame.draw.rect(self.screen, PANEL_BG, (0, y, sw, h))
        pygame.draw.line(self.screen, PANEL_DIVIDER, (0, y), (sw, y))

        self.los_button_rects.clear()
        btn_h = h - 10
        btn_y = y + 5
        pad = 10
        gap = 6

        lbl = self.font_body.render("LoS:", True, TEXT_COLOR)
        entries = [('All', 'all', None), ('None', 'none', None)]
        for fname, faction in factions.items():
            entries.append((fname, fname, faction))

        text_surfs = [self.font_body.render(label, True, BUTTON_TEXT) for label, _, _ in entries]
        btn_widths = [s.get_width() + 2 * pad for s in text_surfs]

        total_w = lbl.get_width() + 10 + sum(btn_widths) + gap * (len(btn_widths) - 1)
        x = (sw - total_w) // 2

        self.screen.blit(lbl, (x, y + (h - lbl.get_height()) // 2))
        x += lbl.get_width() + 10

        for (label, key, faction), text_surf, btn_w in zip(entries, text_surfs, btn_widths):
            if los is None:
                is_active = (key == 'all')
            elif key == 'all':
                is_active = los.mode == 'all'
            elif key == 'none':
                is_active = los.mode == 'none'
            else:
                is_active = los.mode == 'faction' and los.faction is faction

            if faction:
                base = faction.colors['dark']
                color = base if is_active else tuple(max(0, int(v * 0.55)) for v in base)
            else:
                color = BUTTON_ACTIVE if is_active else BUTTON_NORMAL

            rect = pygame.Rect(x, btn_y, btn_w, btn_h)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            self.screen.blit(text_surf, (x + pad, btn_y + (btn_h - text_surf.get_height()) // 2))
            self.los_button_rects[key] = rect
            x += btn_w + gap

    def _draw_battle_popup(self, preview):
        import collections
        from src.game.city import City
        from src.game.unit import unit_list as UNIT_DISPLAY_ORDER
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        def unit_type_rows(side_data):
            if isinstance(side_data, City):
                return [('Pop', len(side_data.pops))]
            counts = collections.Counter(u.unit_type for g in side_data for u in g.units)
            return [(t, counts[t]) for t in UNIT_DISPLAY_ORDER if t in counts]

        atk_types = unit_type_rows(preview['attacker_groups'])
        def_types = unit_type_rows(preview['defender'])
        atk_mods = [(lbl, val) for lbl, side, val in preview['modifiers'] if side == 'attacker']
        def_mods = [(lbl, val) for lbl, side, val in preview['modifiers'] if side == 'defender']

        line_h = 18
        type_rows = max(len(atk_types), len(def_types), 1)
        mod_rows  = max(len(atk_mods),  len(def_mods))

        pad = 16
        H = (40                       # title + title divider
             + line_h                 # faction name row
             + type_rows * line_h + 8 # unit type rows
             + 1 + 6                  # section divider
             + (mod_rows * line_h + 8 + 1 + 6 if mod_rows else 0)  # modifier section
             + line_h + 8            # totals
             + 1 + 8                  # button divider
             + 24 + pad)             # buttons + bottom pad
        W = 340
        sx = (self.screen.get_width()  - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER,  (sx, sy, W, H), 1, border_radius=6)

        title = self.font_header.render("BATTLE", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (sx + W // 2 - title.get_width() // 2, sy + 10))

        title_div_y = sy + 30
        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, title_div_y), (sx + W - pad, title_div_y))

        col_w   = (W - pad * 2) // 2
        left_x  = sx + pad
        right_x = sx + pad + col_w
        mid_x   = sx + W // 2
        y = title_div_y + 8

        def faction_name(data):
            if isinstance(data, City):
                return data.faction.name if data.faction else data.name
            return data[0].faction.name if data and data[0].faction else '—'

        # Faction name headers
        for x, data in [(left_x, preview['attacker_groups']), (right_x, preview['defender'])]:
            surf = self.font_header.render(faction_name(data), True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
        y += line_h

        # Unit type rows
        content_top_y = y
        for i in range(type_rows):
            if i < len(atk_types):
                t, n = atk_types[i]
                self.screen.blit(self.font_body.render(f"{n} {t}", True, TEXT_COLOR), (left_x, y))
            if i < len(def_types):
                t, n = def_types[i]
                self.screen.blit(self.font_body.render(f"{n} {t}", True, TEXT_COLOR), (right_x, y))
            y += line_h
        y += 8

        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 6

        # Modifier rows (per side)
        if mod_rows:
            mod_top_y = y
            for i in range(mod_rows):
                for col_x, mods in [(left_x, atk_mods), (right_x, def_mods)]:
                    if i < len(mods):
                        lbl, val = mods[i]
                        sign = '+' if val >= 0 else ''
                        color = (180, 200, 160) if val > 0 else (200, 160, 160)
                        self.screen.blit(self.font_body.render(f"{lbl}: {sign}{int(val * 100)}%", True, color), (col_x, y))
                y += line_h
            y += 8
            pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
            y += 6

        content_bot_y = y

        # Vertical divider spanning unit + modifier sections
        pygame.draw.line(self.screen, PANEL_DIVIDER, (mid_x, content_top_y), (mid_x, content_bot_y))

        # Summed combat strength
        at_surf = self.font_body.render(f"Strength: {preview['attacker_total']:.0f}", True, TEXT_COLOR)
        dt_surf = self.font_body.render(f"Strength: {preview['defender_total']:.0f}", True, TEXT_COLOR)
        self.screen.blit(at_surf, (left_x, y))
        self.screen.blit(dt_surf, (right_x, y))
        y += line_h + 8

        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 8

        btn_w = (W - pad * 2 - 8) // 2
        self.battle_popup_confirm_rect = self._draw_button(sx + pad, y, btn_w, 24, "Attack")
        self.battle_popup_cancel_rect  = self._draw_button(sx + pad + btn_w + 8, y, btn_w, 24, "Cancel")

    def _draw_battle_result_popup(self, result, preview):
        from src.game.city import City
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        rounds  = result.get('rounds', [])
        stat_rows = 4  # units, strength, advantage, lambda per round
        line_h = 18
        pad = 16
        per_round_h = line_h + stat_rows * line_h + 2 * line_h + 8 + 1 + 6  # label + stats + 2 log lines + gap + divider
        H = (40                                                          # title + divider
             + line_h                                                    # faction headers
             + (len(rounds) * per_round_h if DISPLAY_FULL_BATTLE else 0) # per-round blocks (full mode only)
             + 1 + 6                                                     # divider before losses
             + line_h + 8                                                # losses
             + 1 + 8                                                     # button divider
             + 24 + pad)                                                 # close button + bottom pad
        W = 380
        sx = (self.screen.get_width()  - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER,  (sx, sy, W, H), 1, border_radius=6)

        title = self.font_header.render("BATTLE RESULT", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (sx + W // 2 - title.get_width() // 2, sy + 10))

        title_div_y = sy + 30
        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, title_div_y), (sx + W - pad, title_div_y))

        y = title_div_y + 8

        def faction_name(data):
            if isinstance(data, City):
                return data.faction.name if data.faction else data.name
            return data[0].faction.name if data and data[0].faction else '—'

        col_w   = (W - pad * 2) // 2
        left_x  = sx + pad
        right_x = sx + pad + col_w
        mid_x   = sx + W // 2

        # Faction headers
        for x, data in [(left_x, preview['attacker_groups']), (right_x, preview['defender'])]:
            self.screen.blit(self.font_header.render(faction_name(data), True, HEADER_TEXT_COLOR), (x, y))
        y += line_h

        stat_color = (200, 200, 220)
        log_color  = (180, 180, 200)

        if DISPLAY_FULL_BATTLE:
            for round_i, rnd in enumerate(rounds):
                round_top_y = y

                # Round label (left-aligned)
                lbl = self.font_body.render(f"Round {round_i + 1}", True, HEADER_TEXT_COLOR)
                self.screen.blit(lbl, (left_x, y))
                y += line_h

                # Stats in two columns
                for side, col_x in [('attacker', left_x), ('defender', right_x)]:
                    s = rnd.get(side, {})
                    for row_i, (label, val) in enumerate([
                        ('Units',     f"{s.get('units', '—')}"),
                        ('Strength',  f"{s.get('strength', '—')}"),
                        ('Advantage', f"{s.get('advantage', 0):.2f}"),
                        ('λ',         f"{s.get('lam', 0):.2f}"),
                    ]):
                        self.screen.blit(
                            self.font_body.render(f"{label}: {val}", True, stat_color),
                            (col_x, y + row_i * line_h)
                        )
                y += stat_rows * line_h

                # Round log
                for line in rnd.get('log', []):
                    self.screen.blit(self.font_body.render(line, True, log_color), (sx + pad, y))
                    y += line_h
                y += 8

                pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
                y += 6

        # Losses
        self.screen.blit(self.font_body.render(f"Losses: {result['attacker_losses']}", True, TEXT_COLOR), (left_x, y))
        self.screen.blit(self.font_body.render(f"Losses: {result['defender_losses']}", True, TEXT_COLOR), (right_x, y))
        y += line_h + 8

        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 8

        self.battle_result_close_rect = self._draw_button(sx + pad, y, W - pad * 2, 24, "Close")

    def _draw_save_popup(self, text):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        W, H = 300, 115
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("SAVE MAP", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + 16, sy + 14))

        input_rect = pygame.Rect(sx + 16, sy + 42, W - 32, 26)
        pygame.draw.rect(self.screen, (25, 25, 35), input_rect, border_radius=3)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, input_rect, 1, border_radius=3)
        surf = self.font_body.render(text + "|", True, TEXT_COLOR)
        self.screen.blit(surf, (input_rect.x + 6, input_rect.y + (input_rect.height - surf.get_height()) // 2))

        surf = self.font_body.render("Enter to save  •  Esc to cancel", True, (110, 110, 130))
        self.screen.blit(surf, (sx + 16, sy + 85))

    def _draw_terrain_popup(self, selected_tile):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        row_h = 28
        swatch = 12
        W = 260
        pad = 16
        btn_w = W - pad * 2

        n_biome_rows = len(BIOMES)
        n_feat_rows = len([f for f in TERRAIN_FEATURES if f not in _NON_SELECTABLE_FEATURES])
        confirm_h = 28
        H = (pad + 18 + 6                        # title
             + 16 + 4                            # biome subheader
             + n_biome_rows * row_h              # biome buttons
             + 12 + 16 + 4                       # features subheader gap
             + n_feat_rows * row_h               # feature buttons
             + 12 + confirm_h + pad)             # confirm/cancel + bottom padding
        sx = (self.screen.get_width() - W) // 2
        sy = max(8, (self.screen.get_height() - H) // 2)
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        y = sy + pad
        surf = self.font_header.render("CHANGE TERRAIN", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + pad, y))
        y += surf.get_height() + 6

        # Biome section
        sub = self.font_header.render("BIOME", True, (130, 150, 180))
        self.screen.blit(sub, (sx + pad, y))
        y += sub.get_height() + 4

        for biome in BIOMES:
            is_current = selected_tile and selected_tile.biome == biome
            rect = self._draw_button(sx + pad, y, btn_w, row_h - 2, "", active=is_current)
            color = BIOME_COLORS.get(biome, BUTTON_NORMAL)
            pygame.draw.rect(self.screen, color,
                             (rect.x + 8, rect.y + (rect.height - swatch) // 2, swatch, swatch),
                             border_radius=2)
            label = self.font_body.render(biome.capitalize(), True, BUTTON_TEXT)
            self.screen.blit(label, (rect.x + 8 + swatch + 8, rect.y + (rect.height - label.get_height()) // 2))
            self.biome_option_rects[biome] = rect
            y += row_h

        # Features section
        y += 12
        sub = self.font_header.render("FEATURES", True, (130, 150, 180))
        self.screen.blit(sub, (sx + pad, y))
        y += sub.get_height() + 4

        current_features = selected_tile.terrain_features if selected_tile else []
        selectable_features = [f for f in TERRAIN_FEATURES if f not in _NON_SELECTABLE_FEATURES]
        for feature in selectable_features:
            is_active = feature in current_features
            rect = self._draw_button(sx + pad, y, btn_w, row_h - 2, "", active=is_active)
            label = self.font_body.render(feature.capitalize(), True, BUTTON_TEXT)
            self.screen.blit(label, (rect.x + 8, rect.y + (rect.height - label.get_height()) // 2))
            self.feature_option_rects[feature] = rect
            y += row_h

        y += 12
        half_w = (btn_w - 6) // 2
        self.terrain_confirm_rect = self._draw_button(sx + pad, y, half_w, confirm_h, "Confirm", active=True)
        self.terrain_cancel_rect  = self._draw_button(sx + pad + half_w + 6, y, half_w, confirm_h, "Cancel")

    def _draw_river_popup(self, selected_tile):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        btn_w, btn_h = 74, 28
        col_gap, row_gap = 8, 6
        grid_w = btn_w * 2 + col_gap
        grid_rows = len(RIVER_DIR_GRID)
        grid_h = grid_rows * btn_h + (grid_rows - 1) * row_gap

        W = grid_w + 32
        H = 38 + grid_h + 28
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("DRAW RIVER", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + 16, sy + 12))

        gx = sx + (W - grid_w) // 2
        gy = sy + 38
        for row_idx, directions in enumerate(RIVER_DIR_GRID):
            by = gy + row_idx * (btn_h + row_gap)
            if len(directions) == 1:
                bx = gx + (btn_w + col_gap) // 2
                direction = directions[0]
                is_active = selected_tile and direction in selected_tile.river_edges
                rect = self._draw_button(bx, by, btn_w, btn_h, direction, active=is_active)
                self.river_option_rects[direction] = rect
            else:
                for col_idx, direction in enumerate(directions):
                    bx = gx + col_idx * (btn_w + col_gap)
                    is_active = selected_tile and direction in selected_tile.river_edges
                    rect = self._draw_button(bx, by, btn_w, btn_h, direction, active=is_active)
                    self.river_option_rects[direction] = rect

        hint = self.font_body.render("Esc to cancel", True, (110, 110, 130))
        self.screen.blit(hint, (sx + 16, sy + H - 18))
