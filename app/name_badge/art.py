# art.py — neon-arcade pixel-art engine for the Fri3d name-badge app.
#
# A tiny RGB565 framebuffer ("FB") with drawing primitives (pixel/rect/line/circle/
# triangle/arc), a 5x7 bitmap font for neon text, and the 9 hobby icons drawn
# procedurally. Everything is rendered into bytearrays and wrapped in lv.image_dsc_t
# so lvgl blits them (cheap to animate: just move/swap image widgets).
#
# MicroPython 1.23 + lvgl v9. Verified API (on-device probe):
#   lv.image_dsc_t({"header":{"cf":lv.COLOR_FORMAT.RGB565,"w":w,"h":h},
#                   "data_size":len,"data":buf})
#   img=lv.image(scr); img.set_src(dsc); img.set_pos(x,y); img.set_scale(256==1x)

import math
import lvgl as lv

# --------------------------------------------------------------------------
# Palette (RGB888 -> we convert to RGB565)
# --------------------------------------------------------------------------
BLACK = 0x000000
WHITE = 0xFFFFFF
CYAN = 0x00FFFF
MAGENTA = 0xFF00FF
GREEN = 0x39FF14
YELLOW = 0xFFE700
ORANGE = 0xFF8800
RED = 0xFF2A2A
BLUE = 0x18BCF2      # Home Assistant blue
AMBER = 0xFFB300
GOLD = 0xFFD000
SILVER = 0xC8C8D0
GREY = 0x707080
DGREY = 0x2A2A36
PURPLE = 0xB026FF
BROWN = 0x9A6A33


def _px565(rgb):
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


class FB:
    """RGB565 framebuffer."""
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 2)

    def _set(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 2
            self.buf[i] = v >> 8
            self.buf[i + 1] = v & 0xFF

    def px(self, x, y, rgb):
        self._set(x, y, _px565(rgb))

    def clear(self, rgb=BLACK):
        v = _px565(rgb)
        b1 = v >> 8
        b2 = v & 0xFF
        b = self.buf
        for i in range(0, len(b), 2):
            b[i] = b1
            b[i + 1] = b2

    def fill_rect(self, x0, y0, x1, y1, rgb):
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if x0 < 0:
            x0 = 0
        if y0 < 0:
            y0 = 0
        if x1 >= self.w:
            x1 = self.w - 1
        if y1 >= self.h:
            y1 = self.h - 1
        if x0 > x1 or y0 > y1:
            return
        v = _px565(rgb)
        for y in range(y0, y1 + 1):
            base = (y * self.w) * 2
            for x in range(x0, x1 + 1):
                j = base + x * 2
                self.buf[j] = v >> 8
                self.buf[j + 1] = v & 0xFF

    def rect(self, x0, y0, x1, y1, rgb, t=1):
        v = _px565(rgb)
        for off in range(t):
            yy0, yy1 = y0 + off, y1 - off
            xx0, xx1 = x0 + off, x1 - off
            if yy0 <= yy1:
                for x in range(xx0, xx1 + 1):
                    self._set(x, yy0, v)
                    self._set(x, yy1, v)
            if xx0 <= xx1:
                for y in range(yy0, yy1 + 1):
                    self._set(xx0, y, v)
                    self._set(xx1, y, v)

    def _stamp(self, x, y, v, t):
        if t <= 1:
            self._set(x, y, v)
        else:
            h = t // 2
            for yy in range(y - h, y - h + t):
                for xx in range(x - h, x - h + t):
                    self._set(xx, yy, v)

    def line(self, x0, y0, x1, y1, rgb, t=1):
        v = _px565(rgb)
        x0 = int(x0); y0 = int(y0); x1 = int(x1); y1 = int(y1)
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self._stamp(x0, y0, v, t)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, rgb, t=1):
        v = _px565(rgb)
        cx = int(cx); cy = int(cy); r = int(r)
        if r < 0:
            r = 0
        x = r
        y = 0
        err = 0
        while x >= y:
            pts = [(cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y), (cx - x, cy - y),
                   (cx + y, cy + x), (cx - y, cy + x), (cx + y, cy - x), (cx - y, cy - x)]
            for px_, py_ in pts:
                self._stamp(px_, py_, v, t)
            y += 1
            if err <= 0:
                err += 2 * y + 1
            if err > 0:
                x -= 1
                err -= 2 * x + 1

    def fill_circle(self, cx, cy, r, rgb):
        v = _px565(rgb)
        cx = int(cx); cy = int(cy); r = int(r)
        for y in range(-r, r + 1):
            ry = r * r - y * y
            if ry < 0:
                continue
            k = int(math.sqrt(ry))
            for x in range(-k, k + 1):
                self._set(cx + x, cy + y, v)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, rgb):
        v = _px565(rgb)
        x0 = int(x0); y0 = int(y0); x1 = int(x1); y1 = int(y1); x2 = int(x2); y2 = int(y2)
        ymin = min(y0, y1, y2)
        ymax = max(y0, y1, y2)
        edges = [(x0, y0, x1, y1), (x1, y1, x2, y2), (x2, y2, x0, y0)]
        for y in range(ymin, ymax + 1):
            xs = []
            for ax, ay, bx, by in edges:
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            if len(xs) >= 2:
                xa = int(min(xs))
                xb = int(max(xs))
                base = (y * self.w) * 2
                for x in range(xa, xb + 1):
                    j = base + x * 2
                    self.buf[j] = v >> 8
                    self.buf[j + 1] = v & 0xFF

    def arc(self, cx, cy, r, a0, a1, rgb, t=2):
        v = _px565(rgb)
        steps = max(6, int(r * abs(a1 - a0)))
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            x = cx + int(r * math.cos(a))
            y = cy + int(r * math.sin(a))
            self._stamp(x, y, v, t)


