import pygame, json, os
from settings import *
from save_manager import load_user_save, reset_user_save
import character_data as _cd
import enemy_data     as _ed

from admin_dashboard  import DashboardMixin,   _all_users
from admin_users      import UsersMixin
from admin_levels     import LevelsMixin,      _builtin_metas, _custom_fnames
from admin_characters import CharactersMixin,  _CHAR_CATS, _CHAR_NAMES, _INT_FIELDS
from admin_enemies    import (EnemiesMixin,
                              _ENEMY_ORDER, _ENEMY_CATS, _ENEMY_ROW_LABEL,
                              _ENEMY_EXTRA, _ENEMY_FLOAT_FIELDS, _ENEMY_STR_FIELDS)
from admin_settings   import SettingsMixin,    _PHYS_FIELDS, _PHYS_DEFAULTS

_SETTINGS_FILE = "settings.json"


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


# ──────────────────────────────────────────────────────────────────────────────

class AdminPanel(DashboardMixin, UsersMixin, LevelsMixin,
                 CharactersMixin, EnemiesMixin, SettingsMixin):

    _TABS      = ["Dashboard", "Users", "Levels", "Characters", "Enemies", "Settings"]
    _THUMB_SIZE = 200

    # ── Init ──────────────────────────────────────────────────────────────────

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

        loaded = _cd.load()
        self._chars = {}
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            c = loaded.get(wid, _cd.DEFAULTS.get(wid, {}))
            self._chars[wid] = {k: str(v) for k, v in c.items()}

        eloaded = _ed.load()
        self._enemies = {}
        for eid in _ENEMY_ORDER:
            e = eloaded.get(eid, _ed.DEFAULTS.get(eid, {}))
            self._enemies[eid] = {k: str(v) for k, v in e.items()}

        self._active        = None
        self._status        = ""
        self._status_ok     = True
        self._users         = []
        self._level_metas   = []
        self._custom_lvls   = []
        self._user_scroll   = 0
        self._confirm       = None
        self._confirm_rects = (None, None)

        self._char_detail  = None
        self._enemy_detail = None
        self._char_thumbs  = {}
        self._enemy_thumbs = {}
        self._load_all_thumbs()

        self._refresh_data()

    # ── Data refresh ──────────────────────────────────────────────────────────

    def _refresh_data(self):
        self._users       = _all_users()
        self._level_metas = _builtin_metas()
        self._custom_lvls = _custom_fnames()

    # ── Shared UI helpers ─────────────────────────────────────────────────────

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill((12, 12, 28))
        return surf

    def _draw_btn(self, rect, text, color, mpos, surface=None):
        sf  = surface or self.screen
        hov = rect.collidepoint(mpos)
        if not hov:
            sh = tuple(max(0, v - 55) for v in color)
            pygame.draw.rect(sf, sh,
                             pygame.Rect(rect.x + 2, rect.y + 3, rect.w, rect.h),
                             border_radius=8)
        face = rect.move(0, 2 if hov else 0)
        c    = tuple(min(255, v + 20) for v in color) if hov else color
        pygame.draw.rect(sf, c, face, border_radius=8)
        pygame.draw.rect(sf, tuple(min(255, v + 50) for v in c), face, 2, border_radius=8)
        t = self.fnt.render(text, True, WHITE)
        sf.blit(t, t.get_rect(center=face.center))

    def _draw_field(self, rect, value, active, surface=None):
        sf = surface or self.screen
        pygame.draw.rect(sf, (28, 28, 52), rect, border_radius=4)
        pygame.draw.rect(sf, WHITE if active else (80, 80, 110), rect, 2, border_radius=4)
        t = self.fnt.render(value + ("|" if active else ""), True, WHITE)
        sf.blit(t, (rect.x + 6, rect.centery - t.get_height() // 2))

    def _row_bg(self, y, w, h, i):
        c = (30, 40, 68) if i % 2 == 0 else (20, 28, 50)
        pygame.draw.rect(self.screen, c, pygame.Rect(20, y, w, h - 2), border_radius=3)

    # ── Thumbnail helpers (shared by Characters & Enemies mixins) ─────────────

    def _load_all_thumbs(self):
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            sd = self._chars[wid].get("sprite_dir", "")
            self._char_thumbs[wid] = self._load_thumb(sd, self._THUMB_SIZE)

        from enemies import _load_enemy_anim, _TINTS
        for eid in _ENEMY_ORDER:
            tint = _TINTS.get(eid)
            anim = _load_enemy_anim(eid, self._THUMB_SIZE, tint)
            if anim:
                for sname in ("idle", "walk", "attack", "attack2", "hurt"):
                    frames = anim._states.get(sname, {}).get("frames", [])
                    if frames:
                        self._enemy_thumbs[eid] = self._fit_square(
                            frames[0], self._THUMB_SIZE)
                        break

    def _fit_square(self, surf, size):
        w, h   = surf.get_size()
        scale  = size / max(w, h)
        nw, nh = int(w * scale), int(h * scale)
        scaled = pygame.transform.smoothscale(surf, (nw, nh))
        result = pygame.Surface((size, size), pygame.SRCALPHA)
        result.blit(scaled, ((size - nw) // 2, (size - nh) // 2))
        return result

    def _load_thumb(self, sprite_dir, size):
        if not os.path.isdir(sprite_dir):
            return None
        for fname in ["Idle.png", "idle.png", "Walk.png", "Run.png", "walk.png",
                      "Attack.png", "Attack3.png", "Attack1.png", "attack.png"]:
            fpath = os.path.join(sprite_dir, fname)
            if os.path.exists(fpath):
                try:
                    raw   = pygame.image.load(fpath).convert_alpha()
                    h     = raw.get_height()
                    frame = pygame.Surface((h, h), pygame.SRCALPHA)
                    frame.blit(raw, (0, 0), pygame.Rect(0, 0, h, h))
                    return pygame.transform.smoothscale(frame, (size, size))
                except Exception:
                    pass
        return None

    def _fallback_thumb(self, label, color, size):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(surf, color, (0, 0, size, size), border_radius=14)
        pygame.draw.rect(surf, tuple(min(255, v + 60) for v in color),
                         (0, 0, size, size), 2, border_radius=14)
        t = self.fnt_big.render(label[0].upper(), True, WHITE)
        surf.blit(t, t.get_rect(center=(size // 2, size // 2)))
        return surf

    def _draw_card(self, rect, thumb, name, sub_text, base_color, mpos):
        hov = rect.collidepoint(mpos)
        bg  = tuple(min(255, v + (18 if hov else 0)) for v in base_color)
        pygame.draw.rect(self.screen, bg, rect, border_radius=14)
        acc = tuple(min(255, v + 70) for v in base_color)
        pygame.draw.rect(self.screen, acc,
                         pygame.Rect(rect.x, rect.y, rect.w, 5), border_radius=14)
        brd = tuple(min(255, v + (90 if hov else 45)) for v in base_color)
        pygame.draw.rect(self.screen, brd, rect, 2 if not hov else 3, border_radius=14)

        TS = min(rect.w - 30, rect.h - 58)
        tx = rect.x + (rect.w - TS) // 2
        ty = rect.y + 12
        if thumb:
            self.screen.blit(pygame.transform.smoothscale(thumb, (TS, TS)), (tx, ty))
        else:
            self.screen.blit(
                self._fallback_thumb(name, tuple(min(255,v+30) for v in base_color), TS),
                (tx, ty))

        nt = self.fnt_hd.render(name, True, WHITE)
        self.screen.blit(nt, nt.get_rect(centerx=rect.centerx, top=ty + TS + 6))
        if sub_text:
            st = self.fnt_sm.render(sub_text, True, (170, 175, 200))
            self.screen.blit(st, st.get_rect(centerx=rect.centerx, top=ty + TS + 22))

    # ── Confirm overlay ───────────────────────────────────────────────────────

    def _draw_confirm(self, mpos):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        self.screen.blit(ov, (0, 0))
        bw, bh = 500, 170
        bx, by = SCREEN_W // 2 - bw // 2, SCREEN_H // 2 - bh // 2
        pygame.draw.rect(self.screen, (22, 25, 48), (bx, by, bw, bh), border_radius=12)
        pygame.draw.rect(self.screen, ORANGE,       (bx, by, bw, bh), 2, border_radius=12)
        t = self.fnt_hd.render("Confirm Action", True, ORANGE)
        self.screen.blit(t, t.get_rect(centerx=bx + bw // 2, top=by + 16))
        m = self.fnt.render(self._confirm["msg"], True, LTGRAY)
        self.screen.blit(m, m.get_rect(centerx=bx + bw // 2, top=by + 58))
        ok_r  = pygame.Rect(bx + bw // 2 - 125, by + 112, 110, 36)
        can_r = pygame.Rect(bx + bw // 2 +  15, by + 112, 110, 36)
        self._draw_btn(ok_r,  "Confirm", (160, 38, 38), mpos)
        self._draw_btn(can_r, "Cancel",  (55,  55, 85), mpos)
        return ok_r, can_r

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save_all(self):
        data = _load_settings()
        for key in _PHYS_DEFAULTS:
            try:
                data[key] = float(self._phys[key])
            except ValueError:
                self._status    = f"Invalid value for {key}"
                self._status_ok = False
                return
        data.pop("characters", None)
        _save_settings(data)

        chars = {}
        for wid in [W_SWORD, W_BOW, W_STAFF]:
            entry = {}
            for key, val in self._chars[wid].items():
                if key in _INT_FIELDS:
                    try:
                        entry[key] = int(val)
                    except ValueError:
                        self._status    = f"Invalid value for {key} ({_CHAR_NAMES.get(wid, wid)})"
                        self._status_ok = False
                        return
                else:
                    entry[key] = val.strip()
            chars[wid] = entry
        _cd.save(chars)
        _cd.CHARS.update(chars)

        enemies = {}
        for eid in _ENEMY_ORDER:
            entry = {}
            for key, val in self._enemies[eid].items():
                if key in _ENEMY_STR_FIELDS:
                    entry[key] = val.strip()
                elif key in _ENEMY_FLOAT_FIELDS:
                    try:
                        entry[key] = float(val)
                    except ValueError:
                        self._status    = f"Invalid value for {key} ({_ENEMY_ROW_LABEL.get(eid, eid)})"
                        self._status_ok = False
                        return
                else:
                    try:
                        entry[key] = int(val)
                    except ValueError:
                        self._status    = f"Invalid value for {key} ({_ENEMY_ROW_LABEL.get(eid, eid)})"
                        self._status_ok = False
                        return
            enemies[eid] = entry
        _ed.save(enemies)
        _ed.ENEMIES.update(enemies)
        self._status    = "Saved.  Stats take effect on next game launch."
        self._status_ok = True

    # ── Keyboard input ────────────────────────────────────────────────────────

    def _type(self, ch):
        if self._active is None:
            return
        if isinstance(self._active, tuple) and len(self._active) == 3:
            eid, key, _ = self._active
            if key not in _ENEMY_STR_FIELDS:
                allowed = "0123456789." if key in _ENEMY_FLOAT_FIELDS else "0123456789"
                if ch not in allowed:
                    return
            self._enemies[eid][key] = self._enemies[eid].get(key, "") + ch
        elif isinstance(self._active, tuple):
            wid, sub = self._active
            if sub in _INT_FIELDS and ch not in "0123456789":
                return
            self._chars[wid][sub] = self._chars[wid].get(sub, "") + ch
        else:
            if ch not in "0123456789.-":
                return
            self._phys[self._active] += ch

    def _backspace(self):
        if self._active is None:
            return
        if isinstance(self._active, tuple) and len(self._active) == 3:
            eid, key, _ = self._active
            self._enemies[eid][key] = self._enemies[eid].get(key, "")[:-1]
        elif isinstance(self._active, tuple):
            wid, sub = self._active
            self._chars[wid][sub] = self._chars[wid].get(sub, "")[:-1]
        else:
            self._phys[self._active] = self._phys[self._active][:-1]

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        clock    = pygame.time.Clock()
        N        = len(self._TABS)
        TAB_W    = (SCREEN_W - 40) // N
        tab_rects = [pygame.Rect(20 + i * (TAB_W + 2), 56, TAB_W, 36) for i in range(N)]
        back_btn  = pygame.Rect(SCREEN_W - 130, SCREEN_H - 48, 108, 34)
        save_btn  = pygame.Rect(SCREEN_W - 250, SCREEN_H - 48, 108, 34)

        dash_ref = None;  user_acts = {};  lvl_edits = {};  lvl_regen = None
        char_rects = {};  enemy_rects = {};  phys_rects = {}

        while True:
            mpos = pygame.mouse.get_pos()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"

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

                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
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
                            self.tab           = i
                            self._user_scroll  = 0
                            self._char_detail  = None
                            self._enemy_detail = None
                            self._active       = None

                    if back_btn.collidepoint(pos):
                        return "menu"

                    if self.tab in (3, 4, 5) and save_btn.collidepoint(pos):
                        self._save_all()

                    if self.tab == 0:
                        if dash_ref and dash_ref.collidepoint(pos):
                            self._refresh_data()

                    elif self.tab == 1:
                        for uname, btns in user_acts.items():
                            if btns["reset"].collidepoint(pos):
                                def _do_rst(u=uname): self._reset_user(u)
                                self._confirm = {"msg": f'Reset all progress for "{uname}"?',
                                                 "on_confirm": _do_rst}
                            elif btns["delete"].collidepoint(pos):
                                def _do_del(u=uname): self._delete_user(u)
                                self._confirm = {"msg": f'Permanently delete user "{uname}"?',
                                                 "on_confirm": _do_del}

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
                        if "_gallery" in char_rects:
                            for wid, cr in char_rects["_gallery"].items():
                                if cr.collidepoint(pos):
                                    self._char_detail = wid;  self._active = None
                        else:
                            if char_rects.get("_back", pygame.Rect(0,0,0,0)).collidepoint(pos):
                                self._char_detail = None;  self._active = None
                            else:
                                for fname, frect in char_rects.items():
                                    if not fname.startswith("_") and frect.collidepoint(pos):
                                        self._active = (self._char_detail, fname)

                    elif self.tab == 4:
                        if "_gallery" in enemy_rects:
                            for eid, cr in enemy_rects["_gallery"].items():
                                if cr.collidepoint(pos):
                                    self._enemy_detail = eid;  self._active = None
                        else:
                            if enemy_rects.get("_back", pygame.Rect(0,0,0,0)).collidepoint(pos):
                                self._enemy_detail = None;  self._active = None
                            else:
                                for fname, frect in enemy_rects.items():
                                    if not fname.startswith("_") and frect.collidepoint(pos):
                                        self._active = (self._enemy_detail, fname, "enemy")

                    elif self.tab == 5:
                        for key, fr in phys_rects.items():
                            if fr.collidepoint(pos):
                                self._active = key

            # ── Draw ──────────────────────────────────────────────────────────
            self.screen.blit(self._bg, (0, 0))
            title = self.fnt_title.render("ADMIN PANEL", True, ORANGE)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 28)))

            for i, (r, name) in enumerate(zip(tab_rects, self._TABS)):
                sel = (i == self.tab)
                pygame.draw.rect(self.screen, (62,102,182) if sel else (30,30,52),
                                 r, border_radius=6)
                pygame.draw.rect(self.screen, WHITE if sel else (58,58,88),
                                 r, 2, border_radius=6)
                nt = self.fnt_tab.render(name, True, WHITE)
                self.screen.blit(nt, nt.get_rect(center=r.center))

            panel = pygame.Rect(10, 100, SCREEN_W - 20, SCREEN_H - 158)
            pygame.draw.rect(self.screen, (18, 18, 38), panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 80), panel, 2, border_radius=8)

            dash_ref = None;  user_acts = {};  lvl_edits = {};  lvl_regen = None
            char_rects = {};  enemy_rects = {};  phys_rects = {}

            if   self.tab == 0: dash_ref              = self._draw_dashboard(mpos)
            elif self.tab == 1: user_acts             = self._draw_users_tab(mpos)
            elif self.tab == 2: lvl_edits, lvl_regen  = self._draw_levels_tab(mpos)
            elif self.tab == 3: char_rects             = self._draw_char_tab(mpos)
            elif self.tab == 4: enemy_rects            = self._draw_enemies_tab(mpos)
            elif self.tab == 5: phys_rects             = self._draw_settings_tab(mpos)

            if self._status:
                col = GREEN if self._status_ok else RED
                st  = self.fnt.render(self._status, True, col)
                self.screen.blit(st, st.get_rect(midleft=(20, SCREEN_H - 30)))

            if self.tab in (3, 4, 5):
                self._draw_btn(save_btn, "Save All", (45, 135, 45), mpos)
            self._draw_btn(back_btn, "Back", (75, 75, 75), mpos)

            if self._confirm is not None:
                self._confirm_rects = self._draw_confirm(mpos)
            else:
                self._confirm_rects = (None, None)

            pygame.display.flip()
            clock.tick(FPS)
