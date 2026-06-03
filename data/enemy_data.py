import json, os

_FILE = "enemies.json"

DEFAULTS = {
    "goblin": dict(
        label="Goblin",       hp=35,  damage=14, speed=3.5,  display=80),
    "bomber_goblin": dict(
        label="Bomber Goblin",hp=45,  damage=18, speed=2.2,  display=80),
    "skeleton": dict(
        label="Skeleton",     hp=25,  damage=12, speed=3.0,  display=92),
    "slime": dict(
        label="Slime",        hp=25,  damage=10, speed=2.0,  display=72),
    "worm": dict(
        label="Worm",         hp=20,  damage=8,  speed=1.5,  display=48),
    "flying_eye": dict(
        label="Flying Eye",   hp=30,  damage=12, speed=2.5,  display=72,
        sight_range=300, attack_range=200, shoot_cooldown=80),
    "mushroom": dict(
        label="Mushroom",     hp=50,  damage=20, dash_speed=10, display=80,
        detect_radius=200, dash_cooldown=120),
}


def load():
    if os.path.exists(_FILE):
        try:
            with open(_FILE) as f:
                raw = json.load(f)
            merged = {}
            for eid, defs in DEFAULTS.items():
                merged[eid] = dict(defs)
                merged[eid].update(raw.get(eid, {}))
            return merged
        except Exception:
            pass
    return {k: dict(v) for k, v in DEFAULTS.items()}


def save(data):
    with open(_FILE, "w") as f:
        json.dump(data, f, indent=2)


ENEMIES = load()


def get(enemy_id, key, default=None):
    fallback = DEFAULTS.get(enemy_id, {}).get(key, default)
    return ENEMIES.get(enemy_id, {}).get(key, fallback)
