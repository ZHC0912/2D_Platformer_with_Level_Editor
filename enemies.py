import pygame, math, os
from settings import *
from weapons import EnemyBullet

_PACK    = "Tiny RPG Character Asset Pack v1.03 -Free Soldier&Orc"
_ORC_DIR = os.path.join(_PACK, "Characters(100x100)", "Orc", "Orc with shadows")

# ── Custom sprite directory for any enemy subtype ─────────────────────────────
# Drop a folder at  assets/sprites/enemies/<subtype>/  with these files:
#   <Name>-Idle.png   <Name>-Walk.png   <Name>-Attack.png
#   <Name>-Hurt.png   <Name>-Death.png
# The game will auto-load them instead of the tinted Orc fallback.
_ENEMY_SPRITE_BASE = os.path.join("assets", "sprites", "enemies")

# ── Enemy subtype configuration ───────────────────────────────────────────────
# Each entry: hp, contact_damage, display_size, RGBA_tint_or_None, label
#             + speed / dash_speed where applicable
ENEMY_CONFIG = {
    # ── Melee (BasicEnemy) ────────────────────────────────────────────────────
    "orc": dict(
        hp=40,  damage=15, speed=2.0, display=100,
        tint=None,
        label="Orc"),
    "elite_orc": dict(
        hp=90,  damage=25, speed=2.5, display=110,
        tint=(255, 120, 120, 255),          # red-tinted
        label="Elite Orc"),
    "skeleton": dict(
        hp=25,  damage=12, speed=3.0, display=92,
        tint=(230, 230, 200, 255),          # bone-white
        label="Skeleton"),
    "werebear": dict(
        hp=120, damage=30, speed=1.6, display=118,
        tint=(180, 120,  80, 255),          # brown
        label="Werebear"),
    "greatsword_skeleton": dict(
        hp=60,  damage=22, speed=1.4, display=105,
        tint=(160, 190, 220, 255),          # steel-grey
        label="Greatsword Skeleton"),
    # ── Ranged (ShooterEnemy) ─────────────────────────────────────────────────
    "skeleton_archer": dict(
        hp=25,  damage=12, display=92,
        tint=(215, 215, 185, 255),          # ivory
        label="Skeleton Archer"),
    # ── Dash (DashEnemy) ─────────────────────────────────────────────────────
    "orc_rider": dict(
        hp=70,  damage=25, dash_speed=14, display=112,
        tint=(120, 180, 255, 255),          # sky-blue mount
        label="Orc Rider"),
    "greatsword_skeleton_dash": dict(
        hp=55,  damage=20, dash_speed=10, display=105,
        tint=(160, 190, 220, 255),          # steel-grey
        label="Greatsword Skeleton"),
    # ── New characters from the character pack ────────────────────────────────
    "skeleton": dict(
        hp=25,  damage=12, speed=3.0, display=92,
        tint=(230, 230, 200, 255), label="Skeleton"),
    "goblin": dict(
        hp=35,  damage=14, speed=3.5, display=95,
        tint=(140, 200, 100, 255), label="Goblin"),
    "flying_eye": dict(          # ranged — floats, shoots projectiles
        hp=30,  damage=12,        display=90,
        tint=(200, 140, 255, 255), label="Flying Eye"),
    "mushroom": dict(             # dash attacker
        hp=50,  damage=20, dash_speed=10, display=95,
        tint=(200, 130,  80, 255), label="Mushroom"),
    # ── Legacy IDs (backward-compatible) ─────────────────────────────────────
    "basic":   dict(hp=40,  damage=15, speed=2.0,  display=100, tint=None, label="Orc"),
    "shooter": dict(hp=30,  damage=12,             display=100, tint=None, label="Shooter"),
    "dash":    dict(hp=50,  damage=20, dash_speed=12, display=100, tint=None, label="Dasher"),
}
# Frame-count overrides for new packs (add when a pack has different counts)
# "subtype": dict(idle=N, walk=N, attack=N, hurt=N, die=N)
ENEMY_FRAME_COUNTS: dict = {
    # Example (fill in when you add a new pack):
    # "skeleton": dict(idle=4, walk=6, attack=5, hurt=3, die=4),
}


# ── Tint helper ───────────────────────────────────────────────────────────────

