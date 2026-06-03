import pygame
from settings import *

_ADMIN_USER = "admin"
_ADMIN_PASS = ""

_CLR_BTN_PRIMARY = (45,  120,  55)   # green  — main action
_CLR_BTN_GHOST   = (55,   55,  75)   # muted  — secondary
_CLR_LINK        = (90,  180, 255)   # cyan-blue for hyperlinks


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


def _make_bg(screen_w, screen_h):
    surf = pygame.Surface((screen_w, screen_h))
    for y in range(screen_h):
        t = y / screen_h
        pygame.draw.line(surf,
                         (int(8 + 18*t), int(4 + 12*t), int(22 + 35*t)),
                         (0, y), (screen_w, y))
    return surf


# ── Shared input field ────────────────────────────────────────────────────────

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
        border = WHITE if self.active else (80, 85, 110)
        pygame.draw.rect(surface, (20, 20, 42), self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=8)
        display  = ("•" * len(self.text)) if self.password else self.text
        rendered = self._fnt.render(display or self.placeholder,
                                    True,
                                    WHITE if display else (90, 95, 120))
        surface.blit(rendered, (self.rect.x + 14,
                                self.rect.centery - rendered.get_height() // 2))


# ── Shared button helper ──────────────────────────────────────────────────────

def _draw_btn(screen, fnt, rect, text, color, mpos, full_round=True):
    rad = rect.h // 2 if full_round else 10
    hov = rect.collidepoint(mpos)
    if not hov:
        sh = tuple(max(0, v - 50) for v in color)
        pygame.draw.rect(screen, sh,
                         pygame.Rect(rect.x + 2, rect.y + 4, rect.w, rect.h),
                         border_radius=rad)
    face = rect.move(0, 3 if hov else 0)
    c    = tuple(min(255, v + 22) for v in color) if hov else color
    pygame.draw.rect(screen, c, face, border_radius=rad)
    pygame.draw.rect(screen, tuple(min(255, v + 60) for v in c),
                     face, 2, border_radius=rad)
    t  = fnt.render(text, True, WHITE)
    ts = fnt.render(text, True, (0, 0, 0))
    ts.set_alpha(70)
    tc = t.get_rect(center=face.center)
    screen.blit(ts, tc.move(1, 2))
    screen.blit(t, tc)


def _draw_link(screen, fnt, text, cx, y, mpos):
    """Draw a cyan hyperlink; returns its rect for click detection."""
    surf = fnt.render(text, True, _CLR_LINK)
    r    = surf.get_rect(centerx=cx, top=y)
    hov  = r.collidepoint(mpos)
    if hov:
        pygame.draw.line(screen, _CLR_LINK, (r.left, r.bottom), (r.right, r.bottom))
    screen.blit(surf, r)
    return r


def _draw_status(screen, fnt, msg, color, cx, y):
    if msg:
        s = fnt.render(msg, True, color)
        screen.blit(s, s.get_rect(centerx=cx, top=y))


# ── Screen 1: Welcome ─────────────────────────────────────────────────────────

class WelcomeScreen:
    """
    Startup screen — shows only the title and two buttons.
    Returns: "login" | "guest" | "quit"
    """

    def __init__(self, screen):
        self.screen    = screen
        self.fnt_title = _font(72, bold=True)
        self.fnt_sub   = _font(20)
        self.fnt_btn   = _font(20, bold=True)
        self._bg       = _make_bg(SCREEN_W, SCREEN_H)

        bw, bh = 280, 54
        cx = SCREEN_W // 2
        self.btn_login = pygame.Rect(cx - bw // 2, 390, bw, bh)
        self.btn_guest = pygame.Rect(cx - bw // 2, 460, bw, bh)

    def run(self):
        clock = pygame.time.Clock()
        while True:
            mpos = pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "quit"
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.btn_login.collidepoint(ev.pos):
                        return "login"
                    if self.btn_guest.collidepoint(ev.pos):
                        return "guest"

            self.screen.blit(self._bg, (0, 0))

            # Title
            title = self.fnt_title.render(TITLE, True, CYAN)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 240)))

            sub = self.fnt_sub.render(
                "Adventure awaits — save your progress or jump right in.", True, LTGRAY)
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_W // 2, 320)))

            _draw_btn(self.screen, self.fnt_btn,
                      self.btn_login, "Login", _CLR_BTN_PRIMARY, mpos)
            _draw_btn(self.screen, self.fnt_btn,
                      self.btn_guest, "Play as Guest", _CLR_BTN_GHOST, mpos)

            pygame.display.flip()
            clock.tick(FPS)


# ── Screen 2: Login ───────────────────────────────────────────────────────────

class LoginScreen:
    """
    Login form — single Login button.
    Admin credentials route to admin panel; player credentials to game.
    Returns: ("play"|"admin", username, save_data) | "register" | "back" | "quit"
    """

    def __init__(self, screen):
        self.screen    = screen
        self.fnt_hd    = _font(38, bold=True)
        self.fnt_lbl   = _font(16)
        self.fnt_btn   = _font(20, bold=True)
        self.fnt_link  = _font(15)
        self.fnt_msg   = _font(16)
        self._bg       = _make_bg(SCREEN_W, SCREEN_H)

        cx    = SCREEN_W // 2
        fw, fh = 400, 44
        fx     = cx - fw // 2

        self.user_field = _InputField((fx, 255, fw, fh), placeholder="Username")
        self.pass_field = _InputField((fx, 320, fw, fh), placeholder="Password",
                                      password=True)

        bw, bh = fw, 50
        self.btn_login  = pygame.Rect(fx, 392, bw, bh)

        self._status       = ""
        self._status_color = RED
        self._reg_link_r   = None   # set each frame
        self._back_link_r  = None

    def _try_login(self):
        u = self.user_field.text.strip()
        p = self.pass_field.text
        if not u:
            self._status = "Please enter your username."
            self._status_color = RED
            return None
        if u.lower() == _ADMIN_USER and p == _ADMIN_PASS:
            return ("admin", u, None)
        from save_manager import authenticate
        data = authenticate(u, p)
        if data is None:
            self._status = "Incorrect username or password."
            self._status_color = RED
            return None
        self._status = ""
        return ("play", u, data)

    def run(self):
        clock = pygame.time.Clock()
        while True:
            mpos = pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return "back"
                    if ev.key == pygame.K_RETURN:
                        r = self._try_login()
                        if r:
                            return r
                self.user_field.handle_event(ev)
                self.pass_field.handle_event(ev)
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.btn_login.collidepoint(ev.pos):
                        r = self._try_login()
                        if r:
                            return r
                    if self._reg_link_r and self._reg_link_r.collidepoint(ev.pos):
                        return "register"
                    if self._back_link_r and self._back_link_r.collidepoint(ev.pos):
                        return "back"

            self.screen.blit(self._bg, (0, 0))
            cx = SCREEN_W // 2

            # Header
            hd = self.fnt_hd.render("Login", True, WHITE)
            self.screen.blit(hd, hd.get_rect(center=(cx, 175)))

            # Field labels + fields
            for lbl, field in [("Username", self.user_field),
                                ("Password", self.pass_field)]:
                l = self.fnt_lbl.render(lbl, True, LTGRAY)
                self.screen.blit(l, (field.rect.x, field.rect.y - 20))
                field.draw(self.screen)

            _draw_btn(self.screen, self.fnt_btn,
                      self.btn_login, "Login", _CLR_BTN_PRIMARY, mpos)

            # "Don't have an account? Register" link
            gray_part = self.fnt_link.render("Don't have an account?  ", True, (120, 125, 150))
            gx = cx - (gray_part.get_width() +
                        self.fnt_link.size("Register")[0]) // 2
            gy = self.btn_login.bottom + 20
            self.screen.blit(gray_part, (gx, gy))
            self._reg_link_r = _draw_link(
                self.screen, self.fnt_link, "Register",
                gx + gray_part.get_width() + self.fnt_link.size("Register")[0] // 2,
                gy, mpos)

            # Back link
            self._back_link_r = _draw_link(
                self.screen, self.fnt_link, "← Back",
                cx, self.btn_login.bottom + 52, mpos)

            _draw_status(self.screen, self.fnt_msg,
                         self._status, self._status_color, cx,
                         self.btn_login.bottom + 80)

            pygame.display.flip()
            clock.tick(FPS)


# ── Screen 3: Register ────────────────────────────────────────────────────────

class RegisterScreen:
    """
    Registration form.
    Returns: ("play", username, save_data) | "back" | "quit"
    """

    def __init__(self, screen):
        self.screen   = screen
        self.fnt_hd   = _font(38, bold=True)
        self.fnt_lbl  = _font(16)
        self.fnt_btn  = _font(20, bold=True)
        self.fnt_link = _font(15)
        self.fnt_msg  = _font(16)
        self._bg      = _make_bg(SCREEN_W, SCREEN_H)

        cx     = SCREEN_W // 2
        fw, fh = 400, 44
        fx     = cx - fw // 2

        self.user_field    = _InputField((fx, 230, fw, fh), placeholder="Username")
        self.pass_field    = _InputField((fx, 300, fw, fh), placeholder="Password",
                                         password=True)
        self.confirm_field = _InputField((fx, 370, fw, fh),
                                         placeholder="Confirm Password", password=True)

        self.btn_register  = pygame.Rect(fx, 440, fw, 50)

        self._status       = ""
        self._status_color = RED
        self._login_link_r = None
        self._back_link_r  = None

    def _try_register(self):
        u  = self.user_field.text.strip()
        p  = self.pass_field.text
        p2 = self.confirm_field.text
        if not u:
            self._status = "Please enter a username."
            self._status_color = RED
            return None
        if u.lower() == _ADMIN_USER:
            self._status = "That username is reserved."
            self._status_color = RED
            return None
        if len(p) < 4:
            self._status = "Password must be at least 4 characters."
            self._status_color = RED
            return None
        if p != p2:
            self._status = "Passwords do not match."
            self._status_color = RED
            return None
        from save_manager import register
        data = register(u, p)
        if data is None:
            self._status = f'"{u}" is already taken — try logging in.'
            self._status_color = YELLOW
            return None
        self._status = ""
        return ("play", u, data)

    def run(self):
        clock = pygame.time.Clock()
        while True:
            mpos = pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return "back"
                    if ev.key == pygame.K_RETURN:
                        r = self._try_register()
                        if r:
                            return r
                self.user_field.handle_event(ev)
                self.pass_field.handle_event(ev)
                self.confirm_field.handle_event(ev)
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.btn_register.collidepoint(ev.pos):
                        r = self._try_register()
                        if r:
                            return r
                    if self._login_link_r and self._login_link_r.collidepoint(ev.pos):
                        return "back"
                    if self._back_link_r and self._back_link_r.collidepoint(ev.pos):
                        return "back"

            self.screen.blit(self._bg, (0, 0))
            cx = SCREEN_W // 2

            # Header
            hd = self.fnt_hd.render("Create Account", True, WHITE)
            self.screen.blit(hd, hd.get_rect(center=(cx, 155)))

            # Fields
            for lbl, field in [("Username",         self.user_field),
                                ("Password",         self.pass_field),
                                ("Confirm Password", self.confirm_field)]:
                l = self.fnt_lbl.render(lbl, True, LTGRAY)
                self.screen.blit(l, (field.rect.x, field.rect.y - 20))
                field.draw(self.screen)

            _draw_btn(self.screen, self.fnt_btn,
                      self.btn_register, "Register", _CLR_BTN_PRIMARY, mpos)

            # "Already have an account? Login" link
            gray_part = self.fnt_link.render("Already have an account?  ", True, (120, 125, 150))
            gx = cx - (gray_part.get_width() +
                        self.fnt_link.size("Login")[0]) // 2
            gy = self.btn_register.bottom + 20
            self.screen.blit(gray_part, (gx, gy))
            self._login_link_r = _draw_link(
                self.screen, self.fnt_link, "Login",
                gx + gray_part.get_width() + self.fnt_link.size("Login")[0] // 2,
                gy, mpos)

            # Back link
            self._back_link_r = _draw_link(
                self.screen, self.fnt_link, "← Back",
                cx, self.btn_register.bottom + 52, mpos)

            _draw_status(self.screen, self.fnt_msg,
                         self._status, self._status_color, cx,
                         self.btn_register.bottom + 80)

            pygame.display.flip()
            clock.tick(FPS)
