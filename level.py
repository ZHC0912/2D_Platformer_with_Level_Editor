import json, os, pygame
from settings import *
from tiles import TileMap
from enemies import make_enemy
from weapons import WeaponPickup, SwordSlash, MagicBolt


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
        lv._spawn_enemies()
        lv._spawn_pickups()
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
            if isinstance(proj, MagicBolt) and proj.exploded:
                exp = proj.get_explosion_rect()
                if exp:
                    for enemy in list(self.enemies):
                        if exp.colliderect(enemy.rect):
                            enemy.take_damage(proj.damage)
            else:
                for enemy in list(self.enemies):
                    if proj.rect.colliderect(enemy.rect):
                        enemy.take_damage(proj.damage)
                        if not isinstance(proj, SwordSlash):
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
        self.tilemap.draw(surface, cam_off)
        ox, oy = cam_off
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

    # Enemy rosters per level
    enemy_rosters = [
        # Level 1: two basic orcs
        [("orc", 8, 120), ("orc", 20, 120)],
        # Level 2: orc + archer + orc
        [("orc", 8, 120), ("skeleton_archer", 22, 0), ("orc", 38, 120)],
        # Level 3: orc + archer + rider + skeleton
        [("orc", 8, 120), ("skeleton_archer", 20, 0),
         ("orc_rider", 32, 200), ("skeleton", 44, 100)],
        # Level 4: elite + archer + rider + werebear + skeleton
        [("elite_orc", 6, 100), ("skeleton_archer", 16, 0),
         ("orc_rider", 26, 200), ("werebear", 36, 80), ("skeleton", 48, 120)],
        # Level 5: full roster
        [("elite_orc", 4, 100), ("skeleton_archer", 12, 0),
         ("orc_rider", 22, 200), ("werebear", 32, 80),
         ("greatsword_skeleton", 42, 120), ("greatsword_skeleton_dash", 52, 200)],
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

    lv._spawn_enemies()
    lv._spawn_pickups()
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
    return lv
