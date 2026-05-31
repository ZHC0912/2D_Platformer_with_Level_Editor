import pygame, os
from settings import *
from save_manager import load_save, reset_user_save


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
        c = tuple(min(255, v+30) for v in self.color) if self.hovered else self.color
        pygame.draw.rect(surface, c, self.rect, border_radius=8)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=8)
        t = self.fnt.render(self.text, True, self.text_color)
        surface.blit(t, t.get_rect(center=self.rect.center))

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
    def __init__(self, screen, save_data=None):
        self.screen    = screen
        self.save_data = save_data
        self.fnt_title = _font(36, bold=True)
        self.fnt       = _font(20)
        self.fnt_sm    = _font(15)
        self._bg = self._make_bg()

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
            pos = pygame.mouse.get_pos()
            for i, (name, key, unlocked) in enumerate(all_levels):
                ry = list_top + i * row_h - scroll
                if ry + row_h < list_top or ry > SCREEN_H - 70:
                    continue
                r = pygame.Rect(SCREEN_W//2 - 220, ry, 440, 44)
                hov = r.collidepoint(pos) and unlocked
                is_tut = (key == "custom:tutorial.json")
                if is_tut and unlocked:
                    base = (100, 80, 20) if not hov else (140, 110, 30)
                    border = YELLOW
                elif unlocked:
                    base = (60, 80, 60) if not hov else (50, 150, 50)
                    border = WHITE
                else:
                    base, border = (40, 40, 40), GRAY
                pygame.draw.rect(self.screen, base, r, border_radius=6)
                pygame.draw.rect(self.screen, border, r, 2, border_radius=6)
                t = self.fnt.render(name, True, YELLOW if is_tut else (WHITE if unlocked else GRAY))
                self.screen.blit(t, t.get_rect(center=r.center))
                if not unlocked:
                    lock = self.fnt_sm.render("[Locked]", True, (150, 80, 80))
                    self.screen.blit(lock, (r.right - 80, r.centery - 8))
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
