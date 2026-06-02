import pygame, json, os, time, tempfile
from settings import *
from save_manager import load_user_save, reset_user_save

_EDITOR_SAVE = {
    "level_reached": 99, "coins_total": 0,
    "unlocked_weapons": [W_SWORD, W_BOW, W_STAFF],
    "double_jump": True, "custom_levels_beaten": [],
}

_SETTINGS_FILE = "settings.json"

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
    "GRAVITY": 0.6, "PLAYER_SPEED": 5.0, "JUMP_FORCE": -17.0,
    "DJUMP_FORCE": -15.0, "MAX_FALL": 18.0, "GROUND_FRIC": 0.82, "AIR_FRIC": 0.90,
}
_CHAR_DEFAULTS = {
    W_SWORD: {"scale": 120, "sprite_dir": "assets/sprites/knight"},
    W_BOW:   {"scale": 120, "sprite_dir": "assets/sprites/archer"},
    W_STAFF: {"scale": 120, "sprite_dir": "assets/sprites/wizard"},
}
_CHAR_NAMES = {W_SWORD: "Knight", W_BOW: "Archer (Huntress)", W_STAFF: "Wizard (Mage)"}
_WEAPON_ABBR = {"sword": "Kn", "bow": "Ar", "staff": "Wz"}


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


def _all_users():
    if not os.path.isdir(SAVES_DIR):
        return []
    now = time.time()
    result = []
    for fname in sorted(os.listdir(SAVES_DIR)):
        if not fname.endswith(".json"):
            continue
        uname = fname[:-5]
        path = os.path.join(SAVES_DIR, fname)
        try:
            d = load_user_save(uname)
            wpns = "/".join(_WEAPON_ABBR.get(w, w[:2])
                            for w in d.get("unlocked_weapons", []))
            result.append({
                "username": uname,
                "level":    d.get("level_reached", 1),
                "coins":    d.get("coins_total", 0),
                "weapons":  wpns or "—",
                "djump":    d.get("double_jump", False),
                "days_ago": (now - os.path.getmtime(path)) / 86400,
            })
        except Exception:
            pass
    return result


def _builtin_metas():
    entries = [("Tutorial", "tutorial.json")] + \
              [(f"Level {i+1}", f"level{i+1}.json") for i in range(5)]
    result = []
    for display, fname in entries:
        path = os.path.join(LEVELS_DIR, fname)
        m = {"display": display, "fname": fname,
             "path": path, "exists": os.path.exists(path)}
        if m["exists"]:
            try:
                d = json.loads(open(path).read())
                m.update({
                    "enemies":     len(d.get("enemies", [])),
                    "checkpoints": len(d.get("checkpoints", [])),
                    "win_door":    d.get("win_door") is not None,
                    "cols":        d.get("cols", 60),
                    "triggers":    len(d.get("triggers", [])),
                })
            except Exception:
                pass
        result.append(m)
    return result


def _custom_fnames():
    if not os.path.isdir(LEVELS_DIR):
        return []
    builtin = {f"level{i+1}.json" for i in range(5)} | {"tutorial.json"}
    return sorted(f for f in os.listdir(LEVELS_DIR)
                  if f.endswith(".json") and f not in builtin)


# ──────────────────────────────────────────────────────────────────────────────

