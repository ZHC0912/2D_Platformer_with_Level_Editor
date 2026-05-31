import pygame
from settings import *


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


class HUD:
    def __init__(self):
        self.fnt_sm = _font(16)
        self.fnt_md = _font(20, bold=True)
        self.fnt_lg = _font(28, bold=True)
        self._coin_anim = 0
        self._msg = ""
        self._msg_timer = 0

    def show_message(self, text, frames=120):
        self._msg = text
        self._msg_timer = frames

    def draw(self, surface, player, level_name, level_num, username=None):
        self._coin_anim += 1
        # dark bar
        bar = pygame.Surface((SCREEN_W, HUD_H), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 160))
        surface.blit(bar, (0, 0))

        # HP bar
        hp_w = 200
        pygame.draw.rect(surface, (80, 0, 0), (10, 10, hp_w, 20), border_radius=4)
        filled = int(hp_w * max(0, player.hp) / player.MAX_HP)
        color = GREEN if player.hp > 40 else (YELLOW if player.hp > 20 else RED)
        pygame.draw.rect(surface, color, (10, 10, filled, 20), border_radius=4)
        pygame.draw.rect(surface, WHITE, (10, 10, hp_w, 20), 2, border_radius=4)
        hp_txt = self.fnt_sm.render(f"HP {player.hp}/{player.MAX_HP}", True, WHITE)
        surface.blit(hp_txt, (14, 12))

        # Coins
        c_txt = self.fnt_md.render(f"Coins: {player.coins}", True, YELLOW)
        surface.blit(c_txt, (220, 10))

        # Current character
        cname = CHAR_DISPLAY.get(player.current_weapon, "—")
        w_txt = self.fnt_md.render(f"[{cname}]", True, CYAN)
        surface.blit(w_txt, (420, 10))

        # Character slots
        slots_x = 620
        for i, wid in enumerate(player.unlocked_weapons):
            sel   = (i == player.weapon_idx)
            color = YELLOW if sel else LTGRAY
            label = CHAR_ICON.get(wid, f"{i+1}:?")
            t = self.fnt_sm.render(label, True, color)
            surface.blit(t, (slots_x + i * 75, 14))

        # Double jump badge
        if player.double_jump:
            dj = self.fnt_sm.render("2x JUMP", True, PURPLE)
            surface.blit(dj, (slots_x + 220, 14))

        # Level name
        lv_txt = self.fnt_md.render(f"Level {level_num}: {level_name}", True, WHITE)
        surface.blit(lv_txt, (SCREEN_W - lv_txt.get_width() - 10, 10))

        # Username / guest indicator
        uname = username if username else "Guest"
        u_col = LTGRAY if username else GRAY
        u_txt = self.fnt_sm.render(f"User: {uname}", True, u_col)
        surface.blit(u_txt, (SCREEN_W - u_txt.get_width() - 10, 32))

        # Notification message
        if self._msg_timer > 0:
            self._msg_timer -= 1
            alpha = min(255, self._msg_timer * 4)
            txt = self.fnt_lg.render(self._msg, True, YELLOW)
            txt.set_alpha(alpha)
            surface.blit(txt, txt.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60)))