def fb_image(fb):
    """Wrap an FB's buffer as an lv.image_dsc_t (RGB565). Caller must keep fb alive."""
    return lv.image_dsc_t({
        "header": {"cf": lv.COLOR_FORMAT.RGB565, "w": fb.w, "h": fb.h},
        "data_size": len(fb.buf),
        "data": fb.buf,
    })


# --------------------------------------------------------------------------
# 5x7 bitmap font (only the glyphs we need). '1' = lit.
# --------------------------------------------------------------------------
BLANK = ["00000"] * 7
FONT = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    '4': ["00001", "00011", "00101", "01001", "11111", "00001", "00001"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ' ': BLANK,
}


def render_text(text, rgb=WHITE, scale=1, gap=1, glow=None):
    """Render `text` into an FB at the given pixel scale. Optional `glow` (rgb) draws a
    1px halo around each lit pixel (cheap neon bloom) and composites the bright text on top."""
    glyphs = [FONT.get(c.upper(), BLANK) for c in text]
    gw = [len(g[0]) for g in glyphs]
    width = sum(gw) + gap * (len(glyphs) - 1) if glyphs else 1
    out = FB(width * scale, 7 * scale)

    def stamp(target, bx, by, color):
        target.fill_rect(bx, by, bx + scale - 1, by + scale - 1, color)

    # halo first (so the bright core overwrites its center)
    if glow is not None:
        x = 0
        for g, wdt in zip(glyphs, gw):
            for ry, row in enumerate(g):
                for cx, ch in enumerate(row):
                    if ch == '1':
                        bx = (x + cx) * scale
                        by = ry * scale
                        for oy in range(-1, 2):
                            for ox in range(-1, 2):
                                stamp(out, bx + ox, by + oy, glow)
            x += wdt + gap

    # bright core
    x = 0
    for g, wdt in zip(glyphs, gw):
        for ry, row in enumerate(g):
            for cx, ch in enumerate(row):
                if ch == '1':
                    stamp(out, (x + cx) * scale, ry * scale, rgb)
        x += wdt + gap
    return out


