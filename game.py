import pygame, os
from settings import *
from player import Player
from level import Level, load_builtin_level
from camera import Camera
from hud import HUD
from save_manager import load_save, write_save, write_user_save, DEFAULT_SAVE
from menus import PauseMenu


# ── Parallax background ───────────────────────────────────────────────────────

class _ParallaxBg:
    """Parallax background supporting 'forest' and 'dungeon' sets."""

    _SKY_COLORS = {
        "forest":  (135, 206, 235),
        "dungeon": (18,  14,  30),
    }

    # (filename, x_factor, y_factor, anchor_bottom)
    _FOREST_CFG = [
        ("Layer_03.png", 0.05, 0.02, False),
        ("Layer_02.png", 0.20, 0.05, True),
        ("Layer_01.png", 0.45, 0.10, True),
    ]
    # dungeon: bg_0 far, bg_1 mid, bg_2 near, fg_0/fg_1 foreground
    _DUNGEON_CFG = [
        ("bg_0.png", 0.02, 0.01, False),
        ("bg_1.png", 0.15, 0.04, False),
        ("bg_2.png", 0.35, 0.08, False),
        ("fg_0.png", 0.60, 0.12, True),
        ("fg_1.png", 0.80, 0.18, True),
    ]

    def __init__(self, bg_set="forest"):
        self._bg_set = bg_set
        self._sky    = self._SKY_COLORS.get(bg_set, self._SKY_COLORS["forest"])
        self._layers = []

        if bg_set == "dungeon":
            bg_dir = os.path.join("assets", "Platform tiles", "Background_dungeon")
            cfg    = self._DUNGEON_CFG
        else:
            bg_dir = os.path.join("assets", "Platform tiles", "Background")
            cfg    = self._FOREST_CFG

        for fname, fx, fy, anchor in cfg:
            path = os.path.join(bg_dir, fname)
            if not os.path.exists(path):
                continue
            img = pygame.image.load(path).convert_alpha()
            scale = SCREEN_H / img.get_height()
            new_w = max(1, int(img.get_width() * scale))
            img   = pygame.transform.scale(img, (new_w, SCREEN_H))
            self._layers.append((img, fx, fy, anchor))

    def draw(self, surface, cam_x, cam_y):
        surface.fill(self._sky)
        for img, fx, fy, anchor in self._layers:
            iw, ih = img.get_width(), img.get_height()
            off_x  = int(cam_x * fx)
            off_y  = int(cam_y * fy)
            y      = (SCREEN_H - ih - off_y) if anchor else -off_y
            x      = -(off_x % iw) - iw
            while x < SCREEN_W:
                surface.blit(img, (x, y))
                x += iw


