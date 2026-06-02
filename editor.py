import pygame, os, json
from settings import *
from tiles import TileMap, Tile
from level import Level, Checkpoint, WinDoor
from enemies import make_enemy, ENEMY_CONFIG
from weapons import WeaponPickup
from ui_helpers import HERO_ORB_CFG


PANEL_W  = 260
PANEL_BG = (20, 20, 35)

# Panel layout constants
_PREVIEW   = 36          # thumbnail px
_ROW_H     = 46          # list-row height
_CELL_H    = _PREVIEW + 22  # grid-cell height (tile grid)
_BOT_H     = 112         # px reserved for bottom buttons + level name
_BTN_W     = (PANEL_W - 14) // 4   # mode-button width (~61px)

# Tool modes
MODE_TILE     = "tile"
MODE_ENEMY    = "enemy"
MODE_PICKUP   = "pickup"
MODE_OBJECTS  = "objects"   # spawn + checkpoint + win door (sub-selected)
MODE_BG       = "bg"        # background set picker
MODE_ERASE    = "erase"
MODE_SETTINGS = "settings"

# Legacy aliases kept so _place_at / _erase_at logic still works
MODE_SPAWN      = "spawn"
MODE_CHECKPOINT = "checkpoint"
MODE_WINDOOR    = "windoor"

# (forced_character value, display label, swatch colour)
CHAR_OPTIONS = [
    (None,    "Any character",  (140, 140, 140)),
    (W_SWORD, "Knight (Sword)", (180, 180, 200)),
    (W_BOW,   "Archer (Bow)",   (100, 200, 80)),
    (W_STAFF, "Wizard (Staff)", (180, 100, 240)),
]

# Categorised enemy roster for the editor panel
ENEMY_CATEGORIES = [
    ("Melee",  ["goblin", "bomber_goblin", "skeleton", "slime", "worm"]),
    ("Ranged", ["flying_eye"]),
    ("Dash",   ["mushroom"]),
]

def _etype_color(etype):
    tint = ENEMY_CONFIG.get(etype, {}).get("tint")
    return tint[:3] if tint else (160, 70, 40)

def _etype_label(etype):
    return ENEMY_CONFIG.get(etype, {}).get("label", etype.replace("_", " ").title())

def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)

# 2×4 mode grid — None slots are skipped (greyed out)
_MODES_GRID = [
    [(MODE_TILE,"Tiles"), (MODE_ENEMY,"Enemies"), (MODE_PICKUP,"Pickups"), (MODE_OBJECTS,"Objects")],
    [(MODE_BG,"Background"), (MODE_ERASE,"Erase"), (MODE_SETTINGS,"Settings"), None],
]

def _content_h():
    """Pixel height of the scrollable content area."""
    # title(28) + 2 mode rows(64) + separator(8) = 100; bottom = _BOT_H
    return SCREEN_H - 100 - _BOT_H


