import pygame


def make_orb(size, core_col, glow_col, symbol, sym_col):
    """
    Procedural glowing orb surface.
    Layers: outer glow rings → dark rim → radial-gradient body →
            specular highlight → centred symbol with drop-shadow.
    """
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    r  = (size - 6) // 2

    # Outer soft glow (4 concentric transparent rings)
    for i in range(4, 0, -1):
        pygame.draw.circle(surf, (*glow_col, 15 * i), (cx, cy), r + i + 2)

    # Dark rim
    pygame.draw.circle(surf, tuple(max(0, v - 40) for v in core_col), (cx, cy), r)

    # Radial gradient body: bright centre fades to core colour at edge
    bright = tuple(min(255, int(c * 0.55 + g * 0.45))
                   for c, g in zip(core_col, glow_col))
    for i in range(r - 1, 0, -1):
        t   = i / (r - 1)
        col = tuple(int(bright[j] * t + core_col[j] * (1 - t)) for j in range(3))
        pygame.draw.circle(surf, col, (cx, cy), i)

    # Specular highlight (top-left quadrant)
    hi_r = max(2, r // 3)
    hi   = pygame.Surface((hi_r * 2, hi_r * 2), pygame.SRCALPHA)
    pygame.draw.circle(hi, (255, 255, 255, 150), (hi_r, hi_r), hi_r)
    surf.blit(hi, (cx - r // 3 - hi_r, cy - r // 3 - hi_r))

    # Symbol with drop-shadow
    fnt = pygame.font.SysFont("Arial", max(10, size // 2 + 2), bold=True)
    t   = fnt.render(symbol, True, sym_col)
    tc  = t.get_rect(center=(cx, cy + 1))
    ts  = fnt.render(symbol, True, (0, 0, 0))
    ts.set_alpha(110)
    surf.blit(ts, tc.move(1, 2))
    surf.blit(t,  tc)
    return surf


# ── Per-hero orb specs (shared between HUD, pickups, level-select) ────────────
HERO_ORB_CFG = {
    "sword": ((150, 45,  35), (225,  95,  55), "K", (255, 205, 185)),
    "bow":   (( 25, 110,  45), ( 70, 205, 100), "A", (185, 255, 200)),
    "staff": (( 50,  40, 155), (105, 115, 230), "W", (185, 190, 255)),
}
LOCKED_ORB_CFG = ((35, 35, 48), (78, 78, 100), "?", (160, 160, 185))
