import pygame, os
from settings import *
from save_manager import reset_user_save


class UsersMixin:
    def _draw_users_tab(self, mpos):
        ROW_H    = 30
        HEADER_Y = 112
        LIST_Y   = HEADER_Y + 32
        MAX_Y    = SCREEN_H - 175

        for cx_pos, hd in [(28,"Username"),(250,"Level"),(330,"Coins"),
                           (430,"Weapons"),(540,"2× Jump"),(640,"Last Active"),(800,"Actions")]:
            self.screen.blit(self.fnt_sm.render(hd, True, GRAY), (cx_pos, HEADER_Y))
        pygame.draw.line(self.screen, (50, 55, 80),
                         (20, HEADER_Y + 18), (SCREEN_W - 20, HEADER_Y + 18))

        visible    = (MAX_Y - LIST_Y) // ROW_H
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
            rst_r = pygame.Rect(800, y + 3, 72, 22)
            del_r = pygame.Rect(878, y + 3, 72, 22)
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

    def _reset_user(self, uname):
        reset_user_save(uname)
        self._status    = f'Progress reset for "{uname}".'
        self._status_ok = True

    def _delete_user(self, uname):
        p = os.path.join(SAVES_DIR, f"{uname}.json")
        if os.path.exists(p):
            os.remove(p)
        self._status    = f'User "{uname}" deleted.'
        self._status_ok = True
