import pygame, os
from settings import *
from weapons import Arrow, MagicBolt, SwordSlash

# ── Asset paths ───────────────────────────────────────────────────────────────
_PACK     = "Tiny RPG Character Asset Pack v1.03 -Free Soldier&Orc"
_SOLDIER  = os.path.join(_PACK, "Characters(100x100)", "Soldier", "Soldier with shadows")

# Default target height. Can be overridden per-character via settings.json.
_TARGET_H = 120


def _load_char_json():
    """Read per-character overrides from settings.json["characters"] if present."""
    import json as _j
    sf = "settings.json"
    if not os.path.exists(sf):
        return {}
    try:
        with open(sf) as f:
            return _j.load(f).get("characters", {})
    except Exception:
        return {}

_CHAR_JSON = _load_char_json()   # {"sword": {"scale": 120, "sprite_dir": "..."}, ...}

# Per-character config: (attack_file, attack_frames, attack_dur, RGB_tint_or_None)
# Tint uses BLEND_RGBA_MULT — (150,255,150) keeps greens, mutes blues → archer green
#                               (200,140,255) boosts purple channel → wizard violet
_CHAR_CFG = {
    W_SWORD: ("Soldier-Attack01.png", 6, 4, None),
    W_BOW:   ("Soldier-Attack02.png", 6, 4, None),
    W_STAFF: ("Soldier-Attack03.png", 9, 3, None),
}

# Optional dedicated sprite directories (user can drop in assets/sprites/archer/, etc.)
_CHAR_CUSTOM_DIR = {
    W_SWORD: os.path.join("assets", "sprites", "knight"),
    W_BOW:   os.path.join("assets", "sprites", "archer"),
    W_STAFF: os.path.join("assets", "sprites", "wizard"),
}


# ── Tinting helper ────────────────────────────────────────────────────────────

def _tint(frames, rgba):
    """Multiply every pixel by rgba. Returns new list; original unchanged."""
    if not rgba or not frames:
        return frames
    result = []
    for f in frames:
        copy = f.copy()
        overlay = pygame.Surface(copy.get_size(), pygame.SRCALPHA)
        overlay.fill(rgba)
        copy.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        result.append(copy)
    return result


# ── Player ────────────────────────────────────────────────────────────────────

