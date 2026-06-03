import pygame, os, time
from settings import *
from save_manager import load_user_save

_WEAPON_ABBR = {"sword": "Kn", "bow": "Ar", "staff": "Wz"}


def _all_users():
    if not os.path.isdir(SAVES_DIR):
        return []
    now = time.time()
    result = []
    for fname in sorted(os.listdir(SAVES_DIR)):
        if not fname.endswith(".json"):
            continue
        uname = fname[:-5]
        path  = os.path.join(SAVES_DIR, fname)
        try:
            d    = load_user_save(uname)
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


class DashboardMixin:
    def _stat_card(self, rect, label, value, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        brd = tuple(min(255, v + 50) for v in color)
        pygame.draw.rect(self.screen, brd, rect, 2, border_radius=10)
        lt = self.fnt_sm.render(label.upper(), True, (200, 210, 230))
        self.screen.blit(lt, lt.get_rect(centerx=rect.centerx, top=rect.y + 10))
        vt = self.fnt_big.render(str(value), True, WHITE)
        self.screen.blit(vt, vt.get_rect(centerx=rect.centerx, centery=rect.centery + 10))

    def _draw_dashboard(self, mpos):
        u           = self._users
        total       = len(u)
        active_7d   = sum(1 for x in u if x["days_ago"] < 7)
        avg_lv      = sum(x["level"] for x in u) / max(1, total)
        total_coins = sum(x["coins"] for x in u)

        cw = (SCREEN_W - 50) // 4
        ch = 90
        for i, (lbl, val, clr) in enumerate([
            ("Total Users",     total,              (45,  75, 155)),
            ("Active ≤ 7 days", active_7d,          (38, 125,  72)),
            ("Avg Level",       f"{avg_lv:.1f}",    (115,  60, 145)),
            ("Total Coins",     f"{total_coins:,}", (140,  90,  22)),
        ]):
            self._stat_card(pygame.Rect(20 + i * (cw + 4), 112, cw, ch), lbl, val, clr)

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

        for rank, usr in enumerate(sorted(u, key=lambda x: (-x["level"], -x["coins"]))[:10], 1):
            self._row_bg(y, SCREEN_W - 40, 26, rank)
            rc = YELLOW if rank == 1 else (LTGRAY if rank <= 3 else GRAY)
            for cx_pos, text, col in [
                (28,  f"#{rank}",             rc),
                (80,  usr["username"],        WHITE),
                (280, str(usr["level"]),      GREEN),
                (420, f"{usr['coins']:,}",    YELLOW),
                (540, usr["weapons"],         CYAN),
                (670, f"{usr['days_ago']:.0f}d ago" if usr["days_ago"] < 365 else "Long ago", LTGRAY),
            ]:
                self.screen.blit(self.fnt_sm.render(text, True, col), (cx_pos, y + 5))
            y += 26

        if not u:
            t = self.fnt.render("No registered users yet.", True, GRAY)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W // 2, 350)))

        return ref_r
