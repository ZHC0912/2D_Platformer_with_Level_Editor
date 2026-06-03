import pygame, os


def load_strip(path, frame_w, frame_h, count, scale=1.0):
    """
    Load `count` horizontal frames from a PNG strip file.
    Returns a list of Surfaces, or [] if the file is missing / unreadable.
    """
    if not os.path.exists(path):
        return []
    try:
        raw = pygame.image.load(path).convert_alpha()
        if scale != 1.0:
            nw = int(raw.get_width()  * scale)
            nh = int(raw.get_height() * scale)
            raw = pygame.transform.scale(raw, (nw, nh))
        fw = int(frame_w * scale)
        fh = int(frame_h * scale)
        frames = []
        for i in range(count):
            surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
            surf.blit(raw, (0, 0), pygame.Rect(i * fw, 0, fw, fh))
            frames.append(surf)
        return frames
    except Exception as e:
        print(f"[load_strip] {path}: {e}")
        return []


def compute_y_crop_auto(paths, alpha_threshold=80, margin_top=10, margin_bottom=0):
    """
    Compute a union vertical bounding box from a list of sprite strip paths where
    each strip has square frames (frame_h == image height, auto-detected).
    All paths must share the same frame height; strips with a different height
    are skipped.  Returns (y1, y2) or None.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    ref_h  = None
    strips = []
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        try:
            raw = pygame.image.load(path).convert_alpha()
            fh  = raw.get_height()
            if fh == 0:
                continue
            if ref_h is None:
                ref_h = fh
            if fh != ref_h:
                continue
            strips.append((raw, fh, raw.get_width() // fh))
        except Exception:
            continue

    if not strips:
        return None

    row_any = np.zeros(ref_h, dtype=bool)
    for raw, fh, count in strips:
        for i in range(count):
            sf = pygame.Surface((fh, fh), pygame.SRCALPHA)
            sf.blit(raw, (0, 0), pygame.Rect(i * fh, 0, fh, fh))
            a  = pygame.surfarray.pixels_alpha(sf)
            row_any |= (a.max(axis=0) >= alpha_threshold)
            del a

    rows = np.where(row_any)[0]
    if len(rows) == 0:
        return None
    y1 = max(0,      int(rows.min()) - margin_top)
    y2 = min(ref_h,  int(rows.max()) + margin_bottom + 1)
    return (y1, y2)


def load_strip_auto(path, target_h, **kwargs):
    """
    Load a horizontal strip PNG with auto-detected frame count.
    Assumes square frames (frame_w == frame_h == image height).
    Passes through to load_strip_cropped for auto-crop and scaling.
    Accepts y_crop=(y1,y2) kwarg to use a pre-computed vertical crop region.
    """
    if not os.path.exists(path):
        return []
    try:
        raw = pygame.image.load(path)
        fh  = raw.get_height()
        if fh == 0:
            return []
        count = raw.get_width() // fh
        # crop_sides kwarg: translate to crop_horizontal for load_strip_cropped
        crop_sides = kwargs.pop("crop_sides", True)
        if not crop_sides:
            kwargs["crop_horizontal"] = False
        return load_strip_cropped(path, fh, fh, count, target_h, **kwargs)
    except Exception as e:
        print(f"[load_strip_auto] {path}: {e}")
        return []


def compute_y_crop(paths_counts, frame_w, frame_h,
                   alpha_threshold=80, margin_top=10, margin_bottom=0):
    """
    Compute a union vertical bounding box across multiple sprite strips so that
    all animations for the same character use an identical crop region, keeping
    the character at a consistent size regardless of how much each attack/idle
    frame extends vertically.

    paths_counts: iterable of (path, frame_count) pairs.
    Returns (y1, y2) or None if numpy is unavailable / all strips are missing.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    row_any = np.zeros(frame_h, dtype=bool)
    found_any = False
    for path, count in paths_counts:
        if not os.path.exists(path):
            continue
        try:
            raw = pygame.image.load(path).convert_alpha()
            for i in range(count):
                sf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                sf.blit(raw, (0, 0), pygame.Rect(i * frame_w, 0, frame_w, frame_h))
                a = pygame.surfarray.pixels_alpha(sf)
                row_any |= (a.max(axis=0) >= alpha_threshold)
                del a
                found_any = True
        except Exception:
            continue
    if not found_any:
        return None
    rows = np.where(row_any)[0]
    if len(rows) == 0:
        return None
    y1 = max(0,        int(rows.min()) - margin_top)
    y2 = min(frame_h,  int(rows.max()) + margin_bottom + 1)
    return (y1, y2)


