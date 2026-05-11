import math
import os
import pygame
from src.game.city import STOCKPILE_MAX
from src.game.constants import DEFAULT_MOVE_DISTANCE, LAND_CARRY_CAPACITY
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
        screen_h = int((game_map.rows - 1) * HEX_SIZE * 1.5 + 2 * HEX_SIZE + 2 * MARGIN)
        self.offset_x = CITY_PANEL_WIDTH + MARGIN + w / 2
        self.offset_y = MARGIN + HEX_SIZE
        self.screen = pygame.display.set_mode((self.map_w + PANEL_WIDTH, screen_h))
        pygame.display.set_caption("HexGame")
        self.font_header = pygame.font.SysFont('segoeui', 13, bold=True)
        self.font_body = pygame.font.SysFont('segoeui', 13)
        self.font_small = pygame.font.SysFont('segoeui', 10)
        self.font_city = pygame.font.SysFont('tempussansitc', 12, bold=True)
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
        for icon_name, file_name in (('castle', 'city'), ('sword', 'sword')):
            path = os.path.join(icons_dir, f'{file_name}.png')
            if os.path.exists(path):
                self._icons_raw[icon_name] = pygame.image.load(path).convert_alpha()
        self._river_imgs_raw = []
        for img_file, entries in (
            ('sw2ne_2',   [(frozenset({'W',  'E'}),  -30),
                       (frozenset({'NW', 'SE'}),   -90),
                       (frozenset({'NE', 'SW'}),  30)]),
            ('nw2s',  [(frozenset({'NW', 'SW'}),  -30),
                       (frozenset({'NE', 'W'}),   -90),
                       (frozenset({'NW', 'E'}),   -150)]),
            ('ne2s',  [(frozenset({'E',  'SW'}),  -30),
                       (frozenset({'SE', 'W'}),   -90),
                       (frozenset({'NE', 'SE'}),  30)]),
        ):
            path = os.path.join(_ASSETS_DIR, 'rivers', f'{img_file}.png')
            if os.path.exists(path):
                self._river_imgs_raw.append((pygame.image.load(path).convert_alpha(), entries))
        self.zoom = 1.0
        self.terrain_images = {}
        self.river_imgs = {}
        self.icons = {}
        self.icons_tinted = {}
        self._apply_zoom()
        self.move_button_rect = None
        self.end_turn_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.rebalance_pops_button_rect = None
        self.admin_minus_rect = None
        self.admin_plus_rect = None
        self.city_focus_rects = {}
        self.adding_trade_route = False
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
        self._glow_surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        self.terrain_option_rects = {}
        self.river_option_rects = {}

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
            for key, angle in entries:
                rotated = pygame.transform.rotate(base, angle)
                mask = rotated.copy()
                mask.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                tinted = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
                tinted.fill(COLOR_RIVER_LINE + (255,))
                tinted.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                black = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
                black.fill((0, 0, 0, 100))
                black.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                size = rotated.get_size()
                radius = int(sz * math.sqrt(3) / 2)
                circle_mask = pygame.Surface(size, pygame.SRCALPHA)
                circle_mask.fill((0, 0, 0, 0))
                pygame.draw.circle(circle_mask, (255, 255, 255, 255), (size[0] // 2, size[1] // 2), radius)
                outline = pygame.Surface(size, pygame.SRCALPHA)
                for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)):
                    outline.blit(black, (dx, dy))
                outline.blit(circle_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                outlined = pygame.Surface(size, pygame.SRCALPHA)
                outlined.blit(outline, (0, 0))
                outlined.blit(tinted, (0, 0))
                self.river_imgs[key] = outlined
        castle_size = int(ICON_SIZE * 1.4 * self.zoom)
        sword_size = int(ICON_SIZE * self.zoom)
        self.icons = {}
        self.icons_tinted = {}
        if 'castle' in self._icons_raw:
            self.icons['castle'] = pygame.transform.scale(self._icons_raw['castle'], (castle_size, castle_size))
            self.icons_tinted['castle'] = self.icons['castle']
        if 'sword' in self._icons_raw:
            scaled = pygame.transform.scale(self._icons_raw['sword'], (sword_size, sword_size))
            self.icons['sword'] = scaled
            tinted = scaled.copy()
            tinted.fill((180, 210, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.icons_tinted['sword'] = tinted

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

    def _hex_cross_section(self, hex_corners, cx, cy, nx, ny, depth):
        """Find the two points where a line at `depth` from (cx,cy) along normal (nx,ny),
        perpendicular to that normal, intersects the hex polygon. Returns (p1, p2) or None."""
        mx = cx + nx * depth
        my = cy + ny * depth
        tx, ty = -ny, nx  # tangent perpendicular to normal
        intersections = []
        n = len(hex_corners)
        for i in range(n):
            ax, ay = hex_corners[i]
            bx, by = hex_corners[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            denom = ex * ty - ey * tx
            if abs(denom) < 1e-9:
                continue
            t = ((mx - ax) * ty - (my - ay) * tx) / denom
            if 0.0 <= t <= 1.0:
                intersections.append((ax + t * ex, ay + t * ey))
        if len(intersections) >= 2:
            return intersections[0], intersections[1]
        return None

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

    def draw(self, selected_tile=None, reachable=None, move_mode=False,
             save_popup_active=False, save_popup_text="",
             terrain_popup_active=False, river_popup_active=False,
             moves_remaining=None, game_log=None,
             console_active=False, console_input=""):
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
                straight_img = self.river_imgs.get(frozenset(tile.river_edges))
                if straight_img:
                    self.screen.blit(straight_img,
                                     (int(cx) - straight_img.get_width() // 2,
                                      int(cy) - straight_img.get_height() // 2))
                else:
                    for direction in tile.river_edges:
                        angle = RIVER_DIR_ANGLES[direction]
                        ex = cx + apothem * math.cos(angle)
                        ey = cy + apothem * math.sin(angle)
                        pygame.draw.line(self.screen, COLOR_RIVER_LINE,
                                         (int(cx), int(cy)), (int(ex), int(ey)), 3)


        # Pass 3b: city territory borders + inner glow
        self._glow_surf.fill((0, 0, 0, 0))
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                if tile.owning_city is None:
                    continue
                cx, cy = all_centers[(r, c)]
                corners = all_corners[(r, c)]
                for i, (dr, dc) in enumerate(_RENDER_NEIGHBORS[r % 2]):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.map.rows and 0 <= nc < self.map.cols):
                        neighbor_city = None
                    else:
                        neighbor_city = self.map.tiles[nr][nc].owning_city
                    if neighbor_city is not tile.owning_city:
                        ci, cj = _NEIGHBOR_EDGE_CORNERS[i]
                        p1 = corners[ci]
                        p2 = corners[cj]
                        glow_reach = 0.1
                        emx = (p1[0] + p2[0]) / 2 - cx
                        emy = (p1[1] + p2[1]) / 2 - cy
                        em_len = math.sqrt(emx * emx + emy * emy)
                        if em_len < 1e-9:
                            continue
                        nx, ny = emx / em_len, emy / em_len
                        inner_depth = em_len * (1 - glow_reach)
                        cross = self._hex_cross_section(corners, cx, cy, nx, ny, inner_depth)
                        if cross:
                            g1, g2 = cross
                            poly = [
                                (int(p1[0]), int(p1[1])),
                                (int(p2[0]), int(p2[1])),
                                (int(g2[0]), int(g2[1])),
                                (int(g1[0]), int(g1[1])),
                            ]
                            pygame.draw.polygon(self._glow_surf, (180, 210, 255, 80), poly)
                        pygame.draw.line(self.screen, (40, 70, 160),
                                         (int(p1[0]), int(p1[1])),
                                         (int(p2[0]), int(p2[1])), 4)
        self.screen.blit(self._glow_surf, (0, 0))

        # Pass 4: reachable borders
        for (r, c) in reachable:
            pygame.draw.polygon(self.screen, COLOR_REACHABLE, all_corners[(r, c)], 2)

        # Pass 4b: remaining move cost labels on reachable tiles
        if moves_remaining is not None and reachable:
            for (r, c), cost in reachable.items():
                label = f"{moves_remaining - cost:.2f}"
                cx, cy = all_centers[(r, c)]
                lx = int(cx)
                ly = int(cy)
                shadow = self.font_small.render(label, True, (0, 0, 0))
                surf = self.font_small.render(label, True, (255, 255, 255))
                hw, hh = surf.get_width() // 2, surf.get_height() // 2
                self.screen.blit(shadow, (lx - hw + 1, ly - hh + 1))
                self.screen.blit(surf, (lx - hw, ly - hh))

        # Pass 5: selected border
        if selected_tile is not None:
            pygame.draw.polygon(self.screen, COLOR_SELECTED,
                                all_corners[(selected_tile.row, selected_tile.col)], 2)

        # Pass 6: city markers
        selected_city_pos = (selected_tile.row, selected_tile.col) if selected_tile else None
        for (r, c), city in self.map.cities.items():
            cx, cy = all_centers[(r, c)]
            if self.adding_trade_route and (r, c) != selected_city_pos:
                corners = [(int(px), int(py)) for px, py in self._hex_corners(cx, cy)]
                pygame.draw.polygon(self.screen, (255, 210, 50), corners, 3)
            icon = self.icons_tinted.get('castle')
            if icon:
                ix = int(cx) - icon.get_width() // 2
                iy = int(cy) - HEX_SIZE - 3.5
                self.screen.blit(icon, (ix, iy))
                name_y = iy + icon.get_height() - 15
            else:
                s = 6
                rect = pygame.Rect(int(cx) - s, int(cy) - s, s * 2, s * 2)
                pygame.draw.rect(self.screen, COLOR_CITY, rect)
                pygame.draw.rect(self.screen, COLOR_CITY_BORDER, rect, 1)
                name_y = int(cy) + s + 2
            label = f"{city.name.upper()}  {len(city.pops)}"
            name_surf = self.font_city.render(label, True, (255, 255, 255))
            shadow_surf = self.font_city.render(label, True, (0, 0, 0))
            nx = int(cx) - name_surf.get_width() // 2
            for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                self.screen.blit(shadow_surf, (nx + dx, name_y + dy))
            self.screen.blit(name_surf, (nx, name_y))

            mini_bar_w = 50
            mini_bar_h = 2
            mini_gap = 1
            mini_pad = 2
            block_w = mini_bar_w + mini_pad * 2
            block_h = mini_bar_h * 3 + mini_gap * 2 + mini_pad * 2
            bx = int(cx) - block_w // 2
            by = name_y + name_surf.get_height() - 2
            pygame.draw.rect(self.screen, (0, 0, 0), (bx, by, block_w, block_h))
            food_max = city._stockpile_max()
            bars = [
                (city.food_stockpile, food_max if food_max > 0 else 1, (120, 190, 80)),
                (city.growth_progress, 100, (40, 160, 150)),
                (city.construction_progress, 1000, (130, 130, 140)),
            ]
            min_stockpile = min(len(city.pops), food_max)
            for i, (val, mx, color) in enumerate(bars):
                bar_y = by + mini_pad + i * (mini_bar_h + mini_gap)
                if i == 0 and food_max > 0:
                    proj = min(city.food_stockpile + city.food_allocated_to_stockpile, food_max)
                    proj_fill = max(int(mini_bar_w * proj / food_max), 0)
                    if proj_fill > 0:
                        pygame.draw.rect(self.screen, (200, 240, 165), (bx + mini_pad, bar_y, proj_fill, mini_bar_h))
                if i == 1:
                    proj = min(city.growth_progress + city.growth_allocated, 100)
                    proj_fill = max(int(mini_bar_w * proj / 100), 0)
                    if proj_fill > 0:
                        pygame.draw.rect(self.screen, (120, 210, 200), (bx + mini_pad, bar_y, proj_fill, mini_bar_h))
                fill = max(int(mini_bar_w * min(val, mx) / mx), 0)
                if fill > 0:
                    pygame.draw.rect(self.screen, color, (bx + mini_pad, bar_y, fill, mini_bar_h))
                if i == 0 and food_max > 0 and 0 < min_stockpile < food_max:
                    tick_x = bx + mini_pad + int(mini_bar_w * min_stockpile / food_max)
                    pygame.draw.line(self.screen, (255, 255, 255), (tick_x, bar_y - 1), (tick_x, bar_y + mini_bar_h), 1)

        # Pass 6b: worked farm dots (top-left of each tile, one dot per assigned pop)
        dot_radius = 2
        dot_spacing = 5
        dot_offset_x = int(apothem * 0.72)
        dot_start_y_offset = int(HEX_SIZE * self.zoom * ISO_SCALE * 0.35)
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                if tile.worked_farms <= 0:
                    continue
                cx, cy = all_centers[(r, c)]
                dx = int(cx) - dot_offset_x
                dy = int(cy) - dot_start_y_offset
                for i in range(tile.worked_farms):
                    col_i = i // 4
                    row_i = i % 4
                    ddx = dx + col_i * dot_spacing
                    ddy = dy + row_i * dot_spacing
                    pygame.draw.circle(self.screen, (30, 60, 120), (ddx, ddy), dot_radius + 1)
                    pygame.draw.circle(self.screen, (180, 210, 255), (ddx, ddy), dot_radius)

        # Pass 7: unit markers
        for (r, c) in self.map.units:
            cx, cy = all_centers[(r, c)]
            icon = self.icons_tinted.get('sword')
            if icon:
                self.screen.blit(icon, (int(cx) - icon.get_width() // 2,
                                        int(cy) - icon.get_height() // 2))
            else:
                self._draw_unit_marker(int(cx), int(cy))

        self._draw_city_panel(selected_tile)
        self._draw_panel(selected_tile, move_mode)

        self.terrain_option_rects = {}
        self.river_option_rects = {}
        if river_popup_active:
            self._draw_river_popup(selected_tile)
        elif terrain_popup_active:
            self._draw_terrain_popup(selected_tile)
        elif save_popup_active:
            self._draw_save_popup(save_popup_text)

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

        surf = self.font_header.render("CITY", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6

        city = self.map.cities.get((tile.row, tile.col)) if tile else None
        if not city:
            pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
            y += 10
            surf = self.font_header.render("TRADE ROUTES", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            return

        surf = self.font_body.render(city.name, True, TEXT_COLOR)
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 8

        # Food stockpile bar
        food_max = city._stockpile_max()
        label = self.font_small.render("Food", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.food_stockpile)}/{food_max}", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        if food_max > 0:
            proj = min(city.food_stockpile + city.food_allocated_to_stockpile, food_max)
            proj_w = int(bar_w * proj / food_max)
            if proj_w > 0:
                pygame.draw.rect(self.screen, (200, 240, 165), (bar_x, y, proj_w, bar_h), border_radius=2)
            fill_w = int(bar_w * min(city.food_stockpile, food_max) / food_max)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (120, 190, 80), (bar_x, y, fill_w, bar_h), border_radius=2)
            min_stockpile = min(len(city.pops), food_max)
            if 0 < min_stockpile < food_max:
                tick_x = bar_x + int(bar_w * min_stockpile / food_max)
                pygame.draw.line(self.screen, (255, 255, 255), (tick_x, y - 2), (tick_x, y + bar_h + 1), 2)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
        y += bar_h + 8

        # Growth bar
        label = self.font_small.render("Growth", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.growth_progress)}/100", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        proj_w = int(bar_w * min(city.growth_progress + city.growth_allocated, 100) / 100)
        if proj_w > 0:
            pygame.draw.rect(self.screen, (120, 210, 200), (bar_x, y, proj_w, bar_h), border_radius=2)
        fill_w = int(bar_w * min(city.growth_progress, 100) / 100)
        if fill_w > 0:
            pygame.draw.rect(self.screen, (40, 160, 150), (bar_x, y, fill_w, bar_h), border_radius=2)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
        y += bar_h + 8

        # Construction bar
        label = self.font_small.render("Construction", True, TEXT_COLOR)
        val = self.font_small.render(f"{int(city.construction_progress)}/1000", True, TEXT_COLOR)
        self.screen.blit(label, (bar_x, y))
        self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
        y += label.get_height() + 2
        pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
        fill_w = int(bar_w * city.construction_progress / 1000)
        if fill_w > 0:
            pygame.draw.rect(self.screen, (130, 130, 140), (bar_x, y, fill_w, bar_h), border_radius=2)
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
            rect = self._draw_button(focus_x, y, fw, focus_btn_h, label,
                                     active=(label == city.city_focus))
            self.city_focus_rects[label] = rect
            focus_x += fw + 2
        y += focus_btn_h + 10

        surf = self.font_header.render("POPS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        btn_s = 16
        for job in city.jobs:
            if job.job_type == 'administrator':
                label_surf = self.font_body.render(f"{job.assigned} {job.label.lower()}", True, TEXT_COLOR)
                self.screen.blit(label_surf, (x + 4, y + (btn_s - label_surf.get_height()) // 2))
                self.admin_plus_rect = self._draw_button(
                    CITY_PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "+")
                self.admin_minus_rect = self._draw_button(
                    CITY_PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                y += btn_s + 4
            else:
                surf = self.font_body.render(f"{job.assigned} {job.label.lower()}", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
        surf = self.font_body.render(f"{city.total_farm_assigned} peasants", True, TEXT_COLOR)
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 8

        surf = self.font_header.render("AVAILABLE JOBS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 4
        available_farm = city.total_farm_slots - city.total_farm_assigned
        surf = self.font_body.render(f"{available_farm} peasants", True, TEXT_COLOR)
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 12

        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (CITY_PANEL_WIDTH - pad, y), 1)
        y += 10
        surf = self.font_header.render("TRADE ROUTES", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6

        def _fmt_amt(v):
            return str(int(v)) if v == int(v) else f"{v:.1f}"

        for route in city.trade_routes:
            is_origin = route.city_a == city
            other = route.city_b if is_origin else route.city_a
            name_surf = self.font_body.render(other.name, True, TEXT_COLOR)
            self.screen.blit(name_surf, (x + 4, y))
            y += name_surf.get_height() + 1
            parts = []
            if is_origin:
                parts.append(f"{route.pops} pops in caravan")
                if route.import_material:
                    parts.append(f"+{_fmt_amt(route.import_amount)} {route.import_material}")
                if route.export_material:
                    parts.append(f"-{_fmt_amt(route.export_amount)} {route.export_material}")
            else:
                if route.export_material:
                    parts.append(f"+{_fmt_amt(route.export_amount)} {route.export_material}")
                if route.import_material:
                    parts.append(f"-{_fmt_amt(route.import_amount)} {route.import_material}")
            detail_surf = self.font_body.render(", ".join(parts) if parts else "—", True, TEXT_COLOR)
            self.screen.blit(detail_surf, (x + 4, y))
            y += detail_surf.get_height() + 6

        if self.trade_route_pending:
            city_a, city_b = self.trade_route_pending
            surf = self.font_body.render(f"{city_a.name} <-> {city_b.name}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 4
            dist = self.map.get_travel_cost(city_a.row, city_a.col, city_b.row, city_b.col)
            dist_text = f"Distance: {dist:.1f}" if dist is not None else "Distance: N/A"
            surf = self.font_body.render(dist_text, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 10

            # Pops allocated slider (1–8)
            label_surf = self.font_small.render(f"Pops allocated: {self.trade_route_pops}", True, TEXT_COLOR)
            self.screen.blit(label_surf, (x + 4, y))
            y += label_surf.get_height() + 6

            track_w = CITY_PANEL_WIDTH - pad * 2
            track_h = 4
            track_x = pad
            track_y = y
            pygame.draw.rect(self.screen, (60, 60, 80), (track_x, track_y, track_w, track_h), border_radius=2)
            t = (self.trade_route_pops - 1) / 7.0
            handle_x = int(track_x + t * track_w)
            handle_y = track_y + track_h // 2
            pygame.draw.circle(self.screen, (160, 190, 240), (handle_x, handle_y), 6)
            pygame.draw.circle(self.screen, (100, 130, 190), (handle_x, handle_y), 6, 1)
            min_surf = self.font_small.render("1", True, PANEL_DIVIDER)
            max_surf = self.font_small.render("8", True, PANEL_DIVIDER)
            self.screen.blit(min_surf, (track_x, track_y + track_h + 3))
            self.screen.blit(max_surf, (track_x + track_w - max_surf.get_width(), track_y + track_h + 3))
            self.trade_route_slider_rect = pygame.Rect(track_x, track_y - 6, track_w, track_h + 16)
            y = track_y + track_h + min_surf.get_height() + 12

            # Export material selector
            surf = self.font_small.render("Export material", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 4
            export_btn_w = (CITY_PANEL_WIDTH - pad * 2 - 4) // 3
            self.trade_route_export_rects = {}
            bx = pad
            for export_label in ('Food', 'Wood', 'Iron'):
                rect = self._draw_button(bx, y, export_btn_w, 20, export_label,
                                         active=(self.trade_route_export == export_label.lower()))
                self.trade_route_export_rects[export_label] = rect
                bx += export_btn_w + 2
            y += 28

            city_a, city_b = self.trade_route_pending
            dist = self.map.get_travel_cost(city_a.row, city_a.col, city_b.row, city_b.col)
            track_w_s = CITY_PANEL_WIDTH - pad * 2
            track_h_s = 4
            label_h = self.font_small.size("0")[1]

            # Export amount slider
            ex_steps, ex_max = self._amount_steps(dist, self.trade_route_pops, 2)
            self.trade_route_max_export = ex_max
            ex_val = min(self.trade_route_export_amount, ex_max)
            ex_str = str(int(ex_val)) if ex_val == int(ex_val) else f"{ex_val:.1f}"
            surf = self.font_small.render(f"Export amount: {ex_str}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 6
            self.trade_route_amount_slider_rect = self._draw_route_slider(
                pad, y, track_w_s, track_h_s, ex_steps, ex_max, ex_val)
            y += track_h_s + label_h + 14

            # Import material selector
            surf = self.font_small.render("Import material", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 4
            import_btn_w = (CITY_PANEL_WIDTH - pad * 2 - 4) // 3
            self.trade_route_import_rects = {}
            bx = pad
            for import_label in ('Food', 'Wood', 'Iron'):
                rect = self._draw_button(bx, y, import_btn_w, 20, import_label,
                                         active=(self.trade_route_import == import_label.lower()))
                self.trade_route_import_rects[import_label] = rect
                bx += import_btn_w + 2
            y += 28

            # Import amount slider
            im_steps, im_max = self._amount_steps(dist, self.trade_route_pops, 1)
            self.trade_route_max_import = im_max
            im_val = min(self.trade_route_import_amount, im_max)
            im_str = str(int(im_val)) if im_val == int(im_val) else f"{im_val:.1f}"
            surf = self.font_small.render(f"Import amount: {im_str}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 6
            self.trade_route_import_slider_rect = self._draw_route_slider(
                pad, y, track_w_s, track_h_s, im_steps, im_max, im_val)
            y += track_h_s + label_h + 14

            self.trade_route_confirm_rect = self._draw_button(
                pad, y, CITY_PANEL_WIDTH - pad * 2, 22, "Confirm")
            y += 28
        else:
            self.trade_route_slider_rect = None
            self.trade_route_amount_slider_rect = None
            self.trade_route_import_slider_rect = None
            self.trade_route_export_rects = {}
            self.trade_route_import_rects = {}
            self.add_trade_route_button_rect = self._draw_button(
                pad, y, CITY_PANEL_WIDTH - pad * 2, 22, "Add New Route",
                active=self.adding_trade_route)
            y += 28

    def _draw_panel(self, tile, move_mode=False):
        self.move_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        panel_x = self.map_w
        pad = 16
        pygame.draw.rect(self.screen, PANEL_BG, (panel_x, 0, PANEL_WIDTH, self.screen.get_height()))
        pygame.draw.line(self.screen, PANEL_DIVIDER, (panel_x, 0), (panel_x, self.screen.get_height()), 1)

        x = panel_x + pad
        y = 20

        # Terrain section header
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
        y += 6

        pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (panel_x + PANEL_WIDTH - pad, y), 1)
        y += 16

        # Unit section
        surf = self.font_header.render("UNIT", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (x, y))
        y += surf.get_height() + 6

        unit = self.map.get_unit(tile.row, tile.col) if tile else None
        if unit:
            btn_w, btn_h = 50, 20
            btn_x = panel_x + PANEL_WIDTH - pad - btn_w
            name_surf = self.font_body.render(unit.unit_type.capitalize(), True, TEXT_COLOR)
            self.screen.blit(name_surf, (x + 4, y + (btn_h - name_surf.get_height()) // 2))
            self.move_button_rect = self._draw_button(
                btn_x, y, btn_w, btn_h, "Move",
                active=move_mode, disabled=unit.moves_remaining == 0,
            )
            y += btn_h + 6
            surf = self.font_body.render(f"Moves: {unit.moves_remaining:g} / {unit.max_moves:g}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 12

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
