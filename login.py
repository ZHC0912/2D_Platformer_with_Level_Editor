import pygame
from settings import *

_ADMIN_USER = "admin"
_ADMIN_PASS = "admin1234"


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


class _InputField:
    def __init__(self, rect, placeholder="", password=False):
        self.rect        = pygame.Rect(rect)
        self.placeholder = placeholder
        self.password    = password
        self.text        = ""
        self.active      = False
        self._fnt        = _font(20)

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.KEYDOWN and self.active:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key not in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                if len(self.text) < 32 and ev.unicode.isprintable():
                    self.text += ev.unicode

    def draw(self, surface):
        border = WHITE if self.active else LTGRAY
        pygame.draw.rect(surface, (25, 25, 45), self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=6)
        display = ("*" * len(self.text)) if self.password else self.text
        rendered = self._fnt.render(display or self.placeholder,
                                    True,
                                    WHITE if display else GRAY)
        surface.blit(rendered, (self.rect.x + 10,
                                self.rect.centery - rendered.get_height() // 2))


class LoginScreen:
    def __init__(self, screen):
        self.screen = screen
        self.fnt_title = _font(56, bold=True)
        self.fnt_label = _font(18)
        self.fnt_msg   = _font(17)
        self._bg = self._make_bg()

        cx = SCREEN_W // 2
        fw, fh = 400, 40

        self.user_field = _InputField((cx - fw//2, 290, fw, fh), placeholder="Username")
        self.pass_field = _InputField((cx - fw//2, 355, fw, fh), placeholder="Password",
                                      password=True)

        # Buttons:  [Login]  [Register]  — row 1
        #           [Admin]  [Play as Guest] — row 2
        bw, bh = 185, 46
        gap = 16
        total = bw * 2 + gap
        lx = cx - total // 2
        self.btn_login    = pygame.Rect(lx,          430, bw, bh)
        self.btn_register = pygame.Rect(lx + bw + gap, 430, bw, bh)
        self.btn_admin    = pygame.Rect(lx,          492, bw, bh)
        self.btn_guest    = pygame.Rect(lx + bw + gap, 492, bw, bh)

        self._status       = ""
        self._status_color = RED

    # ── Background ────────────────────────────────────────────────────────────

    def _make_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            pygame.draw.line(surf,
                             (int(10+20*t), int(5+15*t), int(30+40*t)),
                             (0, y), (SCREEN_W, y))
        return surf

    # ── Button helper ─────────────────────────────────────────────────────────

    def _draw_btn(self, rect, text, color, hover_pos):
        hov = rect.collidepoint(hover_pos)
        c   = tuple(min(255, v + 30) for v in color) if hov else color
        pygame.draw.rect(self.screen, c, rect, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, rect, 2, border_radius=8)
        t = _font(18, bold=True).render(text, True, WHITE)
        self.screen.blit(t, t.get_rect(center=rect.center))

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _try_login(self):
        from save_manager import authenticate
        u = self.user_field.text.strip()
        p = self.pass_field.text
        if not u:
            self._status = "Please enter a username.";  self._status_color = RED
            return None
        data = authenticate(u, p)
        if data is None:
            self._status = "Incorrect username or password."
            self._status_color = RED
            return None
        self._status = f"Welcome back, {u}!";  self._status_color = GREEN
        return ("play", u, data)

    def _try_register(self):
        from save_manager import register
        u = self.user_field.text.strip()
        p = self.pass_field.text
        if not u:
            self._status = "Please enter a username.";  self._status_color = RED
            return None
        if len(p) < 4:
            self._status = "Password must be at least 4 characters."
            self._status_color = RED
            return None
        # Block admin username
        if u.lower() == _ADMIN_USER:
            self._status = "That username is reserved.";  self._status_color = RED
            return None
        data = register(u, p)
        if data is None:
            self._status = f"'{u}' already exists — try logging in."
            self._status_color = YELLOW
            return None
        self._status = f"Account created! Welcome, {u}!"
        self._status_color = GREEN
        return ("play", u, data)

    def _try_admin(self):
        u = self.user_field.text.strip()
        p = self.pass_field.text
        if u == _ADMIN_USER and p == _ADMIN_PASS:
            return ("admin", u, None)
        self._status = "Invalid admin credentials."
        self._status_color = RED
        return None

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """
        Blocking loop.  Returns (mode, username, save_data) where mode is:
          "play"  — start/continue game session
          "admin" — open admin panel
          "quit"  — exit application
        username and save_data are None for guest and admin modes.
        """
        clock = pygame.time.Clock()

        while True:
            mouse_pos = pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return ("quit", None, None)

                self.user_field.handle_event(ev)
                self.pass_field.handle_event(ev)

                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                    result = self._try_login()
                    if result:
                        return result

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = ev.pos
                    if self.btn_login.collidepoint(pos):
                        r = self._try_login()
                        if r: return r
                    elif self.btn_register.collidepoint(pos):
                        r = self._try_register()
                        if r: return r
                    elif self.btn_admin.collidepoint(pos):
                        r = self._try_admin()
                        if r: return r
                    elif self.btn_guest.collidepoint(pos):
                        return ("play", None, None)

            # ── Draw ──────────────────────────────────────────────────────────
            self.screen.blit(self._bg, (0, 0))

            # Title
            title = self.fnt_title.render("2D PLATFORMER", True, CYAN)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 130)))

            sub = self.fnt_label.render(
                "Login to save your progress, or play as a guest.", True, LTGRAY)
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_W // 2, 192)))

            # Field labels
            ul = self.fnt_label.render("Username:", True, WHITE)
            self.screen.blit(ul, (self.user_field.rect.x, self.user_field.rect.y - 22))
            pl = self.fnt_label.render("Password:", True, WHITE)
            self.screen.blit(pl, (self.pass_field.rect.x, self.pass_field.rect.y - 22))

            self.user_field.draw(self.screen)
            self.pass_field.draw(self.screen)

            # Buttons
            self._draw_btn(self.btn_login,    "Login",         (50, 150, 50),  mouse_pos)
            self._draw_btn(self.btn_register, "Register",      (50, 80,  160), mouse_pos)
            self._draw_btn(self.btn_admin,    "Admin Login",   (150, 80, 20),  mouse_pos)
            self._draw_btn(self.btn_guest,    "Play as Guest", (70,  70,  70), mouse_pos)

            # Status message
            if self._status:
                st = self.fnt_msg.render(self._status, True, self._status_color)
                self.screen.blit(st, st.get_rect(center=(SCREEN_W // 2, 565)))

            # Hint text
            hint = self.fnt_msg.render(
                "New player? Enter a username + password and click Register.",
                True, (100, 100, 130))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_W // 2, SCREEN_H - 20)))

            pygame.display.flip()
            clock.tick(FPS)