class Player(pygame.sprite.Sprite):
    WIDTH  = 28
    HEIGHT = 44
    MAX_HP = 100
    INVUL_FRAMES = 60
    SHOOT_COOLDOWN = {W_SWORD: 22, W_BOW: 28, W_STAFF: 50}

    def __init__(self, x, y, save_data):
        super().__init__()
        self.image = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground   = False
        self.on_platform = False
        self.jumps_left  = 2
        self.hp    = self.MAX_HP
        self.invul = 0
        self.coins = 0
        self.facing = 1
        self._flash = 0
        self._just_attacked = 0   # brief countdown to trigger attack anim
        self._draw_player()
        self.rect = self.image.get_rect(topleft=(x, y))

        self.unlocked_weapons = list(save_data.get("unlocked_weapons", [W_SWORD]))
        self.double_jump      = save_data.get("double_jump", False)
        self.weapon_idx       = 0
        self.current_weapon   = self.unlocked_weapons[0] if self.unlocked_weapons else None

        self.shoot_timer = 0
        self.projectiles = pygame.sprite.Group()

        # Load one Animator per unlocked character; swap on character change
        self._animators: dict = {}
        for wid in self.unlocked_weapons:
            a = self._load_char_anim(wid)
            if a:
                self._animators[wid] = a
        self._anim = self._animators.get(self.current_weapon)

    # ── Animator loading ──────────────────────────────────────────────────────

    def _load_char_anim(self, wid):
        """
        Build an Animator for character `wid`.
        Respects per-character scale and sprite_dir from settings.json["characters"],
        falling back to the hardcoded defaults.
        """
        cfg      = _CHAR_JSON.get(wid, {})
        custom   = cfg.get("sprite_dir", _CHAR_CUSTOM_DIR.get(wid, ""))
        target_h = int(cfg.get("scale", _TARGET_H))

        if os.path.isdir(custom):
            return self._load_dir_anim(custom, wid, target_h)
        if os.path.isdir(_SOLDIER):
            return self._load_soldier_anim(wid, target_h)
        return None

    def _load_soldier_anim(self, wid, target_h=_TARGET_H):
        from animator import Animator, load_strip_cropped, compute_y_crop
        atk_file, atk_count, atk_dur, color_tint = _CHAR_CFG.get(
            wid, ("Soldier-Attack01.png", 6, 4, None))

        # One shared crop region across every animation so the character stays
        # the same size in idle, walk, attack, etc.
        all_strips = [
            (os.path.join(_SOLDIER, "Soldier-Idle.png"),  6),
            (os.path.join(_SOLDIER, "Soldier-Walk.png"),  8),
            (os.path.join(_SOLDIER, atk_file),            atk_count),
            (os.path.join(_SOLDIER, "Soldier-Hurt.png"),  4),
            (os.path.join(_SOLDIER, "Soldier-Death.png"), 4),
        ]
        y_crop = compute_y_crop(all_strips, 100, 100)

        def s(name, n):
            return _tint(
                load_strip_cropped(os.path.join(_SOLDIER, name),
                                   100, 100, n, target_h=target_h,
                                   y_crop=y_crop),
                color_tint)

        idle = s("Soldier-Idle.png",    6)
        walk = s("Soldier-Walk.png",    8)
        atk  = s(atk_file,             atk_count)
        hurt = s("Soldier-Hurt.png",   4)
        die  = s("Soldier-Death.png",  4)

        if not idle:
            return None
        a = Animator()
        a.add_state("idle",   idle,      duration=8,  loop=True)
        a.add_state("walk",   walk,      duration=5,  loop=True)
        a.add_state("jump",   walk[:3],  duration=7,  loop=True)
        a.add_state("fall",   walk[5:],  duration=7,  loop=True)
        a.add_state("attack", atk,       duration=atk_dur, loop=False)
        a.add_state("hurt",   hurt,      duration=6,  loop=False)
        a.add_state("die",    die,       duration=8,  loop=False)
        char_name = CHAR_DISPLAY.get(wid, wid)
        print(f"[Player] {char_name} loaded ({'tinted' if color_tint else 'original'}).")
        return a

    def _load_dir_anim(self, dirpath, wid, target_h=_TARGET_H):
        """
        Load from a custom sprite directory.
        Tries multiple filename conventions so any pack naming style works.
        Uses load_strip_auto: auto-detects square frame size from image height.
        """
        from animator import Animator, load_strip_auto, compute_y_crop_auto

        _, _, atk_dur, color_tint = _CHAR_CFG.get(wid, ("", 6, 4, None))
        base = os.path.basename(dirpath).capitalize()

        def find(*names):
            for name in names:
                p = os.path.join(dirpath, name)
                if os.path.exists(p):
                    return p
            return None

        idle_p   = find("Idle.png",     f"{base}-Idle.png")
        walk_p   = find("Run.png",      "Walk.png",    "Move.png",  f"{base}-Walk.png")
        jump_p   = find("Jump.png",     f"{base}-Jump.png")
        fall_p   = find("Fall.png",     f"{base}-Fall.png")
        attack_p = find("Attack.png",   "Attack1.png", "Attack3.png")
        hurt_p   = find("Take Hit.png", "Get Hit.png", "Hurt.png")
        die_p    = find("Death.png",    "Die.png")

        if not idle_p:
            return None

        # One shared vertical crop region across every animation so the character
        # stays the same size in idle, walk, attack, etc.
        all_paths = [p for p in [idle_p, walk_p, jump_p, fall_p,
                                  attack_p, hurt_p, die_p] if p]
        y_crop = compute_y_crop_auto(all_paths)

        def load(path):
            if not path:
                return []
            # crop_sides=False: keep full frame width so the character stays at a
            # consistent x position across frames (prevents horizontal jitter).
            frames = _tint(
                load_strip_auto(path, target_h, crop_sides=False, y_crop=y_crop),
                color_tint)
            return frames if frames else []

        idle   = load(idle_p)
        walk   = load(walk_p)
        jump   = load(jump_p)
        fall   = load(fall_p)
        attack = load(attack_p)
        hurt   = load(hurt_p)
        die    = load(die_p)

        if not idle:
            return None

        # Graceful fallbacks for missing animations (Wizard has no jump/fall)
        _walk = walk   or idle
        _jump = jump   or _walk[:3]
        _fall = fall   or _walk[-3:]
        _atk  = attack or idle[:2]
        _hurt = hurt   or idle[:2]
        _die  = die    or idle

        a = Animator()
        a.add_state("idle",   idle,  duration=8,       loop=True)
        a.add_state("walk",   _walk, duration=5,       loop=True)
        a.add_state("jump",   _jump, duration=7,       loop=True)
        a.add_state("fall",   _fall, duration=7,       loop=True)
        a.add_state("attack", _atk,  duration=atk_dur, loop=False)
        a.add_state("hurt",   _hurt, duration=6,       loop=False)
        a.add_state("die",    _die,  duration=8,       loop=False)
        char_name = CHAR_DISPLAY.get(wid, os.path.basename(dirpath))
        print(f"[Player] {char_name} loaded from {os.path.relpath(dirpath)}.")
        return a

    # ── Animation state ───────────────────────────────────────────────────────

    def _update_anim_state(self):
        a = self._anim
        a.set_flip(self.facing < 0)

        if self.hp <= 0:
            a.set_state("die", force=True);  return
        if self._flash > 0:
            a.set_state("hurt", force=True); return
        if self._just_attacked > 0:
            a.set_state("attack");           return   # one-shot; won't re-trigger

        if not self.on_ground:
            a.set_state("jump" if self.vel_y < 0 else "fall")
        elif abs(self.vel_x) > 0.4:
            a.set_state("walk")
        else:
            a.set_state("idle")

    # ── Drawn fallback ────────────────────────────────────────────────────────

    def _draw_player(self, flash=False):
        self.image.fill((0, 0, 0, 0))
        bc = (80, 140, 220) if not flash else (255, 80, 80)
        pygame.draw.rect(self.image, bc,
                         (4, 14, self.WIDTH-8, self.HEIGHT-14), border_radius=4)
        pygame.draw.circle(self.image,
                           (240,200,160) if not flash else (255,150,150),
                           (self.WIDTH//2, 10), 10)
        pygame.draw.circle(self.image, BLACK,
                           (self.WIDTH//2 + 4*self.facing, 8), 2)
        lc = (50,80,160) if not flash else (200,50,50)
        pygame.draw.rect(self.image, lc, (4, self.HEIGHT-14, 9, 14), border_radius=3)
        pygame.draw.rect(self.image, lc, (self.WIDTH-13, self.HEIGHT-14, 9, 14), border_radius=3)

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def alive(self):
        return self.hp > 0

    def select_weapon(self, idx):
        if self.unlocked_weapons:
            self.weapon_idx    = idx % len(self.unlocked_weapons)
            self.current_weapon = self.unlocked_weapons[self.weapon_idx]
            self._anim         = self._animators.get(self.current_weapon)

    def add_weapon(self, wid):
        if wid not in self.unlocked_weapons:
            self.unlocked_weapons.append(wid)
            self.unlocked_weapons.sort(
                key=lambda w: [W_SWORD,W_BOW,W_STAFF].index(w)
                              if w in [W_SWORD,W_BOW,W_STAFF] else 99)
            if wid not in self._animators:
                a = self._load_char_anim(wid)
                if a:
                    self._animators[wid] = a

    def handle_input(self, keys, events):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel_x -= 1.8;  self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel_x += 1.8;  self.facing =  1
        if keys[pygame.K_1]: self.select_weapon(0)
        if keys[pygame.K_2]: self.select_weapon(1)
        if keys[pygame.K_3]: self.select_weapon(2)
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self._try_jump()
                if ev.key in (pygame.K_DOWN, pygame.K_s) and self.on_platform:
                    self.rect.y   += 4
                    self.on_ground = False
                    self.on_platform = False

    def _try_jump(self):
        if self.on_ground:
            self.vel_y = JUMP_FORCE
            self.on_ground = False;  self.on_platform = False
            self.jumps_left = (2 if self.double_jump else 1) - 1
        elif self.jumps_left > 0 and self.double_jump:
            self.vel_y = DJUMP_FORCE
            self.jumps_left -= 1

    def try_shoot(self, pressed):
        if not pressed or self.shoot_timer > 0 or not self.current_weapon:
            return None
        self.shoot_timer      = self.SHOOT_COOLDOWN.get(self.current_weapon, 30)
        self._just_attacked   = 10   # trigger attack anim for 10 frames
        cx, cy = self.rect.centerx, self.rect.centery
        w = self.current_weapon
        if w == W_SWORD:
            p = SwordSlash(self.rect, self.facing)
        elif w == W_BOW:
            p = Arrow(cx + self.facing * 20, cy, self.facing)
        elif w == W_STAFF:
            p = MagicBolt(cx + self.facing * 20, cy, self.facing)
        else:
            return None
        self.projectiles.add(p);  return p

    def apply_physics(self):
        self.vel_x *= GROUND_FRIC if self.on_ground else AIR_FRIC
        self.vel_x  = max(-PLAYER_SPEED, min(PLAYER_SPEED, self.vel_x))
        self.vel_y += GRAVITY
        self.vel_y  = min(self.vel_y, MAX_FALL)

    def move_and_collide(self, tilemap):
        solid = tilemap.get_solid_tiles()
        self.rect.x += int(self.vel_x)
        for t in solid:
            if self.rect.colliderect(t.rect) and not t.is_platform():
                if self.vel_x > 0: self.rect.right = t.rect.left
                elif self.vel_x < 0: self.rect.left = t.rect.right
                self.vel_x = 0

        # Hard map boundaries — player cannot walk off either horizontal edge
        map_pixel_w = tilemap.cols * TILE_SIZE
        if self.rect.left < 0:
            self.rect.left = 0
            self.vel_x = 0
        elif self.rect.right > map_pixel_w:
            self.rect.right = map_pixel_w
            self.vel_x = 0

        prev_bottom = self.rect.bottom
        self.rect.y += int(self.vel_y)
        self.on_ground = False;  self.on_platform = False
        for t in solid:
            if self.rect.colliderect(t.rect):
                if t.is_platform():
                    if self.vel_y > 0 and prev_bottom <= t.rect.top + 4:
                        self.rect.bottom = t.rect.top
                        self.vel_y = 1;  self.on_ground = True
                        self.on_platform = True
                        self.jumps_left = 2 if self.double_jump else 1
                else:
                    if self.vel_y > 0:
                        self.rect.bottom = t.rect.top
                        self.vel_y = 1;  self.on_ground = True
                        self.jumps_left = 2 if self.double_jump else 1
                    elif self.vel_y < 0:
                        self.rect.top = t.rect.bottom;  self.vel_y = 0

    def take_damage(self, amount):
        if self.invul > 0:
            return
        self.hp    = max(0, self.hp - amount)
        self.invul = self.INVUL_FRAMES
        self._flash = 8

    def update(self, tilemap, keys, events, shoot_pressed):
        self.handle_input(keys, events)
        self.apply_physics()
        self.move_and_collide(tilemap)
        if self.shoot_timer    > 0: self.shoot_timer    -= 1
        if self.invul          > 0: self.invul          -= 1
        if self._flash         > 0: self._flash         -= 1
        if self._just_attacked > 0: self._just_attacked -= 1

        if self._anim:
            self._update_anim_state()
            self._anim.update()
        else:
            self._draw_player(flash=self._flash > 0)

        self.projectiles.update(tilemap)
        self.try_shoot(shoot_pressed)
        for spike in tilemap.get_spike_tiles():
            if self.rect.colliderect(spike.rect):
                self.hp = 0

    def collect_coins(self, tilemap):
        count = 0
        for coin in tilemap.get_coin_tiles():
            if self.rect.colliderect(coin.rect):
                coin.kill()
                tilemap.grid[coin.row][coin.col] = T_EMPTY
                count += 1
        self.coins += count
        return count

    def draw(self, surface, cam_off):
        ox, oy = cam_off
        if self.invul > 0 and (self.invul // 4) % 2 == 1:
            return  # blink
        if self._anim:
            img = self._anim.image
            # Center sprite over hitbox; sprite bottom == character feet == rect.bottom
            dx = self.rect.centerx - img.get_width()  // 2 - ox
            dy = self.rect.bottom  - img.get_height()     - oy
            surface.blit(img, (dx, dy))
        else:
            surface.blit(self.image, (self.rect.x - ox, self.rect.y - oy))
        self._draw_projectiles(surface, cam_off)

    def _draw_projectiles(self, surface, cam_off):
        ox, oy = cam_off
        for p in self.projectiles:
            surface.blit(p.image, (p.rect.x - ox, p.rect.y - oy))
