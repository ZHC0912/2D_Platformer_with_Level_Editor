"""Generate levels/tutorial.json."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)

from level import _generate_tutorial_level, LEVELS_DIR
import os

os.makedirs(LEVELS_DIR, exist_ok=True)
lv   = _generate_tutorial_level()
path = os.path.join(LEVELS_DIR, "tutorial.json")
lv.save_to_file(path)
print(f"Generated {path}")
print(f"  triggers : {len(lv.triggers)}")
print(f"  enemies  : {len(lv.enemy_data)}")
print(f"  pickups  : {len(lv.pickup_data)}")

pygame.quit()
