"""
Generates  assets/sprites/player.png  — a color-coded placeholder sprite sheet.

Each row = one animation state.  Open the PNG in Aseprite / Piskel and draw
your character on top.  The sheet layout matches what animator.py expects:

  Row 0  idle    4 frames   (soft blue)
  Row 1  walk    6 frames   (green)
  Row 2  jump    2 frames   (yellow)
  Row 3  fall    2 frames   (orange)
  Row 4  attack  4 frames   (red / pink)
  Row 5  hurt    2 frames   (magenta)
  Row 6  die     5 frames   (gray)

Frame size: 32 × 48 px  (change FRAME_W / FRAME_H to suit your art).
"""

import pygame, os, sys, math

FRAME_W = 32
FRAME_H = 48

ROWS = [
    ("idle",    4, (80,  120, 220)),
    ("walk",    6, (60,  180, 80)),
    ("jump",    2, (220, 200, 50)),
    ("fall",    2, (220, 130, 50)),
    ("attack",  4, (220, 60,  60)),
    ("hurt",    2, (220, 60,  200)),
    ("die",     5, (120, 120, 120)),
]

SHEET_W = max(count for _, count, _ in ROWS) * FRAME_W
SHEET_H = len(ROWS) * FRAME_H


def _draw_stick_figure(surf, frame_idx, row_idx, color, state):
    """Draw a simple stick-figure character as a pixel-art placeholder."""
    w, h = surf.get_size()
    cx   = w // 2
    dark = tuple(max(0, c - 60) for c in color)
    lite = tuple(min(255, c + 60) for c in color)

    # Body silhouette background
    pygame.draw.rect(surf, (*color, 180), (4, 4, w - 8, h - 8), border_radius=4)

    # Head
    pygame.draw.circle(surf, lite, (cx, 10), 7)
    # Eyes (blink on idle frame 3)
    eye_h = 2 if (state == "idle" and frame_idx == 3) else 3
    pygame.draw.circle(surf, dark, (cx - 3, 9), 1)
    pygame.draw.circle(surf, dark, (cx + 3, 9), 1)

    # Torso
    pygame.draw.rect(surf, color, (cx - 5, 18, 10, 14))

    # Legs — animate based on state/frame
    if state == "walk":
        angles = [0, 20, 35, 20, 0, -20][frame_idx % 6]
        rad    = math.radians(angles)
        lx = cx - 4 + int(math.sin(rad) * 8)
        rx = cx + 4 - int(math.sin(rad) * 8)
        ly = 32 + int(abs(math.cos(rad)) * 6)
        ry = 32 + int(abs(math.cos(-rad)) * 6)
        pygame.draw.line(surf, dark, (cx - 2, 32), (lx, ly + 8), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (rx, ry + 8), 2)
    elif state == "jump":
        # Knees bent up
        pygame.draw.line(surf, dark, (cx - 2, 32), (cx - 6, 28), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (cx + 6, 28), 2)
    elif state == "fall":
        # Legs trailing
        pygame.draw.line(surf, dark, (cx - 2, 32), (cx - 4, 44), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (cx + 4, 44), 2)
    elif state == "attack":
        swing = [0, 15, 30, 10][frame_idx % 4]
        pygame.draw.line(surf, dark, (cx - 2, 32), (cx - 3, 42), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (cx + 3, 42), 2)
        # Sword arm
        rad = math.radians(swing - 15)
        ex  = cx + int(math.cos(rad) * 14)
        ey  = 24 + int(math.sin(rad) * 14)
        pygame.draw.line(surf, (220, 220, 255), (cx + 5, 22), (ex, ey), 2)
    elif state == "die":
        t = frame_idx / 4.0
        lean = int(t * 20)
        pygame.draw.line(surf, dark, (cx - 2, 32), (cx - 3 - lean, 44), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (cx + 4 - lean, 44), 2)
    else:
        pygame.draw.line(surf, dark, (cx - 2, 32), (cx - 3, 44), 2)
        pygame.draw.line(surf, dark, (cx + 2, 32), (cx + 3, 44), 2)

    # Arms
    if state == "attack":
        pass   # drawn above
    elif state == "jump":
        pygame.draw.line(surf, dark, (cx - 5, 20), (cx - 12, 14), 2)
        pygame.draw.line(surf, dark, (cx + 5, 20), (cx + 12, 14), 2)
    else:
        sway = math.sin(frame_idx * 1.1) * 3 if state == "walk" else 0
        pygame.draw.line(surf, dark, (cx - 5, 20), (cx - 10, 28 + int(sway)), 2)
        pygame.draw.line(surf, dark, (cx + 5, 20), (cx + 10, 28 - int(sway)), 2)

    # Frame number (tiny, top-right)
    fnt = pygame.font.SysFont("Arial", 7)
    t   = fnt.render(str(frame_idx), True, (255, 255, 255))
    surf.blit(t, (w - t.get_width() - 1, 1))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    pygame.font.init()

    sheet = pygame.Surface((SHEET_W, SHEET_H), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))

    fnt_label = pygame.font.SysFont("Arial", 9, bold=True)

    for row_idx, (state, count, color) in enumerate(ROWS):
        y = row_idx * FRAME_H
        for col in range(count):
            x   = col * FRAME_W
            frm = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
            frm.fill((0, 0, 0, 0))
            _draw_stick_figure(frm, col, row_idx, color, state)
            sheet.blit(frm, (x, y))

        # Faint grid lines
        for col in range(count + 1):
            pygame.draw.line(sheet, (60, 60, 60, 120),
                             (col * FRAME_W, y), (col * FRAME_W, y + FRAME_H))
        pygame.draw.line(sheet, (60, 60, 60, 120),
                         (0, y), (SHEET_W, y))

        # Row label (overlaid at left)
        lbl = fnt_label.render(state, True, (255, 255, 255))
        sheet.blit(lbl, (2, y + FRAME_H - lbl.get_height() - 1))

    os.makedirs(os.path.join("assets", "sprites"), exist_ok=True)
    out = os.path.join("assets", "sprites", "player.png")
    pygame.image.save(sheet, out)
    print(f"Saved {SHEET_W}x{SHEET_H} sprite sheet -> {out}")
    print()
    print("Sheet layout:")
    for i, (state, count, _) in enumerate(ROWS):
        print(f"  Row {i}  {state:<8}  {count} frames  "
              f"({count * FRAME_W} x {FRAME_H} px)")
    print()
    print("Open assets/sprites/player.png in Aseprite / Piskel,")
    print("draw your character on each frame, then save back to the same path.")
    print("The game will auto-load it next time you run main.py.")
    print(f"Sheet size: {SHEET_W} x {SHEET_H} px")
    pygame.quit()


if __name__ == "__main__":
    main()
