import pygame, math, os
from settings import *
from ui_components import make_orb, HERO_ORB_CFG

_PACK        = "Tiny RPG Character Asset Pack v1.03 -Free Soldier&Orc"
_ARROW_32    = os.path.join(_PACK, "Arrow(Projectile)", "Arrow01(32x32).png")
_ARROW_CACHE = {}   # direction (+1/-1) → Surface, loaded on first use


def _get_arrow_image(direction):
    """Return the real arrow sprite (or drawn fallback), cached."""
    if direction not in _ARROW_CACHE:
        if os.path.exists(_ARROW_32):
            img = pygame.image.load(_ARROW_32).convert_alpha()
            img = pygame.transform.scale(img, (28, 12))   # fit game scale
            # asset faces right by default
            _ARROW_CACHE[ 1] = img
            _ARROW_CACHE[-1] = pygame.transform.flip(img, True, False)
        else:
            # Drawn fallback
            surf = pygame.Surface((18, 6), pygame.SRCALPHA)
            pygame.draw.rect(surf, (180, 130, 60), (0, 2, 14, 2))
            pygame.draw.polygon(surf, (220, 180, 80), [(14, 0), (18, 3), (14, 6)])
            _ARROW_CACHE[ 1] = surf
            _ARROW_CACHE[-1] = pygame.transform.flip(surf, True, False)
    return _ARROW_CACHE[direction]


# ── Projectiles ───────────────────────────────────────────────────────────────

class Arrow(pygame.sprite.Sprite):
    SPEED    = 14
    DAMAGE   = 20
    LIFETIME = 90

    def __init__(self, x, y, direction, damage=None, speed=None, lifetime=None):
        super().__init__()
        self.vel_x   = (speed    if speed    is not None else self.SPEED)    * direction
        self.vel_y   = 0
        self.damage  =  damage   if damage   is not None else self.DAMAGE
        self.timer   =  lifetime if lifetime is not None else self.LIFETIME
        self.image   = _get_arrow_image(direction)
        self.rect    = self.image.get_rect(center=(x, y))
        self.from_player = True

    def update(self, tilemap, *_):
        self.rect.x += self.vel_x
        self.timer -= 1
        if self.timer <= 0:
            self.kill()
            return
        col = self.rect.centerx // TILE_SIZE
        row = self.rect.centery // TILE_SIZE
        tt = tilemap.get_tile_type(col, row)
        if tt in (T_GROUND, T_PLATFORM):
            self.kill()


class MagicBolt(pygame.sprite.Sprite):
    DAMAGE   = 40
    DURATION = 15   # frames the hitbox stays active

    def __init__(self, player_rect, direction, damage=None, duration=None):
        super().__init__()
        self.damage      = damage   if damage   is not None else self.DAMAGE
        self.timer       = duration if duration is not None else self.DURATION
        self.from_player = True
        w = TILE_SIZE * 2
        h = TILE_SIZE * 2
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        self._draw_frame(1.0)
        if direction > 0:
            self.rect = self.image.get_rect(midleft=(player_rect.right, player_rect.centery))
        else:
            self.rect = self.image.get_rect(midright=(player_rect.left, player_rect.centery))

    def _draw_frame(self, alpha_factor):
        self.image.fill((0, 0, 0, 0))
        w, h = self.image.get_size()
        a_bg   = int(120 * alpha_factor)
        a_mid  = int(200 * alpha_factor)
        a_edge = int(255 * alpha_factor)
        pygame.draw.rect(self.image, (*PURPLE[:3], a_bg),  (0, 0, w, h),         border_radius=10)
        pygame.draw.rect(self.image, (200, 150, 255, a_mid), (5, 5, w-10, h-10), border_radius=7)
        pygame.draw.rect(self.image, (255, 220, 255, a_edge), (0, 0, w, h), 2,   border_radius=10)

    def update(self, *_):
        self.timer -= 1
        if self.timer <= 0:
            self.kill()
            return
        self._draw_frame(self.timer / self.DURATION)


class EnemyBullet(pygame.sprite.Sprite):
    SPEED = 6
    DAMAGE = 10
    LIFETIME = 150

    def __init__(self, x, y, direction):
        super().__init__()
        self.vel_x = self.SPEED * direction
        self.vel_y = 0
        self.damage = self.DAMAGE
        self.timer = self.LIFETIME
        self.from_player = False
        sz = 10
        self.image = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.circle(self.image, ORANGE, (sz//2, sz//2), sz//2)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self, tilemap, *_):
        self.rect.x += self.vel_x
        self.timer -= 1
        if self.timer <= 0:
            self.kill()
            return
        col = self.rect.centerx // TILE_SIZE
        row = self.rect.centery // TILE_SIZE
        tt = tilemap.get_tile_type(col, row)
        if tt in (T_GROUND, T_PLATFORM):
            self.kill()


# ── Weapon Pickup sprite ─────────────────────────────────────────────────────

class WeaponPickup(pygame.sprite.Sprite):
    # Orb size slightly smaller than the tile so the glow ring has breathing room
    _ORB_SIZE = TILE_SIZE - 4

    def __init__(self, weapon_id, x, y):
        super().__init__()
        self.weapon_id = weapon_id
        sz  = TILE_SIZE
        cfg = HERO_ORB_CFG.get(weapon_id, HERO_ORB_CFG["sword"])
        orb = make_orb(self._ORB_SIZE, *cfg)

        # Centre the orb inside the tile-sized surface
        self.image = pygame.Surface((sz, sz), pygame.SRCALPHA)
        off = (sz - self._ORB_SIZE) // 2
        self.image.blit(orb, (off, off))

        self.rect       = self.image.get_rect(center=(x, y))
        self.bob_timer  = 0
        self._base_img  = self.image.copy()   # used for pulse redraw

    def update(self, *_):
        self.bob_timer += 0.08
        self.rect.y += int(math.sin(self.bob_timer) * 0.5)

        # Gentle alpha pulse to draw the player's attention
        pulse = 0.75 + 0.25 * math.sin(self.bob_timer * 1.8)
        self.image = self._base_img.copy()
        self.image.set_alpha(int(255 * pulse))


# ── Sword swing hitbox ───────────────────────────────────────────────────────

class SwordSlash(pygame.sprite.Sprite):
    DAMAGE = 30
    DURATION = 12   # frames

    def __init__(self, player_rect, direction, damage=None):
        super().__init__()
        self.damage = damage if damage is not None else self.DAMAGE
        self.timer = self.DURATION
        self.from_player = True
        w, h = 44, 32
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (*WHITE, 160), (0, 0, w, h))
        if direction > 0:
            self.rect = self.image.get_rect(midleft=(player_rect.right, player_rect.centery))
        else:
            self.rect = self.image.get_rect(midright=(player_rect.left, player_rect.centery))
        self.direction = direction

    def update(self, *_):
        self.timer -= 1
        if self.timer <= 0:
            self.kill()
