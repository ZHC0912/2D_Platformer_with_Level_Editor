import pygame, os, math
from settings import *
from save_manager import load_save, reset_user_save
from ui_helpers import make_orb as _make_orb


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


class Button:
    def __init__(self, text, rect, color=BLUE, text_color=WHITE, fnt=None):
        self.text  = text
        self.rect  = pygame.Rect(rect)
        self.color = color
        self.text_color = text_color
        self.fnt   = fnt or _font(22, bold=True)
        self.hovered = False

    def draw(self, surface):
        r   = self.rect
        rad = 16

        # Drop shadow — only shown when the button is raised (not hovered)
        if not self.hovered:
            sh_c = tuple(max(0, v - 55) for v in self.color)
            pygame.draw.rect(surface, sh_c,
                             pygame.Rect(r.x + 3, r.y + 5, r.w - 2, r.h),
                             border_radius=rad)

        # Button face — sinks 4 px when hovered to simulate a press
        press  = 4 if self.hovered else 0
        face   = r.move(0, press)
        c      = tuple(min(255, v + 25) for v in self.color) if self.hovered else self.color
        pygame.draw.rect(surface, c, face, border_radius=rad)

        # Highlight strip near the top
        hi_c = tuple(min(255, v + 75) for v in c)
        pygame.draw.rect(surface, hi_c,
                         pygame.Rect(face.x + 8, face.y + 5, face.w - 16, 5),
                         border_radius=2)

        # Border (slightly lighter than the face colour)
        bc = tuple(min(255, v + 55) for v in c)
        pygame.draw.rect(surface, bc, face, 2, border_radius=rad)

        # Text with a soft dark shadow for depth
        t  = self.fnt.render(self.text, True, self.text_color)
        tc = t.get_rect(center=face.center)
        ts = self.fnt.render(self.text, True, (0, 0, 0))
        ts.set_alpha(80)
        surface.blit(ts, tc.move(1, 2))
        surface.blit(t, tc)

    def check(self, pos):
        self.hovered = self.rect.collidepoint(pos)
        return self.hovered

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