def load_strip_cropped(path, frame_w, frame_h, count, target_h,
                       alpha_threshold=80, margin_top=10,
                       margin_side=8,  margin_bottom=0,
                       crop_horizontal=True, y_crop=None):
    """
    Load a horizontal strip, auto-crop transparent padding by computing the
    UNION bounding box of non-transparent pixels across ALL frames, then
    scale the cropped region to target_h.

    This fixes the "tiny / floating" problem caused by oversized sprite
    sheet frames with large transparent borders (e.g. 100×100 frames where
    the actual character is only 20–26 px tall in the centre).

    margin_bottom=0  → sprite bottom == character feet → aligns perfectly
                       to rect.bottom without any extra offset.
    """
    if not os.path.exists(path):
        return []
    try:
        import numpy as np
    except ImportError:
        # numpy not available — fall back to simple scaled strip
        return load_strip(path, frame_w, frame_h, count, scale=target_h / frame_h)
    try:
        raw = pygame.image.load(path).convert_alpha()

        # Extract native-resolution frames
        frames_raw = []
        for i in range(count):
            sf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            sf.blit(raw, (0, 0), pygame.Rect(i * frame_w, 0, frame_w, frame_h))
            frames_raw.append(sf)

        # Union bounding box across all frames
        # surfarray.pixels_alpha → shape (frame_w, frame_h), column-major
        row_any = np.zeros(frame_h, dtype=bool)   # y-rows that have any content
        col_any = np.zeros(frame_w, dtype=bool)   # x-cols that have any content
        for sf in frames_raw:
            a = pygame.surfarray.pixels_alpha(sf)  # (W, H)
            row_any |= (a.max(axis=0) >= alpha_threshold)   # max over x per row y
            col_any |= (a.max(axis=1) >= alpha_threshold)   # max over y per col x
            del a

        rows = np.where(row_any)[0]
        cols = np.where(col_any)[0]
        if len(rows) == 0 or len(cols) == 0:
            return [pygame.transform.scale(f, (target_h, target_h)) for f in frames_raw]

        # Vertical crop — use caller-supplied region if provided so all
        # animations for one character share the same crop and scale identically.
        if y_crop is not None:
            y1, y2 = y_crop
        else:
            y1 = max(0,        int(rows.min()) - margin_top)
            y2 = min(frame_h,  int(rows.max()) + margin_bottom + 1)

        # Horizontal crop — ONLY when crop_horizontal=True.
        # For platformer character sprites disable this: each frame has the
        # character at a slightly different x position (31-48 px jitter across
        # walk/idle cycles). Cropping to a shared union bbox makes the character
        # visibly bounce left-right every frame.  Keeping the full frame width
        # locks the character to the same x reference in every frame.
        if crop_horizontal and len(cols) > 0:
            x1 = max(0,       int(cols.min()) - margin_side)
            x2 = min(frame_w, int(cols.max()) + margin_side + 1)
        else:
            x1, x2 = 0, frame_w

        crop_h, crop_w = y2 - y1, x2 - x1
        if crop_h <= 0 or crop_w <= 0:
            return [pygame.transform.scale(f, (target_h, target_h)) for f in frames_raw]

        out_w = max(1, int(crop_w * target_h / crop_h))

        result = []
        for sf in frames_raw:
            crop = pygame.Surface((crop_w, crop_h), pygame.SRCALPHA)
            crop.blit(sf, (0, 0), pygame.Rect(x1, y1, crop_w, crop_h))
            result.append(pygame.transform.scale(crop, (out_w, target_h)))
        return result

    except Exception as e:
        print(f"[load_strip_cropped] {path}: {e}")
        return load_strip(path, frame_w, frame_h, count, scale=target_h / frame_h)


