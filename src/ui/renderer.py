import math
import os
import pygame
from src.game.map import TERRAIN_TYPES

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets')

HEX_SIZE = 32
MARGIN = 40
PANEL_WIDTH = 220

COLOR_PARCHMENT = (240, 220, 185)

TERRAIN_COLORS = {
    # 'desert':   (210, 180, 100),
    # 'hills':    (139, 100,  60),
    # 'river':    (100, 180,  80),
    # 'mountain': (140, 140, 140),
    'desert':   (200, 175, 115),
    'hills':    (130, 102,  68),
    'river':    (105, 168,  88),
    'mountain': (140, 140, 140),
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
    'river':    'grass',
}

ICON_SIZE   = 40
ICON_OFFSET = 10
RIVER_IMG_SCALE = 1.2  # bleed past tile edge so adjacent river images connect


class Renderer:
    def __init__(self, game_map):
        self.map = game_map
        w = math.sqrt(3) * HEX_SIZE
        self.map_w = int(game_map.cols * w + w / 2 + 2 * MARGIN)
        screen_h = int((game_map.rows - 1) * HEX_SIZE * 1.5 + 2 * HEX_SIZE + 2 * MARGIN)
        self.offset_x = MARGIN + w / 2
        self.offset_y = MARGIN + HEX_SIZE
        self.screen = pygame.display.set_mode((self.map_w + PANEL_WIDTH, screen_h))
        pygame.display.set_caption("HexGame")
        self.font_header = pygame.font.SysFont('segoeui', 13, bold=True)
        self.font_body = pygame.font.SysFont('segoeui', 13)
        self.font_small = pygame.font.SysFont('segoeui', 10)
        hex_w = int(math.sqrt(3) * HEX_SIZE)
        hex_h = 2 * HEX_SIZE
        self.terrain_images = {}
        terrain_dir = os.path.join(_ASSETS_DIR, 'terrain')
        for name in TERRAIN_TYPES:
            img_file = _TERRAIN_IMG_FILES.get(name, name)
            path = os.path.join(terrain_dir, f'{img_file}.png')
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self.terrain_images[name] = pygame.transform.scale(img, (hex_w, hex_h))
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
        self.assign_pops_button_rect = None
        self.assign_input_rects = {}
        self.assign_confirm_rect = None
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
             moves_remaining=None, assign_popup_data=None):
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
                img = self.terrain_images.get(self.map.tiles[r][c].terrain)
                if img:
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
        for (r, c) in self.map.cities:
            cx, cy = all_centers[(r, c)]
            icon = self.icons.get('castle')
            if icon:
                self.screen.blit(icon, (int(cx) - ICON_OFFSET - icon.get_width() // 2,
                                        int(cy) - icon.get_height() // 2))
            else:
                s = 6
                rect = pygame.Rect(int(cx) - s, int(cy) - s, s * 2, s * 2)
                pygame.draw.rect(self.screen, COLOR_CITY, rect)
                pygame.draw.rect(self.screen, COLOR_CITY_BORDER, rect, 1)

        # Pass 7: unit markers
        for (r, c) in self.map.units:
            cx, cy = all_centers[(r, c)]
            icon = self.icons.get('sword')
            if icon:
                self.screen.blit(icon, (int(cx) + ICON_OFFSET - icon.get_width() // 2,
                                        int(cy) - icon.get_height() // 2))
            else:
                self._draw_unit_marker(int(cx), int(cy))

        self._draw_panel(selected_tile, move_mode)

        self.terrain_option_rects = {}
        self.river_option_rects = {}
        if assign_popup_data is not None:
            self._draw_assign_popup(assign_popup_data)
        elif river_popup_active:
            self._draw_river_popup(selected_tile)
        elif terrain_popup_active:
            self._draw_terrain_popup(selected_tile)
        elif save_popup_active:
            self._draw_save_popup(save_popup_text)

        pygame.display.flip()

    def _draw_panel(self, tile, move_mode=False):
        self.move_button_rect = None
        self.save_map_button_rect = None
        self.change_terrain_button_rect = None
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

            surf = self.font_body.render(f"Food: {city.food_stockpile:.1f}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 4

            surf = self.font_body.render(f"Unassigned: {city.unassigned_pops}", True, TEXT_COLOR)
            self.screen.blit(surf, (x + 4, y))
            y += surf.get_height() + 6

            btn_w2 = PANEL_WIDTH - pad * 2
            btn_h2 = 22
            has_jobs = bool(city.jobs)
            if has_jobs:
                self.assign_pops_button_rect = self._draw_button(panel_x + pad, y, btn_w2, btn_h2, "Assign Pops")
            else:
                self._draw_button(panel_x + pad, y, btn_w2, btn_h2, "Assign Pops", disabled=True)
            y += btn_h2 + 8

            for job in city.jobs:
                surf = self.font_body.render(f"{job.label}: {job.assigned}/{job.slots} slots", True, TEXT_COLOR)
                self.screen.blit(surf, (x + 4, y))
                y += surf.get_height() + 2
                yd = job.yield_display()
                if yd:
                    surf = self.font_body.render(yd, True, TEXT_COLOR)
                    self.screen.blit(surf, (x + 4, y))
                    y += surf.get_height() + 6

        # End Turn button anchored to bottom
        btn_w = PANEL_WIDTH - pad * 2
        btn_h = 28
        self.end_turn_button_rect = self._draw_button(
            panel_x + pad, self.screen.get_height() - pad - btn_h, btn_w, btn_h, "End Turn"
        )

    def _draw_assign_popup(self, data):
        city = data['city']
        inputs = data['inputs']
        focused = data['focused']

        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        row_h = 32
        W = 260
        H = 50 + len(city.jobs) * row_h + 52
        sx = (self.screen.get_width() - W) // 2
        sy = (self.screen.get_height() - H) // 2
        pygame.draw.rect(self.screen, (40, 40, 55), (sx, sy, W, H), border_radius=6)
        pygame.draw.rect(self.screen, PANEL_DIVIDER, (sx, sy, W, H), 1, border_radius=6)

        surf = self.font_header.render("ASSIGN POPS", True, HEADER_TEXT_COLOR)
        self.screen.blit(surf, (sx + 16, sy + 14))

        self.assign_input_rects = {}
        input_w = 50
        y = sy + 42
        for job in city.jobs:
            label_surf = self.font_body.render(job.label, True, TEXT_COLOR)
            self.screen.blit(label_surf, (sx + 16, y + (row_h - label_surf.get_height()) // 2))

            max_surf = self.font_body.render(f"/ {job.slots}", True, (130, 130, 150))
            max_x = sx + W - 16 - input_w - 6 - max_surf.get_width()
            self.screen.blit(max_surf, (max_x, y + (row_h - max_surf.get_height()) // 2))

            input_rect = pygame.Rect(sx + W - 16 - input_w, y + 4, input_w, row_h - 8)
            is_focused = focused == job.job_type
            pygame.draw.rect(self.screen, (25, 25, 35), input_rect, border_radius=3)
            pygame.draw.rect(self.screen, COLOR_SELECTED if is_focused else PANEL_DIVIDER,
                             input_rect, 1, border_radius=3)
            text = inputs.get(job.job_type, '') + ('|' if is_focused else '')
            t_surf = self.font_body.render(text, True, TEXT_COLOR)
            self.screen.blit(t_surf, (
                input_rect.x + input_rect.width - t_surf.get_width() - 6,
                input_rect.y + (input_rect.height - t_surf.get_height()) // 2,
            ))

            self.assign_input_rects[job.job_type] = input_rect
            y += row_h

        btn_y = sy + H - 44
        self.assign_confirm_rect = self._draw_button(sx + 16, btn_y, W - 32, 26, "Confirm")

        hint = self.font_body.render("Esc to cancel", True, (110, 110, 130))
        self.screen.blit(hint, (sx + 16, sy + H - 18))

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