class Game:
    """Runs one play session (one or more levels)."""

    def __init__(self, screen, level_key=None, username=None, save_data=None):
        self.screen     = screen
        self.clock      = pygame.time.Clock()
        self.username   = username          # None → guest
        self.save_data  = save_data if save_data is not None else dict(DEFAULT_SAVE)
        self.hud        = HUD()
        self._bg        = None   # created per-level in _load_current_level
        self.camera     = Camera()
        self.pause_menu = PauseMenu(screen)

        # resolve starting level
        self._level_keys = self._build_level_sequence()
        if level_key:
            try:
                self._current_idx = self._level_keys.index(level_key)
            except ValueError:
                self._current_idx = 0
        else:
            # find first unbeaten
            reached = self.save_data.get("level_reached", 1)
            self._current_idx = min(reached - 1, len(self._level_keys) - 1)

        self._load_current_level()

    # ── Level management ─────────────────────────────────────────────────────

    def _build_level_sequence(self):
        keys = [f"builtin:{i}" for i in range(5)]
        # append custom levels
        if os.path.isdir(LEVELS_DIR):
            builtin_set = set(BUILTIN_LEVELS)
            custom = sorted(f for f in os.listdir(LEVELS_DIR)
                            if f.endswith(".json") and f not in builtin_set)
            for fname in custom:
                keys.append(f"custom:{fname}")
        return keys

    def _load_current_level(self):
        key = self._level_keys[self._current_idx]
        if key.startswith("builtin:"):
            idx = int(key.split(":")[1])
            self.level = load_builtin_level(idx)
            self._level_number = idx + 1
        else:
            fname = key.split(":", 1)[1]
            path  = os.path.join(LEVELS_DIR, fname)
            self.level = Level.load_from_file(path)
            self._level_number = self._current_idx + 1

        self.player = Player(self.level.spawn_x, self.level.spawn_y, self.save_data)

        # Enforce character lock set by the level designer
        fc = self.level.forced_character
        if fc:
            if fc not in self.player._animators:
                anim = self.player._load_char_anim(fc)
                if anim:
                    self.player._animators[fc] = anim
            self.player.unlocked_weapons = [fc]
            self.player.select_weapon(0)

        self._bg = _ParallaxBg(getattr(self.level, "bg_set", "forest"))
        self.camera.x = max(0, self.level.spawn_x - SCREEN_W // 2)
        self.camera.y = max(0, self.level.spawn_y - SCREEN_H // 2)
        self._level_complete = False
        self._dead = False
        self._respawn_timer = 0

    def _check_unlocks(self):
        """Check milestone unlocks after completing a level."""
        num = self._level_number
        changed = False

        # weapon unlocks
        for wid, req in WEAPON_UNLOCK_LEVEL.items():
            if num >= req and wid not in self.save_data["unlocked_weapons"]:
                self.save_data["unlocked_weapons"].append(wid)
                self.save_data["unlocked_weapons"].sort(
                    key=lambda w: [W_SWORD, W_BOW, W_STAFF].index(w)
                    if w in [W_SWORD, W_BOW, W_STAFF] else 99)
                self.hud.show_message(f"Unlocked: {wid.capitalize()}!")
                changed = True

        # double jump
        if num >= DJUMP_UNLOCK_LEVEL and not self.save_data["double_jump"]:
            self.save_data["double_jump"] = True
            self.hud.show_message("Double Jump Unlocked!")
            changed = True

        # progress
        if num >= self.save_data["level_reached"]:
            self.save_data["level_reached"] = num + 1
            changed = True

        self.save_data["coins_total"] = (self.save_data.get("coins_total", 0)
                                         + self.player.coins)

        if changed:
            self._persist()

    def _persist(self):
        """Write save_data to the appropriate file (skips guest sessions)."""
        if self.username:
            write_user_save(self.username, self.save_data)

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        try:
            return self._run_inner()
        finally:
            self._persist()   # auto-save on any exit (level complete already saved too)

    def _run_inner(self):
        while True:
            result = self._game_loop()
            if result == "quit":
                return "quit"
            if result == "menu":
                return "menu"
            if result == "editor":
                return "editor"
            if result == "next_level":
                if self._current_idx + 1 < len(self._level_keys):
                    self._current_idx += 1
                    self._load_current_level()
                else:
                    # all levels complete
                    self._show_victory()
                    return "menu"
            if result == "restart":
                if self._checkpoint_pos:
                    self._soft_respawn()
                else:
                    self._load_current_level()

    def _soft_respawn(self):
        """Respawn player at the last checkpoint without reloading the level."""
        cx, cy = self._checkpoint_pos
        self.player = Player(cx, cy, self.save_data)
        self._dead = False
        self._respawn_timer = 0
        self._level_complete = False
        self._complete_timer = 0

    def _game_loop(self):
        while True:
            dt_events = pygame.event.get()
            for ev in dt_events:
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        r = self.pause_menu.run()
                        if r == "quit":   return "quit"
                        if r == "menu":   return "menu"
                        if r == "editor": return "editor"

            keys         = pygame.key.get_pressed()
            shoot_pressed = keys[pygame.K_z] or keys[pygame.K_LCTRL] or keys[pygame.K_j]

            if not self._dead:
                self.player.update(self.level.tilemap, keys, dt_events, shoot_pressed)
                self.level.update(self.player)
                self._check_death_or_complete()
            else:
                self._respawn_timer -= 1
                if self._respawn_timer <= 0:
                    return "restart"

            # camera
            map_w = self.level.tilemap.cols * TILE_SIZE
            map_h = self.level.tilemap.rows * TILE_SIZE
            self.camera.update(self.player.rect, map_w, map_h)

            # draw
            self._draw()

            self.clock.tick(FPS)

    def _check_death_or_complete(self):
        p = self.player
        # fell off map
        if p.rect.top > self.level.tilemap.rows * TILE_SIZE:
            p.hp = 0

        if p.hp <= 0 and not self._dead:
            self._dead = True
            self._respawn_timer = 90
            return

        # level complete: reach right edge or a designated trigger
        map_right = self.level.tilemap.cols * TILE_SIZE - TILE_SIZE
        if p.rect.right >= map_right and not self._level_complete:
            self._level_complete = True
            self._check_unlocks()
            self.hud.show_message("Level Complete!")
            pygame.time.set_timer(pygame.USEREVENT + 1, 2000)

        for ev in pygame.event.get(pygame.USEREVENT + 1):
            if self._level_complete:
                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                # return next_level via outer loop
                self._trigger_next = True

        if getattr(self, "_trigger_next", False):
            self._trigger_next = False
            # signal outer loop
            raise _NextLevelSignal()

    def _draw(self):
        cam = self.camera.offset
        self._bg.draw(self.screen, cam[0], cam[1])
        self.level.draw(self.screen, cam)
        self.player.draw(self.screen, cam)

        self.hud.draw(self.screen, self.player, self.level.name,
                      self._level_number, username=self.username)

        if self._dead:
            self._draw_death_screen()

        pygame.display.flip()

    def _draw_death_screen(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        alpha   = min(180, int(180 * (1 - self._respawn_timer / 90)))
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))
        fnt = pygame.font.SysFont("Arial", 48, bold=True)
        t = fnt.render("YOU DIED", True, RED)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 30)))
        s = pygame.font.SysFont("Arial", 22).render("Respawning...", True, LTGRAY)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 20)))

    def _show_victory(self):
        fnt = pygame.font.SysFont("Arial", 52, bold=True)
        clock = pygame.time.Clock()
        start = pygame.time.get_ticks()
        while pygame.time.get_ticks() - start < 4000:
            for ev in pygame.event.get():
                if ev.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return
            self.screen.fill((10, 10, 30))
            t = fnt.render("ALL LEVELS COMPLETE!", True, YELLOW)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
            pygame.display.flip()
            clock.tick(FPS)


