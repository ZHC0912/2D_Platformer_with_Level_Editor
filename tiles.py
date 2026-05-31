import pygame, os
from settings import *


# ── Tile texture manager ──────────────────────────────────────────────────────

class TileTextureManager:
    """
    Loads dungeon tile textures from assets/tiles/.
    Singleton — call TileTextureManager.get() everywhere.
    Lazy-initialised on first use so pygame must be ready first.
    """
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = TileTextureManager()
            cls._inst._load()
        return cls._inst

    def __init__(self):
        self._static: dict  = {}   # tile_type  → Surface (TILE_SIZE × TILE_SIZE)
        self._anim:   dict  = {}   # name_str   → [Surface, ...]
        self._ts = None

    def _load(self):
        ts_path = os.path.join("assets", "tiles", "Dungeon_Tileset.png")
        if os.path.exists(ts_path):
            self._ts = pygame.image.load(ts_path).convert_alpha()

        # Static tile textures — (row, col) in the 16×16 tileset grid
        # Tune these constants if the visual tile doesn't look right.
        self._static[T_GROUND]   = self._tile(4, 0)
        self._static[T_PLATFORM] = self._tile(6, 4)

        # Animated tiles (individual PNG frames)
        for key, folder in [("coin", "coin"), ("spike", "spikes")]:
            d = os.path.join("assets", "tiles", folder)
            if os.path.isdir(d):
                frames = []
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith(".png"):
                        img = pygame.image.load(os.path.join(d, f)).convert_alpha()
                        frames.append(pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE)))
                if frames:
                    self._anim[key] = frames

    def _tile(self, row, col):
        """Extract one 16×16 tile from the tileset and scale to TILE_SIZE."""
        if self._ts is None:
            return None
        src = pygame.Rect(col * 16, row * 16, 16, 16)
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        surf.blit(self._ts, (0, 0), src)
        return pygame.transform.scale(surf, (TILE_SIZE, TILE_SIZE))

    def static(self, tile_type):
        return self._static.get(tile_type)

    def anim_frame(self, key):
        """Return the current animation frame based on wall-clock time."""
        frames = self._anim.get(key)
        if not frames:
            return None
        idx = pygame.time.get_ticks() // 150 % len(frames)
        return frames[idx]


# ── Tile sprite ───────────────────────────────────────────────────────────────