class AdminPanel:
    _TABS = ["Dashboard", "Users", "Levels", "Characters", "Settings"]

    def __init__(self, screen):
        self.screen = screen
        self.tab    = 0

        self.fnt_title = _font(30, bold=True)
        self.fnt_tab   = _font(14, bold=True)
        self.fnt_big   = _font(26, bold=True)
        self.fnt_hd    = _font(16, bold=True)
        self.fnt       = _font(14)
        self.fnt_sm    = _font(12)
        self.fnt_lbl   = _font(14)
        self._bg       = self._make_bg()

        cfg = _load_settings()
        self._phys = {k: str(cfg.get(k, v)) for k, v in _PHYS_DEFAULTS.items()}
        chars = cfg.get("characters", {})
        self._chars = {}
        for wid, defs in _CHAR_DEFAULTS.items():
            sv = chars.get(wid, {})
            self._chars[wid] = {
                "scale":      str(sv.get("scale",      defs["scale"])),
                "sprite_dir": str(sv.get("sprite_dir", defs["sprite_dir"])),
            }

        self._active       = None
        self._status       = ""
        self._status_ok    = True
        self._users        = []
        self._level_metas  = []
        self._custom_lvls  = []
        self._user_scroll  = 0
        self._confirm      = None   # {"msg": str, "on_confirm": callable}
        self._confirm_rects = (None, None)

        self._refresh_data()

    # ── Data ──────────────────────────────────────────────────────────────────

    def _refresh_data(self):
        self._users       = _all_users()
        self._level_metas = _builtin_metas()
        self._custom_lvls = _custom_fnames()

    # ── Generic helpers ───────────────────────────────────────────────────────

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill((12, 12, 28))
        return surf

    def _draw_btn(self, rect, text, color, mpos, surface=None):
        sf  = surface or self.screen
        rad = 8
        hov = rect.collidepoint(mpos)
        if not hov:
            sh = tuple(max(0, v - 55) for v in color)
            pygame.draw.rect(sf, sh,
                             pygame.Rect(rect.x + 2, rect.y + 3, rect.w, rect.h),
                             border_radius=rad)
        face = rect.move(0, 2 if hov else 0)
        c    = tuple(min(255, v + 20) for v in color) if hov else color
        pygame.draw.rect(sf, c, face, border_radius=rad)
        pygame.draw.rect(sf, tuple(min(255, v + 50) for v in c), face, 2, border_radius=rad)
        t = self.fnt.render(text, True, WHITE)
        sf.blit(t, t.get_rect(center=face.center))

    def _draw_field(self, rect, value, active, surface=None):
        sf = surface or self.screen
        pygame.draw.rect(sf, (28, 28, 52), rect, border_radius=4)
        pygame.draw.rect(sf, WHITE if active else (80, 80, 110), rect, 2, border_radius=4)
        t = self.fnt.render(value + ("|" if active else ""), True, WHITE)
        sf.blit(t, (rect.x + 6, rect.centery - t.get_height() // 2))

    def _stat_card(self, rect, label, value, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        brd = tuple(min(255, v + 50) for v in color)
        pygame.draw.rect(self.screen, brd, rect, 2, border_radius=10)
        lt = self.fnt_sm.render(label.upper(), True, (200, 210, 230))
        self.screen.blit(lt, lt.get_rect(centerx=rect.centerx, top=rect.y + 10))
        vt = self.fnt_big.render(str(value), True, WHITE)
        self.screen.blit(vt, vt.get_rect(centerx=rect.centerx, centery=rect.centery + 10))

    def _row_bg(self, y, w, h, i):
        c = (30, 40, 68) if i % 2 == 0 else (20, 28, 50)
        pygame.draw.rect(self.screen, c,
                         pygame.Rect(20, y, w, h - 2), border_radius=3)

    # ── Tab 0: Dashboard ──────────────────────────────────────────────────────

    def _draw_dashboard(self, mpos):
        u = self._users
        total       = len(u)
        active_7d   = sum(1 for x in u if x["days_ago"] < 7)
        avg_lv      = sum(x["level"] for x in u) / max(1, total)
        total_coins = sum(x["coins"] for x in u)

        # Stat cards
        cw = (SCREEN_W - 50) // 4
        ch = 90
        cards = [
            ("Total Users",    total,              (45,  75, 155)),
            ("Active ≤ 7 days", active_7d,         (38, 125,  72)),
            ("Avg Level",      f"{avg_lv:.1f}",    (115,  60, 145)),
            ("Total Coins",    f"{total_coins:,}",  (140,  90,  22)),
        ]
        for i, (lbl, val, clr) in enumerate(cards):
            self._stat_card(pygame.Rect(20 + i * (cw + 4), 112, cw, ch), lbl, val, clr)

        # Leaderboard header
        y = 112 + ch + 18
        self.screen.blit(self.fnt_hd.render("Top Players", True, CYAN), (28, y))
        ref_r = pygame.Rect(SCREEN_W - 150, y, 120, 26)
        self._draw_btn(ref_r, "↻ Refresh", (45, 55, 85), mpos)
        y += 28

        for cx_pos, hd in [(28,"#"),(80,"Username"),(280,"Level Reached"),
                           (420,"Coins"),(540,"Weapons"),(670,"Last Active")]:
            self.screen.blit(self.fnt_sm.render(hd, True, GRAY), (cx_pos, y))
        y += 18
        pygame.draw.line(self.screen, (50, 55, 80), (20, y), (SCREEN_W - 20, y))
        y += 4

        sorted_u = sorted(u, key=lambda x: (-x["level"], -x["coins"]))
        for rank, usr in enumerate(sorted_u[:10], 1):
            self._row_bg(y, SCREEN_W - 40, 26, rank)
            rc = YELLOW if rank == 1 else (LTGRAY if rank <= 3 else GRAY)
            for cx_pos, text, col in [
                (28,  f"#{rank}",              rc),
                (80,  usr["username"],         WHITE),
                (280, str(usr["level"]),       GREEN),
                (420, f"{usr['coins']:,}",     YELLOW),
                (540, usr["weapons"],          CYAN),
                (670, f"{usr['days_ago']:.0f}d ago" if usr["days_ago"] < 365 else "Long ago",
                      LTGRAY),
            ]:
                self.screen.blit(self.fnt_sm.render(text, True, col), (cx_pos, y + 5))
            y += 26

        if not u:
            t = self.fnt.render("No registered users yet.", True, GRAY)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W // 2, 350)))

        return ref_r

    # ── Tab 1: Users ──────────────────────────────────────────────────────────

    def _draw_users_tab(self, mpos):
        ROW_H       = 30
        HEADER_Y    = 112
        LIST_Y      = HEADER_Y + 32
        MAX_Y       = SCREEN_H - 175

        for cx_pos, hd in [(28,"Username"),(250,"Level"),(330,"Coins"),
                           (430,"Weapons"),(540,"2× Jump"),(640,"Last Active"),(800,"Actions")]:
            self.screen.blit(self.fnt_sm.render(hd, True, GRAY), (cx_pos, HEADER_Y))
        pygame.draw.line(self.screen, (50, 55, 80),
                         (20, HEADER_Y + 18), (SCREEN_W - 20, HEADER_Y + 18))

        visible = (MAX_Y - LIST_Y) // ROW_H
        max_scroll = max(0, (len(self._users) - visible) * ROW_H)
        self._user_scroll = min(self._user_scroll, max_scroll)

        action_rects = {}
        for i, usr in enumerate(self._users):
            y = LIST_Y + i * ROW_H - self._user_scroll
            if y + ROW_H < LIST_Y or y > MAX_Y:
                continue
            self._row_bg(y, SCREEN_W - 40, ROW_H, i)
            for cx_pos, text, col in [
                (28,  usr["username"],       WHITE),
                (250, str(usr["level"]),     GREEN),
                (330, f"{usr['coins']:,}",   YELLOW),
                (430, usr["weapons"],        CYAN),
                (540, "Yes" if usr["djump"] else "No", LTGRAY),
                (640, f"{usr['days_ago']:.0f}d" if usr["days_ago"] < 365 else "Old", GRAY),
            ]:
                self.screen.blit(self.fnt_sm.render(text, True, col), (cx_pos, y + 7))
            rst_r = pygame.Rect(800,  y + 3, 72, 22)
            del_r = pygame.Rect(878,  y + 3, 72, 22)
            self._draw_btn(rst_r, "Reset",  (85, 100, 25), mpos)
            self._draw_btn(del_r, "Delete", (135, 28, 28), mpos)
            action_rects[usr["username"]] = {"reset": rst_r, "delete": del_r}

        if not self._users:
            t = self.fnt.render("No registered users.", True, GRAY)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W // 2, 300)))

        if len(self._users) > visible:
            hint = self.fnt_sm.render(
                f"Mouse wheel to scroll  ({len(self._users)} users total)", True, GRAY)
            self.screen.blit(hint, (28, MAX_Y + 6))

        return action_rects

    # ── Tab 2: Levels ─────────────────────────────────────────────────────────

    def _draw_levels_tab(self, mpos):
        y = 112

        # Column headers
        for cx_pos, hd in [(28,"Level"),(200,"Cols"),(280,"Enemies"),
                           (370,"Checkpts"),(460,"Win Door"),(560,"Triggers"),
                           (SCREEN_W - 140,"")]:
            self.screen.blit(self.fnt_sm.render(hd, True, GRAY), (cx_pos, y))
        pygame.draw.line(self.screen, (50, 55, 80), (20, y + 18), (SCREEN_W - 20, y + 18))
        y += 26

        edit_rects = {}
        ROW_H = 32

        # Built-in
        self.screen.blit(self.fnt_hd.render("Built-in Levels", True, CYAN), (28, y))
        y += 24
        for m in self._level_metas:
            pygame.draw.rect(self.screen, (28, 38, 60),
                             pygame.Rect(20, y, SCREEN_W - 150, ROW_H - 2), border_radius=3)
            nc = WHITE if m["exists"] else GRAY
            self.screen.blit(self.fnt.render(m["display"], True, nc), (30, y + 7))
            if m["exists"]:
                for cx_pos, text, col in [
                    (200, str(m.get("cols", "?")),         LTGRAY),
                    (280, str(m.get("enemies", "?")),      ORANGE),
                    (370, str(m.get("checkpoints", "?")),  YELLOW),
                    (460, "Yes" if m.get("win_door") else "No",
                          GREEN if m.get("win_door") else RED),
                    (560, str(m.get("triggers", 0)),       LTGRAY),
                ]:
                    self.screen.blit(self.fnt.render(text, True, col), (cx_pos, y + 7))
                er = pygame.Rect(SCREEN_W - 138, y + 4, 76, 24)
                self._draw_btn(er, "Edit", (40, 80, 160), mpos)
                edit_rects[m["fname"]] = er
            else:
                self.screen.blit(self.fnt_sm.render("(missing — click Regenerate)", True, RED),
                                 (200, y + 9))
            y += ROW_H

        # Custom
        y += 10
        self.screen.blit(
            self.fnt_hd.render(f"Custom Levels  ({len(self._custom_lvls)})", True, CYAN),
            (28, y))
        y += 24
        for fname in self._custom_lvls[:5]:
            pygame.draw.rect(self.screen, (22, 32, 50),
                             pygame.Rect(20, y, SCREEN_W - 150, ROW_H - 2), border_radius=3)
            self.screen.blit(self.fnt.render(fname[:-5], True, LTGRAY), (30, y + 7))
            er = pygame.Rect(SCREEN_W - 138, y + 4, 76, 24)
            self._draw_btn(er, "Edit", (40, 80, 160), mpos)
            edit_rects[fname] = er
            y += ROW_H
        if len(self._custom_lvls) > 5:
            self.screen.blit(
                self.fnt_sm.render(f"…and {len(self._custom_lvls)-5} more", True, GRAY),
                (30, y))

        regen_r = pygame.Rect(28, SCREEN_H - 165, 280, 34)
        self._draw_btn(regen_r, "Regenerate All Built-in Levels", (105, 58, 18), mpos)
        return edit_rects, regen_r

    # ── Tab 3: Characters ─────────────────────────────────────────────────────

    def _draw_char_tab(self, mpos):
        rects = {}
        fy = 140
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            self.screen.blit(self.fnt.render(_CHAR_NAMES[wid], True, CYAN), (60, fy))
            self.screen.blit(self.fnt_lbl.render("Sprite height (px):", True, LTGRAY), (80, fy + 26))
            sr = pygame.Rect(320, fy + 22, 100, 28)
            self._draw_field(sr, self._chars[wid]["scale"], self._active == (wid, "scale"))
            self.screen.blit(self.fnt_lbl.render("Sprite folder path:", True, LTGRAY), (80, fy + 62))
            dr = pygame.Rect(320, fy + 58, 500, 28)
            self._draw_field(dr, self._chars[wid]["sprite_dir"],
                             self._active == (wid, "sprite_dir"))
            rects[wid] = (sr, dr)
            fy += 115
        return rects

    # ── Tab 4: Settings ───────────────────────────────────────────────────────

    def _draw_settings_tab(self, mpos):
        frects = {}
        fy = 135
        for key, label in _PHYS_FIELDS:
            self.screen.blit(self.fnt.render(f"{label}:", True, LTGRAY), (60, fy + 5))
            fr = pygame.Rect(SCREEN_W // 2 + 60, fy, 180, 28)
            self._draw_field(fr, self._phys[key], self._active == key)
            frects[key] = fr
            fy += 50
        return frects

    # ── Confirm overlay ───────────────────────────────────────────────────────

    def _draw_confirm(self, mpos):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        self.screen.blit(ov, (0, 0))
        bw, bh = 500, 170
        bx, by = SCREEN_W // 2 - bw // 2, SCREEN_H // 2 - bh // 2
        pygame.draw.rect(self.screen, (22, 25, 48), (bx, by, bw, bh), border_radius=12)
        pygame.draw.rect(self.screen, ORANGE, (bx, by, bw, bh), 2, border_radius=12)
        t = self.fnt_hd.render("Confirm Action", True, ORANGE)
        self.screen.blit(t, t.get_rect(centerx=bx + bw // 2, top=by + 16))
        m = self.fnt.render(self._confirm["msg"], True, LTGRAY)
        self.screen.blit(m, m.get_rect(centerx=bx + bw // 2, top=by + 58))
        ok_r  = pygame.Rect(bx + bw // 2 - 125, by + 112, 110, 36)
        can_r = pygame.Rect(bx + bw // 2 +  15, by + 112, 110, 36)
        self._draw_btn(ok_r,  "Confirm", (160, 38, 38), mpos)
        self._draw_btn(can_r, "Cancel",  (55,  55, 85), mpos)
        return ok_r, can_r

    # ── Save logic ────────────────────────────────────────────────────────────

    def _save_all(self):
        data = _load_settings()
        for key in _PHYS_DEFAULTS:
            try:
                data[key] = float(self._phys[key])
            except ValueError:
                self._status = f"Invalid value for {key}"
                self._status_ok = False
                return
        chars = {}
        for wid in _CHAR_DEFAULTS:
            try:
                scale = int(self._chars[wid]["scale"])
            except ValueError:
                self._status = f"Invalid scale for {_CHAR_NAMES[wid]}"
                self._status_ok = False
                return
            chars[wid] = {"scale": scale,
                          "sprite_dir": self._chars[wid]["sprite_dir"].strip()}
        data["characters"] = chars
        _save_settings(data)
        self._status = "Saved.  Physics changes take effect on next launch."
        self._status_ok = True

    # ── Keyboard input ────────────────────────────────────────────────────────

    def _type(self, ch):
        if self._active is None:
            return
        if isinstance(self._active, tuple):
            wid, sub = self._active
            if sub == "scale" and ch not in "0123456789":
                return
            self._chars[wid][sub] += ch
        else:
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

    # ── Launchers / actions ───────────────────────────────────────────────────

    def _launch_editor(self, path=None):
        from editor import LevelEditor
        from level import Level
        from game import Game

        lv = Level.load_from_file(path) if (path and os.path.exists(path)) else None

        while True:
            ed     = LevelEditor(self.screen, level=lv)
            result = ed.run()
            lv     = ed.get_level()

            if result == "play":
                # Save edits to original file before play-test
                if path:
                    lv.save_to_file(path)
                # Write temp level for the game session
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".json",
                            delete=False, dir=LEVELS_DIR) as f:
                        json.dump(lv.to_dict(), f)
                        tmp_path = f.name
                    fname = os.path.basename(tmp_path)
                    Game(self.screen, level_key=f"custom:{fname}",
                         username=None, save_data=dict(_EDITOR_SAVE)).run()
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
                # Re-enter editor with the (already saved) level
                continue

            # "menu" or "quit" — exit without auto-saving (use editor's Save button)
            break

        self._refresh_data()

    def _regen_builtin(self):
        from level import _generate_default_level, _generate_tutorial_level
        os.makedirs(LEVELS_DIR, exist_ok=True)
        _generate_tutorial_level().save_to_file(
            os.path.join(LEVELS_DIR, "tutorial.json"))
        for i in range(5):
            _generate_default_level(i + 1).save_to_file(
                os.path.join(LEVELS_DIR, BUILTIN_LEVELS[i]))
        self._refresh_data()
        self._status = "All 6 built-in levels regenerated."
        self._status_ok = True

    def _reset_user(self, uname):
        reset_user_save(uname)
        self._status = f'Progress reset for "{uname}".'
        self._status_ok = True

    def _delete_user(self, uname):
        p = os.path.join(SAVES_DIR, f"{uname}.json")
        if os.path.exists(p):
            os.remove(p)
        self._status = f'User "{uname}" deleted.'
        self._status_ok = True

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        clock = pygame.time.Clock()

        N = len(self._TABS)
        TAB_W = (SCREEN_W - 40) // N
        tab_rects = [pygame.Rect(20 + i * (TAB_W + 2), 56, TAB_W, 36)
                     for i in range(N)]

        back_btn = pygame.Rect(SCREEN_W - 130, SCREEN_H - 48, 108, 34)
        save_btn = pygame.Rect(SCREEN_W - 250, SCREEN_H - 48, 108, 34)

        # Per-frame click targets (refreshed each draw)
        dash_ref     = None
        user_acts    = {}
        lvl_edits    = {}
        lvl_regen    = None
        char_rects   = {}
        phys_rects   = {}

        while True:
            mpos = pygame.mouse.get_pos()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"

                # ── Confirm dialog intercepts all input ────────────────────────
                if self._confirm is not None:
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        self._confirm = None
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        ok_r, can_r = self._confirm_rects
                        if ok_r and ok_r.collidepoint(ev.pos):
                            self._confirm["on_confirm"]()
                            self._confirm = None
                            self._refresh_data()
                        elif can_r and can_r.collidepoint(ev.pos):
                            self._confirm = None
                    continue

                # ── Normal input ───────────────────────────────────────────────
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self._active = None if self._active else None
                        return "menu"
                    elif ev.key == pygame.K_BACKSPACE:
                        self._backspace()
                    elif ev.key not in (pygame.K_RETURN, pygame.K_TAB):
                        if ev.unicode.isprintable():
                            self._type(ev.unicode)

                if ev.type == pygame.MOUSEWHEEL and self.tab == 1:
                    self._user_scroll = max(0, self._user_scroll - ev.y * 30)

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    self._active = None

                    for i, r in enumerate(tab_rects):
                        if r.collidepoint(pos):
                            self.tab = i
                            self._user_scroll = 0

                    if back_btn.collidepoint(pos):
                        return "menu"

                    if self.tab in (3, 4) and save_btn.collidepoint(pos):
                        self._save_all()

                    if self.tab == 0:
                        if dash_ref and dash_ref.collidepoint(pos):
                            self._refresh_data()

                    elif self.tab == 1:
                        for uname, btns in user_acts.items():
                            if btns["reset"].collidepoint(pos):
                                def _do_rst(u=uname):
                                    self._reset_user(u)
                                self._confirm = {
                                    "msg": f'Reset all progress for "{uname}"?',
                                    "on_confirm": _do_rst,
                                }
                            elif btns["delete"].collidepoint(pos):
                                def _do_del(u=uname):
                                    self._delete_user(u)
                                self._confirm = {
                                    "msg": f'Permanently delete user "{uname}"?',
                                    "on_confirm": _do_del,
                                }

                    elif self.tab == 2:
                        for fname, er in lvl_edits.items():
                            if er.collidepoint(pos):
                                self._launch_editor(os.path.join(LEVELS_DIR, fname))
                        if lvl_regen and lvl_regen.collidepoint(pos):
                            self._confirm = {
                                "msg": "Regenerate all 6 built-in levels? Unsaved edits will be lost.",
                                "on_confirm": self._regen_builtin,
                            }

                    elif self.tab == 3:
                        for wid, (sr, dr) in char_rects.items():
                            if sr.collidepoint(pos):
                                self._active = (wid, "scale")
                            elif dr.collidepoint(pos):
                                self._active = (wid, "sprite_dir")

                    elif self.tab == 4:
                        for key, fr in phys_rects.items():
                            if fr.collidepoint(pos):
                                self._active = key

            # ── Draw ──────────────────────────────────────────────────────────
            self.screen.blit(self._bg, (0, 0))

            title = self.fnt_title.render("ADMIN PANEL", True, ORANGE)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 28)))

            for i, (r, name) in enumerate(zip(tab_rects, self._TABS)):
                sel = (i == self.tab)
                c   = (62, 102, 182) if sel else (30, 30, 52)
                pygame.draw.rect(self.screen, c, r, border_radius=6)
                pygame.draw.rect(self.screen, (WHITE if sel else (58, 58, 88)),
                                 r, 2, border_radius=6)
                nt = self.fnt_tab.render(name, True, WHITE)
                self.screen.blit(nt, nt.get_rect(center=r.center))

            panel = pygame.Rect(10, 100, SCREEN_W - 20, SCREEN_H - 158)
            pygame.draw.rect(self.screen, (18, 18, 38), panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 80), panel, 2, border_radius=8)

            # Dispatch to tab draw
            dash_ref   = None
            user_acts  = {}
            lvl_edits  = {}
            lvl_regen  = None
            char_rects = {}
            phys_rects = {}

            if self.tab == 0:
                dash_ref = self._draw_dashboard(mpos)
            elif self.tab == 1:
                user_acts = self._draw_users_tab(mpos)
            elif self.tab == 2:
                lvl_edits, lvl_regen = self._draw_levels_tab(mpos)
            elif self.tab == 3:
                char_rects = self._draw_char_tab(mpos)
            elif self.tab == 4:
                phys_rects = self._draw_settings_tab(mpos)

            # Status bar
            if self._status:
                col = GREEN if self._status_ok else RED
                st = self.fnt.render(self._status, True, col)
                self.screen.blit(st, st.get_rect(
                    midleft=(20, SCREEN_H - 30)))

            if self.tab in (3, 4):
                self._draw_btn(save_btn, "Save All", (45, 135, 45), mpos)
            self._draw_btn(back_btn, "Back", (75, 75, 75), mpos)

            # Confirm overlay (drawn last so it's on top)
            if self._confirm is not None:
                self._confirm_rects = self._draw_confirm(mpos)
            else:
                self._confirm_rects = (None, None)

            pygame.display.flip()
            clock.tick(FPS)
