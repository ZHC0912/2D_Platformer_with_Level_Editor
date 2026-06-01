import pygame

# Screen
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TITLE = "2D Platformer"

# Colors
WHITE   = (255, 255, 255)
BLACK   = (0,   0,   0)
RED     = (220, 50,  50)
GREEN   = (50,  200, 50)
BLUE    = (50,  100, 220)
YELLOW  = (255, 220, 0)
ORANGE  = (255, 140, 0)
PURPLE  = (150, 50,  220)
CYAN    = (0,   200, 220)
GRAY    = (120, 120, 120)
DARK    = (30,  30,  30)
BROWN   = (120, 80,  40)
LTGRAY  = (180, 180, 180)
PINK    = (255, 150, 180)
TEAL    = (0,   180, 160)

# Physics
GRAVITY       = 0.6
MAX_FALL      = 18
GROUND_FRIC   = 0.82
AIR_FRIC      = 0.90
PLAYER_SPEED  = 5.0
JUMP_FORCE    = -17.0   # raised: platforms sit 200-280 px above ground
DJUMP_FORCE   = -15.0

# Tiles
TILE_SIZE = 40

# Tile type IDs
T_EMPTY    = 0
T_GROUND   = 1
T_PLATFORM = 2
T_SPIKE    = 3
T_COIN     = 4
T_SPAWN    = 5
T_TORCH    = 6

TILE_NAMES = {
    T_EMPTY:    "Empty",
    T_GROUND:   "Ground",
    T_PLATFORM: "Platform",
    T_SPIKE:    "Spike",
    T_COIN:     "Coin",
    T_SPAWN:    "Spawn",
    T_TORCH:    "Torch",
}

TILE_COLORS = {
    T_EMPTY:    (0, 0, 0, 0),
    T_GROUND:   BROWN,
    T_PLATFORM: (160, 110, 60),
    T_SPIKE:    RED,
    T_COIN:     YELLOW,
    T_SPAWN:    CYAN,
    T_TORCH:    ORANGE,
}

# Enemy type IDs
E_BASIC    = "basic"
E_SHOOTER  = "shooter"
E_DASH     = "dash"

# Weapon IDs
W_SWORD = "sword"
W_BOW   = "bow"
W_STAFF = "staff"

WEAPON_UNLOCK_LEVEL = {
    W_SWORD: 1,
    W_BOW:   2,
    W_STAFF: 3,
}

# ── Character display (weapons map to playable characters) ────────────────────
CHAR_DISPLAY = {W_SWORD: "Knight", W_BOW: "Archer", W_STAFF: "Wizard"}
CHAR_ICON    = {W_SWORD: "1:Kn",   W_BOW: "2:Ar",   W_STAFF: "3:Wz"}

DJUMP_UNLOCK_LEVEL = 2

# HUD
HUD_H = 50

# Camera
CAM_LERP = 0.12

# Save file
SAVE_FILE  = "save.json"
SAVES_DIR  = "saves"
LEVELS_DIR = "levels"

# Built-in levels
BUILTIN_LEVELS = [
    "level1.json",
    "level2.json",
    "level3.json",
    "level4.json",
    "level5.json",
]

# ── Runtime overrides from settings.json (written by the Admin panel) ─────────
import os as _os, json as _json
try:
    _sf = "settings.json"
    if _os.path.exists(_sf):
        _ov = _json.loads(open(_sf).read())
        GRAVITY      = float(_ov.get("GRAVITY",      GRAVITY))
        PLAYER_SPEED = float(_ov.get("PLAYER_SPEED", PLAYER_SPEED))
        JUMP_FORCE   = float(_ov.get("JUMP_FORCE",   JUMP_FORCE))
        DJUMP_FORCE  = float(_ov.get("DJUMP_FORCE",  DJUMP_FORCE))
        MAX_FALL     = float(_ov.get("MAX_FALL",      MAX_FALL))
        GROUND_FRIC  = float(_ov.get("GROUND_FRIC",  GROUND_FRIC))
        AIR_FRIC     = float(_ov.get("AIR_FRIC",      AIR_FRIC))
except Exception:
    pass
