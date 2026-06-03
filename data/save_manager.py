import json, os
from settings import W_SWORD, W_BOW, W_STAFF

SAVES_DIR = "saves"
SAVE_FILE  = "save.json"   # legacy single-file path (kept for compatibility)

DEFAULT_SAVE = {
    "level_reached": 1,
    "coins_total": 0,
    "unlocked_weapons": [W_SWORD],
    "double_jump": False,
    "custom_levels_beaten": [],
}

# ── Legacy single-file API ────────────────────────────────────────────────────

def load_save():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
            for k, v in DEFAULT_SAVE.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    return dict(DEFAULT_SAVE)

def write_save(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def reset_save():
    write_save(dict(DEFAULT_SAVE))
    return dict(DEFAULT_SAVE)

# ── Per-user save API ─────────────────────────────────────────────────────────

def _user_path(username):
    return os.path.join(SAVES_DIR, f"{username}.json")

def load_user_save(username):
    path = _user_path(username)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            for k, v in DEFAULT_SAVE.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    return dict(DEFAULT_SAVE)

def write_user_save(username, data):
    os.makedirs(SAVES_DIR, exist_ok=True)
    with open(_user_path(username), "w") as f:
        json.dump(data, f, indent=2)

def authenticate(username, password):
    """Return save_data if credentials match, else None."""
    path = _user_path(username)
    if not os.path.exists(path):
        return None
    data = load_user_save(username)
    if data.get("_password") == password:
        return data
    return None

def register(username, password):
    """Create a new user and return their save_data, or None if username taken."""
    os.makedirs(SAVES_DIR, exist_ok=True)
    if os.path.exists(_user_path(username)):
        return None
    data = dict(DEFAULT_SAVE)
    data["_password"] = password
    write_user_save(username, data)
    return data

def reset_user_save(username):
    """Reset a user's game progress while keeping their password."""
    data = load_user_save(username)
    pwd  = data.get("_password", "")
    fresh = dict(DEFAULT_SAVE)
    fresh["_password"] = pwd
    write_user_save(username, fresh)
    return fresh
