import pygame, json, os
from settings import *

_SETTINGS_FILE = "settings.json"

# Physics fields shown in the Settings tab
_PHYS_FIELDS = [
    ("GRAVITY",      "Gravity strength"),
    ("PLAYER_SPEED", "Player max speed"),
    ("JUMP_FORCE",   "Jump force  (negative = up)"),
    ("DJUMP_FORCE",  "Double-jump force"),
    ("MAX_FALL",     "Max fall speed"),
    ("GROUND_FRIC",  "Ground friction  (0 – 1)"),
    ("AIR_FRIC",     "Air friction  (0 – 1)"),
]

_PHYS_DEFAULTS = {
    "GRAVITY":      0.6,
    "PLAYER_SPEED": 5.0,
    "JUMP_FORCE":   -17.0,
    "DJUMP_FORCE":  -15.0,
    "MAX_FALL":     18.0,
    "GROUND_FRIC":  0.82,
    "AIR_FRIC":     0.90,
}

_CHAR_DEFAULTS = {
    W_SWORD: {"scale": 120, "sprite_dir": "assets/sprites/knight"},
    W_BOW:   {"scale": 120, "sprite_dir": "assets/sprites/archer"},
    W_STAFF: {"scale": 120, "sprite_dir": "assets/sprites/wizard"},
}

_CHAR_NAMES = {W_SWORD: "Knight", W_BOW: "Archer (Huntress)", W_STAFF: "Wizard (Mage)"}


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