# --------------------------------------------------------------------------
# Icon builders — each draws on a fresh 64x64 FB and returns it.
# --------------------------------------------------------------------------
ISZ = 64


def _rocket():
    fb = FB(ISZ, ISZ)
    fb.fill_triangle(32, 4, 23, 26, 41, 26, CYAN)          # nose
    fb.fill_rect(24, 24, 40, 50, CYAN)                      # body
    fb.rect(24, 24, 40, 50, WHITE, 1)
    fb.fill_circle(32, 34, 5, DGREY)                        # window
    fb.fill_circle(32, 34, 3, BLUE)
    fb.fill_triangle(24, 40, 24, 56, 12, 58, CYAN)          # left fin
    fb.fill_triangle(40, 40, 40, 56, 52, 58, CYAN)          # right fin
    fb.fill_triangle(27, 50, 37, 50, 32, 63, YELLOW)        # flame
    fb.fill_triangle(30, 50, 34, 50, 32, 57, ORANGE)
    return fb


def _beer():
    fb = FB(ISZ, ISZ)
    fb.fill_rect(16, 18, 40, 56, AMBER)                     # liquid
    fb.rect(14, 16, 42, 58, WHITE, 2)                       # mug
    fb.fill_rect(14, 16, 42, 22, WHITE)                     # foam band
    fb.fill_circle(20, 16, 4, WHITE)
    fb.fill_circle(30, 13, 5, WHITE)
    fb.fill_circle(39, 16, 4, WHITE)
    fb.line(42, 24, 52, 24, WHITE, 2)                       # handle
    fb.line(52, 24, 52, 48, WHITE, 2)
    fb.line(52, 48, 42, 48, WHITE, 2)
    for by, bx in [(30, 24), (40, 30), (48, 22)]:
        fb.fill_circle(bx, by, 2, 0xFFF0C0)                 # bubbles
    return fb


def _printer():
    fb = FB(ISZ, ISZ)
    fb.fill_rect(8, 10, 56, 14, CYAN)                       # top frame
    fb.fill_rect(10, 14, 14, 50, CYAN)                      # left post
    fb.fill_rect(50, 14, 54, 50, CYAN)                      # right post
    fb.fill_rect(6, 50, 58, 55, CYAN)                       # bed
    fb.fill_rect(18, 22, 46, 25, CYAN)                      # gantry
    fb.fill_triangle(32, 25, 28, 33, 36, 33, YELLOW)        # hotend
    fb.fill_rect(31, 30, 33, 36, SILVER)
    fb.fill_rect(27, 45, 37, 50, GREEN)                     # print
    fb.fill_rect(30, 41, 34, 45, GREEN)
    return fb


def _lathe():
    fb = FB(ISZ, ISZ)
    fb.fill_rect(12, 28, 52, 36, SILVER)                    # workpiece
    fb.rect(12, 28, 52, 36, WHITE, 1)
    fb.fill_rect(6, 18, 14, 46, GREY)                       # headstock
    fb.fill_rect(50, 18, 58, 46, GREY)                      # tailstock
    fb.rect(6, 18, 14, 46, WHITE, 1)
    fb.rect(50, 18, 58, 46, WHITE, 1)
    fb.fill_rect(30, 6, 34, 24, GOLD)                       # tool post
    fb.fill_triangle(30, 24, 34, 24, 32, 29, GOLD)          # tool bit
    for sx in (18, 24, 30, 38, 44):
        fb.line(sx, 30, sx + 2, 34, DGREY, 1)              # spin marks
    return fb


