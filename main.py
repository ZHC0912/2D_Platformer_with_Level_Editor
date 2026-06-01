import sys, os, json, tempfile
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
        from login import LoginScreen
        mode, username, save_data = LoginScreen(screen).run()

        if mode == "quit":
            break

        if mode == "admin":
            from admin import AdminPanel
            if AdminPanel(screen).run() == "quit":
                break
            continue   # back to login

        # mode == "play"  (logged-in user or guest)
        result = _run_session(screen, username, save_data)
        if result == "quit":
            break
        # result == "logout" → loop back to login screen


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
