import pygame, json, os, tempfile
from settings import *

_EDITOR_SAVE = {
    "level_reached": 99, "coins_total": 0,
    "unlocked_weapons": [W_SWORD, W_BOW, W_STAFF],
    "double_jump": True, "custom_levels_beaten": [],
}


def _builtin_metas():
    entries = [("Tutorial", "tutorial.json")] + \
              [(f"Level {i+1}", f"level{i+1}.json") for i in range(5)]
    result = []
    for display, fname in entries:
        path = os.path.join(LEVELS_DIR, fname)
        m = {"display": display, "fname": fname,
             "path": path, "exists": os.path.exists(path)}
        if m["exists"]:
            try:
                d = json.loads(open(path).read())
                m.update({
                    "enemies":     len(d.get("enemies", [])),
                    "checkpoints": len(d.get("checkpoints", [])),
                    "win_door":    d.get("win_door") is not None,
                    "cols":        d.get("cols", 60),
                    "triggers":    len(d.get("triggers", [])),
                })
            except Exception:
                pass
        result.append(m)
    return result


def _custom_fnames():
    if not os.path.isdir(LEVELS_DIR):
        return []
    builtin = {f"level{i+1}.json" for i in range(5)} | {"tutorial.json"}
    return sorted(f for f in os.listdir(LEVELS_DIR)
                  if f.endswith(".json") and f not in builtin)


class LevelsMixin:
    def _draw_levels_tab(self, mpos):
        y = 112

        for cx_pos, hd in [(28,"Level"),(200,"Cols"),(280,"Enemies"),
                           (370,"Checkpts"),(460,"Win Door"),(560,"Triggers"),
                           (SCREEN_W - 140,"")]:
            self.screen.blit(self.fnt_sm.render(hd, True, GRAY), (cx_pos, y))
        pygame.draw.line(self.screen, (50, 55, 80), (20, y + 18), (SCREEN_W - 20, y + 18))
        y += 26

        edit_rects = {}
        ROW_H = 32

        self.screen.blit(self.fnt_hd.render("Built-in Levels", True, CYAN), (28, y))
        y += 24
        for m in self._level_metas:
            pygame.draw.rect(self.screen, (28, 38, 60),
                             pygame.Rect(20, y, SCREEN_W - 150, ROW_H - 2), border_radius=3)
            nc = WHITE if m["exists"] else GRAY
            self.screen.blit(self.fnt.render(m["display"], True, nc), (30, y + 7))
            if m["exists"]:
                for cx_pos, text, col in [
                    (200, str(m.get("cols", "?")),        LTGRAY),
                    (280, str(m.get("enemies", "?")),     ORANGE),
                    (370, str(m.get("checkpoints","?")),  YELLOW),
                    (460, "Yes" if m.get("win_door") else "No",
                          GREEN if m.get("win_door") else RED),
                    (560, str(m.get("triggers", 0)),      LTGRAY),
                ]:
                    self.screen.blit(self.fnt.render(text, True, col), (cx_pos, y + 7))
                er = pygame.Rect(SCREEN_W - 138, y + 4, 76, 24)
                self._draw_btn(er, "Edit", (40, 80, 160), mpos)
                edit_rects[m["fname"]] = er
            else:
                self.screen.blit(self.fnt_sm.render("(missing — click Regenerate)", True, RED),
                                 (200, y + 9))
            y += ROW_H

        y += 10
        self.screen.blit(
            self.fnt_hd.render(f"Custom Levels  ({len(self._custom_lvls)})", True, CYAN), (28, y))
        y += 24
        for fname in self._custom_lvls[:5]:
            pygame.draw.rect(self.screen, (22, 32, 50),
                             pygame.Rect(20, y, SCREEN_W - 150, ROW_H - 2), border_radius=3)
            self.screen.blit(self.fnt.render(fname[:-5], True, LTGRAY), (30, y + 7))
            er = pygame.Rect(SCREEN_W - 138, y + 4, 76, 24)
            self._draw_btn(er, "Edit", (40, 80, 160), mpos)
            edit_rects[fname] = er
            y += ROW_H
        if len(self._custom_lvls) > 5:
            self.screen.blit(
                self.fnt_sm.render(f"…and {len(self._custom_lvls)-5} more", True, GRAY), (30, y))

        regen_r = pygame.Rect(28, SCREEN_H - 165, 280, 34)
        self._draw_btn(regen_r, "Regenerate All Built-in Levels", (105, 58, 18), mpos)
        return edit_rects, regen_r

    def _launch_editor(self, path=None):
        from editor import LevelEditor
        from level import Level
        from game import Game

        lv = Level.load_from_file(path) if (path and os.path.exists(path)) else None

        while True:
            ed     = LevelEditor(self.screen, level=lv)
            result = ed.run()
            lv     = ed.get_level()

            if result == "play":
                if path:
                    lv.save_to_file(path)
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".json",
                            delete=False, dir=LEVELS_DIR) as f:
                        json.dump(lv.to_dict(), f)
                        tmp_path = f.name
                    fname = os.path.basename(tmp_path)
                    Game(self.screen, level_key=f"custom:{fname}",
                         username=None, save_data=dict(_EDITOR_SAVE)).run()
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
                continue

            break

        self._refresh_data()

    def _regen_builtin(self):
        from level import _generate_default_level, _generate_tutorial_level
        os.makedirs(LEVELS_DIR, exist_ok=True)
        _generate_tutorial_level().save_to_file(
            os.path.join(LEVELS_DIR, "tutorial.json"))
        for i in range(5):
            _generate_default_level(i + 1).save_to_file(
                os.path.join(LEVELS_DIR, BUILTIN_LEVELS[i]))
        self._refresh_data()
        self._status    = "All 6 built-in levels regenerated."
        self._status_ok = True
