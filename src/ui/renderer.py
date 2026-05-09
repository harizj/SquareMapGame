import math
import os
import pygame
from src.game.city import STOCKPILE_MAX
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
    # 50% blended with parchment (240, 220, 185)
    # 'desert':   (220, 197, 150),
    # 'hills':    (185, 161, 126),
    # 'river':    (172, 194, 136),
    # 'mountain': (190, 180, 162),
}
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

# Maps terrain name → image filename stem when they differ
_TERRAIN_IMG_FILES = {
    'mountain': 'mountains',
}

ICON_SIZE      = 40
ICON_OFFSET    = 10
RIVER_IMG_SCALE = 1.2  # bleed past tile edge so adjacent river images connect
LOG_PANEL_WIDTH = 180


class Renderer:
    def __init__(self, game_map):
        self.map = game_map
        w = math.sqrt(3) * HEX_SIZE
        map_area_w = int(game_map.cols * w + w / 2 + 2 * MARGIN)
        self.map_w = LOG_PANEL_WIDTH + map_area_w
        screen_h = int((game_map.rows - 1) * HEX_SIZE * 1.5 + 2 * HEX_SIZE + 2 * MARGIN)
        self.offset_x = LOG_PANEL_WIDTH + MARGIN + w / 2
        self.offset_y = MARGIN + HEX_SIZE
        self.screen = pygame.display.set_mode((self.map_w + PANEL_WIDTH, screen_h))
        pygame.display.set_caption("HexGame")
        self.font_header = pygame.font.SysFont('segoeui', 13, bold=True)
        self.font_body = pygame.font.SysFont('segoeui', 13)
        self.font_small = pygame.font.SysFont('segoeui', 10)
        self.font_city = pygame.font.SysFont('tempussansitc', 12, bold=True)
        hex_w = int(math.sqrt(3) * HEX_SIZE)
        hex_h = 2 * HEX_SIZE
        self.terrain_images = {}
        terrain_dir = os.path.join(_ASSETS_DIR, 'terrain')
        for name in TERRAIN_TYPES:
            img_file = _TERRAIN_IMG_FILES.get(name, name)
            variants = []
            for i in range(1, 5):
                path = os.path.join(terrain_dir, f'{img_file}{i}.png')
                if os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    variants.append(pygame.transform.scale(img, (hex_w, hex_h)))
            if variants:
                self.terrain_images[name] = variants
        self.icons = {}
        icons_dir = os.path.join(_ASSETS_DIR, 'icons')
        for icon_name in ('castle', 'sword'):
            path = os.path.join(icons_dir, f'{icon_name}.png')
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self.icons[icon_name] = pygame.transform.scale(img, (ICON_SIZE, ICON_SIZE))
        self.river_imgs = {}
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
                base = pygame.transform.scale(
                    pygame.image.load(path).convert_alpha(),
                    (int(hex_w * RIVER_IMG_SCALE), int(hex_h * RIVER_IMG_SCALE))
                )
                for key, angle in entries:
                    self.river_imgs[key] = pygame.transform.rotate(base, angle)
        self.move_button_rect = None
        self.end_turn_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.draw_river_button_rect = None
        self.rebalance_pops_button_rect = None
        self.terrain_option_rects = {}
        self.river_option_rects = {}

    def _hex_to_pixel(self, row, col):
        w = math.sqrt(3) * HEX_SIZE
        x = col * w + (w / 2 if row % 2 == 1 else 0)
        y = row * HEX_SIZE * 1.5
        return x, y

    def _hex_corners(self, cx, cy):
        corners = []
        for i in range(6):
            angle_rad = math.radians(60 * i - 30)
            corners.append((cx + HEX_SIZE * math.cos(angle_rad), cy + HEX_SIZE * math.sin(angle_rad)))
        return corners

    def _pixel_to_hex(self, px, py):
        x = px - self.offset_x
        y = py - self.offset_y
        q = (x * math.sqrt(3) / 3 - y / 3) / HEX_SIZE
        r = (y * 2 / 3) / HEX_SIZE
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
        pygame.draw.line(self.screen, COLOR_UNIT_SHADOW, (cx - s, cy - s), (cx + s, cy + s), 4)
        pygame.draw.line(self.screen, COLOR_UNIT_SHADOW, (cx + s, cy - s), (cx - s, cy + s), 4)
        pygame.draw.line(self.screen, COLOR_UNIT, (cx - s, cy - s), (cx + s, cy + s), 2)
        pygame.draw.line(self.screen, COLOR_UNIT, (cx + s, cy - s), (cx - s, cy + s), 2)

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
        apothem = HEX_SIZE * math.sqrt(3) / 2

        # Pass 1: hex fills
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                tile = self.map.tiles[r][c]
                px, py = self._hex_to_pixel(r, c)
                cx, cy = px + self.offset_x, py + self.offset_y
                corners = self._hex_corners(cx, cy)
                all_corners[(r, c)] = corners
                all_centers[(r, c)] = (cx, cy)
                pygame.draw.polygon(self.screen, TERRAIN_COLORS.get(tile.terrain, BG_COLOR), corners)

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

        # Pass 3: hex outlines (skip selected and reachable)
        for r in range(self.map.rows):
            for c in range(self.map.cols):
                if selected_tile and self.map.tiles[r][c] is selected_tile:
                    continue
                if (r, c) in reachable:
                    continue
                pygame.draw.polygon(self.screen, COLOR_OUTLINE, all_corners[(r, c)], 1)

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
        for (r, c), city in self.map.cities.items():
            cx, cy = all_centers[(r, c)]
            icon = self.icons.get('castle')
            if icon:
                self.screen.blit(icon, (int(cx) - icon.get_width() // 2,
                                        int(cy) - icon.get_height() // 2))
                name_y = int(cy) + icon.get_height() // 2 - 12
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

        # Pass 7: unit markers
        for (r, c) in self.map.units:
            cx, cy = all_centers[(r, c)]
            icon = self.icons.get('sword')
            if icon:
                self.screen.blit(icon, (int(cx) - icon.get_width() // 2,
                                        int(cy) - icon.get_height() // 2))
            else:
                self._draw_unit_marker(int(cx), int(cy))

        self._draw_log_panel(game_log or [])
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

    def _draw_log_panel(self, game_log):
        pygame.draw.rect(self.screen, PANEL_BG, (0, 0, LOG_PANEL_WIDTH, self.screen.get_height()))
        pygame.draw.line(self.screen, PANEL_DIVIDER,
                         (LOG_PANEL_WIDTH - 1, 0), (LOG_PANEL_WIDTH - 1, self.screen.get_height()), 1)
        pad = 10
        y = 16
        surf = self.font_header.render("LOG", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (pad, y))
        y += surf.get_height() + 6
        pygame.draw.line(self.screen, PANEL_DIVIDER, (pad, y), (LOG_PANEL_WIDTH - pad, y), 1)
        y += 8

        line_h = self.font_small.get_height() + 3
        max_lines = (self.screen.get_height() - y - 8) // line_h
        visible = game_log[-max_lines:] if len(game_log) > max_lines else game_log
        max_w = LOG_PANEL_WIDTH - pad * 2
        for msg in reversed(visible):
            surf = self.font_small.render(msg, True, TEXT_COLOR)
            if surf.get_width() > max_w:
                while surf.get_width() > max_w and msg:
                    msg = msg[:-1]
                    surf = self.font_small.render(msg + '…', True, TEXT_COLOR)
            self.screen.blit(surf, (pad, y))
            y += line_h

    def _draw_panel(self, tile, move_mode=False):
        self.move_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
        self.admin_minus_rect = None
        self.admin_plus_rect = None
        self.draw_river_button_rect = None
        self.assign_pops_button_rect = None
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
        y += btn_h + 12

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
        else:
            surf = self.font_body.render("No unit in tile", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 12

        # City section
        city = self.map.cities.get((tile.row, tile.col)) if tile else None
        if city:
            pygame.draw.line(self.screen, PANEL_DIVIDER, (x, y), (panel_x + PANEL_WIDTH - pad, y), 1)
            y += 14
            surf = self.font_header.render("CITY", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 6

            surf = self.font_body.render(city.name, True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 4

            bar_w = PANEL_WIDTH - pad * 2
            bar_h = 8
            bar_x = panel_x + pad

            # Food stockpile bar (fills to current stockpile max)
            food_max = city._stockpile_max()
            label = self.font_small.render("Food", True, TEXT_COLOR)
            val = self.font_small.render(f"{int(city.food_stockpile)}/{food_max}", True, TEXT_COLOR)
            self.screen.blit(label, (bar_x, y))
            self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
            y += label.get_height() + 2
            pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
            fill_w = int(bar_w * min(city.food_stockpile, food_max) / food_max)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (120, 190, 80), (bar_x, y, fill_w, bar_h), border_radius=2)
            pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
            y += bar_h + 8

            # Growth progress bar
            label = self.font_small.render("Growth", True, TEXT_COLOR)
            val = self.font_small.render(f"{int(city.growth_progress)}/100", True, TEXT_COLOR)
            self.screen.blit(label, (bar_x, y))
            self.screen.blit(val, (bar_x + bar_w - val.get_width(), y))
            y += label.get_height() + 2
            pygame.draw.rect(self.screen, (30, 30, 40), (bar_x, y, bar_w, bar_h), border_radius=2)
            fill_w = int(bar_w * min(city.growth_progress, 100) / 100)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (55, 120, 30), (bar_x, y, fill_w, bar_h), border_radius=2)
            pygame.draw.rect(self.screen, PANEL_DIVIDER, (bar_x, y, bar_w, bar_h), 1, border_radius=2)
            y += bar_h + 8

            btn_w2 = PANEL_WIDTH - pad * 2
            btn_h2 = 22
            self.rebalance_pops_button_rect = self._draw_button(panel_x + pad, y, btn_w2, btn_h2, "Rebalance Pops")
            y += btn_h2 + 10

            surf = self.font_header.render("POPS", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 4
            btn_s = 16
            for job in city.jobs:
                if job.job_type == 'administrator':
                    label_surf = self.font_body.render(
                        f"{job.assigned} {job.label.lower()}", True, TEXT_COLOR)
                    self.screen.blit(label_surf, (x + 4, y + (btn_s - label_surf.get_height()) // 2))
                    self.admin_plus_rect = self._draw_button(
                        panel_x + PANEL_WIDTH - pad - btn_s, y, btn_s, btn_s, "+")
                    self.admin_minus_rect = self._draw_button(
                        panel_x + PANEL_WIDTH - pad - btn_s * 2 - 3, y, btn_s, btn_s, "-")
                    y += btn_s + 4
                else:
                    surf = self.font_body.render(f"{job.assigned} {job.label.lower()}", True, TEXT_COLOR)
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 2
            y += 6

            surf = self.font_header.render("AVAILABLE JOBS", True, HEADER_TEXT_COLOR)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 4
            for job in city.jobs:
                if job.job_type == 'farm':
                    surf = self.font_body.render(f"{job.available_slots} {job.label.lower()}", True, TEXT_COLOR)
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 2

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