def _electronics():
    fb = FB(ISZ, ISZ)
    fb.fill_rect(8, 14, 56, 50, DGREY)                      # board
    fb.rect(8, 14, 56, 50, GREEN, 1)
    for cx, cy in [(12, 18), (52, 18), (12, 46), (52, 46)]:  # mounting holes
        fb.fill_circle(cx, cy, 2, BLACK)
    fb.line(14, 22, 24, 22, GREEN, 1)
    fb.line(24, 22, 24, 30, GREEN, 1)
    fb.line(40, 44, 50, 44, GREEN, 1)
    fb.fill_rect(24, 26, 40, 40, BLACK)                     # DIP chip
    fb.rect(24, 26, 40, 40, WHITE, 1)
    for py in (28, 32, 36):
        fb.px(22, py, WHITE)
        fb.px(42, py, WHITE)
    fb.fill_circle(48, 40, 3, BLUE)                         # cap
    fb.line(14, 44, 22, 44, YELLOW, 1)                      # resistor zigzag
    fb.line(22, 44, 24, 42, YELLOW, 1)
    fb.line(24, 42, 26, 44, YELLOW, 1)
    return fb


def _radio():
    fb = FB(ISZ, ISZ)
    fb.line(32, 60, 32, 22, MAGENTA, 3)                     # mast
    fb.fill_triangle(22, 60, 42, 60, 32, 50, MAGENTA)       # base
    fb.line(25, 56, 39, 30, MAGENTA, 1)                     # braces
    fb.line(39, 56, 25, 30, MAGENTA, 1)
    fb.fill_circle(32, 20, 3, WHITE)                        # antenna tip
    fb.arc(32, 20, 10, -math.pi * 0.80, -math.pi * 0.20, CYAN, 2)
    fb.arc(32, 20, 16, -math.pi * 0.85, -math.pi * 0.15, CYAN, 2)
    fb.arc(32, 20, 22, -math.pi * 0.88, -math.pi * 0.12, CYAN, 2)
    return fb


def _balloon():
    fb = FB(ISZ, ISZ)
    fb.fill_circle(32, 22, 16, YELLOW)                      # balloon
    fb.fill_circle(26, 17, 5, 0xFFFF99)                     # highlight
    fb.fill_triangle(29, 37, 35, 37, 32, 42, YELLOW)        # knot
    fb.line(32, 42, 29, 54, WHITE, 1)                       # string
    fb.line(29, 54, 33, 58, WHITE, 1)
    fb.fill_rect(25, 56, 37, 62, RED)                       # payload
    fb.rect(25, 56, 37, 62, WHITE, 1)
    return fb


def _trumpet():
    fb = FB(ISZ, ISZ)
    fb.fill_rect(6, 30, 11, 34, GOLD)                       # mouthpiece
    fb.fill_rect(11, 31, 24, 33, GOLD)                      # lead pipe
    for vx in (18, 24, 30):                                 # valve casings
        fb.fill_rect(vx, 20, vx + 4, 36, GOLD)
        fb.rect(vx, 20, vx + 4, 36, WHITE, 1)
    fb.fill_rect(24, 31, 30, 33, GOLD)                      # tuning pipe
    fb.fill_triangle(30, 24, 30, 40, 56, 46, GOLD)          # bell lower
    fb.fill_triangle(30, 24, 56, 46, 56, 16, GOLD)          # bell upper
    fb.line(56, 16, 56, 46, WHITE, 2)                       # bell rim
    return fb


def _homeassistant():
    fb = FB(ISZ, ISZ)
    fb.fill_triangle(32, 8, 8, 30, 56, 30, BLUE)            # roof
    fb.fill_rect(14, 30, 50, 54, BLUE)                      # body
    fb.rect(14, 30, 50, 54, WHITE, 1)
    fb.fill_circle(32, 38, 5, DGREY)                        # HA node
    fb.circle(32, 38, 8, WHITE, 1)                          # ring
    fb.fill_rect(28, 44, 36, 54, WHITE)                     # door
    return fb


_ICONS = {
    "rocket": _rocket,
    "beer": _beer,
    "printer": _printer,
    "lathe": _lathe,
    "electronics": _electronics,
    "radio": _radio,
    "balloon": _balloon,
    "trumpet": _trumpet,
    "homeassistant": _homeassistant,
}

_cache = {}


def build_icon(name):
    fb = _cache.get(name)
    if fb is None:
        fb = _ICONS[name]()
        _cache[name] = fb
    return fb
