from settings import SCREEN_W, SCREEN_H, CAM_LERP, TILE_SIZE


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, target_rect, map_pixel_w, map_pixel_h):
        target_x = target_rect.centerx - SCREEN_W // 2
        target_y = target_rect.centery - SCREEN_H // 2
        self.x += (target_x - self.x) * CAM_LERP
        self.y += (target_y - self.y) * CAM_LERP
        # clamp
        self.x = max(0, min(self.x, map_pixel_w - SCREEN_W))
        self.y = max(0, min(self.y, map_pixel_h - SCREEN_H))

    @property
    def offset(self):
        return (int(self.x), int(self.y))