class LevelEditor:
    def __init__(self, screen, level=None):
        self.screen = screen
        self.level  = level or Level()
        self.cam_x  = 0
        self.cam_y  = 0
        self.cam_speed = 6

        # Tool state
        self.mode            = MODE_TILE
        self.selected_tile   = T_GROUND
        self.selected_enemy  = "goblin"
        self.selected_pickup = W_SWORD
        self.selected_object = "spawn"   # sub-selection within MODE_OBJECTS
        self.enemy_param     = 120       # patrol_range or detect_radius
        self.placing_enemy   = False

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

        # parallax background layers — both sets loaded once, switched by level.bg_set
        self._bg_sets = self._load_all_bg_sets()

        # Scrollable-panel state
        self._content_scroll = {}   # mode → scroll_y_offset
        self._content_max    = {}   # mode → total content height (set each draw)

        # Preview thumbnail caches (built once after pygame is ready)
        self._tile_previews  = {}   # tid → Surface
        self._enemy_previews = {}   # etype → Surface
        self._char_previews  = {}   # wid → Surface
        self._weapon_orbs    = {}   # wid → Surface
        self._build_previews()

    # ── Background ────────────────────────────────────────────────────────────

    def _load_all_bg_sets(self):
        """Load both background sets; return dict bg_set → [(img, parallax_factor)]."""
        _CFG = {
            "forest": (
                os.path.join("assets", "Platform tiles", "Background"),
                [("Layer_03.png", 0.05), ("Layer_02.png", 0.20), ("Layer_01.png", 0.45)],
                (135, 206, 235),
            ),
            "dungeon": (
                os.path.join("assets", "Platform tiles", "Background_dungeon"),
                [("bg_0.png", 0.02), ("bg_1.png", 0.15), ("bg_2.png", 0.35),
                 ("fg_0.png", 0.60), ("fg_1.png", 0.80)],
                (18, 14, 30),
            ),
        }
        result = {}
        for key, (bg_dir, file_cfg, sky) in _CFG.items():
            layers = []
            for fname, pf in file_cfg:
                path = os.path.join(bg_dir, fname)
                if not os.path.exists(path):
                    continue
                img = pygame.image.load(path).convert_alpha()
                iw, ih = img.get_size()
                img = pygame.transform.scale(img, (max(1, int(iw * SCREEN_H / ih)), SCREEN_H))
                layers.append((img, pf))
            result[key] = (sky, layers)
        return result

    # ── Preview builder ───────────────────────────────────────────────────────

    def _build_previews(self):
        from tiles import TileTextureManager
        from ui_helpers import make_orb, HERO_ORB_CFG
        from animator import load_strip_auto

        ttm = TileTextureManager.get()

        # Tile previews — use actual TileTextureManager textures
        _tile_src = {
            T_GROUND:   lambda: ttm.ground_tex(False),
            T_PLATFORM: lambda: ttm.platform_tex(),
            T_COIN:     lambda: ttm.anim_frame("coin"),
            T_SPIKE:    lambda: ttm.anim_frame("spike"),
            T_TORCH:    lambda: ttm.anim_frame("torch"),
        }
        for tid, src_fn in _tile_src.items():
            surf = pygame.Surface((_PREVIEW, _PREVIEW), pygame.SRCALPHA)
            src  = src_fn()
            if src:
                surf.blit(pygame.transform.scale(src, (_PREVIEW, _PREVIEW)), (0, 0))
            else:
                c = TILE_COLORS.get(tid, GRAY)
                surf.fill(c[:3] if len(c) >= 3 else c)
            self._tile_previews[tid] = surf

        # Enemy previews — use actual idle sprite frame
        from enemies import _load_enemy_anim
        for etype, cfg in ENEMY_CONFIG.items():
            sub  = cfg.get("label", "").lower().replace(" ", "_")
            anim = _load_enemy_anim(sub, _PREVIEW, cfg.get("tint"))
            if anim:
                anim.set_state("idle", force=True)
                anim.update()
                img = anim.image
                # Scale to fit inside _PREVIEW square, preserving aspect ratio
                iw, ih = img.get_size()
                scale  = min(_PREVIEW / max(iw, 1), _PREVIEW / max(ih, 1))
                nw = max(1, int(iw * scale))
                nh = max(1, int(ih * scale))
                img   = pygame.transform.scale(img, (nw, nh))
                surf  = pygame.Surface((_PREVIEW, _PREVIEW), pygame.SRCALPHA)
                surf.blit(img, ((_PREVIEW - nw) // 2, (_PREVIEW - nh) // 2))
            else:
                # Fallback procedural figure
                surf  = pygame.Surface((_PREVIEW, _PREVIEW), pygame.SRCALPHA)
                color = _etype_color(etype)
                hw    = _PREVIEW // 2
                pygame.draw.circle(surf, color, (hw, 9), 8)
                pygame.draw.circle(surf, (20, 20, 20), (hw - 3, 8), 2)
                pygame.draw.circle(surf, (20, 20, 20), (hw + 3, 8), 2)
                pygame.draw.rect(surf, color, (hw - 5, 17, 10, 14), border_radius=2)
                pygame.draw.line(surf, color, (hw - 3, 31), (hw - 5, _PREVIEW - 1), 2)
                pygame.draw.line(surf, color, (hw + 3, 31), (hw + 5, _PREVIEW - 1), 2)
            self._enemy_previews[etype] = surf

        # Character previews — first idle frame, scaled to _PREVIEW
        char_dirs = {
            W_SWORD: "assets/sprites/knight",
            W_BOW:   "assets/sprites/archer",
            W_STAFF: "assets/sprites/wizard",
        }
        for wid, cdir in char_dirs.items():
            idle_path = os.path.join(cdir, "Idle.png")
            frames = load_strip_auto(idle_path, _PREVIEW) if os.path.exists(idle_path) else []
            if frames:
                self._char_previews[wid] = frames[0]
            else:
                s = pygame.Surface((_PREVIEW, _PREVIEW), pygame.SRCALPHA)
                s.fill((80, 80, 80))
                self._char_previews[wid] = s

        # Weapon orbs for pickup mode
        for wid, cfg in HERO_ORB_CFG.items():
            self._weapon_orbs[wid] = make_orb(_PREVIEW, cfg[0], cfg[1], cfg[2], cfg[3])

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
        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if mx >= self.view_w:  # wheel over panel
                cur  = self._content_scroll.get(self.mode, 0)
                maxs = max(0, self._content_max.get(self.mode, 0) - _content_h())
                self._content_scroll[self.mode] = max(0, min(maxs, cur - ev.y * 28))

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
            if self.mode in (MODE_TILE, MODE_ERASE, MODE_OBJECTS):
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
        elif self.mode == MODE_OBJECTS:
            cx = col * TILE_SIZE + TILE_SIZE // 2
            cy = (row + 1) * TILE_SIZE
            if self.selected_object == "spawn":
                tm.set_tile(col, row, T_SPAWN)
                self.level.spawn_x = col * TILE_SIZE + 4
                self.level.spawn_y = row * TILE_SIZE - 44
            elif self.selected_object == "checkpoint":
                for cd in self.level.checkpoint_data:
                    if abs(cd["x"] - cx) < TILE_SIZE and abs(cd["y"] - cy) < TILE_SIZE:
                        return
                self.level.checkpoint_data.append({"x": cx, "y": cy})
                self.level._spawn_checkpoints()
            elif self.selected_object == "windoor":
                self.level.win_door_data = {"x": cx, "y": cy}
                self.level._spawn_windoor()
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
        # checkpoints
        new_cd = []
        for cd in self.level.checkpoint_data:
            cr = pygame.Rect(cd["x"] - 20, cd["y"] - 80, 40, 80)
            if not erase_r.colliderect(cr):
                new_cd.append(cd)
        if len(new_cd) != len(self.level.checkpoint_data):
            self.level.checkpoint_data = new_cd
            self.level._spawn_checkpoints()
        # win door
        if self.level.win_door_data:
            wd = self.level.win_door_data
            wr = pygame.Rect(wd["x"] - 22, wd["y"] - 80, 44, 80)
            if erase_r.colliderect(wr):
                self.level.win_door_data = None
                self.level._spawn_windoor()

    # ── Panel ─────────────────────────────────────────────────────────────────

    def _panel_click(self, px, py, button):
        if button != 1:
            return None

        # ── Mode grid (2 rows × 4) ────────────────────────────────────────────
        y = 32
        for row in _MODES_GRID:
            for ci, item in enumerate(row):
                if item is None:
                    continue
                mode, _ = item
                r = pygame.Rect(5 + ci * (_BTN_W + 2), y, _BTN_W, 28)
                if r.collidepoint(px, py):
                    self.mode = mode
                    return None
            y += 32
        # content_top = 100 (title 28 + 2 rows*32 + separator 6 = 94+6 = 100)

        # ── Scrollable content area ───────────────────────────────────────────
        content_top = 100
        content_bot = SCREEN_H - _BOT_H
        if content_top <= py < content_bot:
            scroll = self._content_scroll.get(self.mode, 0)
            self._content_click(px, py - content_top + scroll)
            return None

        # ── Bottom buttons (2 rows × 2) ───────────────────────────────────────
        bw   = (PANEL_W - 14) // 2
        by   = SCREEN_H - _BOT_H + 2
        for row_btns in [
            [("Save Level", "save"), ("Load Level", "load")],
            [("Play (F5)",  "play"), ("Main Menu",  "menu")],
        ]:
            for ci, (label, action) in enumerate(row_btns):
                r = pygame.Rect(5 + ci * (bw + 4), by, bw, 30)
                if r.collidepoint(px, py):
                    if action == "save":   self._save_current()
                    elif action == "load": self._refresh_file_list(); self._show_load = not self._show_load
                    elif action == "play": return "play"
                    elif action == "menu": return "menu"
                    return None
            by += 34

        # Level name field
        name_r = pygame.Rect(48, SCREEN_H - _BOT_H + 72, PANEL_W - 54, 24)
        if name_r.collidepoint(px, py):
            self._input_active = True
            self._input_field  = "name"
            self._input_text   = self.level.name
        return None

    def _content_click(self, px, cy):
        """Handle click at panel-x=px, scroll-adjusted content-y=cy."""
        if self.mode == MODE_TILE:
            cw = (PANEL_W - 14) // 2
            tiles = [T_GROUND, T_PLATFORM, T_SPIKE, T_COIN, T_TORCH]
            for i, tid in enumerate(tiles):
                col  = i % 2
                row  = i // 2
                cell_x = 5 + col * (cw + 4)
                cell_y = 4 + row * (_CELL_H + 4)
                if pygame.Rect(cell_x, cell_y, cw, _CELL_H).collidepoint(px, cy):
                    self.selected_tile = tid
                    return

        elif self.mode == MODE_ENEMY:
            if 4 <= cy < 46:   # patrol param input
                self._input_active = True
                self._input_field  = "param"
                self._input_text   = str(self.enemy_param)
                return
            y = 46
            for _, etypes in ENEMY_CATEGORIES:
                y += 22
                for etype in etypes:
                    if y <= cy < y + _ROW_H:
                        self.selected_enemy = etype
                        return
                    y += _ROW_H

        elif self.mode == MODE_PICKUP:
            y = 4
            for wid in [W_SWORD, W_BOW, W_STAFF]:
                if y <= cy < y + _ROW_H:
                    self.selected_pickup = wid
                    return
                y += _ROW_H

        elif self.mode == MODE_OBJECTS:
            y = 4
            for obj_id, _, _, _ in [
                ("spawn",      "", None, ""),
                ("checkpoint", "", None, ""),
                ("windoor",    "", None, ""),
            ]:
                if pygame.Rect(5, y, PANEL_W - 11, _ROW_H).collidepoint(px, cy):
                    self.selected_object = obj_id
                    return
                y += _ROW_H + 4

        elif self.mode == MODE_BG:
            y = 24  # after "Level Background:" label
            for bg_id in ["forest", "dungeon"]:
                if pygame.Rect(5, y, PANEL_W - 11, 52).collidepoint(px, cy):
                    self.level.bg_set = bg_id
                    return
                y += 56

        elif self.mode == MODE_SETTINGS:
            y = 22   # after "Character lock:" label
            for char_id, _, _ in CHAR_OPTIONS:
                if pygame.Rect(5, y, PANEL_W - 11, 28).collidepoint(px, cy):
                    self.level.forced_character = char_id
                    return
                y += 30

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

        bg_key = getattr(self.level, "bg_set", "forest")
        sky, layers = self._bg_sets.get(bg_key, self._bg_sets.get("forest", ((30,35,50), [])))
        surf.fill(sky)

        for img, pf in layers:
            iw = img.get_width()
            off = int(self.cam_x * pf) % iw
            x = -(off % iw)
            while x < self.view_w:
                surf.blit(img, (x, 0))
                x += iw

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

        # checkpoints
        for cp in self.level.checkpoints:
            cp.draw(surf, (int(self.cam_x), int(self.cam_y)))

        # win door
        if self.level.win_door:
            self.level.win_door.draw(surf, (int(self.cam_x), int(self.cam_y)))

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

    # ── Content renderers ─────────────────────────────────────────────────────

    def _draw_mode_content(self, panel, start_y):
        """Dispatch to per-mode content renderer. Returns total content height."""
        if self.mode == MODE_TILE:     return self._content_tiles(panel, start_y)
        if self.mode == MODE_ENEMY:    return self._content_enemies(panel, start_y)
        if self.mode == MODE_PICKUP:   return self._content_pickups(panel, start_y)
        if self.mode == MODE_OBJECTS:  return self._content_objects(panel, start_y)
        if self.mode == MODE_BG:       return self._content_bg(panel, start_y)
        if self.mode == MODE_SETTINGS: return self._content_settings(panel, start_y)
        return self._content_erase(panel, start_y)

    def _content_tiles(self, surf, sy):
        tiles = [(T_GROUND,"Ground"),(T_PLATFORM,"Platform"),
                 (T_SPIKE,"Spike"),(T_COIN,"Coin"),(T_TORCH,"Torch")]
        cw  = (PANEL_W - 14) // 2
        y0  = sy + 4
        for i, (tid, name) in enumerate(tiles):
            col = i % 2;  row = i // 2
            cx  = 5 + col * (cw + 4)
            cy  = y0 + row * (_CELL_H + 4)
            sel = (self.selected_tile == tid)
            r   = pygame.Rect(cx, cy, cw, _CELL_H)
            pygame.draw.rect(surf, (55, 78, 128) if sel else (30, 38, 58), r, border_radius=5)
            if sel:
                pygame.draw.rect(surf, CYAN, r, 2, border_radius=5)
            # Thumbnail
            prev = self._tile_previews.get(tid)
            px0  = cx + (cw - _PREVIEW) // 2
            if prev:
                surf.blit(prev, (px0, cy + 4))
            else:
                c = TILE_COLORS.get(tid, GRAY)
                pygame.draw.rect(surf, c[:3] if len(c) >= 3 else c,
                                 (px0, cy + 4, _PREVIEW, _PREVIEW), border_radius=3)
            t = self.fnt_sm.render(name, True, WHITE if sel else (170, 172, 200))
            surf.blit(t, t.get_rect(centerx=cx + cw // 2, top=cy + _PREVIEW + 7))
        rows = (len(tiles) + 1) // 2
        return 4 + rows * (_CELL_H + 4)

    def _content_enemies(self, surf, sy):
        y = sy + 4
        # Patrol param input at top
        surf.blit(self.fnt_sm.render("Patrol / detect radius:", True, (140, 148, 175)), (6, y))
        y += 16
        inp = self._input_text if (self._input_active and self._input_field == "param") \
              else str(self.enemy_param)
        pygame.draw.rect(surf, (40, 44, 68), (5, y, PANEL_W - 11, 24), border_radius=3)
        if self._input_active and self._input_field == "param":
            pygame.draw.rect(surf, CYAN, (5, y, PANEL_W - 11, 24), 1, border_radius=3)
        surf.blit(self.fnt.render(inp, True, WHITE), (10, y + 4))
        y += 28
        # Categorised enemy list
        for cat_label, etypes in ENEMY_CATEGORIES:
            pygame.draw.rect(surf, (26, 32, 52), (5, y, PANEL_W - 11, 20), border_radius=3)
            surf.blit(self.fnt_sm.render(f"  {cat_label}", True, CYAN), (8, y + 3))
            y += 22
            for etype in etypes:
                sel = (self.selected_enemy == etype)
                r   = pygame.Rect(5, y, PANEL_W - 11, _ROW_H - 2)
                pygame.draw.rect(surf, (55, 78, 125) if sel else (28, 35, 55), r, border_radius=4)
                if sel:
                    pygame.draw.rect(surf, CYAN, r, 1, border_radius=4)
                prev = self._enemy_previews.get(etype)
                if prev:
                    surf.blit(prev, (r.x + 4, r.y + (r.h - prev.get_height()) // 2))
                cfg = ENEMY_CONFIG.get(etype, {})
                surf.blit(self.fnt_sm.render(_etype_label(etype),
                          True, WHITE if sel else (175, 178, 205)),
                          (r.x + _PREVIEW + 8, r.y + 6))
                surf.blit(self.fnt_sm.render(f"HP {cfg.get('hp','?')}",
                          True, (100, 210, 120)),
                          (r.x + _PREVIEW + 8, r.y + r.h - 16))
                y += _ROW_H
        return y - sy

    def _content_pickups(self, surf, sy):
        y  = sy + 4
        labels = {W_SWORD: "Sword / Knight", W_BOW: "Bow / Archer", W_STAFF: "Staff / Wizard"}
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            sel = (self.selected_pickup == wid)
            r   = pygame.Rect(5, y, PANEL_W - 11, _ROW_H - 2)
            pygame.draw.rect(surf, (55, 78, 125) if sel else (28, 35, 55), r, border_radius=4)
            if sel:
                pygame.draw.rect(surf, CYAN, r, 1, border_radius=4)
            # Weapon orb
            orb = self._weapon_orbs.get(wid)
            if orb:
                surf.blit(orb, (r.x + 4, r.y + (r.h - orb.get_height()) // 2))
            # Character idle preview
            cp = self._char_previews.get(wid)
            if cp:
                cs = pygame.transform.scale(cp, (28, 28))
                surf.blit(cs, (r.x + _PREVIEW + 8, r.y + (r.h - 28) // 2))
            surf.blit(self.fnt_sm.render(labels[wid],
                      True, WHITE if sel else (175, 178, 205)),
                      (r.x + _PREVIEW + 42, r.y + (r.h - 12) // 2))
            y += _ROW_H
        return y - sy

    def _content_objects(self, surf, sy):
        """Spawn point + Checkpoint + Win Door in one scrollable list."""
        y = sy + 4
        _OBJS = [
            ("spawn",      "Spawn Point",  CYAN,
             f"({int(self.level.spawn_x)}, {int(self.level.spawn_y)})"),
            ("checkpoint", "Checkpoint",   YELLOW,
             f"Placed: {len(self.level.checkpoint_data)}"),
            ("windoor",    "Win Door",     (160, 100, 255),
             "Set ✓" if self.level.win_door_data else "Not set"),
        ]
        for obj_id, obj_name, obj_col, obj_info in _OBJS:
            sel = (self.selected_object == obj_id)
            r   = pygame.Rect(5, y, PANEL_W - 11, _ROW_H)
            pygame.draw.rect(surf, (55, 78, 125) if sel else (28, 35, 55), r, border_radius=5)
            if sel:
                pygame.draw.rect(surf, obj_col, r, 2, border_radius=5)
            # Icon
            ic_cx, ic_cy = r.x + 22, r.y + r.h // 2
            if obj_id == "spawn":
                pygame.draw.circle(surf, CYAN, (ic_cx, ic_cy), 12, 2)
                pygame.draw.line(surf, CYAN, (ic_cx, ic_cy - 14), (ic_cx, ic_cy + 14), 1)
                pygame.draw.line(surf, CYAN, (ic_cx - 14, ic_cy), (ic_cx + 14, ic_cy), 1)
            elif obj_id == "checkpoint":
                pygame.draw.line(surf, (140, 120, 70), (ic_cx, ic_cy + 12), (ic_cx, ic_cy - 12), 2)
                pygame.draw.polygon(surf, obj_col if sel else (120, 120, 120),
                                    [(ic_cx, ic_cy - 12), (ic_cx + 14, ic_cy - 7),
                                     (ic_cx + 14, ic_cy + 2), (ic_cx, ic_cy + 2)])
            elif obj_id == "windoor":
                pygame.draw.rect(surf, (55, 35, 95), (ic_cx - 10, ic_cy - 14, 20, 26),
                                 border_radius=3)
                pygame.draw.rect(surf, obj_col, (ic_cx - 10, ic_cy - 14, 20, 26), 2,
                                 border_radius=3)
                pygame.draw.circle(surf, (220, 180, 255), (ic_cx, ic_cy - 2), 5)
            # Name + info
            surf.blit(self.fnt_sm.render(obj_name,
                      True, WHITE if sel else (175, 178, 205)), (r.x + 42, r.y + 7))
            surf.blit(self.fnt_sm.render(obj_info,
                      True, obj_col if sel else GRAY), (r.x + 42, r.y + r.h - 17))
            y += _ROW_H + 4
        # Instruction for selected object
        y += 6
        _hint = {
            "spawn":      "Click canvas to move spawn.",
            "checkpoint": "Click canvas to add flags.",
            "windoor":    "Click canvas to place door.",
        }
        surf.blit(self.fnt_sm.render(_hint.get(self.selected_object, ""),
                  True, (140, 145, 170)), (8, y))
        y += 18
        surf.blit(self.fnt_sm.render("Erase tool removes them.",
                  True, (120, 125, 150)), (8, y))
        y += 20
        return y - sy

    def _content_bg(self, surf, sy):
        """Background set picker."""
        y = sy + 4
        surf.blit(self.fnt_sm.render("Level Background:", True, CYAN), (5, y))
        y += 20
        cur_bg = getattr(self.level, "bg_set", "forest")
        _BG_OPTS = [
            ("forest",  "Forest",  (38, 78, 38),  (135, 206, 235)),
            ("dungeon", "Dungeon", (48, 28, 68),  (18,  14,  30)),
        ]
        for bg_id, bg_name, swatch, sky_col in _BG_OPTS:
            sel = (cur_bg == bg_id)
            r   = pygame.Rect(5, y, PANEL_W - 11, 52)
            pygame.draw.rect(surf, (55, 78, 125) if sel else (28, 35, 55), r, border_radius=5)
            if sel:
                pygame.draw.rect(surf, CYAN, r, 2, border_radius=5)
            # Sky swatch
            pygame.draw.rect(surf, sky_col, (r.x + 4, r.y + 4, 44, 44), border_radius=3)
            # Ground swatch
            pygame.draw.rect(surf, swatch,  (r.x + 4, r.y + 32, 44, 16), border_radius=3)
            # Label
            surf.blit(self.fnt.render(bg_name,
                      True, WHITE if sel else (165, 168, 195)), (r.x + 54, r.y + 16))
            if sel:
                surf.blit(self.fnt_sm.render("✓ Active", True, CYAN), (r.x + 54, r.y + 32))
            y += 56
        return y - sy

    def _content_erase(self, surf, sy):
        y = sy + 8
        for line, col in [("Left-click erases tiles,", (160, 165, 195)),
                          ("enemies & objects.", (160, 165, 195)),
                          ("Right-drag also erases.", (140, 145, 175))]:
            surf.blit(self.fnt_sm.render(line, True, col), (8, y))
            y += 20
        return y - sy

    def _content_settings(self, surf, sy):
        y = sy + 4
        surf.blit(self.fnt_sm.render("Character lock:", True, CYAN), (5, y))
        y += 18
        for char_id, char_label, _ in CHAR_OPTIONS:
            sel = (self.level.forced_character == char_id)
            r   = pygame.Rect(5, y, PANEL_W - 11, 28)
            pygame.draw.rect(surf, (55, 78, 125) if sel else (28, 35, 55), r, border_radius=3)
            if sel:
                pygame.draw.rect(surf, CYAN, r, 1, border_radius=3)
            if char_id is not None:
                prev = self._char_previews.get(char_id)
                if prev:
                    cp = pygame.transform.scale(prev, (22, 22))
                    surf.blit(cp, (r.x + 4, r.y + 3))
            else:
                pygame.draw.circle(surf, (100, 100, 110), (r.x + 14, r.y + 14), 9, 2)
            surf.blit(self.fnt_sm.render(char_label,
                      True, WHITE if sel else (165, 168, 195)), (r.x + 30, r.y + 7))
            y += 30
        return y - sy

    # ── Panel draw ────────────────────────────────────────────────────────────

    def _draw_panel(self):
        panel = pygame.Surface((PANEL_W, SCREEN_H))
        panel.fill(PANEL_BG)

        # Title
        t = self.fnt_md.render("LEVEL EDITOR", True, CYAN)
        panel.blit(t, (PANEL_W // 2 - t.get_width() // 2, 6))

        # Mode grid (2 rows × 4; None slots are skipped)
        y = 32
        for row in _MODES_GRID:
            for ci, item in enumerate(row):
                r = pygame.Rect(5 + ci * (_BTN_W + 2), y, _BTN_W, 28)
                if item is None:
                    pygame.draw.rect(panel, (22, 26, 40), r, border_radius=3)
                    continue
                mode, label = item
                sel = (self.mode == mode)
                pygame.draw.rect(panel, (55, 80, 135) if sel else (32, 40, 60), r, border_radius=3)
                if sel:
                    pygame.draw.rect(panel, CYAN, r, 1, border_radius=3)
                t = self.fnt_sm.render(label, True, WHITE if sel else (150, 155, 180))
                panel.blit(t, t.get_rect(center=r.center))
            y += 32

        # Separator + content area
        pygame.draw.line(panel, (48, 52, 72), (5, y + 2), (PANEL_W - 5, y + 2))
        content_top = y + 6   # = 100
        ch = _content_h()

        # Clip, draw, unclip
        panel.set_clip(pygame.Rect(0, content_top, PANEL_W - 7, ch))
        scroll  = self._content_scroll.get(self.mode, 0)
        total_h = self._draw_mode_content(panel, content_top - scroll)
        self._content_max[self.mode] = total_h
        panel.set_clip(None)

        # Clamp scroll now that we know total_h
        max_scroll = max(0, total_h - ch)
        if scroll > max_scroll:
            self._content_scroll[self.mode] = max_scroll

        # Scrollbar
        if total_h > ch:
            bar_h = max(16, int(ch * ch / total_h))
            bar_y = content_top + int(scroll * (ch - bar_h) / max(1, total_h - ch))
            pygame.draw.rect(panel, (32, 35, 54), (PANEL_W - 7, content_top, 6, ch))
            pygame.draw.rect(panel, (88, 100, 148), (PANEL_W - 7, bar_y, 6, bar_h), border_radius=3)

        # Bottom buttons (2 rows × 2)
        bw   = (PANEL_W - 14) // 2
        by   = SCREEN_H - _BOT_H + 2
        for row_btns in [
            [("Save Level", (38, 115, 38)), ("Load Level", (32, 52, 125))],
            [("Play (F5)",  (28, 108, 118)), ("Main Menu",  (115, 70, 22))],
        ]:
            for ci, (label, color) in enumerate(row_btns):
                r = pygame.Rect(5 + ci * (bw + 4), by, bw, 30)
                pygame.draw.rect(panel, color, r, border_radius=5)
                t = self.fnt_sm.render(label, True, WHITE)
                panel.blit(t, t.get_rect(center=r.center))
            by += 34

        # Level name field
        name_y = SCREEN_H - _BOT_H + 72
        panel.blit(self.fnt_sm.render("Name:", True, (125, 128, 155)), (5, name_y + 3))
        nd = self._input_text if (self._input_active and self._input_field == "name") \
             else self.level.name
        pygame.draw.rect(panel, (36, 38, 58), (48, name_y, PANEL_W - 54, 24), border_radius=3)
        if self._input_active and self._input_field == "name":
            pygame.draw.rect(panel, CYAN, (48, name_y, PANEL_W - 54, 24), 1, border_radius=3)
        panel.blit(self.fnt_sm.render(nd, True, WHITE), (52, name_y + 4))

        # Hint
        panel.blit(self.fnt_sm.render("WASD:pan  wheel:scroll panel  ESC:exit",
                   True, (65, 70, 90)), (3, SCREEN_H - 14))

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