def _load_settings():
    if os.path.exists(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(data):
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class AdminPanel:
    _TABS = ["Level Editor", "Character Editor", "Settings"]

    def __init__(self, screen):
        self.screen = screen
        self.tab    = 0

        self.fnt_title = _font(32, bold=True)
        self.fnt_tab   = _font(17, bold=True)
        self.fnt       = _font(15)
        self.fnt_lbl   = _font(14)
        self._bg = self._make_bg()

        cfg = _load_settings()

        # Physics field values (strings for editing)
        self._phys = {k: str(cfg.get(k, v)) for k, v in _PHYS_DEFAULTS.items()}

        # Character field values
        chars = cfg.get("characters", {})
        self._chars = {}
        for wid, defs in _CHAR_DEFAULTS.items():
            saved = chars.get(wid, {})
            self._chars[wid] = {
                "scale":      str(saved.get("scale",      defs["scale"])),
                "sprite_dir": str(saved.get("sprite_dir", defs["sprite_dir"])),
            }

        self._active = None   # key of the currently-focused input field
        self._status = ""
        self._status_ok = True

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill((12, 12, 28))
        return surf

    def _draw_btn(self, rect, text, color, mpos, surface=None):
        surface = surface or self.screen
        hov = rect.collidepoint(mpos)
        c   = tuple(min(255, v + 35) for v in color) if hov else color
        pygame.draw.rect(surface, c, rect, border_radius=7)
        pygame.draw.rect(surface, WHITE, rect, 2, border_radius=7)
        t = self.fnt.render(text, True, WHITE)
        surface.blit(t, t.get_rect(center=rect.center))

    def _draw_field(self, rect, value, active, surface=None):
        surface = surface or self.screen
        border  = WHITE if active else (80, 80, 110)
        pygame.draw.rect(surface, (28, 28, 52), rect, border_radius=4)
        pygame.draw.rect(surface, border, rect, 2, border_radius=4)
        cursor  = "|" if active else ""
        t = self.fnt.render(value + cursor, True, WHITE)
        surface.blit(t, (rect.x + 6, rect.centery - t.get_height() // 2))

    # ── Tab content ───────────────────────────────────────────────────────────

    def _draw_editor_tab(self, mpos):
        cx = SCREEN_W // 2
        msg = self.fnt.render(
            "Launch the level editor to build or modify game levels.", True, LTGRAY)
        self.screen.blit(msg, msg.get_rect(center=(cx, 220)))
        r = pygame.Rect(cx - 160, 290, 320, 52)
        self._draw_btn(r, "Open Level Editor", (50, 80, 180), mpos)
        return r   # caller uses this to detect click

    def _draw_char_tab(self, mpos):
        """Returns list of (scale_rect, dir_rect) per character for click detection."""
        rects = {}
        fy = 140
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            name_t = self.fnt.render(_CHAR_NAMES[wid], True, CYAN)
            self.screen.blit(name_t, (60, fy))

            # Scale field
            sl = self.fnt_lbl.render("Sprite height (px):", True, LTGRAY)
            self.screen.blit(sl, (80, fy + 26))
            sr = pygame.Rect(320, fy + 22, 100, 28)
            self._draw_field(sr, self._chars[wid]["scale"],
                             self._active == (wid, "scale"))

            # Sprite dir field
            dl = self.fnt_lbl.render("Sprite folder path:", True, LTGRAY)
            self.screen.blit(dl, (80, fy + 62))
            dr = pygame.Rect(320, fy + 58, 500, 28)
            self._draw_field(dr, self._chars[wid]["sprite_dir"],
                             self._active == (wid, "sprite_dir"))

            rects[wid] = (sr, dr)
            fy += 115
        return rects

    def _draw_settings_tab(self, mpos):
        """Returns dict of key → field_rect for click detection."""
        field_rects = {}
        fy = 135
        for key, label in _PHYS_FIELDS:
            lbl = self.fnt.render(f"{label}:", True, LTGRAY)
            self.screen.blit(lbl, (60, fy + 5))
            fr = pygame.Rect(SCREEN_W // 2 + 60, fy, 180, 28)
            self._draw_field(fr, self._phys[key], self._active == key)
            field_rects[key] = fr
            fy += 50
        return field_rects

    # ── Save logic ────────────────────────────────────────────────────────────

    def _save_all(self):
        data = _load_settings()

        # Physics
        for key in _PHYS_DEFAULTS:
            try:
                data[key] = float(self._phys[key])
            except ValueError:
                self._status  = f"Invalid value for {key}"
                self._status_ok = False
                return

        # Characters
        chars = {}
        for wid in _CHAR_DEFAULTS:
            try:
                scale = int(self._chars[wid]["scale"])
            except ValueError:
                self._status  = f"Invalid scale for {_CHAR_NAMES[wid]}"
                self._status_ok = False
                return
            chars[wid] = {
                "scale":      scale,
                "sprite_dir": self._chars[wid]["sprite_dir"].strip(),
            }
        data["characters"] = chars

        _save_settings(data)
        self._status   = "Saved.  Changes take effect on next game launch."
        self._status_ok = True

    # ── Keyboard input ────────────────────────────────────────────────────────

    def _type(self, ch):
        """Append character to the active field (with basic validation)."""
        if self._active is None:
            return
        if isinstance(self._active, tuple):   # (wid, "scale" | "sprite_dir")
            wid, sub = self._active
            if sub == "scale" and ch not in "0123456789":
                return
            self._chars[wid][sub] += ch
        else:                                   # physics key
            if ch not in "0123456789.-":
                return
            self._phys[self._active] += ch

    def _backspace(self):
        if self._active is None:
            return
        if isinstance(self._active, tuple):
            wid, sub = self._active
            self._chars[wid][sub] = self._chars[wid][sub][:-1]
        else:
            self._phys[self._active] = self._phys[self._active][:-1]

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Returns 'menu' or 'quit'."""
        clock = pygame.time.Clock()

        TAB_W, TAB_H = 200, 38
        tab_rects = [pygame.Rect(20 + i * (TAB_W + 8), 56, TAB_W, TAB_H)
                     for i in range(len(self._TABS))]

        save_btn = pygame.Rect(SCREEN_W - 260, SCREEN_H - 54, 110, 38)
        back_btn = pygame.Rect(SCREEN_W - 135, SCREEN_H - 54, 110, 38)

        editor_btn = None   # set each frame in editor tab
        char_rects = {}
        phys_rects = {}

        while True:
            mpos = pygame.mouse.get_pos()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"

                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return "menu"
                    elif ev.key == pygame.K_BACKSPACE:
                        self._backspace()
                    elif ev.key not in (pygame.K_RETURN, pygame.K_TAB):
                        if ev.unicode.isprintable():
                            self._type(ev.unicode)

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    self._active = None   # deselect on any click

                    # Tab switching
                    for i, r in enumerate(tab_rects):
                        if r.collidepoint(pos):
                            self.tab = i

                    if back_btn.collidepoint(pos):
                        return "menu"
                    if save_btn.collidepoint(pos):
                        self._save_all()

                    if self.tab == 0 and editor_btn and editor_btn.collidepoint(pos):
                        self._launch_editor()

                    elif self.tab == 1:
                        for wid, (sr, dr) in char_rects.items():
                            if sr.collidepoint(pos):
                                self._active = (wid, "scale")
                            elif dr.collidepoint(pos):
                                self._active = (wid, "sprite_dir")

                    elif self.tab == 2:
                        for key, fr in phys_rects.items():
                            if fr.collidepoint(pos):
                                self._active = key

            # ── Draw ──────────────────────────────────────────────────────────
            self.screen.blit(self._bg, (0, 0))

            title = self.fnt_title.render("ADMIN PANEL", True, ORANGE)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 28)))

            # Tabs
            for i, (r, name) in enumerate(zip(tab_rects, self._TABS)):
                sel = (i == self.tab)
                c   = (70, 110, 190) if sel else (35, 35, 58)
                pygame.draw.rect(self.screen, c, r, border_radius=6)
                pygame.draw.rect(self.screen, (WHITE if sel else GRAY), r, 2, border_radius=6)
                t = self.fnt_tab.render(name, True, WHITE)
                self.screen.blit(t, t.get_rect(center=r.center))

            # Content panel
            panel = pygame.Rect(10, 100, SCREEN_W - 20, SCREEN_H - 165)
            pygame.draw.rect(self.screen, (18, 18, 38), panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 80), panel, 2, border_radius=8)

            if self.tab == 0:
                editor_btn = self._draw_editor_tab(mpos)
                char_rects = {}
                phys_rects = {}
            elif self.tab == 1:
                char_rects = self._draw_char_tab(mpos)
                editor_btn = None
                phys_rects = {}
            elif self.tab == 2:
                phys_rects = self._draw_settings_tab(mpos)
                editor_btn = None
                char_rects = {}

            # Status
            if self._status:
                col = GREEN if self._status_ok else RED
                st = self.fnt.render(self._status, True, col)
                self.screen.blit(st, st.get_rect(center=(SCREEN_W // 2 - 80, SCREEN_H - 34)))

            self._draw_btn(save_btn, "Save All", (50, 140, 50),  mpos)
            self._draw_btn(back_btn, "Back",     (80,  80, 80),  mpos)

            pygame.display.flip()
            clock.tick(FPS)

    def _launch_editor(self):
        from editor import LevelEditor
        ed = LevelEditor(self.screen)
        ed.run()