class MainMenu:
    def __init__(self, screen, save_data=None, username=None):
        self.screen    = screen
        self.save_data = save_data   # None → load from disk (legacy / guest)
        self.username  = username    # None → guest
        self.fnt_title = _font(56, bold=True)
        self.fnt_sub   = _font(18)
        cx = SCREEN_W // 2
        bw, bh = 320, 52
        self.buttons = [
            Button("Play",         (cx-bw//2, 230, bw, bh), color=(50,150,50)),
            Button("Level Editor", (cx-bw//2, 295, bw, bh), color=(50,80,160)),
            Button("Level Select", (cx-bw//2, 360, bw, bh), color=(80,50,150)),
            Button("Reset Save",   (cx-bw//2, 425, bw, bh), color=(160,80,30)),
            Button("Logout",       (cx-bw//2, 490, bw, bh), color=(100,30,30)),
            Button("Quit",         (cx-bw//2, 555, bw, bh), color=(80,80,80)),
        ]
        self._bg = self._make_bg()

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            r = int(10 + 20*t)
            g = int(5  + 15*t)
            b = int(30 + 40*t)
            pygame.draw.line(surf, (r,g,b), (0,y), (SCREEN_W,y))
        return surf

    def run(self):
        clock = pygame.time.Clock()
        while True:
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    if self.buttons[0].clicked(pos): return "play"
                    if self.buttons[1].clicked(pos): return "editor"
                    if self.buttons[2].clicked(pos): return "level_select"
                    if self.buttons[3].clicked(pos):
                        if self.username:
                            self.save_data = reset_user_save(self.username)
                        return "main"
                    if self.buttons[4].clicked(pos): return "logout"
                    if self.buttons[5].clicked(pos): return "quit"

            self.screen.blit(self._bg, (0, 0))

            title = self.fnt_title.render("2D PLATFORMER", True, CYAN)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W//2, 120)))

            # Username / guest greeting
            greet_name = self.username if self.username else "Guest"
            greet_col  = WHITE if self.username else GRAY
            greet = self.fnt_sub.render(f"Playing as: {greet_name}", True, greet_col)
            self.screen.blit(greet, greet.get_rect(center=(SCREEN_W//2, 178)))

            pos = pygame.mouse.get_pos()
            for btn in self.buttons:
                btn.check(pos)
                btn.draw(self.screen)

            # Progress bar at bottom
            save = self.save_data if self.save_data is not None else load_save()
            info = self.fnt_sub.render(
                f"Progress: Level {save['level_reached']}  |  "
                f"Coins: {save['coins_total']}  |  "
                f"Weapons: {', '.join(save['unlocked_weapons'])}",
                True, GRAY)
            self.screen.blit(info, info.get_rect(center=(SCREEN_W//2, SCREEN_H-24)))

            pygame.display.flip()
            clock.tick(FPS)


class LevelSelectMenu:
    _ORB = 38   # orb diameter in pixels

    def __init__(self, screen, save_data=None):
        self.screen    = screen
        self.save_data = save_data
        self.fnt_title = _font(36, bold=True)
        self.fnt       = _font(20)
        self.fnt_sm    = _font(15)
        self._bg = self._make_bg()

        s = self._ORB
        # Locked  → pulsing dark-purple "?" orb
        self._orb_lock = _make_orb(s, (45, 15, 75),  (150, 60, 210), "?", (210, 170, 255))
        # Unlocked → teal "★" orb
        self._orb_open = _make_orb(s, (15, 95,  65),  (60, 210, 140), "★", (190, 255, 215))
        # Tutorial → gold "★" orb
        self._orb_tut  = _make_orb(s, (115, 80,  5),  (250, 195,  35), "★", (255, 245, 160))

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill((10, 15, 30))
        return surf

    def run(self):
        clock = pygame.time.Clock()
        save  = self.save_data if self.save_data is not None else load_save()
        custom = self._get_custom_levels()

        all_levels = [("★  Tutorial  (Start Here)", "custom:tutorial.json", True)]
        all_levels += [(f"Level {i+1}", f"builtin:{i}", i < save["level_reached"])
                       for i in range(5)]
        for fname in custom:
            if fname != "tutorial.json":
                all_levels.append((fname[:-5], f"custom:{fname}", True))

        scroll = 0
        row_h  = 52
        list_top = 110
        visible_h = SCREEN_H - list_top - 70
        max_scroll = max(0, len(all_levels) * row_h - visible_h)

        while True:
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    return ("quit", None)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return ("menu", None)
                if ev.type == pygame.MOUSEWHEEL:
                    scroll = max(0, min(scroll - ev.y * 30, max_scroll))
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    for i, (name, key, unlocked) in enumerate(all_levels):
                        ry = list_top + i * row_h - scroll
                        if ry + row_h < list_top or ry > SCREEN_H - 70:
                            continue
                        r = pygame.Rect(SCREEN_W//2 - 220, ry, 440, 44)
                        if r.collidepoint(pos) and unlocked:
                            return ("select", key)
                    back_r = pygame.Rect(SCREEN_W//2 - 100, SCREEN_H - 58, 200, 40)
                    if back_r.collidepoint(pos):
                        return ("menu", None)

            self.screen.blit(self._bg, (0, 0))
            title = self.fnt_title.render("SELECT LEVEL", True, CYAN)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W//2, 62)))

            clip = pygame.Rect(0, list_top, SCREEN_W, visible_h)
            self.screen.set_clip(clip)
            mpos = pygame.mouse.get_pos()
            s    = self._ORB
            now  = pygame.time.get_ticks()

            for i, (name, key, unlocked) in enumerate(all_levels):
                ry = list_top + i * row_h - scroll
                if ry + row_h < list_top or ry > SCREEN_H - 70:
                    continue

                r      = pygame.Rect(SCREEN_W//2 - 220, ry, 440, 44)
                hov    = r.collidepoint(mpos) and unlocked
                is_tut = (key == "custom:tutorial.json")

                # Row background
                if is_tut and unlocked:
                    base   = (120, 95, 15) if not hov else (155, 120, 25)
                    border = YELLOW
                elif unlocked:
                    base   = (35, 70, 55) if not hov else (45, 130, 85)
                    border = (80, 200, 140)
                else:
                    base, border = (30, 20, 45), (90, 55, 120)
                pygame.draw.rect(self.screen, base,   r, border_radius=8)
                pygame.draw.rect(self.screen, border, r, 2, border_radius=8)

                # Pick orb
                if not unlocked:
                    orb = self._orb_lock
                elif is_tut:
                    orb = self._orb_tut
                else:
                    orb = self._orb_open

                # Pulsing outer glow ring on locked orbs
                ox = r.x + 4
                oy = r.y + (r.h - s) // 2
                if not unlocked:
                    pulse  = 0.5 + 0.5 * math.sin(now / 550 + i * 1.1)
                    ga     = int(35 + 55 * pulse)
                    gr     = int(s // 2 + 4 + 4 * pulse)
                    gsurf  = pygame.Surface((gr * 2 + 4, gr * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(gsurf, (150, 60, 210, ga),
                                       (gr + 2, gr + 2), gr)
                    self.screen.blit(gsurf, (ox + s // 2 - gr - 2,
                                             oy + s // 2 - gr - 2))

                self.screen.blit(orb, (ox, oy))

                # Level name (shifted right to leave room for the orb)
                txt_col = YELLOW if is_tut else (WHITE if unlocked else (160, 110, 200))
                t = self.fnt.render(name, True, txt_col)
                text_cx = r.x + s + 12 + (r.w - s - 16) // 2
                self.screen.blit(t, t.get_rect(center=(text_cx, r.centery)))

            self.screen.set_clip(None)

            back = pygame.Rect(SCREEN_W//2 - 100, SCREEN_H - 58, 200, 40)
            pygame.draw.rect(self.screen, (80, 80, 80), back, border_radius=6)
            bt = self.fnt.render("Back", True, WHITE)
            self.screen.blit(bt, bt.get_rect(center=back.center))

            if max_scroll > 0:
                hint = self.fnt_sm.render("Scroll to see more", True, GRAY)
                self.screen.blit(hint, hint.get_rect(center=(SCREEN_W//2, SCREEN_H - 12)))

            pygame.display.flip()
            clock.tick(FPS)

    def _get_custom_levels(self):
        if not os.path.isdir(LEVELS_DIR):
            return []
        builtin = set(BUILTIN_LEVELS)
        files = sorted(f for f in os.listdir(LEVELS_DIR)
                       if f.endswith(".json") and f not in builtin)
        return files


class PauseMenu:
    def __init__(self, screen):
        self.screen = screen
        self.fnt_title = _font(40, bold=True)
        self.fnt       = _font(22, bold=True)
        cx = SCREEN_W // 2
        bw, bh = 280, 48
        self.buttons = [
            Button("Resume",      (cx-bw//2, 260, bw, bh), color=(50,150,50)),
            Button("Level Editor",(cx-bw//2, 320, bw, bh), color=(50,80,160)),
            Button("Main Menu",   (cx-bw//2, 380, bw, bh), color=(80,80,80)),
            Button("Quit",        (cx-bw//2, 440, bw, bh), color=(160,50,50)),
        ]

    def run(self):
        clock = pygame.time.Clock()
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        snap = self.screen.copy()

        while True:
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "resume"
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    if self.buttons[0].clicked(pos): return "resume"
                    if self.buttons[1].clicked(pos): return "editor"
                    if self.buttons[2].clicked(pos): return "menu"
                    if self.buttons[3].clicked(pos): return "quit"

            self.screen.blit(snap, (0, 0))
            self.screen.blit(overlay, (0, 0))
            title = self.fnt_title.render("PAUSED", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W//2, 200)))
            pos = pygame.mouse.get_pos()
            for btn in self.buttons:
                btn.check(pos)
                btn.draw(self.screen)
            pygame.display.flip()
            clock.tick(FPS)
