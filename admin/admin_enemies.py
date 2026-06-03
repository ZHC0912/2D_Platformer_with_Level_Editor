import pygame
from settings import *

_ENEMY_ORDER = ["goblin", "bomber_goblin", "skeleton", "slime", "worm",
                "flying_eye", "mushroom"]

_ENEMY_CATS = [
    ("Melee",  ["goblin", "bomber_goblin", "skeleton", "slime", "worm"]),
    ("Ranged", ["flying_eye"]),
    ("Dash",   ["mushroom"]),
]

_ENEMY_ROW_LABEL = {
    "goblin": "Goblin", "bomber_goblin": "Bomber Goblin", "skeleton": "Skeleton",
    "slime":  "Slime",  "worm": "Worm", "flying_eye": "Flying Eye", "mushroom": "Mushroom",
}

_ENEMY_COMMON = [("label","Name",110), ("hp","HP",42), ("damage","Dmg",42)]
_ENEMY_EXTRA  = {
    "goblin":        [("speed","Speed",50),       ("display","Size",42)],
    "bomber_goblin": [("speed","Speed",50),       ("display","Size",42)],
    "skeleton":      [("speed","Speed",50),       ("display","Size",42)],
    "slime":         [("speed","Speed",50),       ("display","Size",42)],
    "worm":          [("speed","Speed",50),       ("display","Size",42)],
    "flying_eye":    [("speed","Fly Spd",52),     ("display","Size",42),
                      ("sight_range","Sight",52), ("attack_range","Rng",52),
                      ("shoot_cooldown","Shoot CD",62)],
    "mushroom":      [("dash_speed","Dash Spd",58), ("display","Size",42),
                      ("detect_radius","Detect",58), ("dash_cooldown","Dash CD",58)],
}

_ENEMY_FLOAT_FIELDS = {"speed", "dash_speed"}
_ENEMY_STR_FIELDS   = {"label"}


class EnemiesMixin:
    _ENEMY_COLORS = {
        "goblin":        (105, 55,  35), "bomber_goblin": (130, 65, 25),
        "skeleton":      ( 88, 88,  78), "slime":         ( 32,105, 68),
        "worm":          ( 65, 90,  35), "flying_eye":    ( 48, 52,148),
        "mushroom":      ( 95, 35, 110),
    }

    def _draw_enemies_tab(self, mpos):
        if self._enemy_detail:
            return self._draw_enemy_detail(mpos)
        return self._draw_enemy_gallery(mpos)

    def _draw_enemy_gallery(self, mpos):
        CW, CH, GAP = 148, 150, 12
        X0 = 28
        cards = {}
        y = 112

        for cat_name, eids in _ENEMY_CATS:
            pygame.draw.line(self.screen, (55, 62, 95), (X0, y), (SCREEN_W - X0, y))
            self.screen.blit(self.fnt_hd.render(cat_name, True, (140, 160, 210)),
                             (X0 + 4, y + 3))
            y += 24

            if not eids:
                self.screen.blit(
                    self.fnt_sm.render("(none)", True, (75, 85, 115)), (X0 + 10, y + 4))
                y += 28
            else:
                x = X0
                for eid in eids:
                    e    = self._enemies.get(eid, {})
                    clr  = self._ENEMY_COLORS.get(eid, (55, 55, 90))
                    rect = pygame.Rect(x, y, CW, CH)
                    sub  = f"HP {e.get('hp','?')}  Dmg {e.get('damage','?')}"
                    self._draw_card(rect, self._enemy_thumbs.get(eid),
                                    e.get("label", _ENEMY_ROW_LABEL[eid]), sub, clr, mpos)
                    cards[eid] = rect
                    x += CW + GAP
                y += CH + 6
            y += 6

        return {"_gallery": cards}

    def _draw_enemy_detail(self, mpos):
        eid = self._enemy_detail
        e   = self._enemies[eid]
        fr  = {}
        clr = self._ENEMY_COLORS.get(eid, (55, 55, 90))
        FH, ROW, FX = 26, 36, 210

        back_r = pygame.Rect(28, 116, 88, 28)
        self._draw_btn(back_r, "← Back", (55, 55, 88), mpos)
        self.screen.blit(self.fnt_big.render(e.get("label", eid), True, CYAN), (128, 118))
        fr["_back"] = back_r

        TS = 150
        thumb = self._enemy_thumbs.get(eid)
        if thumb:
            self.screen.blit(pygame.transform.smoothscale(thumb, (TS, TS)), (28, 158))
        else:
            self.screen.blit(self._fallback_thumb(e.get("label","?"), clr, TS), (28, 158))

        fy = 155

        def field(key, lbl, fw, cx=FX):
            lbl_s = self.fnt_sm.render(lbl + ":", True, LTGRAY)
            self.screen.blit(lbl_s, (cx, fy + 7))
            r = pygame.Rect(cx + lbl_s.get_width() + 6, fy, fw, FH)
            self._draw_field(r, e.get(key, ""), self._active == (eid, key, "enemy"))
            fr[key] = r
            return r.right + 18

        cx = FX
        cx = field("label",   "Name",     170, cx)
        field("display", "Size (px)", 60,  cx)
        fy += ROW

        cx = FX
        cx = field("hp",     "Max HP", 70, cx)
        field("damage", "Damage",  70, cx)
        fy += ROW

        combat = [(k, lbl, fw) for k, lbl, fw in _ENEMY_EXTRA.get(eid, [])
                  if k not in ("label", "display")]
        if combat:
            cx = FX
            for key, lbl, fw in combat:
                cx = field(key, lbl, fw, cx)
            fy += ROW

        return fr