class SpriteSheet:
    """
    Slice animation frames from a PNG sprite sheet.

    Layout expected:
        Row 0 : idle   (4 frames)
        Row 1 : walk   (6 frames)
        Row 2 : jump   (2 frames)
        Row 3 : fall   (2 frames)
        Row 4 : attack (4 frames)
        Row 5 : hurt   (2 frames)
        Row 6 : die    (5 frames)

    All frames must be the same size (frame_w × frame_h).
    """

    def __init__(self, path, frame_w, frame_h, scale=1.0):
        raw = pygame.image.load(path).convert_alpha()
        if scale != 1.0:
            w = int(raw.get_width()  * scale)
            h = int(raw.get_height() * scale)
            raw = pygame.transform.scale(raw, (w, h))
        self._sheet = raw
        self.fw = int(frame_w * scale)
        self.fh = int(frame_h * scale)

    def get_row(self, row, count):
        """Return list of `count` frames from horizontal row `row`."""
        frames = []
        for col in range(count):
            src  = pygame.Rect(col * self.fw, row * self.fh, self.fw, self.fh)
            surf = pygame.Surface((self.fw, self.fh), pygame.SRCALPHA)
            surf.blit(self._sheet, (0, 0), src)
            frames.append(surf)
        return frames


class Animator:
    """
    Lightweight state-machine animator.

    Example
    -------
        anim = Animator()
        anim.add_state("idle",   idle_frames,   duration=10)
        anim.add_state("walk",   walk_frames,   duration=6)
        anim.add_state("jump",   jump_frames,   duration=8,  loop=False)
        anim.add_state("attack", atk_frames,    duration=5,  loop=False)

        # every game frame:
        anim.set_state("walk")   # ignored if already walking
        anim.update()
        screen.blit(anim.image, pos)
    """

    def __init__(self):
        self._states   = {}    # name -> {frames, dur, loop}
        self._state    = None
        self._idx      = 0
        self._timer    = 0
        self.finished  = False  # True after a one-shot animation ends
        self._flipped  = False

    # ── Building states ───────────────────────────────────────────────────────

    def add_state(self, name, frames, duration=6, loop=True):
        if not frames:
            return          # silently skip states with no frames
        self._states[name] = {"frames": frames, "dur": duration, "loop": loop}
        if self._state is None:
            self._state = name

    # ── Control ───────────────────────────────────────────────────────────────

    def set_state(self, name, force=False):
        """Switch to state `name`. No-op if already in that state (unless force=True)."""
        if name not in self._states:
            return
        if self._state == name and not force:
            return
        # Don't interrupt a one-shot animation that hasn't finished
        if (self._state and not force
                and not self._states[self._state]["loop"]
                and not self.finished):
            return
        self._state   = name
        self._idx     = 0
        self._timer   = 0
        self.finished = False

    def set_flip(self, flipped: bool):
        """Mirror the sprite horizontally (for left-facing direction)."""
        self._flipped = flipped

    # ── Tick ─────────────────────────────────────────────────────────────────

    def update(self):
        if not self._state or self._state not in self._states:
            return
        s = self._states[self._state]
        self._timer += 1
        if self._timer >= s["dur"]:
            self._timer = 0
            self._idx  += 1
            if self._idx >= len(s["frames"]):
                if s["loop"]:
                    self._idx = 0
                else:
                    self._idx     = len(s["frames"]) - 1
                    self.finished = True

    # ── Current image ─────────────────────────────────────────────────────────

    @property
    def image(self):
        if not self._state or self._state not in self._states:
            return pygame.Surface((32, 48), pygame.SRCALPHA)
        frame = self._states[self._state]["frames"][self._idx]
        return pygame.transform.flip(frame, True, False) if self._flipped else frame