def _tint(frames, rgba):
    if not rgba or not frames:
        return frames
    result = []
    for f in frames:
        copy = f.copy()
        ov   = pygame.Surface(copy.get_size(), pygame.SRCALPHA)
        ov.fill(rgba)
        copy.blit(ov, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        result.append(copy)
    return result


# ── Orc animator (cached per tint so we don't re-load the same PNG repeatedly) ──

_sprite_cache: dict = {}   # cache_key → prototype Animator


def _fresh_copy(proto):
    """Return a new Animator that shares frame surfaces with proto."""
    from animator import Animator
    a = Animator()
    for name, info in proto._states.items():
        a.add_state(name, info["frames"], duration=info["dur"], loop=info["loop"])
    return a


def _load_enemy_anim(subtype: str, display_size: int, tint_rgba):
    """
    Load an Animator for `subtype`.

    Priority:
      1. assets/sprites/enemies/<subtype>/   — real sprites dropped by the user
      2. Tinted Orc fallback

    Frame counts come from ENEMY_FRAME_COUNTS[subtype] if present,
    otherwise default Orc counts are used.
    """
    key = (subtype, display_size, tint_rgba)
    if key in _sprite_cache:
        return _fresh_copy(_sprite_cache[key])

    from animator import Animator, load_strip_cropped, load_strip_auto

    counts = ENEMY_FRAME_COUNTS.get(subtype, {})
    n_idle = counts.get("idle",   6)
    n_walk = counts.get("walk",   8)
    n_atk  = counts.get("attack", 6)
    n_hurt = counts.get("hurt",   4)
    n_die  = counts.get("die",    4)

    # ── 1. Try custom sprite directory ────────────────────────────────────────
    # The pack only ships Attack3.png per enemy, so:
    #   attack  → load Attack3.png (real sprite)
    #   idle / walk / hurt / die → Orc fallback (see step 2)
    custom_dir = os.path.join(_ENEMY_SPRITE_BASE, subtype)
    custom_atk = None
    if os.path.isdir(custom_dir):
        for fname in ("Attack.png", "Attack1.png", "Attack3.png"):
            full = os.path.join(custom_dir, fname)
            if os.path.exists(full):
                frames = load_strip_auto(full, display_size)
                if frames:
                    custom_atk = _tint(frames, tint_rgba)
                    break

    # ── 2. Tinted Orc fallback ────────────────────────────────────────────────
    if not os.path.isdir(_ORC_DIR):
        return None
    try:
        def s(fname, n):
            return _tint(
                load_strip_cropped(os.path.join(_ORC_DIR, fname),
                                   100, 100, n, target_h=display_size),
                tint_rgba)

        idle = s("Orc-Idle.png",     n_idle)
        walk = s("Orc-Walk.png",     n_walk)
        atk1 = s("Orc-Attack01.png", n_atk)
        atk2 = s("Orc-Attack02.png", n_atk)
        hurt = s("Orc-Hurt.png",     n_hurt)
        die  = s("Orc-Death.png",    n_die)

        if not idle:
            return None

        # Use real attack sprite if available, otherwise Orc attack
        final_atk  = custom_atk or atk1
        final_atk2 = custom_atk or atk2

        a = Animator()
        a.add_state("idle",    idle,       duration=8,  loop=True)
        a.add_state("walk",    walk,       duration=5,  loop=True)
        a.add_state("attack",  final_atk,  duration=4,  loop=False)
        a.add_state("attack2", final_atk2, duration=4,  loop=False)
        a.add_state("hurt",    hurt,       duration=6,  loop=False)
        a.add_state("die",     die,        duration=8,  loop=False)
        _sprite_cache[key] = a
        src = "custom+Orc" if custom_atk else "Orc"
        print(f"[Enemy] {subtype}: loaded ({src} sprites).")
        return _fresh_copy(a)

    except Exception as e:
        print(f"[Enemy] {subtype} fallback failed: {e}")
        return None


# ── Base class ────────────────────────────────────────────────────────────────

class BaseEnemy(pygame.sprite.Sprite):
    WIDTH  = 28
    HEIGHT = 38
    INVUL_FRAMES = 20

    def __init__(self, x, y, color, cfg: dict):
        super().__init__()
        self.base_color   = color
        self.facing       = 1
        self.vel_x = 0.0;  self.vel_y = 0.0
        self.on_ground    = False
        self.MAX_HP       = cfg["hp"]
        self.CONTACT_DAMAGE = cfg["damage"]
        self.hp           = self.MAX_HP
        self.invul        = 0
        self._flash       = 0
        self.dead         = False
        self._dying       = False
        self._display     = cfg.get("display", 100)

        self.image = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        self._draw(color)
        self.rect = self.image.get_rect(bottomleft=(x, y))

        self._anim = _load_enemy_anim(cfg.get("label", "orc").lower().replace(" ", "_"),
                                      self._display, cfg.get("tint"))

    # ── Drawn fallback ────────────────────────────────────────────────────────

    def _draw(self, color=None, flash=False):
        self.image.fill((0, 0, 0, 0))
        c = (255, 80, 80) if flash else (color or self.base_color)
        pygame.draw.rect(self.image, c,
                         (2, 10, self.WIDTH-4, self.HEIGHT-10), border_radius=4)
        pygame.draw.circle(self.image, c, (self.WIDTH//2, 8), 8)
        pygame.draw.circle(self.image, BLACK,
                           (self.WIDTH//2 + 3*self.facing, 6), 2)

    # ── Damage / dying ────────────────────────────────────────────────────────

    def take_damage(self, amount):
        if self.invul > 0 or self._dying:
            return
        self.hp    -= amount
        self.invul  = self.INVUL_FRAMES
        self._flash = 6
        if self.hp <= 0:
            self.dead   = True
            self._dying = True
            if self._anim:
                self._anim.set_state("die", force=True)

    def _tick_dying(self):
        """Advance death anim; kill when done. Returns True while dying."""
        if not self._dying:
            return False
        if self._anim:
            self._anim.update()
            if self._anim.finished:
                self.kill()
        else:
            self.kill()
        return True

    # ── Physics ───────────────────────────────────────────────────────────────

    def apply_gravity(self):
        self.vel_y += GRAVITY
        self.vel_y  = min(self.vel_y, MAX_FALL)

    def move_and_collide(self, tilemap):
        solid = tilemap.get_solid_tiles()
        self.rect.x += int(self.vel_x)
        for t in solid:
            if self.rect.colliderect(t.rect) and not t.is_platform():
                if self.vel_x > 0: self.rect.right = t.rect.left
                elif self.vel_x < 0: self.rect.left = t.rect.right
                self.vel_x *= -1;  self.facing *= -1

        prev_bottom = self.rect.bottom
        self.rect.y += int(self.vel_y)
        self.on_ground = False
        for t in solid:
            if self.rect.colliderect(t.rect):
                if t.is_platform():
                    if self.vel_y > 0 and prev_bottom <= t.rect.top + 4:
                        self.rect.bottom = t.rect.top
                        self.vel_y = 0;  self.on_ground = True
                else:
                    if self.vel_y > 0:
                        self.rect.bottom = t.rect.top
                        self.vel_y = 0;  self.on_ground = True
                    elif self.vel_y < 0:
                        self.rect.top = t.rect.bottom;  self.vel_y = 0

    # ── Shared anim helpers ───────────────────────────────────────────────────

    def _tick_invul(self):
        if self.invul  > 0: self.invul  -= 1
        if self._flash > 0: self._flash -= 1
        if not self._anim:
            self._draw(flash=self._flash > 0)

    def _update_anim(self, attacking=False):
        if not self._anim:
            return
        self._anim.set_flip(self.facing < 0)
        if self._flash > 0:
            self._anim.set_state("hurt", force=True)
        elif attacking:
            self._anim.set_state("attack")
        elif abs(self.vel_x) > 0.2:
            self._anim.set_state("walk")
        else:
            self._anim.set_state("idle")
        self._anim.update()

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface, cam_off):
        ox, oy = cam_off
        if self._anim:
            img = self._anim.image
            # Center over hitbox; sprite bottom == feet == rect.bottom
            dx = self.rect.centerx - img.get_width()  // 2 - ox
            dy = self.rect.bottom  - img.get_height()     - oy
            surface.blit(img, (dx, dy))
        else:
            surface.blit(self.image, (self.rect.x - ox, self.rect.y - oy))
        self._draw_hp_bar(surface, cam_off)

    def _draw_hp_bar(self, surface, cam_off):
        if self._dying:
            return
        ox, oy = cam_off
        bw  = self.WIDTH
        pct = max(0, self.hp) / self.MAX_HP
        x   = self.rect.x - ox
        y   = self.rect.y - oy - 8
        pygame.draw.rect(surface, (80, 0, 0), (x, y, bw, 5))
        pygame.draw.rect(surface, RED,        (x, y, int(bw * pct), 5))


# ── BasicEnemy (patrols) ──────────────────────────────────────────────────────

class BasicEnemy(BaseEnemy):
    def __init__(self, x, y, cfg: dict, patrol_range=120):
        color = {
            "elite_orc": (200, 80, 80), "skeleton": (210,210,185),
            "werebear": (140,90,60), "greatsword_skeleton": (140,155,175),
        }.get(cfg.get("label","").lower().replace(" ","_"), (180, 60, 60))
        super().__init__(x, y, color, cfg)
        self.start_x      = x
        self.patrol_range = patrol_range
        self._speed       = cfg.get("speed", 2.0)
        self.vel_x        = self._speed

    def update(self, tilemap, player, projectiles):
        if self._tick_dying():
            return
        self.apply_gravity()
        self.move_and_collide(tilemap)
        if self.rect.x - self.start_x > self.patrol_range:
            self.vel_x = -self._speed;  self.facing = -1
        elif self.rect.x - self.start_x < 0:
            self.vel_x =  self._speed;  self.facing =  1
        self._tick_invul()
        self._update_anim()


# ── ShooterEnemy (fires projectiles) ─────────────────────────────────────────

class ShooterEnemy(BaseEnemy):
    SIGHT_RANGE    = 340
    SHOOT_COOLDOWN = 90

    def __init__(self, x, y, cfg: dict):
        super().__init__(x, y, (180, 100, 30), cfg)
        self.shoot_timer = 0
        self.bullets     = pygame.sprite.Group()

    def update(self, tilemap, player, projectiles):
        if self._tick_dying():
            self.bullets.update(tilemap);  return
        self.apply_gravity()
        self.move_and_collide(tilemap)

        dx = player.rect.centerx - self.rect.centerx
        self.facing = 1 if dx > 0 else -1
        dist = math.hypot(dx, player.rect.centery - self.rect.centery)

        firing = False
        if dist < self.SIGHT_RANGE and self.shoot_timer <= 0:
            b = EnemyBullet(self.rect.centerx, self.rect.centery, self.facing)
            self.bullets.add(b);  projectiles.add(b)
            self.shoot_timer = self.SHOOT_COOLDOWN
            firing = True
        if self.shoot_timer > 0:
            self.shoot_timer -= 1

        self.bullets.update(tilemap)
        self._tick_invul()
        self._update_anim(attacking=(self.shoot_timer >= self.SHOOT_COOLDOWN - 8))

    def draw(self, surface, cam_off):
        super().draw(surface, cam_off)
        ox, oy = cam_off
        for b in self.bullets:
            surface.blit(b.image, (b.rect.x - ox, b.rect.y - oy))


# ── DashEnemy ────────────────────────────────────────────────────────────────

class DashEnemy(BaseEnemy):
    DASH_DURATION = 18
    DASH_COOLDOWN = 120

    def __init__(self, x, y, cfg: dict, detect_radius=200):
        super().__init__(x, y, (100, 30, 180), cfg)
        self.detect_radius = detect_radius
        self._dash_speed   = cfg.get("dash_speed", 12)
        self.dashing    = False
        self.dash_timer = 0
        self.cooldown   = 0

    def update(self, tilemap, player, projectiles):
        if self._tick_dying():
            return
        self.apply_gravity()

        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        self.facing = 1 if dx > 0 else -1

        if self.dashing:
            self.dash_timer -= 1
            if self.dash_timer <= 0:
                self.dashing  = False;  self.vel_x = 0
                self.cooldown = self.DASH_COOLDOWN
        else:
            if self.cooldown > 0:
                self.cooldown -= 1
            elif math.hypot(dx, dy) < self.detect_radius:
                ang        = math.atan2(dy, dx)
                self.vel_x = math.cos(ang) * self._dash_speed
                self.vel_y = min(math.sin(ang) * self._dash_speed, -4)
                self.dashing    = True
                self.dash_timer = self.DASH_DURATION

        self.move_and_collide(tilemap)
        self._tick_invul()

        if self._anim:
            self._anim.set_flip(self.facing < 0)
            if self._flash > 0:
                self._anim.set_state("hurt", force=True)
            elif self.dashing:
                self._anim.set_state("attack2")
            else:
                self._anim.set_state("idle")
            self._anim.update()


# ── Factory ───────────────────────────────────────────────────────────────────

def make_enemy(etype, x, y, **kwargs):
    cfg = ENEMY_CONFIG.get(etype)
    if cfg is None:
        cfg = ENEMY_CONFIG["basic"]   # unknown type → default orc

    # Melee patrol types
    if etype in ("orc","elite_orc","skeleton","werebear",
                 "greatsword_skeleton","goblin","basic"):
        return BasicEnemy(x, y, cfg, patrol_range=kwargs.get("patrol_range", 120))

    # Ranged types
    if etype in ("skeleton_archer","flying_eye","shooter"):
        return ShooterEnemy(x, y, cfg)

    # Dash types
    if etype in ("orc_rider","greatsword_skeleton_dash","mushroom","dash"):
        return DashEnemy(x, y, cfg, detect_radius=kwargs.get("detect_radius", 200))

    # Final fallback
    return BasicEnemy(x, y, cfg, patrol_range=kwargs.get("patrol_range", 120))
