import json, os

_FILE = "characters.json"

# Hardcoded defaults — used when characters.json is absent or a key is missing
DEFAULTS = {
    "sword": {
        "name":           "Knight",
        "sprite_dir":     "assets/sprites/knight",
        "scale":          120,
        "max_hp":         100,
        "shoot_cooldown": 22,
        "attack_damage":  30,
    },
    "bow": {
        "name":           "Archer",
        "sprite_dir":     "assets/sprites/archer",
        "scale":          120,
        "max_hp":         100,
        "shoot_cooldown": 28,
        "attack_damage":  20,
        "arrow_speed":    14,
        "arrow_lifetime": 90,
    },
    "staff": {
        "name":           "Wizard",
        "sprite_dir":     "assets/sprites/wizard",
        "scale":          120,
        "max_hp":         100,
        "shoot_cooldown": 50,
        "attack_damage":  40,
        "blast_duration": 15,
    },
}


def load():
    if os.path.exists(_FILE):
        try:
            with open(_FILE) as f:
                raw = json.load(f)
            merged = {}
            for wid, defs in DEFAULTS.items():
                merged[wid] = dict(defs)
                merged[wid].update(raw.get(wid, {}))
            return merged
        except Exception:
            pass
    return {k: dict(v) for k, v in DEFAULTS.items()}


def save(data):
    with open(_FILE, "w") as f:
        json.dump(data, f, indent=2)


# Loaded once at import; admin panel reloads via load() when saving
CHARS = load()


def get(weapon_id, key, default=None):
    fallback = DEFAULTS.get(weapon_id, {}).get(key, default)
    return CHARS.get(weapon_id, {}).get(key, fallback)
