import collections
import math
import os
import pygame
from src.game.city import STOCKPILE_MAX
from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY, MILITARY_CARRY_CAPACITY, WATER_CARRY_CAPACITY, MOVE_CARRY_OVER
from src.game.map import TERRAIN_TYPES

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets')

HEX_SIZE = 32
MARGIN = 40
PANEL_WIDTH = 220

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

# Angle (radians) from hex center to each edge midpoint, for pointy-top hexes.
RIVER_DIR_ANGLES = {
    'NE': math.radians(-60),
    'E':  math.radians(0),
    'SE': math.radians(60),
    'SW': math.radians(120),
    'W':  math.radians(180),
    'NW': math.radians(240),
}
RIVER_DIR_GRID = [('NW', 'NE'), ('W', 'E'), ('SW', 'SE')]

# Neighbor offsets per row parity (matches map.py _NEIGHBORS)
_RENDER_NEIGHBORS = {
    0: [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)],
    1: [(-1,  0), (-1, 1), (0, -1), (0, 1), (1,  0), (1, 1)],
}
# Corner index pairs for each neighbor direction (same for both parities)
# Corners: 0=top-right, 1=bottom-right, 2=bottom, 3=bottom-left, 4=top-left, 5=top
_NEIGHBOR_EDGE_CORNERS = [(4, 5), (5, 0), (3, 4), (0, 1), (2, 3), (1, 2)]

# Edge angle (degrees) toward each neighbor, keyed by row parity then (dr, dc)
# Order matches _RENDER_NEIGHBORS: NW, NE, W, E, SW, SE
_NEIGHBOR_EDGE_ANGLES = {
    0: {(-1, -1): 240, (-1,  0): -60, (0, -1): 180, (0, 1): 0, (1, -1): 120, (1, 0): 60},
    1: {(-1,  0): 240, (-1,  1): -60, (0, -1): 180, (0, 1): 0, (1,  0): 120, (1, 1): 60},
}

# Maps terrain name → image filename stem when they differ
_TERRAIN_IMG_FILES = {
    'mountain': 'mountains',
}

ICON_SIZE      = 40
ICON_OFFSET    = 10
RIVER_IMG_SCALE = 1.2  # bleed past tile edge so adjacent river images connect
ISO_SCALE      = 1  # vertical compression for isometric perspective
LOG_PANEL_WIDTH = 0
CITY_PANEL_WIDTH = 220


