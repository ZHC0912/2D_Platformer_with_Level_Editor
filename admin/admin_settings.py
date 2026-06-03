import pygame
from settings import *

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


class SettingsMixin:
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