class Tile(pygame.sprite.Sprite):
    def __init__(self, tile_type, col, row):
        super().__init__()
        self.tile_type = tile_type
        self.col = col
        self.row = row
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._draw()
        self.rect = self.image.get_rect(topleft=(col * TILE_SIZE, row * TILE_SIZE))

    def _draw(self):
        t = self.tile_type
        if t == T_EMPTY:
            return

        # ── Try texture atlas first ───────────────────────────────────────────
        ttm = TileTextureManager.get()
        tex = ttm.static(t)
        if tex and t in (T_GROUND, T_PLATFORM):
            self.image.fill((0, 0, 0, 0))
            self.image.blit(tex, (0, 0))
            return

        # ── Primitive fallback (coin/spike/spawn use it; animated drawn per-frame) ──
        self._draw_primitive()

    def _draw_primitive(self):
        t = self.tile_type
        color = TILE_COLORS.get(t, GRAY)
        self.image.fill((0, 0, 0, 0))
        if t == T_GROUND:
            self.image.fill(color)
            pygame.draw.rect(self.image, (90, 60, 30), (0, 0, TILE_SIZE, 6))
            pygame.draw.rect(self.image, (80, 50, 20), (0, TILE_SIZE-2, TILE_SIZE, 2))
        elif t == T_PLATFORM:
            self.image.fill(color)
            pygame.draw.rect(self.image, (200, 160, 100), (0, 0, TILE_SIZE, 8))
            pygame.draw.rect(self.image, (100, 70, 30), (0, 8, TILE_SIZE, TILE_SIZE-8))
        elif t == T_SPIKE:
            n = 4
            w = TILE_SIZE // n
            for i in range(n):
                x0 = i * w
                pygame.draw.polygon(self.image, RED,
                    [(x0, TILE_SIZE), (x0 + w//2, 4), (x0 + w, TILE_SIZE)])
        elif t == T_COIN:
            cx, cy = TILE_SIZE//2, TILE_SIZE//2
            r = TILE_SIZE//2 - 4
            pygame.draw.circle(self.image, YELLOW, (cx, cy), r)
            pygame.draw.circle(self.image, ORANGE, (cx, cy), r, 3)
            pygame.draw.circle(self.image, (255, 255, 150), (cx-3, cy-3), r//3)
        elif t == T_SPAWN:
            pygame.draw.rect(self.image, CYAN, (8, 8, TILE_SIZE-16, TILE_SIZE-16), 3)
            pygame.draw.line(self.image, CYAN, (TILE_SIZE//2, 0), (TILE_SIZE//2, TILE_SIZE), 2)
            pygame.draw.line(self.image, CYAN, (0, TILE_SIZE//2), (TILE_SIZE, TILE_SIZE//2), 2)

    def is_solid(self):
        return self.tile_type in (T_GROUND, T_PLATFORM)

    def is_platform(self):
        return self.tile_type == T_PLATFORM

    def is_spike(self):
        return self.tile_type == T_SPIKE

    def is_coin(self):
        return self.tile_type == T_COIN


class TileMap:
    """Manages the grid of tiles for a level."""
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.grid = [[T_EMPTY] * cols for _ in range(rows)]
        self.sprites = pygame.sprite.Group()
        self._tile_cache = {}

    def set_tile(self, col, row, tile_type):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.grid[row][col] = tile_type
            key = (col, row)
            if key in self._tile_cache:
                self._tile_cache[key].kill()
                del self._tile_cache[key]
            if tile_type != T_EMPTY:
                t = Tile(tile_type, col, row)
                self._tile_cache[key] = t
                self.sprites.add(t)

    def get_tile_type(self, col, row):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col]
        return T_EMPTY

    def rebuild_sprites(self):
        self.sprites.empty()
        self._tile_cache.clear()
        for r in range(self.rows):
            for c in range(self.cols):
                t = self.grid[r][c]
                if t != T_EMPTY:
                    tile = Tile(t, c, r)
                    self._tile_cache[(c, r)] = tile
                    self.sprites.add(tile)

    def get_solid_tiles(self):
        return [t for t in self.sprites if t.is_solid()]

    def get_spike_tiles(self):
        return [t for t in self.sprites if t.is_spike()]

    def get_coin_tiles(self):
        return [t for t in self.sprites if t.is_coin()]

    def draw(self, surface, camera_offset):
        ox, oy = camera_offset
        ttm = TileTextureManager.get()
        for tile in self.sprites:
            r = tile.rect.move(-ox, -oy)
            if not (-TILE_SIZE < r.x < SCREEN_W + TILE_SIZE
                    and -TILE_SIZE < r.y < SCREEN_H + TILE_SIZE):
                continue
            # Animated tiles — fetch live frame each draw call
            if tile.tile_type == T_COIN:
                frame = ttm.anim_frame("coin")
                surface.blit(frame if frame else tile.image, r)
            elif tile.tile_type == T_SPIKE:
                frame = ttm.anim_frame("spike")
                surface.blit(frame if frame else tile.image, r)
            else:
                surface.blit(tile.image, r)

    def to_list(self):
        return [row[:] for row in self.grid]

    @classmethod
    def from_list(cls, grid_data):
        rows = len(grid_data)
        cols = len(grid_data[0]) if rows > 0 else 0
        tm = cls(cols, rows)
        for r, row in enumerate(grid_data):
            for c, val in enumerate(row):
                tm.grid[r][c] = val
        tm.rebuild_sprites()
        return tm
