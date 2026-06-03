import sys, os, json, tempfile

# ── Package path setup ────────────────────────────────────────────────────────
# Add every sub-package directory to sys.path so all flat imports
# (e.g. "from settings import *", "from player import Player") continue to
# work unchanged across the whole codebase.
_root = os.path.dirname(os.path.abspath(__file__))
for _pkg in ("core", "entities", "world", "data", "ui", "systems", "admin"):
    _p = os.path.join(_root, _pkg)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
del _root, _pkg, _p
# ─────────────────────────────────────────────────────────────────────────────

os.environ.setdefault("SDL_VIDEODRIVER", "")

import pygame
from settings import SCREEN_W, SCREEN_H, FPS, TITLE, LEVELS_DIR, W_SWORD, W_BOW, W_STAFF

# All skills + weapons unlocked for editor play-testing.
# Never persisted to disk (username=None is passed for play-test runs).
_EDITOR_SAVE = {
    "level_reached": 99,
    "coins_total": 0,
    "unlocked_weapons": [W_SWORD, W_BOW, W_STAFF],
    "double_jump": True,
    "custom_levels_beaten": [],
}


def main():
    pygame.init()
    pygame.mixer.quit()   # avoid audio errors if no audio device
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(TITLE)

    os.makedirs(LEVELS_DIR, exist_ok=True)
    os.makedirs("saves",    exist_ok=True)

    while True:
        # ── Welcome screen ─────────────────────────────────────────────────────
        from login import WelcomeScreen
        welcome_result = WelcomeScreen(screen).run()

        if welcome_result == "quit":
            break

        if welcome_result == "guest":
            result = _run_session(screen, None, None)
            if result == "quit":
                break
            continue   # back to welcome

        # welcome_result == "login"  →  enter the login/register sub-loop
        while True:
            from login import LoginScreen
            login_result = LoginScreen(screen).run()

            if login_result == "quit":
                return  # bubble up to outer loop exit

            if login_result == "back":
                break   # back to welcome screen

            if login_result == "register":
                from login import RegisterScreen
                reg_result = RegisterScreen(screen).run()
                if reg_result == "quit":
                    return
                if reg_result == "back":
                    continue   # back to login
                # reg_result is ("play", username, save_data)
                mode, username, save_data = reg_result
                result = _run_session(screen, username, save_data)
                if result == "quit":
                    return
                break   # back to welcome after session

            # login_result is ("play"|"admin", username, save_data)
            mode, username, save_data = login_result
            if mode == "admin":
                from admin import AdminPanel
                if AdminPanel(screen).run() == "quit":
                    return
                break   # back to welcome after admin
            else:
                result = _run_session(screen, username, save_data)
                if result == "quit":
                    return
                break   # back to welcome after session


def _run_session(screen, username, save_data):
    """
    Full game session for one user (or guest).
    Returns "quit" or "logout".
    """
    state        = "main"
    editor_level = None

    while True:
        if state == "main":
            from menus import MainMenu
            state = MainMenu(screen, save_data=save_data, username=username).run()

        elif state == "play":
            from game import Game
            g       = Game(screen, username=username, save_data=save_data)
            result  = g.run()
            save_data = g.save_data   # pick up any progress updates
            state   = result if result else "main"

        elif state == "level_select":
            from menus import LevelSelectMenu
            result, key = LevelSelectMenu(screen, save_data=save_data).run()
            if result == "select":
                from game import Game
                g      = Game(screen, level_key=key,
                              username=username, save_data=save_data)
                r2     = g.run()
                save_data = g.save_data
                state  = r2 if r2 else "main"
            else:
                state = result if result else "main"

        elif state == "editor":
            from editor import LevelEditor
            ed     = LevelEditor(screen, editor_level)
            result = ed.run()
            editor_level = ed.get_level()

            if result == "play":
                # play-test the editor level in a throw-away session.
                # Always use _EDITOR_SAVE so all weapons and double jump are
                # available regardless of the user's actual progress.
                # username=None prevents any disk write.
                with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json",
                        delete=False, dir=LEVELS_DIR) as f:
                    json.dump(editor_level.to_dict(), f)
                    tmp_path = f.name
                fname = os.path.basename(tmp_path)
                from game import Game
                g  = Game(screen, level_key=f"custom:{fname}",
                          username=None, save_data=dict(_EDITOR_SAVE))
                g.run()
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                state = "editor"

            elif result == "quit":
                return "quit"
            else:
                state = "main"

        elif state == "logout":
            return "logout"

        elif state == "quit":
            return "quit"

        else:
            state = "main"


if __name__ == "__main__":
    main()
    pygame.quit()
    sys.exit(0)
