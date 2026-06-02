import pygame, os
from settings import *


# ── Tile texture manager ──────────────────────────────────────────────────────

# Tileset source — 128×96 px, 16×16 tiles (8 cols × 6 rows)
_TILESET_PATH = os.path.join("assets", "Platform tiles", "Tileset(16x16)", "Tileset.png")

# (row, col) positions inside that tileset:
_ROW_GRASS_TOP  = 0;  _COL_GRASS_TOP  = 0   # bright green surface tile
_ROW_DIRT_FILL  = 1;  _COL_DIRT_FILL  = 0   # dark teal fill (ground interior)
# Platform is composited from the three light-colour tile types in the upper rows:
_PLAT_LIGHT = [(0, 0), (1, 1), (2, 1)]   # bright-green top, medium-green ×2


class TileTextureManager:
    """
    Loads platform tile textures from the new 16×16 tileset.
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
        self._grass_top = None   # T_GROUND, exposed surface
        self._dirt_fill = None   # T_GROUND, buried interior
        self._platform  = None   # T_PLATFORM (composite of 3 light tiles)
        self._anim: dict = {}    # name → [Surface, ...]
        self._ts = None

    def _load(self):
        if os.path.exists(_TILESET_PATH):
            self._ts = pygame.image.load(_TILESET_PATH).convert_alpha()

        self._grass_top = self._tile(_ROW_GRASS_TOP, _COL_GRASS_TOP)
        self._dirt_fill = self._tile(_ROW_DIRT_FILL, _COL_DIRT_FILL)
        self._platform  = self._make_platform_tex()

        # Animated tiles — try new pack strip files first, fall back to frame folders
        _MISC = os.path.join("assets", "platformer_metroidvania asset pack v1.01",
                             "miscellaneous sprites")

        # coin: 48x8, 6 frames of 8x8 (square) — load_strip_auto works
        # spike: 112x16, 7 frames of 16x16 (square) — load_strip_auto works
        # torch: 96x24, 12 frames of 8x24 (non-square) — need explicit dims
        _strip_cfg = {
            "coin":  ("coin_anim_strip_6.png",       None,     None,  None),
            "spike": ("trap_spikes_anim_strip_7.png", None,     None,  None),
            "torch": ("tiki_torch_props_strip_12.png", 8,       24,    12),
        }
        for key, (fname, fw, fh, count) in _strip_cfg.items():
            path = os.path.join(_MISC, fname)
            if os.path.exists(path):
                raw = pygame.image.load(path).convert_alpha()
                h = raw.get_height()
                if fh is None:   # square frames
                    fh = h; fw = h; count = raw.get_width() // h
                frames = []
                for i in range(count):
                    sf = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sf.blit(raw, (0, 0), pygame.Rect(i * fw, 0, fw, fh))
                    frames.append(pygame.transform.scale(sf, (TILE_SIZE, TILE_SIZE)))
                if frames:
                    self._anim[key] = frames
                    continue   # skip folder fallback

            # Folder fallback (original frame-by-frame PNG folders)
            folder_map = {"coin": ("coin", None), "spike": ("spikes", None),
                          "torch": ("torch", "torch_")}
            folder, prefix = folder_map[key]
            d = os.path.join("assets", "tiles", folder)
            if os.path.isdir(d):
                frames = []
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith(".png") and (
                            prefix is None or f.lower().startswith(prefix)):
                        img = pygame.image.load(os.path.join(d, f)).convert_alpha()
                        frames.append(pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE)))
                if frames:
                    self._anim[key] = frames

    def _tile(self, row, col):
        """Extract one 16×16 cell and scale to TILE_SIZE × TILE_SIZE."""
        if self._ts is None:
            return None
        src  = pygame.Rect(col * 16, row * 16, 16, 16)
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        surf.blit(self._ts, (0, 0), src)
        return pygame.transform.scale(surf, (TILE_SIZE, TILE_SIZE))

    def _make_platform_tex(self):
        """
        Stack the three upper light-colour tile types into one platform surface.
        Each tile type contributes one-third of the tile height, producing a
        grass-ledge look that is clearly visible and distinct from solid ground.
        """
        srcs = [self._tile(r, c) for r, c in _PLAT_LIGHT]
        if not srcs[0]:
            return None
        surf   = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        h3     = TILE_SIZE // 3
        slices = [h3, h3, TILE_SIZE - 2 * h3]   # top, mid, bottom (accounts for rounding)
        y = 0
        for src, sh in zip(srcs, slices):
            tile = src or srcs[0]   # fall back to bright-green if a variant is missing
            surf.blit(tile, (0, y), pygame.Rect(0, 0, TILE_SIZE, sh))
            y += sh
        return surf

    def ground_tex(self, has_tile_above: bool):
        """Return the grass-top tile if exposed, dirt fill if buried."""
        return self._dirt_fill if has_tile_above else self._grass_top

    def platform_tex(self):
        return self._platform

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

        # Ground and platform textures are resolved context-sensitively at draw
        # time in TileMap.draw() — bake primitive fallback here for everything else.
        if t in (T_GROUND, T_PLATFORM):
            ttm = TileTextureManager.get()
            # Use a default (grass top) as the baked image; TileMap.draw() overrides.
            tex = (ttm.platform_tex() if t == T_PLATFORM else ttm.ground_tex(False))
            if tex:
                self.image.fill((0, 0, 0, 0))
                self.image.blit(tex, (0, 0))
                return

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
        elif t == T_TORCH:
            cx = TILE_SIZE // 2
            pygame.draw.rect(self.image, (160, 100, 30), (cx-4, TILE_SIZE//2, 8, TILE_SIZE//2-2))
            pygame.draw.ellipse(self.image, ORANGE, (cx-6, 4, 12, 22))
            pygame.draw.ellipse(self.image, YELLOW, (cx-3, 7, 7, 14))

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

            tt = tile.tile_type
            if tt == T_COIN:
                frame = ttm.anim_frame("coin")
                surface.blit(frame if frame else tile.image, r)
            elif tt == T_SPIKE:
                frame = ttm.anim_frame("spike")
                surface.blit(frame if frame else tile.image, r)
            elif tt == T_GROUND:
                # Show grass-top only when the tile above is empty
                above = (tile.row > 0 and
                         self.grid[tile.row - 1][tile.col] != T_EMPTY)
                tex = ttm.ground_tex(above)
                surface.blit(tex if tex else tile.image, r)
            elif tt == T_PLATFORM:
                tex = ttm.platform_tex()
                surface.blit(tex if tex else tile.image, r)
            elif tt == T_TORCH:
                frame = ttm.anim_frame("torch")
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