class _NextLevelSignal(Exception):
    pass


# patch _check_death_or_complete to not raise; handle cleanly in loop
# (re-implement cleanly without exception trick)
def _patched_game_loop(self):
    while True:
        dt_events = pygame.event.get()
        for ev in dt_events:
            if ev.type == pygame.QUIT:
                return "quit"
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    r = self.pause_menu.run()
                    if r == "quit":   return "quit"
                    if r == "menu":   return "menu"
                    if r == "editor": return "editor"

        keys          = pygame.key.get_pressed()
        shoot_pressed = keys[pygame.K_z] or keys[pygame.K_LCTRL] or keys[pygame.K_j]

        if not self._dead:
            self.player.update(self.level.tilemap, keys, dt_events, shoot_pressed)
            self.level.update(self.player)
            result = self._tick_checks()
            if result:
                return result
        else:
            self._respawn_timer -= 1
            if self._respawn_timer <= 0:
                return "restart"

        map_w = self.level.tilemap.cols * TILE_SIZE
        map_h = self.level.tilemap.rows * TILE_SIZE
        self.camera.update(self.player.rect, map_w, map_h)
        self._draw()
        self.clock.tick(FPS)


def _tick_checks(self):
    p = self.player

    # Tutorial / level tip triggers
    for trig in self.level.triggers:
        if not trig.get("fired") and p.rect.centerx >= trig["x"]:
            self.hud.show_message(trig["message"], 220)
            trig["fired"] = True

    # Checkpoint activation
    if self.level._checkpoint_event:
        self._checkpoint_pos = self.level._checkpoint_event
        self.hud.show_message("Checkpoint!", 120)
        self.level._checkpoint_event = None

    if p.rect.top > self.level.tilemap.rows * TILE_SIZE:
        p.hp = 0
    if p.hp <= 0 and not self._dead:
        self._dead = True
        self._respawn_timer = 90
        return None

    # Level complete: win door (primary) or right-edge fallback
    if not self._level_complete:
        wd = self.level.win_door
        map_right = self.level.tilemap.cols * TILE_SIZE - TILE_SIZE
        if (wd and p.rect.colliderect(wd.rect)) or (not wd and p.rect.right >= map_right):
            self._level_complete = True
            self._check_unlocks()
            self.hud.show_message("Level Complete!")
            self._complete_timer = 120
            if wd:
                wd.trigger_open()

    if self._level_complete:
        self._complete_timer -= 1
        if self._complete_timer <= 0:
            return "next_level"
    return None


# Monkey-patch to avoid nested event polling issues
Game._game_loop  = _patched_game_loop
Game._tick_checks = _tick_checks
# Also add _complete_timer default
_orig_load = Game._load_current_level
def _load_patch(self):
    _orig_load(self)
    self._complete_timer = 0
    self._checkpoint_pos = None
Game._load_current_level = _load_patch
