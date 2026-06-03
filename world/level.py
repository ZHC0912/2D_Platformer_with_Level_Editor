import json, math, os, pygame
from settings import *
from tiles import TileMap
from enemies import make_enemy
from weapons import WeaponPickup, SwordSlash, MagicBolt
from animator import load_strip

_MISC = os.path.join("assets", "sprites", "miscellaneous sprites")


# ── Checkpoint ────────────────────────────────────────────────────────────────

def _load_strip_scaled(fname, fw, fh, count, target_h):
    """Load a non-square strip and scale to target_h, preserving aspect."""
    path = os.path.join(_MISC, fname)
    scale = target_h / fh
    return load_strip(path, fw, fh, count, scale)


class Checkpoint:
    """Animated save-point crystal; activates on player contact."""
    W, H = 40, 48   # hitbox; sprite is ~29×48

    # Shared frames — loaded once across all Checkpoint instances
    _frames_idle:   list = []
    _frames_active: list = []
    _loaded:        bool = False

    @classmethod
    def _ensure_loaded(cls):
        if cls._loaded:
            return
        cls._loaded = True
        # save_point_anim_strip_9.png : 108×20, each frame 12×20
        cls._frames_idle   = _load_strip_scaled("save_point_anim_strip_9.png",
                                                 12, 20, 9, cls.H)
        # save_point_saving_anim_strip_3.png : 36×20, each frame 12×20
        cls._frames_active = _load_strip_scaled("save_point_saving_anim_strip_3.png",
                                                 12, 20, 3, cls.H)

    def __init__(self, x, y):
        self._ensure_loaded()
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x - self.W // 2, y - self.H, self.W, self.H)
        self.active = False
        self._t = 0

    def update(self):
        self._t += 1

    def draw(self, surface, cam_off):
        ox, oy = cam_off
        sx, sy = int(self.x - ox), int(self.y - oy)
        frames = self._frames_active if self.active else self._frames_idle
        if frames:
            idx = (self._t // 7) % len(frames)
            img = frames[idx]
            surface.blit(img, (sx - img.get_width() // 2, sy - img.get_height()))
            return
        # Procedural fallback
        pygame.draw.line(surface, (140, 120, 70), (sx, sy), (sx, sy - 48), 3)
        col = (255, 200, 0) if self.active else (120, 120, 120)
        wave = int(math.sin(self._t * 0.12) * 5) if self.active else 0
        pts = [(sx+1, sy-48), (sx+22, sy-42+wave//2),
               (sx+22, sy-32+wave), (sx+1, sy-32)]
        pygame.draw.polygon(surface, col, pts)


# ── Win Door ──────────────────────────────────────────────────────────────────

class WinDoor:
    """Animated exit door; touching it completes the level."""
    W, H = 44, 80   # hitbox; door sprite is ~27×80

    # Shared frames — loaded once
    _frames_closed:  list = []
    _frames_opening: list = []
    _loaded:         bool = False

    @classmethod
    def _ensure_loaded(cls):
        if cls._loaded:
            return
        cls._loaded = True
        # strange_door_closed_anim_strip_10.png  : 160×48, each frame 16×48
        cls._frames_closed  = _load_strip_scaled("strange_door_closed_anim_strip_10.png",
                                                  16, 48, 10, cls.H)
        # strange_door_opening_anim_strip_14.png : 224×48, each frame 16×48
        cls._frames_opening = _load_strip_scaled("strange_door_opening_anim_strip_14.png",
                                                  16, 48, 14, cls.H)

    def __init__(self, x, y):
        self._ensure_loaded()
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x - self.W // 2, y - self.H, self.W, self.H)
        self._t = 0
        self._opening = False   # True while playing opening animation

    def update(self):
        self._t += 1

    def trigger_open(self):
        """Call once when level complete to play the opening anim."""
        self._opening = True
        self._t = 0

    def draw(self, surface, cam_off):
        ox, oy = cam_off
        sx, sy = int(self.x - ox), int(self.y - oy)
        frames = self._frames_opening if self._opening else self._frames_closed
        if frames:
            total = len(frames)
            if self._opening:
                idx = min(self._t // 4, total - 1)   # play once, hold last frame
            else:
                idx = (self._t // 8) % total
            img = frames[idx]
            surface.blit(img, (sx - img.get_width() // 2, sy - img.get_height()))
            return
        # Procedural fallback
        t = self._t
        pygame.draw.rect(surface, (55, 35, 95), (sx-22, sy-60, 44, 60), border_radius=10)
        pygame.draw.rect(surface, (140, 80, 220), (sx-22, sy-60, 44, 60), 3, border_radius=10)
        cy = sy - 30
        r = 14 + int(3 * math.sin(t * 0.06))
        a = int(160 + 60 * math.sin(t * 0.04))
        g = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(g, (180, 100, 255, min(255, a)), (40, 40), r + 10)
        pygame.draw.circle(g, (220, 180, 255, 200), (40, 40), r)
        surface.blit(g, (sx - 40, cy - 40))


class Level:
    """Holds all runtime state for one loaded level."""

    def __init__(self):
        self.name = "Untitled"
        self.tilemap = TileMap(60, 30)
        self.enemies = pygame.sprite.Group()
        self.pickups  = pygame.sprite.Group()
        self.all_projectiles = pygame.sprite.Group()
        self.spawn_x = TILE_SIZE * 2
        self.spawn_y = TILE_SIZE * 10
        self.unlock_requirement = 0   # minimum level_reached to access
        self.enemy_data = []          # raw dicts for editor round-trip
        self.pickup_data = []
        self.triggers = []            # [{"x": int, "message": str, "fired": bool}]
        self.forced_character = None  # None = any; "sword"/"bow"/"staff" = lock to one
        self.checkpoint_data = []     # [{"x": int, "y": int}, ...]
        self.checkpoints = []         # Checkpoint instances
        self.win_door_data = None     # {"x": int, "y": int} or None
        self.win_door = None          # WinDoor instance or None
        self._checkpoint_event = None # set to (x,y) when a checkpoint is first activated
        self.bg_set = "forest"        # "forest" or "dungeon"

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "name": self.name,
            "cols": self.tilemap.cols,
            "rows": self.tilemap.rows,
            "grid": self.tilemap.to_list(),
            "spawn": [self.spawn_x, self.spawn_y],
            "enemies": self.enemy_data,
            "pickups": self.pickup_data,
            "unlock_requirement": self.unlock_requirement,
            "triggers": [{"x": t["x"], "message": t["message"]}
                         for t in self.triggers],
            "forced_character": self.forced_character,
            "checkpoints": self.checkpoint_data,
            "win_door": self.win_door_data,
            "bg_set": self.bg_set,
        }

    @classmethod
    def from_dict(cls, data):
        lv = cls()
        lv.name = data.get("name", "Untitled")
        lv.unlock_requirement = data.get("unlock_requirement", 0)
        grid = data.get("grid", [])
        lv.tilemap = TileMap.from_list(grid) if grid else TileMap(60, 30)
        sp = data.get("spawn", [TILE_SIZE * 2, TILE_SIZE * 10])
        lv.spawn_x, lv.spawn_y = sp
        lv.enemy_data  = data.get("enemies", [])
        lv.pickup_data = data.get("pickups", [])
        lv.triggers    = [{"x": t["x"], "message": t["message"], "fired": False}
                          for t in data.get("triggers", [])]
        lv.forced_character = data.get("forced_character", None)
        lv.checkpoint_data = data.get("checkpoints", [])
        lv.win_door_data   = data.get("win_door", None)
        lv.bg_set          = data.get("bg_set", "forest")
        lv._spawn_enemies()
        lv._spawn_pickups()
        lv._spawn_checkpoints()
        lv._spawn_windoor()
        return lv

    def _spawn_enemies(self):
        self.enemies.empty()
        for ed in self.enemy_data:
            e = make_enemy(ed["type"], ed["x"], ed["y"],
                           patrol_range=ed.get("patrol_range", 120),
                           detect_radius=ed.get("detect_radius", 200))
            self.enemies.add(e)

    def _spawn_pickups(self):
        self.pickups.empty()
        for pd in self.pickup_data:
            p = WeaponPickup(pd["weapon"], pd["x"], pd["y"])
            self.pickups.add(p)

    def _spawn_checkpoints(self):
        self.checkpoints = [Checkpoint(cd["x"], cd["y"]) for cd in self.checkpoint_data]

    def _spawn_windoor(self):
        wd = self.win_door_data
        self.win_door = WinDoor(wd["x"], wd["y"]) if wd else None

    # ── File I/O ─────────────────────────────────────────────────────────────

    def save_to_file(self, path):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path):
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, player):
        self._checkpoint_event = None

        # checkpoints
        for cp in self.checkpoints:
            cp.update()
            if not cp.active and player.rect.colliderect(cp.rect):
                cp.active = True
                self._checkpoint_event = (cp.x, cp.y)

        # win door
        if self.win_door:
            self.win_door.update()

        self.pickups.update()
        for enemy in list(self.enemies):
            enemy.update(self.tilemap, player, self.all_projectiles)

        # enemy-player collision (contact damage — skip dying enemies)
        for enemy in self.enemies:
            if not enemy.dead and player.rect.colliderect(enemy.rect):
                player.take_damage(enemy.CONTACT_DAMAGE)

        # enemy bullets hit player
        for proj in list(self.all_projectiles):
            if not proj.from_player and player.rect.colliderect(proj.rect):
                player.take_damage(proj.damage)
                proj.kill()

        # player projectiles hit enemies
        for proj in list(player.projectiles):
            if not proj.from_player:
                continue
            for enemy in list(self.enemies):
                if proj.rect.colliderect(enemy.rect):
                    enemy.take_damage(proj.damage)
                    if not isinstance(proj, (SwordSlash, MagicBolt)):
                        proj.kill()
                    break

        # coins
        player.collect_coins(self.tilemap)

        # weapon pickups
        for pk in list(self.pickups):
            if player.rect.colliderect(pk.rect):
                player.add_weapon(pk.weapon_id)
                pk.kill()

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface, cam_off):
        self.tilemap.draw(surface, cam_off, getattr(self, "bg_set", "forest"))
        ox, oy = cam_off
        for cp in self.checkpoints:
            cp.draw(surface, cam_off)
        if self.win_door:
            self.win_door.draw(surface, cam_off)
        for pk in self.pickups:
            surface.blit(pk.image, (pk.rect.x - ox, pk.rect.y - oy))
        for enemy in self.enemies:
            enemy.draw(surface, cam_off)
        for proj in self.all_projectiles:
            surface.blit(proj.image, (proj.rect.x - ox, proj.rect.y - oy))


# ── Level loader ─────────────────────────────────────────────────────────────

def load_builtin_level(index):
    """Load levels/levelN.json; generate default if missing."""
    path = os.path.join(LEVELS_DIR, BUILTIN_LEVELS[index])
    if os.path.exists(path):
        return Level.load_from_file(path)
    return _generate_default_level(index + 1)


def _generate_default_level(num):
    lv = Level()
    lv.name = f"Level {num}"
    lv.unlock_requirement = num - 1

    cols, rows = 60, 20
    lv.tilemap = TileMap(cols, rows)

    # floor
    for c in range(cols):
        lv.tilemap.set_tile(c, rows-1, T_GROUND)
        lv.tilemap.set_tile(c, rows-2, T_GROUND)

    # Platforms at rows 14-16 (2-4 tiles above floor) — reachable with jump=-17
    # row 16 = 80 px up (easy),  row 15 = 120 px (comfortable),  row 14 = 160 px (max)
    patterns = [
        # Level 1 — gentle, max 3 tiles up
        [(5,16),(12,15),(18,16),(25,15),(32,16),(40,15)],
        # Level 2 — mix of 2-4 tiles
        [(4,16),(10,15),(16,14),(22,15),(28,16),(36,14),(44,15)],
        # Level 3 — more alternation
        [(3,16),(9,15),(15,14),(21,16),(27,14),(33,15),(39,16),(46,14)],
        # Level 4 — challenging sequence
        [(4,16),(8,15),(14,14),(20,15),(26,14),(32,16),(38,14),(44,15)],
        # Level 5 — hardest pattern
        [(2,16),(7,14),(12,16),(17,14),(22,16),(27,14),(32,15),(37,14),(44,16)],
    ]
    idx = min(num-1, len(patterns)-1)
    for c, r in patterns[idx]:
        for dc in range(5):
            lv.tilemap.set_tile(c+dc, r, T_PLATFORM)
        lv.tilemap.set_tile(c+2, r-1, T_COIN)   # coin on mid of each platform

    # Coins along the floor
    for c in range(3, cols-3, 4):
        lv.tilemap.set_tile(c, rows-3, T_COIN)

    # Spikes (further from spawn in later levels)
    spike_start = 12 + num * 2
    for c in range(spike_start, spike_start + 4 + num):
        lv.tilemap.set_tile(c, rows-3, T_SPIKE)

    # Spawn
    lv.tilemap.set_tile(1, rows-3, T_SPAWN)
    lv.spawn_x = 1 * TILE_SIZE + 4
    lv.spawn_y = (rows-3) * TILE_SIZE - 44

    # Enemy rosters per level (only types with sprite assets)
    enemy_rosters = [
        # Level 1: two goblins
        [("goblin", 8, 120), ("goblin", 20, 120)],
        # Level 2: goblin + flying_eye + goblin
        [("goblin", 8, 120), ("flying_eye", 22, 0), ("goblin", 38, 120)],
        # Level 3: goblin + flying_eye + mushroom + skeleton
        [("goblin", 8, 120), ("flying_eye", 20, 0),
         ("mushroom", 32, 200), ("skeleton", 44, 100)],
        # Level 4: bomber_goblin + flying_eye + mushroom + slime + skeleton
        [("bomber_goblin", 6, 100), ("flying_eye", 16, 0),
         ("mushroom", 26, 200), ("slime", 36, 80), ("skeleton", 48, 120)],
        # Level 5: full sprited roster
        [("bomber_goblin", 4, 100), ("flying_eye", 12, 0),
         ("mushroom", 22, 200), ("slime", 32, 80),
         ("worm", 42, 120), ("mushroom", 52, 200)],
    ]
    roster = enemy_rosters[idx]
    lv.enemy_data = []
    for etype, col, param in roster:
        ex = col * TILE_SIZE
        ey = (rows - 2) * TILE_SIZE
        lv.enemy_data.append({"type": etype, "x": ex, "y": ey,
                               "patrol_range": param, "detect_radius": param or 200})

    # Character pickups (unlock new playable character per milestone level)
    lv.pickup_data = []
    if num == 1:
        lv.pickup_data.append({"weapon": W_SWORD, "x": 5*TILE_SIZE,  "y": (rows-3)*TILE_SIZE})
    elif num == 2:
        lv.pickup_data.append({"weapon": W_BOW,   "x": 10*TILE_SIZE, "y": (rows-3)*TILE_SIZE})
    elif num == 3:
        lv.pickup_data.append({"weapon": W_STAFF, "x": 15*TILE_SIZE, "y": (rows-3)*TILE_SIZE})

    # Checkpoint at roughly 1/3 of the map (after first obstacle cluster)
    cp_col = 22
    lv.checkpoint_data = [{"x": cp_col * TILE_SIZE + TILE_SIZE // 2,
                            "y": (rows - 2) * TILE_SIZE}]

    # Win door near right end
    wd_col = cols - 4
    lv.win_door_data = {"x": wd_col * TILE_SIZE + TILE_SIZE // 2,
                        "y": (rows - 2) * TILE_SIZE}

    lv._spawn_enemies()
    lv._spawn_pickups()
    lv._spawn_checkpoints()
    lv._spawn_windoor()
    return lv


def _generate_tutorial_level():
    lv = Level()
    lv.name = "Tutorial"
    lv.unlock_requirement = 0

    cols, rows = 60, 20
    lv.tilemap = TileMap(cols, rows)

    # ── Floor with a 2-tile gap at cols 10-11 ────────────────────────────────
    gap = {10, 11}
    for c in range(cols):
        if c in gap:
            # Leave floor empty — player must jump
            pass
        else:
            lv.tilemap.set_tile(c, rows - 1, T_GROUND)
            lv.tilemap.set_tile(c, rows - 2, T_GROUND)

    # Safety platform above the gap (visible hint to jump, plus landing net)
    for c in range(9, 13):
        lv.tilemap.set_tile(c, rows - 5, T_PLATFORM)
    lv.tilemap.set_tile(11, rows - 6, T_COIN)   # lure coin above platform

    # ── Spawn ─────────────────────────────────────────────────────────────────
    lv.tilemap.set_tile(1, rows - 3, T_SPAWN)
    lv.spawn_x = TILE_SIZE + 4
    lv.spawn_y = (rows - 3) * TILE_SIZE - 44

    # ── Section 1 – movement warmup: walk & collect ───────────────────────────
    for c in (3, 6):
        lv.tilemap.set_tile(c, rows - 3, T_COIN)

    # ── Section 2 – gap & jump (handled by floor cutout above) ───────────────

    # ── Section 3 – pass-through platforms (cols 16-27) ──────────────────────
    # Low platform
    for c in range(17, 22):
        lv.tilemap.set_tile(c, rows - 4, T_PLATFORM)
    lv.tilemap.set_tile(19, rows - 5, T_COIN)
    # High platform
    for c in range(21, 26):
        lv.tilemap.set_tile(c, rows - 7, T_PLATFORM)
    lv.tilemap.set_tile(23, rows - 8, T_COIN)   # coin on top of high platform

    # ── Section 4 – spike gauntlet (cols 29-33) ──────────────────────────────
    for c in range(29, 34):
        lv.tilemap.set_tile(c, rows - 3, T_SPIKE)
    # Small platform to escape if player lands badly (to the right of spikes)
    for c in range(34, 37):
        lv.tilemap.set_tile(c, rows - 5, T_PLATFORM)

    # ── Section 5 – coin row + sword pickup ──────────────────────────────────
    for c in range(37, 42):
        lv.tilemap.set_tile(c, rows - 3, T_COIN)
    lv.pickup_data = [
        {"weapon": W_SWORD, "x": 43 * TILE_SIZE + 20, "y": (rows - 3) * TILE_SIZE}
    ]

    # ── Section 6 – enemy practice (cols 46-53) ──────────────────────────────
    lv.enemy_data = [
        {"type": E_BASIC, "x": 50 * TILE_SIZE, "y": (rows - 2) * TILE_SIZE,
         "patrol_range": 100, "detect_radius": 200}
    ]

    # ── Section 7 – finish line arrow of coins ────────────────────────────────
    for c in range(54, 59):
        lv.tilemap.set_tile(c, rows - 3, T_COIN)
    lv.tilemap.set_tile(57, rows - 4, T_COIN)
    lv.tilemap.set_tile(58, rows - 5, T_COIN)   # coins angle upward → right

    # ── Checkpoint (mid-tutorial) ─────────────────────────────────────────────
    lv.checkpoint_data = [{"x": 37 * TILE_SIZE + TILE_SIZE // 2,
                            "y": (rows - 2) * TILE_SIZE}]

    # ── Win door at the end ───────────────────────────────────────────────────
    lv.win_door_data = {"x": 57 * TILE_SIZE + TILE_SIZE // 2,
                        "y": (rows - 2) * TILE_SIZE}

    # ── Tutorial tip triggers ─────────────────────────────────────────────────
    lv.triggers = [
        {"x":   80, "message": "Move with  WASD  or  Arrow Keys"},
        {"x":  320, "message": "JUMP!  Space / W / Up  — clear the gap ahead!"},
        {"x":  600, "message": "Pass-through Platforms — jump UP through them!"},
        {"x":  900, "message": "SPIKES ahead!  Jump OVER — they kill instantly!"},
        {"x": 1300, "message": "Pick up the SWORD!  Press  Z / Ctrl  to swing it"},
        {"x": 1700, "message": "A guard patrols ahead — attack it to practice!"},
        {"x": 2080, "message": "Almost there!  Reach the RIGHT EDGE to finish!"},
    ]

    lv._spawn_enemies()
    lv._spawn_pickups()
    lv._spawn_checkpoints()
    lv._spawn_windoor()
    return lv
