import pygame, math, os
from settings import *
from weapons import EnemyBullet
import enemy_data as _ed

_PACK    = "Tiny RPG Character Asset Pack v1.03 -Free Soldier&Orc"
_ORC_DIR = os.path.join(_PACK, "Characters(100x100)", "Orc", "Orc with shadows")

# ── Custom sprite directory for any enemy subtype ─────────────────────────────
# Drop a folder at  assets/sprites/enemies/<subtype>/  with these files:
#   <Name>-Idle.png   <Name>-Walk.png   <Name>-Attack.png
#   <Name>-Hurt.png   <Name>-Death.png
# The game will auto-load them instead of the tinted Orc fallback.
_ENEMY_SPRITE_BASE = os.path.join("assets", "sprites", "enemies")

# ── Enemy subtype configuration ───────────────────────────────────────────────
# Tints are art-only and not user-editable; everything else comes from enemy_data.
_TINTS = {"skeleton": (230, 230, 200, 255)}

def _build_config():
    cfg = {}
    for eid, data in _ed.ENEMIES.items():
        entry = dict(data)
        entry["tint"] = _TINTS.get(eid)
        cfg[eid] = entry
    return cfg

ENEMY_CONFIG = _build_config()

# Exact frame counts per state (keyed by label-derived subtype)
ENEMY_FRAME_COUNTS: dict = {
    "goblin":        dict(idle=4, walk=6,  attack=4, hurt=3, die=6),
    "bomber_goblin": dict(idle=4,          attack=6, hurt=3, die=6),
    "flying_eye":    dict(idle=3, walk=3,  attack=3, hurt=3, die=5),
    "mushroom":      dict(       walk=8,             hurt=3, die=6),
    "slime":         dict(idle=5, walk=15,            hurt=3, die=6),
    "worm":          dict(       walk=6,             hurt=3, die=6),
}