class Renderer:
    def __init__(self, game_map):
        self.map = game_map
        w = math.sqrt(3) * HEX_SIZE
        map_area_w = int(game_map.cols * w + w / 2 + 2 * MARGIN)
        self.map_w = CITY_PANEL_WIDTH + map_area_w
        self.map_start_x = CITY_PANEL_WIDTH
        screen_h = int((game_map.rows - 1) * HEX_SIZE * 1.5 + 2 * HEX_SIZE + 2 * MARGIN)
        self.offset_x = CITY_PANEL_WIDTH + MARGIN + w / 2
        self.offset_y = MARGIN + HEX_SIZE
        self.screen = pygame.display.set_mode((self.map_w + PANEL_WIDTH, screen_h))
        pygame.display.set_caption("HexGame")
        self.font_header = pygame.font.SysFont('segoeui', 13, bold=True)
        self.font_body = pygame.font.SysFont('segoeui', 13)
        self.font_small = pygame.font.SysFont('segoeui', 10)
        self.font_city = pygame.font.SysFont('tempussansitc', 12, bold=True)
        _font_cinzel        = os.path.join(_ASSETS_DIR, 'fonts', 'Cinzel', 'static', 'Cinzel-Bold.ttf')
        _font_almendra      = os.path.join(_ASSETS_DIR, 'fonts', 'Almendra', 'Almendra-Bold.ttf')
        _font_caesar        = os.path.join(_ASSETS_DIR, 'fonts', 'Caesar_Dressing', 'CaesarDressing-Regular.ttf')
        _font_glass_antiqua = os.path.join(_ASSETS_DIR, 'fonts', 'Glass_Antiqua', 'GlassAntiqua-Regular.ttf')
        self.font_pop = pygame.font.Font(_font_cinzel, 13)
        hex_w = int(math.sqrt(3) * HEX_SIZE)
        hex_h = 2 * HEX_SIZE
        self._terrain_images_raw = {}
        terrain_dir = os.path.join(_ASSETS_DIR, 'terrain')
        for name in TERRAIN_TYPES:
            img_file = _TERRAIN_IMG_FILES.get(name, name)
            raw_variants = []
            for i in range(1, 5):
                path = os.path.join(terrain_dir, f'{img_file}{i}.png')
                if os.path.exists(path):
                    raw_variants.append(pygame.image.load(path).convert_alpha())
            if raw_variants:
                self._terrain_images_raw[name] = raw_variants
        self._icons_raw = {}
        icons_dir = os.path.join(_ASSETS_DIR, 'icons')
        for icon_name, file_name in (('castle', 'city'), ('sword', 'gladius'), ('flag', 'flag'), ('torch', 'restriction')):
            path = os.path.join(icons_dir, f'{file_name}.png')
            if os.path.exists(path):
                self._icons_raw[icon_name] = pygame.image.load(path).convert_alpha()
        self._river_imgs_raw = []
        for img_file, entries in (
            ('sw2ne_2',   [(frozenset({'W',  'E'}),  -35, (0, 0)),
                       (frozenset({'NW', 'SE'}),   -95, (0, 0)),
                       (frozenset({'NE', 'SW'}),  25,  (0, 0))]),
            ('nw2s',  [(frozenset({'NW', 'SW'}),  -32,  (0, 0)),
                       (frozenset({'NE', 'W'}),   -90, (-5, -3)),
                       (frozenset({'NW', 'E'}),   -150, (0, 0))]),
            ('ne2s',  [(frozenset({'E',  'SW'}),  -35,  (-5, 0)),
                       (frozenset({'SE', 'W'}),   -90,  (0, 0)),
                       (frozenset({'NE', 'SE'}),  30,   (0, 0))]),
        ):
            path = os.path.join(_ASSETS_DIR, 'rivers', f'{img_file}.png')
            if os.path.exists(path):
                self._river_imgs_raw.append((pygame.image.load(path).convert_alpha(), entries))
        self.zoom = 1.2
        self.terrain_images = {}
        self.river_imgs = {}
        self.icons = {}
        self.icons_tinted = {}
        self.icons_dark = {}
        self.icons_light = {}
        self.icons_selected = {}
        self._faction_castle_icons = {}
        self._faction_sword_icons = {}
        self._faction_flag_icons = {}
        self._faction_torch_icons = {}
        self._apply_zoom()
        self.move_button_rect = None
        self.capture_button_rect = None
        self.raid_button_rect = None
        self.end_turn_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.rebalance_pops_button_rect = None
        self.restrict_tile_button_rect = None
        self.halt_growth_rect = None
        self.gates_closed_rect = None
        self.admin_minus_rect = None
        self.admin_plus_rect = None
        self.city_focus_rects = {}
        self.trade_route_delete_rects = []
        self.trade_route_reduce_rects = []
        self.adding_trade_route = False
        self.adding_one_way_route = False
        self.add_one_way_route_button_rect = None
        self.one_way_route_pending = None
        self.one_way_route_type = 'land'
        self.one_way_route_type_rects = {}
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
        self.trade_route_max_export = 0.0
        self.trade_route_max_import = 0.0
        self.terrain_option_rects = {}
        self.river_option_rects = {}
        self.selected_unit_groups = set()
        self.group_icon_rects = []
        self.select_all_button_rect = None
        self.unselect_all_button_rect = None
        self.merge_button_rect = None
        self.separate_button_rect = None
        self.restock_all_button_rect = None
        self.drop_all_button_rect = None
        self.restock_button_rect = None
        self.drop_button_rect = None
        self.recruit_unit_button_rect = None
        self.disband_button_rect = None
        self.recruit_popup_active = False
        self.recruit_popup_amount = 1
        self.recruit_popup_food = 0
        self.recruit_popup_slider_rect = None
        self.recruit_popup_food_slider_rect = None
        self.recruit_popup_confirm_rect = None
        self.recruit_popup_cancel_rect = None
        self.battle_popup_confirm_rect = None
        self.battle_popup_cancel_rect = None
        self._recruit_slider_dragging = False
        self._recruit_food_slider_dragging = False

    def _make_icon_pair(self, scaled, light_rgb, dark_rgb, outline_radius, pad=0):
        """Returns (tinted, dark_surf): tinted=light fill+dark outline, dark=dark fill+light outline.
        pad expands the output surface so the outline doesn't clip at edges."""
        mask = scaled.copy()
        mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        lb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        lb.fill((*light_rgb, 255))
        lb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        db = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        db.fill((*dark_rgb, 255))
        db.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        w, h = scaled.get_width() + 2 * pad, scaled.get_height() + 2 * pad
        result = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_radius, outline_radius + 1):
            for dy in range(-outline_radius, outline_radius + 1):
                if dx * dx + dy * dy <= outline_radius * 2:
                    result.blit(db, (pad + dx, pad + dy))
        result.blit(lb, (pad, pad))
        dark_result = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_radius, outline_radius + 1):
            for dy in range(-outline_radius, outline_radius + 1):
                if dx * dx + dy * dy <= outline_radius * 2:
                    dark_result.blit(lb, (pad + dx, pad + dy))
        dark_result.blit(db, (pad, pad))
        return result, dark_result

    def _apply_zoom(self):
        sz = HEX_SIZE * self.zoom
        hex_w = int(math.sqrt(3) * sz)
        hex_h = int(2 * sz * ISO_SCALE)
        self.terrain_images = {
            name: [pygame.transform.scale(v, (hex_w, hex_h)) for v in variants]
            for name, variants in self._terrain_images_raw.items()
        }
        self.river_imgs = {}
        for raw, entries in self._river_imgs_raw:
            base = pygame.transform.scale(
                raw, (int(hex_w * RIVER_IMG_SCALE), int(hex_h * RIVER_IMG_SCALE))
            )
            for key, angle, offset in entries:
                rotated = pygame.transform.rotate(base, angle)
                mask = rotated.copy()
                mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                tinted = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
                tinted.fill(COLOR_RIVER_LINE + (255,))
                tinted.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                dark_blue = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
                dark_blue.fill(COLOR_RIVER_DARK + (255,))
                dark_blue.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                black = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
                black.fill((0, 0, 0, 220))
                black.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                size = rotated.get_size()
                outline = pygame.Surface(size, pygame.SRCALPHA)
                for dx in range(-5, 6):
                    for dy in range(-5, 6):
                        if (dx, dy) != (0, 0) and dx*dx + dy*dy <= 25:
                            outline.blit(black, (dx, dy))
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if (dx, dy) != (0, 0) and dx*dx + dy*dy <= 9:
                            outline.blit(dark_blue, (dx, dy))
                outlined = pygame.Surface(size, pygame.SRCALPHA)
                outlined.blit(outline, (0, 0))
                outlined.blit(tinted, (0, 0))
                self.river_imgs[key] = (outlined, offset)
        self._hex_clip_offsets = [
            (sz * math.cos(math.radians(60 * i - 30)),
             sz * math.sin(math.radians(60 * i - 30)) * ISO_SCALE)
            for i in range(6)
        ]
        castle_size = int(ICON_SIZE * 1.2 * self.zoom)
        sword_size = int(ICON_SIZE * 0.4 * self.zoom)
        self.icons = {}
        self.icons_tinted = {}
        if 'castle' in self._icons_raw:
            scaled = pygame.transform.scale(self._icons_raw['castle'], (castle_size, castle_size))
            self.icons['castle'] = scaled
            castle_outline_radius = 8
            tinted, dark_surf = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), castle_outline_radius)
            self.icons_tinted['castle'] = tinted
            self.icons_dark['castle'] = dark_surf
            self._faction_castle_icons = {}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_castle_icons:
                    t, d = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), castle_outline_radius)
                    self._faction_castle_icons[city.faction.name] = {'tinted': t, 'dark': d}
        if 'sword' in self._icons_raw:
            scaled = pygame.transform.scale(self._icons_raw['sword'], (sword_size, sword_size))
            self.icons['sword'] = scaled
            sword_outline_radius = 5
            tinted, dark_surf = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), sword_outline_radius, pad=sword_outline_radius)
            self.icons_tinted['sword'] = tinted
            self.icons_dark['sword'] = dark_surf
            self.icons_selected['sword'] = dark_surf
            mask = scaled.copy()
            mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
            lb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            lb.fill((180, 210, 255, 255))
            lb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.icons_light['sword'] = lb
            self._faction_sword_icons = {}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_sword_icons:
                    t, d = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), sword_outline_radius, pad=sword_outline_radius)
                    self._faction_sword_icons[city.faction.name] = {'tinted': t, 'dark': d}
        if 'flag' in self._icons_raw:
            flag_size = int(ICON_SIZE * 0.4 * self.zoom)
            flag_outline_radius = 6
            scaled = pygame.transform.scale(self._icons_raw['flag'], (flag_size, flag_size))
            self.icons['flag'] = scaled
            mask = scaled.copy()
            mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
            lb = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            lb.fill((180, 210, 255, 255))
            lb.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            db = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            db.fill((35, 65, 150, 255))
            db.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            result = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            for dx in range(-flag_outline_radius, flag_outline_radius + 1):
                for dy in range(-flag_outline_radius, flag_outline_radius + 1):
                    if dx * dx + dy * dy <= flag_outline_radius * 2:
                        result.blit(db, (dx, dy))
            result.blit(lb, (0, 0))
            self.icons_tinted['flag'] = result
            dark_result = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            for dx in range(-flag_outline_radius, flag_outline_radius + 1):
                for dy in range(-flag_outline_radius, flag_outline_radius + 1):
                    if dx * dx + dy * dy <= flag_outline_radius * 2:
                        dark_result.blit(lb, (dx, dy))
            dark_result.blit(db, (0, 0))
            self.icons_dark['flag'] = dark_result
            self._faction_flag_icons = {}
        if 'torch' in self._icons_raw:
            torch_size = int(HEX_SIZE * self.zoom * 0.5)
            scaled_torch = pygame.transform.scale(self._icons_raw['torch'], (torch_size, torch_size))
            outline_r = 5
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
                    t, d = self._make_icon_pair(scaled_torch, city.get_city_color('light'), city.get_city_color('dark'), outline_r, pad=outline_r)
                    self._faction_torch_icons[city.faction.name] = {'tinted': t, 'dark': d}
            for city in self.map.cities.values():
                if city.faction and city.faction.name not in self._faction_flag_icons:
                    t, d = self._make_icon_pair(scaled, city.get_city_color('light'), city.get_city_color('dark'), flag_outline_radius)
                    self._faction_flag_icons[city.faction.name] = {'tinted': t, 'dark': d}

    def zoom_map(self, factor, mx, my):
        old_zoom = self.zoom
        new_zoom = max(0.4, min(3.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return
        self.offset_x = mx + (self.offset_x - mx) * new_zoom / old_zoom
        self.offset_y = my + (self.offset_y - my) * new_zoom / old_zoom
        self.zoom = new_zoom
        self._apply_zoom()

    def _hex_to_pixel(self, row, col):
        sz = HEX_SIZE * self.zoom
        w = math.sqrt(3) * sz
        x = col * w + (w / 2 if row % 2 == 1 else 0)
        y = row * sz * 1.5 * ISO_SCALE
        return x, y

    def _hex_corners(self, cx, cy):
        sz = HEX_SIZE * self.zoom
        corners = []
        for i in range(6):
            angle_rad = math.radians(60 * i - 30)
            corners.append((cx + sz * math.cos(angle_rad), cy + sz * math.sin(angle_rad) * ISO_SCALE))
        return corners

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
        sz = HEX_SIZE * self.zoom
        x = px - self.offset_x
        y = (py - self.offset_y) / ISO_SCALE
        q = (x * math.sqrt(3) / 3 - y / 3) / sz
        r = (y * 2 / 3) / sz
        rx, ry, rz = round(q), round(-q - r), round(r)
        x_diff = abs(rx - q)
        y_diff = abs(ry - (-q - r))
        z_diff = abs(rz - r)
        if x_diff > y_diff and x_diff > z_diff:
            rx = -ry - rz
        elif y_diff > z_diff:
            ry = -rx - rz
        else:
            rz = -rx - ry
        col = rx + (rz - (rz & 1)) // 2
        row = rz
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
            proj = min(city.growth_progress + city.growth_allocated, 100)
            proj_w = max(int(bar_w * proj / 100), 0)
            if proj_w > 0:
                pygame.draw.rect(self.screen, (120, 210, 200), (bx, by, proj_w, bar_h), border_radius=border_radius)
            fill_w = max(int(bar_w * min(city.growth_progress, 100) / 100), 0)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (40, 160, 150), (bx, by, fill_w, bar_h), border_radius=border_radius)
        elif bar_type == 'construction':
            fill_w = max(int(bar_w * min(city.construction_progress, 1000) / 1000), 0)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (130, 130, 140), (bx, by, fill_w, bar_h), border_radius=border_radius)

    def draw(self, selected_tile=None, reachable=None, move_mode=False,
             save_popup_active=False, save_popup_text="",
             terrain_popup_active=False, river_popup_active=False,
             moves_remaining=None, game_log=None,
             move_hover_tile=None,
             console_active=False, console_input="",
             battle_popup_active=False, battle_popup_preview=None):
        if reachable is None:
            reachable = {}
        self.screen.fill(BG_COLOR)

        all_corners = {}
        all_centers = {}
        apothem = HEX_SIZE * self.zoom * math.sqrt(3) / 2

        # Pass 1: hex fills
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                px, py = self._hex_to_pixel(r, c)
                cx, cy = px + self.offset_x, py + self.offset_y
                corners = self._hex_corners(cx, cy)
                all_corners[(r, c)] = corners
                all_centers[(r, c)] = (cx, cy)
                dark_color = TERRAIN_COLORS_DARK.get(tile.terrain, BG_COLOR)
                pygame.draw.polygon(self.screen, dark_color, corners)
                inner = [(cx + 1.0 * (px - cx), cy + 1.0 * (py - cy)) for px, py in corners]
                pygame.draw.polygon(self.screen, TERRAIN_COLORS.get(tile.terrain, BG_COLOR), inner)

        # Pass 1b: terrain images over fills
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                variants = self.terrain_images.get(self.map.tiles[r][c].terrain)
                if variants:
                    img = variants[(r * 7 + c * 13) % len(variants)]
                    cx, cy = all_centers[(r, c)]
                    self.screen.blit(img, (int(cx) - img.get_width() // 2, int(cy) - img.get_height() // 2))

        # Pass 2: river images (straight) / lines (bends) on top of fills
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                if not tile.river_edges:
                    continue
                cx, cy = all_centers[(r, c)]
                result = self.river_imgs.get(frozenset(tile.river_edges))
                if result:
                    straight_img, (ox, oy) = result
                    iw, ih = straight_img.get_size()
                    hcx = iw // 2 - ox
                    hcy = ih // 2 - oy
                    hex_pts = [(hcx + dx, hcy + dy) for dx, dy in self._hex_clip_offsets]
                    clipped = straight_img.copy()
                    hex_clip = pygame.Surface((iw, ih), pygame.SRCALPHA)
                    hex_clip.fill((0, 0, 0, 0))
                    pygame.draw.polygon(hex_clip, (255, 255, 255, 255), hex_pts)
                    clipped.blit(hex_clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    self.screen.blit(clipped,
                                     (int(cx) - iw // 2 + ox,
                                      int(cy) - ih // 2 + oy))
                else:
                    for direction in tile.river_edges:
                        angle = RIVER_DIR_ANGLES[direction]
                        ex = cx + apothem * math.cos(angle)
                        ey = cy + apothem * math.sin(angle)
                        pygame.draw.line(self.screen, COLOR_RIVER_LINE,
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
                    deg = _NEIGHBOR_EDGE_ANGLES[r % 2].get((nr - r, nc - c))
                    if deg is None or (r, c) not in all_centers:
                        return None, None
                    cx, cy = all_centers[(r, c)]
                    return (cx + apothem * math.cos(math.radians(deg)),
                            cy + apothem * math.sin(math.radians(deg))), (cx, cy)

                _ROUTE_DARK = route.faction.colors['dark'] if route.faction else (35, 65, 150)
                _ROUTE_LIGHT = route.faction.colors['light'] if route.faction else (180, 210, 255)
                _ROUTE_OUTLINE_W = 5
                _ROUTE_INNER_W = 3
                destination = route.path[-1]

                # Start city: center → edge toward path[1]
                ep, center = _edge_pt(path[0][0], path[0][1], path[1][0], path[1][1])
                if ep and center:
                    self._draw_dashed_line(center, ep, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_line(center, ep, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)

                # Intermediate tiles
                for i in range(1, len(path) - 1):
                    r, c = path[i]
                    pr, pc = path[i - 1]
                    nr, nc = path[i + 1]
                    if (r, c) not in all_centers:
                        continue
                    cx, cy = all_centers[(r, c)]
                    from_deg = _NEIGHBOR_EDGE_ANGLES[r % 2].get((pr - r, pc - c))
                    to_deg   = _NEIGHBOR_EDGE_ANGLES[r % 2].get((nr - r, nc - c))
                    if from_deg is None or to_deg is None:
                        continue
                    from_pt = (cx + apothem * math.cos(math.radians(from_deg)),
                               cy + apothem * math.sin(math.radians(from_deg)))
                    to_pt   = (cx + apothem * math.cos(math.radians(to_deg)),
                               cy + apothem * math.sin(math.radians(to_deg)))
                    self._draw_dashed_curve(from_pt, (cx, cy), to_pt, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_curve(from_pt, (cx, cy), to_pt, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)

                # End city: edge toward path[-2] → center (only when destination reached)
                ep, center = _edge_pt(path[-1][0], path[-1][1], path[-2][0], path[-2][1])
                if ep and center:
                    self._draw_dashed_line(ep, center, _ROUTE_DARK,  width=_ROUTE_OUTLINE_W, dash_length=8, gap=6)
                    self._draw_dashed_line(ep, center, _ROUTE_LIGHT, width=_ROUTE_INNER_W,   dash_length=8, gap=6)
                    self._draw_arrowhead(center, ep, _ROUTE_LIGHT, size=8)

        # Pass 3b: city territory borders
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                if tile.owning_city is None:
                    continue
                cx, cy = all_centers[(r, c)]
                corners = all_corners[(r, c)]
                border_lines = []
                for i, (dr, dc) in enumerate(_RENDER_NEIGHBORS[r % 2]):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.map.rows and 0 <= nc < self.map.cols):
                        neighbor_city = None
                    else:
                        neighbor_city = self.map.tiles[nr][nc].owning_city
                    if neighbor_city is not tile.owning_city:
                        ci, cj = _NEIGHBOR_EDGE_CORNERS[i]
                        border_lines.append((corners[ci], corners[cj]))
                if not border_lines:
                    continue
                sz = HEX_SIZE * self.zoom
                border_line_w = 8
                outline_radius = 4
                pad = outline_radius + border_line_w
                surf_w = int(math.sqrt(3) * sz) + pad * 2
                surf_h = int(2 * sz * ISO_SCALE) + pad * 2
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
                hex_pts = [(scx + dx, scy + dy) for dx, dy in self._hex_clip_offsets]
                clip_mask = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
                pygame.draw.polygon(clip_mask, (255, 255, 255, 255), hex_pts)
                result.blit(clip_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                self.screen.blit(result, (int(cx) - scx, int(cy) - scy))

        # Pass 4: movement range borders
        if move_mode and selected_tile:
            in_range = set(reachable.keys())
            in_range.add((selected_tile.row, selected_tile.col))
            sz = HEX_SIZE * self.zoom
            border_line_w = 4
            outline_radius = 2
            pad = outline_radius + border_line_w + 1
            surf_w = int(math.sqrt(3) * sz) + pad * 2
            surf_h = int(2 * sz * ISO_SCALE) + pad * 2
            scx = surf_w // 2
            scy = surf_h // 2
            for (r, c) in in_range:
                if (r, c) not in all_corners:
                    continue
                cx, cy = all_centers[(r, c)]
                corners = all_corners[(r, c)]
                border_lines = []
                for i, (dr, dc) in enumerate(_RENDER_NEIGHBORS[r % 2]):
                    nr, nc = r + dr, c + dc
                    if (nr, nc) not in in_range:
                        ci, cj = _NEIGHBOR_EDGE_CORNERS[i]
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
        dot_start_y_offset = int(HEX_SIZE * self.zoom * ISO_SCALE * 0.4)
        dot_positions = []  # (ddx, ddy, owning_city)
        torch_icon = self.icons.get('torch')
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                cx, cy = all_centers[(r, c)]
                dx = int(cx) - dot_offset_x
                dy = int(cy) - dot_start_y_offset
                if tile.is_disrupted and torch_icon:
                    faction = tile.owning_city.faction if tile.owning_city else None
                    faction_torch = self._faction_torch_icons.get(faction.name, {}).get('tinted') if faction else None
                    self.screen.blit(faction_torch or torch_icon, (dx - int(apothem * 0.4), dy - int(apothem * 0.3)))
                    continue
                if tile.worked_farms <= 0:
                    continue
                for i in range(tile.worked_farms):
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
            cx, cy = all_centers[(r, c)]
            fname = city.faction.name if city.faction else None
            faction_icons = self._faction_castle_icons.get(fname)
            if faction_icons:
                icon = faction_icons['tinted'] if (r, c) == selected_city_pos else faction_icons['dark']
            else:
                icon = self.icons_tinted.get('castle') if (r, c) == selected_city_pos else self.icons_dark.get('castle')
            if icon:
                ix = int(cx) - icon.get_width() // 2 + 2
                iy = int(cy) - HEX_SIZE - 3.5
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
                        if key not in seen_dest_tiles and key in all_centers:
                            seen_dest_tiles.add(key)
                            is_selected = selected_tile is not None and (selected_tile.row, selected_tile.col) == key
                            faction_name = route.faction.name if route.faction else None
                            faction_flag = self._faction_flag_icons.get(faction_name) if faction_name else None
                            if faction_flag:
                                flag_icon = faction_flag['tinted'] if is_selected else faction_flag['dark']
                            else:
                                flag_icon = self.icons_tinted.get('flag') if is_selected else self.icons_dark.get('flag')
                            if flag_icon:
                                cx, cy = all_centers[key]
                                ix = int(cx) - flag_icon.get_width() // 2 - 2
                                iy = int(cy) - flag_icon.get_height() // 2 + 2
                                self.screen.blit(flag_icon, (ix, iy))

        # Pass 7: group markers (drawn over city icons)
        for (r, c) in self.map.unit_groups:
            cx, cy = all_centers[(r, c)]
            unit_groups_here = self.map.unit_groups[(r, c)]
            any_selected = any(g in self.selected_unit_groups for g in unit_groups_here)
            first_faction = unit_groups_here[0].faction
            fname = first_faction.name if first_faction else None
            faction_sword = self._faction_sword_icons.get(fname)
            if faction_sword:
                icon = faction_sword['tinted'] if any_selected else faction_sword['dark']
            else:
                icon = self.icons_tinted.get('sword') if any_selected else self.icons_dark.get('sword')
            if icon:
                total_units = sum(len(g.units) for g in unit_groups_here)
                count = max(1, min(3, total_units))
                icon_overlap = 7
                combined_w = icon.get_width() + (count - 1) * icon_overlap
                start_x = int(cx) - combined_w // 2
                icon_y = int(cy) - icon.get_height() // 2
                for i in range(count):
                    self.screen.blit(icon, (start_x + i * icon_overlap, icon_y))
            else:
                self._draw_unit_marker(int(cx), int(cy))
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
            cx, cy = all_centers[(r, c)]
            name_y = city_name_ys.get((r, c), int(cy))
            mini_bar_w = 30
            mini_bar_h = 2
            mini_gap = 1
            mini_pad = 2
            block_w = mini_bar_w + mini_pad * 2
            block_h = mini_bar_h * 3 + mini_gap * 2 + mini_pad * 2
            circle_r = block_h
            overlap = 1
            total_w = circle_r * 2 + block_w - overlap
            start_x = int(cx) - total_w // 2
            by = name_y
            circle_cx = start_x + circle_r
            circle_cy = by + block_h // 2
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
            self._draw_city_bar_fill(city, mbx, constr_bar_y, mini_bar_w, mini_bar_h, 'construction')
            pop_fill_r = circle_r
            pop_ring_r = circle_r + 3
            pygame.draw.circle(self.screen, city_dark,  (circle_cx, circle_cy), pop_ring_r)
            pygame.draw.circle(self.screen, city_light, (circle_cx, circle_cy), pop_fill_r)
            pop_str = str(len(city.pops))
            pop_num_outline_r = 3
            pop_outline = self.font_pop.render(pop_str, True, city_dark)
            pop_white = self.font_pop.render(pop_str, True, (255, 255, 255))
            tx = circle_cx - pop_white.get_width() // 2
            ty = circle_cy - pop_white.get_height() // 2
            for dx in range(-pop_num_outline_r, pop_num_outline_r + 1):
                for dy in range(-pop_num_outline_r, pop_num_outline_r + 1):
                    if (dx, dy) != (0, 0) and dx * dx + dy * dy <= pop_num_outline_r * pop_num_outline_r:
                        self.screen.blit(pop_outline, (tx + dx, ty + dy))
            self.screen.blit(pop_white, (tx, ty))

        # Pass 8: selected tile border (drawn over all map content)
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
        self.river_option_rects = {}
        if river_popup_active:
            self._draw_river_popup(selected_tile)
        elif terrain_popup_active:
            self._draw_terrain_popup(selected_tile)
        elif save_popup_active:
            self._draw_save_popup(save_popup_text)

        if self.recruit_popup_active and selected_tile and selected_tile.city:
            self._draw_recruit_popup(selected_tile.city)

        if battle_popup_active and battle_popup_preview:
            self._draw_battle_popup(battle_popup_preview)

        if console_active:
            self._draw_console_overlay(console_input)

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
        dist = self.map.get_travel_cost(city_a.row, city_a.col, city_b.row, city_b.col)
        self._snap_route_amount(pos_x, self.trade_route_amount_slider_rect, 'trade_route_export_amount', dist, 2)

    def snap_import_amount(self, pos_x):
        if not self.trade_route_pending or not self.trade_route_import_slider_rect:
            return
        city_a, city_b = self.trade_route_pending
        dist = self.map.get_travel_cost(city_a.row, city_a.col, city_b.row, city_b.col)
        self._snap_route_amount(pos_x, self.trade_route_import_slider_rect, 'trade_route_import_amount', dist, 1)

    def _draw_trade_route_popup(self):
        if not self.trade_route_pending:
            return
        city_a, city_b = self.trade_route_pending
        dist = self.map.get_travel_cost(city_a.row, city_a.col, city_b.row, city_b.col)

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
        self.trade_route_max_export = ex_max
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
        self.trade_route_max_import = im_max
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
        water_reachable = self.map.get_travel_cost(city_a.row, city_a.col, dest_tile.row, dest_tile.col, water=True) is not None
        if not water_reachable and self.one_way_route_type == 'water':
            self.one_way_route_type = 'land'
        water = self.one_way_route_type == 'water'
        dist = self.map.get_travel_cost(city_a.row, city_a.col, dest_tile.row, dest_tile.col, water=water)

        pad = 16
        popup_w = 280
        popup_h = 290
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

        btn_w = (inner_w - 4) // 2
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
        y += surf.get_height() + 12

        surf = self.font_body.render("Export Food", True, TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 10

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
            denom = carry_capacity + 1 - 2 * travel_time
            if denom > 0 and travel_time > 0:
                raw = (self.one_way_amount * 2 * travel_time) / denom
                pops_required = max(1, round(raw))
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
        self.one_way_confirm_rect = self._draw_button(x, y, btn_w, 24, "Confirm")
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
                name_line = route.city_a.name
                if not route.established:
                    t = route.turns_until_established()
                    name_line = f"{name_line} ({t} {'turn' if t == 1 else 'turns'})"
                name_surf = self.font_body.render(name_line, True, TEXT_COLOR)
                self.screen.blit(name_surf, (x + 4, y))
                del_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "x")
                self.trade_route_delete_rects.append((del_rect, route))
                red_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                self.trade_route_reduce_rects.append((red_rect, route))
                y += name_surf.get_height() + 2
                net_food = route.export_amount if route.export_material == 'food' else 0
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
        label = self.font_small.render("Food", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.food_stockpile)}/{food_max}", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        self._draw_city_bar_fill(city, bar_x, y, bar_w, bar_h, 'food', tick_w=2, border_radius=2)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
        y += bar_h + 8

        # Growth bar
        label = self.font_small.render("Growth", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.growth_progress)}/100", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        self._draw_city_bar_fill(city, bar_x, y, bar_w, bar_h, 'growth', border_radius=2)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
        y += bar_h + 8

        # Construction bar
        label = self.font_small.render("Construction", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.construction_progress)}/1000", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        self._draw_city_bar_fill(city, bar_x, y, bar_w, bar_h, 'construction', border_radius=2)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
        y += bar_h + 12

        btn_w2 = CITY_PANEL_WIDTH - pad * 2
        btn_h2 = 22
        self.rebalance_pops_button_rect = self._draw_button(pad, y, btn_w2, btn_h2, "Rebalance Pops")
        y += btn_h2 + 10

        surf = self.font_header.render("CITY FOCUS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        focus_btn_h = 20
        focus_widths = [52, 72, 60]
        focus_x = pad
        self.city_focus_rects = {}
        for label, fw in zip(("Growth", "Production", "Stockpile"), focus_widths):
            disabled = label == 'Growth' and city.growth_halted
            rect = self._draw_button(focus_x, y, fw, focus_btn_h, label,
                                     active=(label == city.city_focus),
                                     disabled=disabled)
            if not disabled:
                self.city_focus_rects[label] = rect
            focus_x += fw + 2
        y += focus_btn_h + 6

        half_w = (CITY_PANEL_WIDTH - pad * 2 - 4) // 2
        self.halt_growth_rect = self._draw_button(
            pad, y, half_w, focus_btn_h, "Halt Growth", active=city.growth_halted)
        self.gates_closed_rect = self._draw_button(
            pad + half_w + 4, y, half_w, focus_btn_h, "Close Gates", active=city.gates_closed)
        y += focus_btn_h + 10

        surf = self.font_header.render("POPS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4

        def _jlabel(label, n):
            return label[:-1] if n == 1 else label

        btn_s = 16
        for job in city.jobs:
            if job.job_type == 'administrator':
                label_surf = self.font_body.render(f"{job.assigned} {_jlabel(job.label, job.assigned)}", True, TEXT_COLOR)
                self.screen.blit(label_surf, (x + 4, y + (btn_s - label_surf.get_height()) // 2))
                self.admin_plus_rect = self._draw_button(
                    CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "+")
                if job.assigned > city.min_admin_count():
                    self.admin_minus_rect = self._draw_button(
                        CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                else:
                    self.admin_minus_rect = None
                y += btn_s + 4
            else:
                surf = self.font_body.render(f"{job.assigned} {_jlabel(job.label, job.assigned)}", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
        total_caravans = city._get_pops_assigned_to_routes()
        if total_caravans > 0:
            surf = self.font_body.render(f"{total_caravans} {_jlabel('Caravans', total_caravans)}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
        n_peasants = city.total_farm_assigned
        surf = self.font_body.render(f"{n_peasants}/{city.total_farm_slots} {_jlabel('Peasants', n_peasants)}", True, TEXT_COLOR)
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 8

        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
        y += 10
        surf = self.font_header.render("YIELDS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4

        def _fmt_res(v):
            return str(int(v)) if v == int(v) else f"{v:.1f}"

        surf = self.font_body.render("Food", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 2

        farm_food  = city._food_produced() - city._food_from_routes()
        route_food = city._food_from_routes()

        def _signed(v):
            return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"

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
        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
        y += 10
        surf = self.font_header.render("TRADE ROUTES", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6

        def _fmt_amt(v):
            return str(int(v)) if v == int(v) else f"{v:.1f}"

        self.trade_route_delete_rects = []
        self.trade_route_reduce_rects = []
        btn_s = 16
        for route in city.trade_routes:
            is_origin = route.city_a is city
            other_name = route.destination_name if is_origin else route.city_a.name
            if is_origin:
                net_food = (route.import_amount if route.import_material == 'food' else 0) \
                         - (route.export_amount if route.export_material == 'food' else 0)
            else:
                net_food = (route.export_amount if route.export_material == 'food' else 0) \
                         - (route.import_amount if route.import_material == 'food' else 0)
            if route.missing_caravans:
                print('Missing caravans!!')
            if route.established:
                name_line = other_name
            else:
                t = route.turns_until_established()
                name_line = f"{other_name} ({t} {'turn' if t == 1 else 'turns'})"
            surf = self.font_body.render(name_line, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            del_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "x")
            self.trade_route_delete_rects.append((del_rect, route))
            red_rect = self._draw_button(CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
            self.trade_route_reduce_rects.append((red_rect, route))
            y += surf.get_height() + 2
            pops = route.get_pops_from_city(city)
            food_str = f"+{_fmt_amt(net_food)}" if net_food >= 0 else _fmt_amt(net_food)
            detail = f"{pops} pops, {food_str} food"
            if route.missing_caravans:
                detail += " (ending)"
            surf = self.font_small.render(detail, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 6

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
            pad, y, CITY_PANEL_WIDTH - pad * 2, 22, "Add One Way Route",
            active=self.adding_one_way_route)
        y += 28

    def _draw_panel(self, tile, move_mode=False):
        self.move_button_rect = None
        self.capture_button_rect = None
        self.raid_button_rect = None
        self.restrict_tile_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.recruit_unit_button_rect = None
        self.disband_button_rect = None
        panel_x = self.map_w
        pad = 16
        pygame.draw.rect(self.screen, PANEL_BG, (panel_x, 0, PANEL_WIDTH, self.screen.get_height()))
        pygame.draw.line(self.screen, PANEL_DIVIDER, (panel_x, 0), (panel_x, self.screen.get_height()), 1)

        x = panel_x + pad
        y = 20

        # Terrain section header
        if tile:
            surf = self.font_header.render("TERRAIN", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 6

        # Terrain value + Draw River button on same row
        row_h = 22
        dr_btn_w = 78
        terrain_text = tile.terrain.capitalize() if tile else "—"
        t_surf = self.font_body.render(terrain_text, True, TEXT_COLOR)
        self.screen.blit(t_surf, (x + 4, y + (row_h - t_surf.get_height()) // 2))
        if tile:
            no_river = tile.terrain in ('hills', 'mountain')
            self.draw_river_button_rect = self._draw_button(
                panel_x + PANEL_WIDTH - pad - dr_btn_w, y, dr_btn_w, row_h,
                "Draw River", disabled=no_river,
            )
            if no_river:
                self.draw_river_button_rect = None
        y += row_h + 8

        # Change Terrain + Save Map buttons
        btn_w = PANEL_WIDTH - pad * 2
        btn_h = 22
        if tile:
            self.change_terrain_button_rect = self._draw_button(panel_x + pad, y, btn_w, btn_h, "Change Terrain")
            y += btn_h + 6
        self.save_map_button_rect = self._draw_button(panel_x + pad, y, btn_w, btn_h, "Save Map")
        y += btn_h + 6
        if tile and tile.owning_city:
            owned_surf = self.font_body.render(f"Owned by {tile.owning_city.name}", True, TEXT_COLOR)
            self.screen.blit(owned_surf, (x + 4, y))
            y += owned_surf.get_height() + 2
            dist_surf = self.font_body.render(f"Distance {tile.city_distance:.2f}", True, TEXT_COLOR)
            self.screen.blit(dist_surf, (x + 4, y))
            y += dist_surf.get_height() + 2
            yield_surf = self.font_body.render(f"Effective yield {tile.farm_yield:.2f}", True, TEXT_COLOR)
            self.screen.blit(yield_surf, (x + 4, y))
            y += yield_surf.get_height() + 2
            farms_surf = self.font_body.render(f"{tile.worked_farms} farms", True, TEXT_COLOR)
            self.screen.blit(farms_surf, (x + 4, y))
            y += farms_surf.get_height() + 4
        if tile and tile.cities_in_range:
            surf = self.font_body.render("Cities in range:", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
            for city in tile.cities_in_range:
                faction_name = city.faction.name if city.faction else "none"
                surf = self.font_body.render(f"  {city.name} ({faction_name})", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
        if tile and tile.raided:
            label = f"Raided ({tile._raided_ticker} turns left)" if tile._raided_ticker > 0 else "Raided"
            surf = self.font_body.render(label, True, (200, 80, 80))
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
        if tile and tile.restricted:
            label = f"Restricted ({tile._restricted_ticker} turns left)" if tile._restricted_ticker > 0 else "Restricted"
            surf = self.font_body.render(label, True, (200, 160, 60))
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 2
        if tile:
            btn_label = "Unrestrict Tile" if tile.restricted else "Restrict Tile"
            disabled = tile._restricted_ticker > 0
            self.restrict_tile_button_rect = self._draw_button(x, y, PANEL_WIDTH - pad * 2, 20, btn_label, disabled=disabled)
            if disabled:
                self.restrict_tile_button_rect = None
            y += 26
        y += 6

        unit_groups = self.map.get_unit_groups(tile.row, tile.col) if tile else []
        has_city = tile and tile.city is not None
        if unit_groups or has_city:
            pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (panel_x + PANEL_WIDTH - pad, y), 1)
            y += 16

            # UnitGroup section
            surf = self.font_header.render("UNITS", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 6

            selected_on_tile = [g for g in unit_groups if g in self.selected_unit_groups]
            half_w = (PANEL_WIDTH - pad * 2 - 4) // 2
            recruit_disabled = not has_city
            disband_disabled = not has_city or len(selected_on_tile) == 0
            self.recruit_unit_button_rect = self._draw_button(panel_x + pad, y, half_w, btn_h, "Recruit", disabled=recruit_disabled)
            self.disband_button_rect = self._draw_button(panel_x + pad + half_w + 4, y, half_w, btn_h, "Disband", disabled=disband_disabled)
            if recruit_disabled:
                self.recruit_unit_button_rect = None
            if disband_disabled:
                self.disband_button_rect = None
            y += btn_h + 6

        first_group = unit_groups[0] if unit_groups else None
        if first_group:
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

        icon_h = self.font_body.get_height()
        icon_raw = self._icons_raw.get('sword')
        small_icon = pygame.transform.scale(icon_raw, (icon_h, icon_h)) if icon_raw else None
        small_icon_tinted = None
        small_icon_tinted_by_faction = {}
        if icon_raw:
            scaled = pygame.transform.scale(icon_raw, (icon_h, icon_h))
            outline_r = 2
            small_icon_tinted, _ = self._make_icon_pair(scaled, (180, 210, 255), (35, 65, 150), outline_r, pad=outline_r)
            for group in unit_groups:
                if group.faction:
                    fname = group.faction.name
                    if fname not in small_icon_tinted_by_faction:
                        t, _ = self._make_icon_pair(scaled, group.faction.colors['light'], group.faction.colors['dark'], outline_r, pad=outline_r)
                        small_icon_tinted_by_faction[fname] = t
        bar_w = PANEL_WIDTH - pad * 2
        bar_h = 6

        self.group_icon_rects = []
        for group in unit_groups:
            selected = group in self.selected_unit_groups
            fname = group.faction.name if group.faction else None
            tinted = small_icon_tinted_by_faction.get(fname, small_icon_tinted)
            icon_to_use = tinted if selected else small_icon
            type_counts = collections.Counter(u.unit_type for u in group.units)
            row_top_y = y
            for unit_type, count in type_counts.items():
                icon_overlap = 5
                icons_total_w = 0
                if icon_to_use:
                    for i in range(count):
                        self.screen.blit(icon_to_use, (x + 4 + i * icon_overlap, y))
                    icons_total_w = icon_h + (count - 1) * icon_overlap
                text_x = x + 4 + (icons_total_w + 8 if icon_to_use else 0)
                unit_text_color = (220, 50, 50) if group.pending_pop_loss > 0 else TEXT_COLOR
                surf = self.font_body.render(f"{count} {unit_type.capitalize()}", True, unit_text_color)
                self.screen.blit(surf, (text_x, y))
                y += icon_h + 4
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

        if unit_groups:
            btn_h = 20
            half_w = (bar_w - 4) // 2
            self.select_all_button_rect = self._draw_button(x, y, half_w, btn_h, "Select All")
            self.unselect_all_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Unselect All")
            y += btn_h + 4
            selected_on_tile = [g for g in unit_groups if g in self.selected_unit_groups]
            self.merge_button_rect = self._draw_button(x, y, half_w, btn_h, "Merge", disabled=len(selected_on_tile) < 2)
            self.separate_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Separate", disabled=True)
            y += btn_h + 4
            self.restock_all_button_rect = self._draw_button(x, y, half_w, btn_h, "Restock All", disabled=True)
            self.drop_all_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Drop All", disabled=True)
            y += btn_h + 4
            self.restock_button_rect = self._draw_button(x, y, half_w, btn_h, "Restock", disabled=True)
            self.drop_button_rect = self._draw_button(x + half_w + 4, y, half_w, btn_h, "Drop", disabled=True)
            y += btn_h + 6

        # End Turn button anchored to bottom
        btn_w = PANEL_WIDTH - pad * 2
        btn_h = 28
        self.end_turn_button_rect = self._draw_button(
            panel_x + pad, self.screen.get_height() - pad - btn_h, btn_w, btn_h, "End Turn"
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

    def _draw_recruit_popup(self, city):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        W, H = 280, 168
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pad = 16
        track_h = 6
        track_w = W - pad * 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("RECRUIT UNITS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + pad, sy + 12))

        max_recruit = min(8, len(city.pops) - 1)
        amount = max(1, min(self.recruit_popup_amount, max_recruit))
        self.recruit_popup_amount = amount

        amt_surf = self.font_body.render(f"{amount} unit{'s' if amount != 1 else ''}", True, TEXT_COLOR)
        self.screen.blit(amt_surf, (sx + pad, sy + 36))

        track_x = sx + pad
        track_y = sy + 54
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
        for i in range(1, max_recruit + 1):
            tx = track_x + int((i - 1) / max(max_recruit - 1, 1) * track_w)
            pygame.draw.line(self.screen, PANEL_DIVIDER, (tx, track_y - 2), (tx, track_y + track_h + 2), 1)
        hx = track_x + int((amount - 1) / max(max_recruit - 1, 1) * track_w)
        hy = track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (hx, hy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (hx, hy), 6, 1)
        self.screen.blit(self.font_small.render("1", True, PANEL_DIVIDER), (track_x, track_y + track_h + 3))
        max_r_surf = self.font_small.render(str(max_recruit), True, PANEL_DIVIDER)
        self.screen.blit(max_r_surf, (track_x + track_w - max_r_surf.get_width(), track_y + track_h + 3))
        self.recruit_popup_slider_rect = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)

        carry_cap = amount * MILITARY_CARRY_CAPACITY
        max_food = int(min(city.food_stockpile, carry_cap))
        food = max(0, min(self.recruit_popup_food, max_food))
        self.recruit_popup_food = food

        food_surf = self.font_body.render(f"{food} food", True, TEXT_COLOR)
        self.screen.blit(food_surf, (sx + pad, sy + 88))

        f_track_y = sy + 106
        pygame.draw.rect(self.screen, (60, 60, 80), (track_x, f_track_y, track_w, track_h), border_radius=2)
        if max_food > 0:
            fhx = track_x + int(food / max_food * track_w)
        else:
            fhx = track_x
        fhy = f_track_y + track_h // 2
        pygame.draw.circle(self.screen, (160, 190, 240), (fhx, fhy), 6)
        pygame.draw.circle(self.screen, (100, 130, 190), (fhx, fhy), 6, 1)
        self.screen.blit(self.font_small.render("0", True, PANEL_DIVIDER), (track_x, f_track_y + track_h + 3))
        max_f_surf = self.font_small.render(str(max_food), True, PANEL_DIVIDER)
        self.screen.blit(max_f_surf, (track_x + track_w - max_f_surf.get_width(), f_track_y + track_h + 3))
        self.recruit_popup_food_slider_rect = pygame.Rect(track_x, f_track_y - 6, track_w, track_h + 16)

        btn_y = sy + H - 36
        btn_w = (W - pad * 2 - 8) // 2
        self.recruit_popup_confirm_rect = self._draw_button(sx + pad, btn_y, btn_w, 24, "Confirm")
        self.recruit_popup_cancel_rect = self._draw_button(sx + pad + btn_w + 8, btn_y, btn_w, 24, "Cancel")

    def _draw_battle_popup(self, preview):
        from src.game.city import City
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        mod_count = len(preview['modifiers'])
        W, H = 340, 180 + mod_count * 18
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pad = 16
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        title = self.font_header.render("BATTLE", True, HEADER_TEXT_COLOR)
        self.screen.blit(title, (sx + W // 2 - title.get_width() // 2, sy + 10))

        # Divider below title
        div_y = sy + 30
        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, div_y), (sx + W - pad, div_y))

        # Attacker column (left) / Defender column (right)
        col_w = (W - pad * 2) // 2
        left_x = sx + pad
        right_x = sx + pad + col_w
        y = div_y + 8

        def faction_name(side):
            groups = preview['attacker_groups'] if side == 'attacker' else preview['defender']
            if isinstance(groups, City):
                return groups.faction.name if groups.faction else groups.name
            return groups[0].faction.name if groups and groups[0].faction else '—'

        for side, x, unit_key, str_key, total_key in [
            ('attacker', left_x,  'attacker_units', 'attacker_strength', 'attacker_total'),
            ('defender', right_x, 'defender_units', 'defender_strength', 'defender_total'),
        ]:
            color = HEADER_TEXT_COLOR
            name_surf = self.font_header.render(faction_name(side), True, color)
            self.screen.blit(name_surf, (x, y))
            units_surf = self.font_body.render(f"{preview[unit_key]} units", True, TEXT_COLOR)
            self.screen.blit(units_surf, (x, y + 18))
            str_surf = self.font_body.render(f"Strength: {preview[str_key]}", True, TEXT_COLOR)
            self.screen.blit(str_surf, (x, y + 34))

        # Vertical divider between columns
        mid_x = sx + W // 2
        pygame.draw.line(self.screen, PANEL_DIVIDER, (mid_x, div_y + 4), (mid_x, div_y + 56))

        y += 56
        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 6

        # Modifiers
        for label, side, value in preview['modifiers']:
            sign = '+' if value >= 0 else ''
            text = f"{label} ({side}): {sign}{value}"
            surf = self.font_body.render(text, True, (180, 200, 160) if value > 0 else (200, 160, 160))
            self.screen.blit(surf, (sx + pad, y))
            y += 18

        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 6

        # Totals
        at_surf = self.font_body.render(f"Total: {preview['attacker_total']:.2f}", True, TEXT_COLOR)
        dt_surf = self.font_body.render(f"Total: {preview['defender_total']:.2f}", True, TEXT_COLOR)
        self.screen.blit(at_surf, (left_x, y))
        self.screen.blit(dt_surf, (right_x, y))
        y += 24

        pygame.draw.line(self.screen, PANEL_DIVIDER, (sx + pad, y), (sx + W - pad, y))
        y += 8

        btn_w = (W - pad * 2 - 8) // 2
        self.battle_popup_confirm_rect = self._draw_button(sx + pad, y, btn_w, 24, "Attack")
        self.battle_popup_cancel_rect = self._draw_button(sx + pad + btn_w + 8, y, btn_w, 24, "Cancel")

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

        row_h = 34
        W = 240
        H = 30 + len(TERRAIN_TYPES) * row_h + 24
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("CHANGE TERRAIN", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + 16, sy + 10))

        swatch = 14
        btn_w = W - 32
        for i, terrain in enumerate(TERRAIN_TYPES):
            by = sy + 30 + i * row_h
            is_current = selected_tile and selected_tile.terrain == terrain
            rect = self._draw_button(sx + 16, by, btn_w, row_h - 4, "", active=is_current)
            color = TERRAIN_COLORS.get(terrain, BUTTON_NORMAL)
            pygame.draw.rect(self.screen, color,
                             (rect.x + 8, rect.y + (rect.height - swatch) // 2, swatch, swatch),
                             border_radius=2)
            label = self.font_body.render(terrain.capitalize(), True, BUTTON_TEXT)
            self.screen.blit(label, (rect.x + 8 + swatch + 8, rect.y + (rect.height - label.get_height()) // 2))
            self.terrain_option_rects[terrain] = rect

        hint = self.font_body.render("Esc to cancel", True, (110, 110, 130))
        self.screen.blit(hint, (sx + 16, sy + H - 20))

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
        for row_idx, (left, right) in enumerate(RIVER_DIR_GRID):
            by = gy + row_idx * (btn_h + row_gap)
            for col_idx, direction in enumerate((left, right)):
                bx = gx + col_idx * (btn_w + col_gap)
                is_active = selected_tile and direction in selected_tile.river_edges
                rect = self._draw_button(bx, by, btn_w, btn_h, direction, active=is_active)
                self.river_option_rects[direction] = rect

        hint = self.font_body.render("Esc to cancel", True, (110, 110, 130))
        self.screen.blit(hint, (sx + 16, sy + H - 18))
