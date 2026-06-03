import pygame
from settings import *

_CHAR_CATS = [
    ("Melee",  [W_SWORD]),
    ("Ranged", [W_BOW, W_STAFF]),
    ("Dash",   []),
]

_CHAR_NAMES = {W_SWORD: "Knight", W_BOW: "Archer (Huntress)", W_STAFF: "Wizard (Mage)"}

# Character fields that must be integers (everything else is stored as string)
_INT_FIELDS = {"scale", "max_hp", "shoot_cooldown", "attack_damage",
               "arrow_speed", "arrow_lifetime", "blast_duration"}


class CharactersMixin:
    _CHAR_COLORS = {W_SWORD: (45, 55, 125), W_BOW: (32, 88, 50), W_STAFF: (65, 32, 118)}

    def _draw_char_tab(self, mpos):
        if self._char_detail:
            return self._draw_char_detail(mpos)
        return self._draw_char_gallery(mpos)

    def _draw_char_gallery(self, mpos):
        CW, CH, GAP = 220, 200, 20
        X0 = 28
        cards = {}
        y = 112

        for cat_name, wids in _CHAR_CATS:
            pygame.draw.line(self.screen, (55, 62, 95), (X0, y), (SCREEN_W - X0, y))
            self.screen.blit(self.fnt_hd.render(cat_name, True, (140, 160, 210)),
                             (X0 + 4, y + 3))
            y += 24

            if not wids:
                self.screen.blit(
                    self.fnt_sm.render("(none)", True, (75, 85, 115)), (X0 + 10, y + 4))
                y += 28
            else:
                x = X0
                for wid in wids:
                    c    = self._chars[wid]
                    clr  = self._CHAR_COLORS.get(wid, (50, 55, 100))
                    rect = pygame.Rect(x, y, CW, CH)
                    sub  = f"HP {c.get('max_hp','?')}  Dmg {c.get('attack_damage','?')}"
                    self._draw_card(rect, self._char_thumbs.get(wid),
                                    c.get("name", wid), sub, clr, mpos)
                    cards[wid] = rect
                    x += CW + GAP
                y += CH + 8
            y += 6

        return {"_gallery": cards}

    def _draw_char_detail(self, mpos):
        wid = self._char_detail
        c   = self._chars[wid]
        fr  = {}
        clr = self._CHAR_COLORS.get(wid, (50, 55, 100))
        FH, ROW, FX = 26, 36, 210

        back_r = pygame.Rect(28, 116, 88, 28)
        self._draw_btn(back_r, "← Back", (55, 55, 88), mpos)
        self.screen.blit(self.fnt_big.render(c.get("name", wid), True, CYAN), (128, 118))
        fr["_back"] = back_r

        TS = 150
        thumb = self._char_thumbs.get(wid)
        if thumb:
            self.screen.blit(pygame.transform.smoothscale(thumb, (TS, TS)), (28, 158))
        else:
            self.screen.blit(self._fallback_thumb(c.get("name","?"), clr, TS), (28, 158))

        fy = 155

        def field(key, lbl, fw, cx=FX):
            lbl_s = self.fnt_sm.render(lbl + ":", True, LTGRAY)
            self.screen.blit(lbl_s, (cx, fy + 7))
            r = pygame.Rect(cx + lbl_s.get_width() + 6, fy, fw, FH)
            self._draw_field(r, c.get(key, ""), self._active == (wid, key))
            fr[key] = r
            return r.right + 18

        nx = field("name",  "Name",       190)
        field("scale", "Scale (px)", 70, nx)
        fy += ROW

        lbl_s = self.fnt_sm.render("Sprite folder:", True, LTGRAY)
        self.screen.blit(lbl_s, (FX, fy + 7))
        dr = pygame.Rect(FX + lbl_s.get_width() + 6, fy,
                         SCREEN_W - FX - lbl_s.get_width() - 50, FH)
        self._draw_field(dr, c.get("sprite_dir",""), self._active == (wid, "sprite_dir"))
        fr["sprite_dir"] = dr
        fy += ROW

        cx = FX
        for key, lbl, fw in [("max_hp","Max HP",70),
                              ("shoot_cooldown","Cooldown (fr)",70),
                              ("attack_damage","Damage",70)]:
            cx = field(key, lbl, fw, cx)
        fy += ROW

        if wid == W_BOW:
            cx = FX
            cx = field("arrow_speed",    "Arrow Speed", 70, cx)
            field("arrow_lifetime", "Arrow Range", 70, cx)
            fy += ROW
        elif wid == W_STAFF:
            field("blast_duration", "Blast Dur (fr)", 70)
            fy += ROW

        return fr