# Per-state explicit (frame_w, frame_h) for non-square sprite sheets
# Only needed when frame_w != frame_h (load_strip_auto can't auto-detect these)
_ENEMY_FRAME_DIM: dict = {
    "goblin":  {"attack": (24, 16)},
    "slime":   {"walk":   (16, 24)},
    "worm":    {"walk": (16, 8), "hurt": (16, 8), "die": (16, 8)},
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

    Priority per state (idle/walk/attack/hurt/die):
      1. assets/sprites/enemies/<subtype>/<State>.png  — custom sprites
      2. Tinted Orc fallback (if the Orc asset pack is present)
      3. None → drawn colored-rectangle fallback
    """
    key = (subtype, display_size, tint_rgba)
    if key in _sprite_cache:
        return _fresh_copy(_sprite_cache[key])

    from animator import Animator, load_strip, load_strip_cropped, load_strip_auto

    counts = ENEMY_FRAME_COUNTS.get(subtype, {})
    n_idle = counts.get("idle",   6)
    n_walk = counts.get("walk",   8)
    n_atk  = counts.get("attack", 6)
    n_hurt = counts.get("hurt",   4)
    n_die  = counts.get("die",    4)

    # ── 1. Load all available state sprites from the custom directory ─────────
    custom_dir = os.path.join(_ENEMY_SPRITE_BASE, subtype)
    _STATE_CANDIDATES = {
        "idle":   ["Idle.png",   "idle.png"],
        "walk":   ["Walk.png",   "Run.png",    "walk.png",  "run.png"],
        "attack": ["Attack3.png","Attack.png", "Attack1.png","attack.png"],
        "hurt":   ["Hurt.png",   "Hit.png",    "hurt.png",  "hit.png"],
        "die":    ["Death.png",  "Dead.png",   "death.png", "dead.png"],
    }
    custom = {}
    frame_dims = _ENEMY_FRAME_DIM.get(subtype, {})
    if os.path.isdir(custom_dir):
        for state, fnames in _STATE_CANDIDATES.items():
            for fname in fnames:
                full = os.path.join(custom_dir, fname)
                if os.path.exists(full):
                    dim = frame_dims.get(state)
                    if dim:
                        fw, fh = dim
                        n = ENEMY_FRAME_COUNTS.get(subtype, {}).get(
                            state if state != "die" else "die",
                            pygame.image.load(full).get_width() // fw)
                        scale = display_size / fh
                        frames = load_strip(full, fw, fh, n, scale)
                    else:
                        frames = load_strip_auto(full, display_size)
                    if frames:
                        custom[state] = _tint(frames, tint_rgba)
                        break

    # ── 2. Tinted Orc fallback for any states not covered by custom ───────────
    orc_states = {}
    if os.path.isdir(_ORC_DIR):
        try:
            def s(fname, n):
                return _tint(
                    load_strip_cropped(os.path.join(_ORC_DIR, fname),
                                       100, 100, n, target_h=display_size),
                    tint_rgba)
            orc_states = {
                "idle":    s("Orc-Idle.png",     n_idle),
                "walk":    s("Orc-Walk.png",     n_walk),
                "attack":  s("Orc-Attack01.png", n_atk),
                "attack2": s("Orc-Attack02.png", n_atk),
                "hurt":    s("Orc-Hurt.png",     n_hurt),
                "die":     s("Orc-Death.png",    n_die),
            }
        except Exception as e:
            print(f"[Enemy] Orc pack load failed: {e}")

    # ── 3. Merge: custom overrides Orc; need at least one state ──────────────
    # Fill each state: custom → orc → best custom fallback → None
    best_fallback = (custom.get("attack") or custom.get("idle") or
                     next(iter(custom.values()), None))

    def _get(state):
        return (custom.get(state) or orc_states.get(state) or best_fallback)

    idle   = _get("idle")
    walk   = _get("walk")
    attack = _get("attack")
    atk2   = custom.get("attack") or orc_states.get("attack2") or best_fallback
    hurt   = _get("hurt")
    die    = _get("die")

    if not idle:
        return None   # no sprites at all → drawn rectangle fallback

    a = Animator()
    a.add_state("idle",    idle,   duration=8, loop=True)
    a.add_state("walk",    walk,   duration=5, loop=True)
    a.add_state("attack",  attack, duration=4, loop=False)
    a.add_state("attack2", atk2,   duration=4, loop=False)
    a.add_state("hurt",    hurt,   duration=6, loop=False)
    a.add_state("die",     die,    duration=8, loop=False)
    _sprite_cache[key] = a

    sources = []
    if custom:   sources.append(f"custom({','.join(custom)})")
    if orc_states: sources.append("Orc")
    print(f"[Enemy] {subtype}: loaded ({' + '.join(sources) or 'fallback'}).")
    return _fresh_copy(a)


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

    def __init__(self, x, y, cfg: dict, detect_radius=None):
        super().__init__(x, y, (100, 30, 180), cfg)
        self.detect_radius = (detect_radius if detect_radius is not None
                              else cfg.get("detect_radius", 200))
        self._dash_speed   = cfg.get("dash_speed",   12)
        self._dash_cooldown = cfg.get("dash_cooldown", 120)
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
                self.cooldown = self._dash_cooldown
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


# ── FlyingEnemy (floats, chases, shoots) ─────────────────────────────────────

class FlyingEnemy(BaseEnemy):
    BOB_AMP  = 10    # vertical bobbing pixels
    BOB_RATE = 0.04  # radians per frame

    def __init__(self, x, y, cfg, patrol_range=120):
        super().__init__(x, y, (80, 60, 180), cfg)
        self.start_x        = x
        self.patrol_range   = patrol_range
        self.shoot_timer    = 0
        self.bullets        = pygame.sprite.Group()
        self._fly_speed     = cfg.get("speed",         2.5)
        self._sight_range   = cfg.get("sight_range",   300)
        self._attack_range  = cfg.get("attack_range",  200)
        self._shoot_cd      = cfg.get("shoot_cooldown", 80)
        self._bob_t         = 0.0
        self._base_y        = float(self.rect.centery)
        self._fx            = float(self.rect.x)
        self._fy            = float(self.rect.y)
        self.vel_x          = self._fly_speed

    def update(self, tilemap, player, projectiles):
        if self._tick_dying():
            self.bullets.update(tilemap)
            return

        self._bob_t += self.BOB_RATE

        dx   = player.rect.centerx - self.rect.centerx
        dy   = player.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        self.facing = 1 if dx > 0 else -1

        firing = False

        if dist < self._sight_range:
            # Track player height with a gentle bob
            target_y = float(player.rect.centery) + math.sin(self._bob_t) * (self.BOB_AMP * 0.5)
            if dist > self._attack_range:
                # Chase horizontally
                self.vel_x = self._fly_speed * (1 if dx > 0 else -1)
            else:
                # Hover in place and shoot
                self.vel_x = 0
                if self.shoot_timer <= 0:
                    b = EnemyBullet(self.rect.centerx, self.rect.centery, self.facing)
                    self.bullets.add(b)
                    projectiles.add(b)
                    self.shoot_timer = self._shoot_cd
                    firing = True
        else:
            # Patrol between start_x ± patrol_range, bobbing at base height
            target_y = self._base_y + math.sin(self._bob_t) * self.BOB_AMP
            offset = self._fx - self.start_x
            if offset > self.patrol_range:
                self.vel_x = -self._fly_speed
            elif offset < -self.patrol_range:
                self.vel_x =  self._fly_speed

        # Spring toward target_y (no gravity)
        vy = (target_y - self.rect.centery) * 0.10
        self.vel_y = max(-4.0, min(4.0, vy))

        self._fx += self.vel_x
        self._fy += self.vel_y
        self.rect.x = int(self._fx)
        self.rect.y = int(self._fy)

        if self.shoot_timer > 0:
            self.shoot_timer -= 1

        self.bullets.update(tilemap)
        self._tick_invul()
        self._update_anim(attacking=(firing or self.shoot_timer >= self._shoot_cd - 8))

    def draw(self, surface, cam_off):
        ox, oy = cam_off
        if self._anim:
            img = self._anim.image
            # Center sprite on hitbox (not feet) — flying enemy floats
            surface.blit(img, (self.rect.centerx - img.get_width()  // 2 - ox,
                               self.rect.centery - img.get_height() // 2 - oy))
        else:
            surface.blit(self.image, (self.rect.x - ox, self.rect.y - oy))
        self._draw_hp_bar(surface, cam_off)
        for b in self.bullets:
            surface.blit(b.image, (b.rect.x - ox, b.rect.y - oy))


# ── Factory ───────────────────────────────────────────────────────────────────

def make_enemy(etype, x, y, **kwargs):
    cfg = ENEMY_CONFIG.get(etype, ENEMY_CONFIG["goblin"])  # unknown → goblin

    if etype in ("goblin", "bomber_goblin", "skeleton", "slime", "worm"):
        return BasicEnemy(x, y, cfg, patrol_range=kwargs.get("patrol_range", 120))

    if etype == "flying_eye":
        return FlyingEnemy(x, y, cfg, patrol_range=kwargs.get("patrol_range", 120))

    if etype == "mushroom":
        return DashEnemy(x, y, cfg, detect_radius=kwargs.get("detect_radius"))

    # Legacy / unknown → remap to closest sprited equivalent
    _remap = {
        "orc": "goblin", "elite_orc": "bomber_goblin", "basic": "goblin",
        "skeleton_archer": "flying_eye", "shooter": "flying_eye",
        "orc_rider": "mushroom", "dash": "mushroom",
        "werebear": "slime", "greatsword_skeleton": "worm",
        "greatsword_skeleton_dash": "mushroom",
    }
    mapped = _remap.get(etype, "goblin")
    return make_enemy(mapped, x, y, **kwargs)
