import pygame, math
from settings import *
from ui_components import make_orb, HERO_ORB_CFG, LOCKED_ORB_CFG


def _font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)


# Map settings weapon IDs → ui_helpers keys
_HERO_ORB_CFG  = {W_SWORD: HERO_ORB_CFG["sword"],
                   W_BOW:   HERO_ORB_CFG["bow"],
                   W_STAFF: HERO_ORB_CFG["staff"]}
_LOCKED_ORB_CFG = LOCKED_ORB_CFG
_make_orb = make_orb

_ORB_SIZE    = 32   # px — fits comfortably inside HUD_H = 50
_ORB_SPACING = 42   # px between orb left edges


class HUD:
    def __init__(self):
        self.fnt_sm  = _font(16)
        self.fnt_md  = _font(20, bold=True)
        self.fnt_lg  = _font(28, bold=True)
        self.fnt_key = _font(11)          # tiny keyboard-shortcut label
        self._coin_anim = 0
        self._msg       = ""
        self._msg_timer = 0

        # Pre-bake one orb per hero + one locked orb
        s = _ORB_SIZE
        self._hero_orbs = {
            wid: _make_orb(s, *cfg)
            for wid, cfg in _HERO_ORB_CFG.items()
        }
        self._locked_orb = _make_orb(s, *_LOCKED_ORB_CFG)

        # Dimmed copy of each hero orb (unselected-but-unlocked state)
        self._hero_orbs_dim = {}
        for wid, orb in self._hero_orbs.items():
            dim = orb.copy()
            dim.set_alpha(140)
            self._hero_orbs_dim[wid] = dim

    def show_message(self, text, frames=120):
        self._msg       = text
        self._msg_timer = frames

    def draw(self, surface, player, level_name, level_num, username=None):
        self._coin_anim += 1
        now = pygame.time.get_ticks()

        # Dark HUD bar
        bar = pygame.Surface((SCREEN_W, HUD_H), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 160))
        surface.blit(bar, (0, 0))

        # ── HP bar ────────────────────────────────────────────────────────────
        hp_w = 200
        pygame.draw.rect(surface, (80, 0, 0), (10, 10, hp_w, 20), border_radius=4)
        filled = int(hp_w * max(0, player.hp) / player.MAX_HP)
        hp_col = GREEN if player.hp > 40 else (YELLOW if player.hp > 20 else RED)
        pygame.draw.rect(surface, hp_col, (10, 10, filled, 20), border_radius=4)
        pygame.draw.rect(surface, WHITE,  (10, 10, hp_w, 20), 2, border_radius=4)
        surface.blit(self.fnt_sm.render(f"HP {player.hp}/{player.MAX_HP}", True, WHITE),
                     (14, 12))

        # ── Coins ─────────────────────────────────────────────────────────────
        surface.blit(self.fnt_md.render(f"Coins: {player.coins}", True, YELLOW),
                     (220, 10))

        # ── Current character name ────────────────────────────────────────────
        cname = CHAR_DISPLAY.get(player.current_weapon, "—")
        surface.blit(self.fnt_md.render(f"[{cname}]", True, CYAN), (420, 10))

        # ── Hero orb slots ────────────────────────────────────────────────────
        all_heroes  = [W_SWORD, W_BOW, W_STAFF]
        unlocked    = set(player.unlocked_weapons)
        slots_x     = 620
        s           = _ORB_SIZE
        oy          = (HUD_H - s) // 2   # vertically centred in bar

        for i, wid in enumerate(all_heroes):
            ox = slots_x + i * _ORB_SPACING
            is_selected = (wid == player.current_weapon)
            is_unlocked = (wid in unlocked)

            if is_unlocked:
                if is_selected:
                    # Animated glow ring around selected hero
                    pulse  = 0.5 + 0.5 * math.sin(now / 400)
                    ring_r = s // 2 + 3 + int(2 * pulse)
                    ring_a = int(180 + 60 * pulse)
                    gsurf  = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4),
                                            pygame.SRCALPHA)
                    pygame.draw.circle(gsurf, (255, 220, 50, ring_a),
                                       (ring_r + 2, ring_r + 2), ring_r, 2)
                    surface.blit(gsurf, (ox + s // 2 - ring_r - 2,
                                         oy + s // 2 - ring_r - 2))
                    surface.blit(self._hero_orbs[wid], (ox, oy))
                else:
                    surface.blit(self._hero_orbs_dim[wid], (ox, oy))
            else:
                # Locked: pulsing dim glow + "?" orb
                pulse  = 0.5 + 0.5 * math.sin(now / 700 + i * 1.3)
                ga     = int(20 + 30 * pulse)
                gr     = s // 2 + 3
                gsurf  = pygame.Surface((gr * 2 + 4, gr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(gsurf, (78, 78, 100, ga),
                                   (gr + 2, gr + 2), gr)
                surface.blit(gsurf, (ox + s // 2 - gr - 2,
                                     oy + s // 2 - gr - 2))
                surface.blit(self._locked_orb, (ox, oy))

            # Keyboard shortcut number below the orb
            num = self.fnt_key.render(str(i + 1), True,
                                      YELLOW if is_selected else GRAY)
            surface.blit(num, num.get_rect(centerx=ox + s // 2,
                                           top=oy + s + 1))

        # ── Double jump badge ────────────────────────────────────────────────
        if player.double_jump:
            dj = self.fnt_sm.render("2x JUMP", True, PURPLE)
            surface.blit(dj, (slots_x + len(all_heroes) * _ORB_SPACING + 8, 17))

        # ── Level name ────────────────────────────────────────────────────────
        lv_txt = self.fnt_md.render(f"Level {level_num}: {level_name}", True, WHITE)
        surface.blit(lv_txt, (SCREEN_W - lv_txt.get_width() - 10, 10))

        # ── Username / guest indicator ────────────────────────────────────────
        uname = username if username else "Guest"
        u_txt = self.fnt_sm.render(f"User: {uname}", True,
                                   LTGRAY if username else GRAY)
        surface.blit(u_txt, (SCREEN_W - u_txt.get_width() - 10, 32))

        # ── Notification message (centre-screen) ──────────────────────────────
        if self._msg_timer > 0:
            self._msg_timer -= 1
            alpha = min(255, self._msg_timer * 4)
            txt = self.fnt_lg.render(self._msg, True, YELLOW)
            txt.set_alpha(alpha)
            surface.blit(txt, txt.get_rect(center=(SCREEN_W // 2,
                                                    SCREEN_H // 2 - 60)))
