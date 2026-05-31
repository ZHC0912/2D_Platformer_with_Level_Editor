import pygame, os, json
from settings import *
from tiles import TileMap, Tile
from level import Level
from enemies import make_enemy
from weapons import WeaponPickup


PANEL_W = 220
PANEL_BG = (20, 20, 35)

# Tool modes
MODE_TILE     = "tile"
MODE_ENEMY    = "enemy"
MODE_PICKUP   = "pickup"
MODE_SPAWN    = "spawn"
MODE_ERASE    = "erase"

ENEMY_COLORS = {E_BASIC: (180,60,60), E_SHOOTER: (180,100,30), E_DASH: (100,30,180)}

def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


class LevelEditor:
    def __init__(self, screen, level=None):
        self.screen = screen
        self.level  = level or Level()
        self.cam_x  = 0
        self.cam_y  = 0
        self.cam_speed = 6

        # Tool state
        self.mode          = MODE_TILE
        self.selected_tile = T_GROUND
        self.selected_enemy = E_BASIC
        self.selected_pickup = W_SWORD
        self.enemy_param   = 120   # patrol_range or detect_radius
        self.placing_enemy = False

        self.fnt  = _font(14)
        self.fnt_sm = _font(12)
        self.fnt_md = _font(16, bold=True)

        self.msg = ""
        self.msg_timer = 0

        self.save_name = self.level.name
        self._input_active = False
        self._input_text   = ""
        self._input_field  = None

        # viewport is entire screen minus right panel
        self.view_w = SCREEN_W - PANEL_W
        self.view_h = SCREEN_H

        # load file dialog state
        self._file_list = []
        self._show_load = False
        self._load_scroll = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def get_level(self):
        return self.level

    def run(self):
        """Blocking editor loop. Returns when user exits editor."""
        clock = pygame.time.Clock()
        running = True
        while running:
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    return "quit"
                result = self._handle_event(ev)
                if result == "play":
                    return "play"
                if result == "menu":
                    return "menu"
            self._handle_scroll(pygame.key.get_pressed())
            self._draw()
            clock.tick(FPS)
        return "menu"

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            if self._input_active:
                return self._handle_text_input(ev)
            if ev.key == pygame.K_ESCAPE:
                return "menu"
            if ev.key == pygame.K_F5:
                return "play"
        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            if self._show_load and ev.button == 1:
                return self._load_overlay_click(mx, my)
            if mx >= self.view_w:
                return self._panel_click(mx - self.view_w, my, ev.button)
            else:
                return self._canvas_click(mx, my, ev.button)
        if ev.type == pygame.MOUSEMOTION:
            if pygame.mouse.get_pressed()[0]:
                mx, my = ev.pos
                if mx < self.view_w:
                    self._canvas_paint(mx, my, "left")
            if pygame.mouse.get_pressed()[2]:
                mx, my = ev.pos
                if mx < self.view_w:
                    self._canvas_paint(mx, my, "right")
        return None

    def _handle_text_input(self, ev):
        if ev.key == pygame.K_RETURN:
            if self._input_field == "name":
                self.level.name = self._input_text or "Untitled"
                self.save_name  = self.level.name
            elif self._input_field == "param":
                try:
                    self.enemy_param = int(self._input_text)
                except ValueError:
                    pass
            self._input_active = False
            self._input_text   = ""
        elif ev.key == pygame.K_BACKSPACE:
            self._input_text = self._input_text[:-1]
        elif ev.unicode and len(self._input_text) < 30:
            self._input_text += ev.unicode
        return None

    def _handle_scroll(self, keys):
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.cam_x -= self.cam_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.cam_x += self.cam_speed
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.cam_y -= self.cam_speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.cam_y += self.cam_speed
        max_x = self.level.tilemap.cols * TILE_SIZE - self.view_w
        max_y = self.level.tilemap.rows * TILE_SIZE - self.view_h
        self.cam_x = max(0, min(self.cam_x, max(0, max_x)))
        self.cam_y = max(0, min(self.cam_y, max(0, max_y)))

    def _canvas_click(self, mx, my, button):
        wx = mx + self.cam_x
        wy = my + self.cam_y
        col = int(wx // TILE_SIZE)
        row = int(wy // TILE_SIZE)

        if button == 1:
            self._place_at(col, row, wx, wy)
        elif button == 3:
            self._erase_at(col, row, wx, wy)
        return None

    def _canvas_paint(self, mx, my, side):
        wx = mx + self.cam_x
        wy = my + self.cam_y
        col = int(wx // TILE_SIZE)
        row = int(wy // TILE_SIZE)
        if side == "left":
            if self.mode in (MODE_TILE, MODE_ERASE, MODE_SPAWN):
                self._place_at(col, row, wx, wy)
        else:
            self._erase_at(col, row, wx, wy)

    def _place_at(self, col, row, wx, wy):
        tm = self.level.tilemap
        if self.mode == MODE_TILE:
            tm.set_tile(col, row, self.selected_tile)
        elif self.mode == MODE_ERASE:
            tm.set_tile(col, row, T_EMPTY)
            # also erase enemies/pickups at position
            self._erase_objects_at(wx, wy)
        elif self.mode == MODE_SPAWN:
            tm.set_tile(col, row, T_SPAWN)
            self.level.spawn_x = col * TILE_SIZE + 4
            self.level.spawn_y = row * TILE_SIZE - 44
        elif self.mode == MODE_ENEMY:
            cx = col * TILE_SIZE + TILE_SIZE // 2
            cy = row * TILE_SIZE + TILE_SIZE
            ed = {"type": self.selected_enemy, "x": cx, "y": cy,
                  "patrol_range": self.enemy_param,
                  "detect_radius": self.enemy_param}
            self.level.enemy_data.append(ed)
            self.level._spawn_enemies()
        elif self.mode == MODE_PICKUP:
            cx = col * TILE_SIZE + TILE_SIZE // 2
            cy = (row + 1) * TILE_SIZE
            pd = {"weapon": self.selected_pickup, "x": cx, "y": cy}
            self.level.pickup_data.append(pd)
            self.level._spawn_pickups()

    def _erase_at(self, col, row, wx, wy):
        self.level.tilemap.set_tile(col, row, T_EMPTY)
        self._erase_objects_at(wx, wy)

    def _erase_objects_at(self, wx, wy):
        erase_r = pygame.Rect(wx - TILE_SIZE//2, wy - TILE_SIZE//2, TILE_SIZE, TILE_SIZE)
        # enemies
        new_ed = []
        for ed in self.level.enemy_data:
            er = pygame.Rect(ed["x"] - 14, ed["y"] - 38, 28, 38)
            if not erase_r.colliderect(er):
                new_ed.append(ed)
        if len(new_ed) != len(self.level.enemy_data):
            self.level.enemy_data = new_ed
            self.level._spawn_enemies()
        # pickups
        new_pd = []
        for pd in self.level.pickup_data:
            pr = pygame.Rect(pd["x"] - 20, pd["y"] - 20, 40, 40)
            if not erase_r.colliderect(pr):
                new_pd.append(pd)
        if len(new_pd) != len(self.level.pickup_data):
            self.level.pickup_data = new_pd
            self.level._spawn_pickups()

    # ── Panel ─────────────────────────────────────────────────────────────────

    def _panel_click(self, px, py, button):
        if button != 1:
            return None

        y = 10
        # Mode buttons
        modes = [
            (MODE_TILE,   "Tiles"),
            (MODE_ENEMY,  "Enemies"),
            (MODE_PICKUP, "Pickups"),
            (MODE_SPAWN,  "Set Spawn"),
            (MODE_ERASE,  "Erase"),
        ]
        for mode, label in modes:
            r = pygame.Rect(5, y, PANEL_W-10, 28)
            if r.collidepoint(px, py):
                self.mode = mode
                return None
            y += 32

        y += 4
        if self.mode == MODE_TILE:
            tiles = [(T_GROUND,"Ground"),(T_PLATFORM,"Platform"),
                     (T_SPIKE,"Spike"),(T_COIN,"Coin")]
            for tid, tname in tiles:
                r = pygame.Rect(5, y, PANEL_W-10, 24)
                if r.collidepoint(px, py):
                    self.selected_tile = tid
                y += 28
        elif self.mode == MODE_ENEMY:
            for etype in [E_BASIC, E_SHOOTER, E_DASH]:
                r = pygame.Rect(5, y, PANEL_W-10, 24)
                if r.collidepoint(px, py):
                    self.selected_enemy = etype
                y += 28
            # param field
            param_r = pygame.Rect(5, y+24, PANEL_W-10, 24)
            if param_r.collidepoint(px, py):
                self._input_active = True
                self._input_field = "param"
                self._input_text  = str(self.enemy_param)
        elif self.mode == MODE_PICKUP:
            for wid in [W_SWORD, W_BOW, W_STAFF]:
                r = pygame.Rect(5, y, PANEL_W-10, 24)
                if r.collidepoint(px, py):
                    self.selected_pickup = wid
                y += 28

        # Bottom buttons (save/load/play)
        btn_y = SCREEN_H - 180
        for label, action in [("Save Level", "save"), ("Load Level", "load"),
                               ("Play (F5)", "play"), ("Main Menu", "menu")]:
            r = pygame.Rect(5, btn_y, PANEL_W-10, 32)
            if r.collidepoint(px, py):
                if action == "save":
                    self._save_current()
                elif action == "load":
                    self._refresh_file_list()
                    self._show_load = not self._show_load
                elif action == "play":
                    return "play"
                elif action == "menu":
                    return "menu"
            btn_y += 36

        # Level name field
        name_r = pygame.Rect(5, SCREEN_H - 38, PANEL_W-10, 28)
        if name_r.collidepoint(px, py):
            self._input_active = True
            self._input_field = "name"
            self._input_text  = self.level.name

        return None

    def _save_current(self):
        os.makedirs(LEVELS_DIR, exist_ok=True)
        safe = self.level.name.replace(" ", "_").replace("/", "_") or "untitled"
        path = os.path.join(LEVELS_DIR, f"{safe}.json")
        self.level.save_to_file(path)
        self._show_message(f"Saved: {safe}.json")

    def _refresh_file_list(self):
        if os.path.isdir(LEVELS_DIR):
            self._file_list = sorted(f for f in os.listdir(LEVELS_DIR) if f.endswith(".json"))
        else:
            self._file_list = []

    def _load_file(self, fname):
        path = os.path.join(LEVELS_DIR, fname)
        try:
            self.level = Level.load_from_file(path)
            self.save_name = self.level.name
            self._show_message(f"Loaded: {fname}")
        except Exception as e:
            self._show_message(f"Error: {e}")

    def _load_overlay_click(self, mx, my):
        box_w, box_h = 500, 400
        box_x = SCREEN_W//2 - box_w//2
        box_y = SCREEN_H//2 - box_h//2
        # click outside box closes it
        if not pygame.Rect(box_x, box_y, box_w, box_h).collidepoint(mx, my):
            self._show_load = False
            return None
        for i, fname in enumerate(self._file_list):
            fy = box_y + 50 + i * 26
            if fy > box_y + box_h - 20:
                break
            r = pygame.Rect(box_x + 10, fy, box_w - 20, 24)
            if r.collidepoint(mx, my):
                self._load_file(fname)
                self._show_load = False
                return None
        return None

    def _show_message(self, text, frames=120):
        self.msg = text
        self.msg_timer = frames

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(DARK)
        self._draw_canvas()
        self._draw_panel()
        if self._show_load:
            self._draw_load_overlay()
        if self.msg_timer > 0:
            self.msg_timer -= 1
            t = self.fnt_md.render(self.msg, True, YELLOW)
            self.screen.blit(t, t.get_rect(center=(self.view_w//2, 30)))
        pygame.display.flip()

    def _draw_canvas(self):
        surf = self.screen.subsurface((0, 0, self.view_w, self.view_h))
        surf.fill((30, 35, 50))

        # grid
        start_c = int(self.cam_x // TILE_SIZE)
        start_r = int(self.cam_y // TILE_SIZE)
        end_c   = start_c + self.view_w // TILE_SIZE + 2
        end_r   = start_r + self.view_h // TILE_SIZE + 2
        for c in range(start_c, min(end_c, self.level.tilemap.cols)):
            x = c * TILE_SIZE - self.cam_x
            pygame.draw.line(surf, (40, 45, 60), (x, 0), (x, self.view_h))
        for r in range(start_r, min(end_r, self.level.tilemap.rows)):
            y = r * TILE_SIZE - self.cam_y
            pygame.draw.line(surf, (40, 45, 60), (0, y), (self.view_w, y))

        # tiles
        self.level.tilemap.draw(surf, (int(self.cam_x), int(self.cam_y)))

        # pickups
        for pk in self.level.pickups:
            surf.blit(pk.image, (pk.rect.x - self.cam_x, pk.rect.y - self.cam_y))

        # enemies
        for enemy in self.level.enemies:
            enemy.draw(surf, (int(self.cam_x), int(self.cam_y)))

        # spawn marker
        sx = self.level.spawn_x - self.cam_x
        sy = self.level.spawn_y - self.cam_y
        pygame.draw.circle(surf, CYAN, (int(sx), int(sy)), 8, 2)

        # cursor tile highlight
        mx, my = pygame.mouse.get_pos()
        if mx < self.view_w:
            col = int((mx + self.cam_x) // TILE_SIZE)
            row = int((my + self.cam_y) // TILE_SIZE)
            hx  = col * TILE_SIZE - int(self.cam_x)
            hy  = row * TILE_SIZE - int(self.cam_y)
            hl  = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            hl.fill((255, 255, 255, 40))
            surf.blit(hl, (hx, hy))

    def _draw_panel(self):
        panel = pygame.Surface((PANEL_W, SCREEN_H))
        panel.fill(PANEL_BG)

        y = 10
        title = self.fnt_md.render("LEVEL EDITOR", True, CYAN)
        panel.blit(title, (PANEL_W//2 - title.get_width()//2, y))
        y += 28

        modes = [
            (MODE_TILE,   "Tiles"),
            (MODE_ENEMY,  "Enemies"),
            (MODE_PICKUP, "Pickups"),
            (MODE_SPAWN,  "Set Spawn"),
            (MODE_ERASE,  "Erase"),
        ]
        for mode, label in modes:
            sel = (self.mode == mode)
            pygame.draw.rect(panel, (60, 80, 120) if sel else (40, 50, 70),
                             (5, y, PANEL_W-10, 28), border_radius=4)
            if sel:
                pygame.draw.rect(panel, CYAN, (5, y, PANEL_W-10, 28), 2, border_radius=4)
            t = self.fnt.render(label, True, WHITE if sel else LTGRAY)
            panel.blit(t, (12, y+5))
            y += 32

        y += 8
        pygame.draw.line(panel, GRAY, (5, y), (PANEL_W-5, y))
        y += 8

        if self.mode == MODE_TILE:
            panel.blit(self.fnt_sm.render("Tile type:", True, LTGRAY), (5, y))
            y += 18
            tiles = [(T_GROUND,"Ground"),(T_PLATFORM,"Platform"),
                     (T_SPIKE,"Spike"),(T_COIN,"Coin")]
            for tid, tname in tiles:
                sel = (self.selected_tile == tid)
                c = TILE_COLORS.get(tid, GRAY)
                pygame.draw.rect(panel, c, (5, y, 18, 18))
                if sel:
                    pygame.draw.rect(panel, WHITE, (5, y, 18, 18), 2)
                t = self.fnt_sm.render(tname, True, WHITE if sel else LTGRAY)
                panel.blit(t, (28, y+2))
                y += 24

        elif self.mode == MODE_ENEMY:
            panel.blit(self.fnt_sm.render("Enemy type:", True, LTGRAY), (5, y))
            y += 18
            for etype in [E_BASIC, E_SHOOTER, E_DASH]:
                sel = (self.selected_enemy == etype)
                ec  = ENEMY_COLORS[etype]
                pygame.draw.rect(panel, ec, (5, y, 18, 18))
                if sel:
                    pygame.draw.rect(panel, WHITE, (5, y, 18, 18), 2)
                label = etype.capitalize()
                t = self.fnt_sm.render(label, True, WHITE if sel else LTGRAY)
                panel.blit(t, (28, y+2))
                y += 24
            y += 4
            panel.blit(self.fnt_sm.render("Patrol/Detect radius:", True, LTGRAY), (5, y))
            y += 16
            inp_text = self._input_text if (self._input_active and self._input_field == "param") else str(self.enemy_param)
            pygame.draw.rect(panel, (50, 50, 70), (5, y, PANEL_W-10, 24), border_radius=3)
            if self._input_active and self._input_field == "param":
                pygame.draw.rect(panel, CYAN, (5, y, PANEL_W-10, 24), 2, border_radius=3)
            t = self.fnt.render(inp_text, True, WHITE)
            panel.blit(t, (10, y+4))

        elif self.mode == MODE_PICKUP:
            panel.blit(self.fnt_sm.render("Weapon pickup:", True, LTGRAY), (5, y))
            y += 18
            for wid in [W_SWORD, W_BOW, W_STAFF]:
                sel = (self.selected_pickup == wid)
                wc  = WeaponPickup.COLORS.get(wid, WHITE)
                pygame.draw.rect(panel, wc, (5, y, 18, 18))
                if sel:
                    pygame.draw.rect(panel, WHITE, (5, y, 18, 18), 2)
                t = self.fnt_sm.render(wid.capitalize(), True, WHITE if sel else LTGRAY)
                panel.blit(t, (28, y+2))
                y += 24

        elif self.mode == MODE_SPAWN:
            panel.blit(self.fnt_sm.render("Click canvas to set", True, LTGRAY), (5, y))
            y += 18
            panel.blit(self.fnt_sm.render("spawn point.", True, LTGRAY), (5, y))

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_y = SCREEN_H - 180
        for label, color in [("Save Level", GREEN), ("Load Level", BLUE),
                              ("Play (F5)", CYAN), ("Main Menu", ORANGE)]:
            pygame.draw.rect(panel, color, (5, btn_y, PANEL_W-10, 32), border_radius=5)
            t = self.fnt.render(label, True, BLACK)
            panel.blit(t, (PANEL_W//2 - t.get_width()//2, btn_y+8))
            btn_y += 36

        # Level name
        panel.blit(self.fnt_sm.render("Level Name:", True, LTGRAY), (5, SCREEN_H - 56))
        name_display = self._input_text if (self._input_active and self._input_field == "name") else self.level.name
        pygame.draw.rect(panel, (50, 50, 70), (5, SCREEN_H-38, PANEL_W-10, 28), border_radius=3)
        if self._input_active and self._input_field == "name":
            pygame.draw.rect(panel, CYAN, (5, SCREEN_H-38, PANEL_W-10, 28), 2, border_radius=3)
        nt = self.fnt.render(name_display, True, WHITE)
        panel.blit(nt, (10, SCREEN_H-34))

        # Controls hint
        hint = self.fnt_sm.render("WASD: scroll  ESC: menu", True, GRAY)
        panel.blit(hint, (5, SCREEN_H - 12))

        self.screen.blit(panel, (self.view_w, 0))

    def _draw_load_overlay(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 500, 400
        box_x = SCREEN_W//2 - box_w//2
        box_y = SCREEN_H//2 - box_h//2
        pygame.draw.rect(self.screen, (20, 25, 40), (box_x, box_y, box_w, box_h), border_radius=8)
        pygame.draw.rect(self.screen, CYAN, (box_x, box_y, box_w, box_h), 2, border_radius=8)

        title = self.fnt_md.render("Load Level", True, CYAN)
        self.screen.blit(title, (box_x + box_w//2 - title.get_width()//2, box_y + 10))

        if not self._file_list:
            t = self.fnt.render("No levels found.", True, LTGRAY)
            self.screen.blit(t, (box_x + 20, box_y + 50))
        else:
            for i, fname in enumerate(self._file_list):
                fy = box_y + 50 + i*26
                if fy > box_y + box_h - 20:
                    break
                hover = pygame.Rect(box_x+10, fy, box_w-20, 24).collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen, (50,60,80) if hover else (30,35,50),
                                 (box_x+10, fy, box_w-20, 24), border_radius=3)
                t = self.fnt.render(fname, True, WHITE)
                self.screen.blit(t, (box_x+15, fy+3))

        close = self.fnt.render("ESC / click outside to close", True, GRAY)
        self.screen.blit(close, (box_x + box_w//2 - close.get_width()//2, box_y + box_h - 26))
