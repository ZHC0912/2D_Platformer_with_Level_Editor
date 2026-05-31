"""Run once to generate the 5 built-in JSON levels."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()
# Need a display surface for Tile Surface creation
pygame.display.set_mode((1, 1), pygame.NOFRAME)

from level import _generate_default_level, LEVELS_DIR, BUILTIN_LEVELS
import os

os.makedirs(LEVELS_DIR, exist_ok=True)
for i in range(5):
    lv = _generate_default_level(i + 1)
    path = os.path.join(LEVELS_DIR, BUILTIN_LEVELS[i])
    lv.save_to_file(path)
    print(f"Generated {path}")

pygame.quit()
print("Done.")
