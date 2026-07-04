# render_test.py — verify art.py on the badge: ASCII previews (over serial) + on-screen draw.
import sys
sys.path.insert(0, '/user/name_badge')
import art
import lvgl as lv
import lvgl_esp32
from fri3d.badge.display import display

w = lvgl_esp32.Wrapper(display)
try:
    w.init()
except Exception as e:
    print("wrapper init:", e)

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)


def preview(fb, step=2):
    lines = []
    for y in range(0, fb.h, step):
        row = ""
        for x in range(0, fb.w, step):
            i = (y * fb.w + x) * 2
            v = (fb.buf[i] << 8) | fb.buf[i + 1]
            row += " " if v == 0 else "#"
        lines.append(row)
    return "\n".join(lines)


print("RENDER_TEST_START")

# text previews (no glow, to show true glyph shapes)
for s, sc, col in [("DAVID", 8, art.CYAN), ("STEEMAN", 3, art.WHITE), ("ON4BDS", 3, art.MAGENTA)]:
    fb = art.render_text(s, col, scale=sc)
    print("=== TEXT %s  %dx%d ===" % (s, fb.w, fb.h))
    print(preview(fb, 3))

# icon previews
for name in ["rocket", "beer", "printer", "lathe", "electronics",
             "radio", "balloon", "trumpet", "homeassistant"]:
    fb = art.build_icon(name)
    print("=== ICON %s  %dx%d ===" % (name, fb.w, fb.h))
    print(preview(fb, 2))

# ---- draw to the actual LCD so a human can see it ----
# title
david = art.render_text("DAVID", art.CYAN, scale=8, glow=art.BLUE)
last = art.render_text("STEEMAN", art.WHITE, scale=3)
call = art.render_text("ON4BDS", art.MAGENTA, scale=3)


def put(fb, x, y):
    d = lv.image_dsc_t({"header": {"cf": lv.COLOR_FORMAT.RGB565, "w": fb.w, "h": fb.h},
                        "data_size": len(fb.buf), "data": fb.buf})
    im = lv.image(scr)
    im.set_src(d)
    im.set_pos(x, y)
    return im


put(david, (296 - david.w) // 2, 16)
put(last, (296 - last.w) // 2, 82)
put(call, (296 - call.w) // 2, 108)
# one sample icon centred below the title
sample = art.build_icon("rocket")
put(sample, (296 - sample.w) // 2, 140)
print("RENDER_TEST_DONE")
print("mem_free:", __import__("gc").mem_free())
