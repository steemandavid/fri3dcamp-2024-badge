# §6 on-device verification probe for the Fri3d badge. Prints PROBE_START...PROBE_END.
import os
import sys
import gc

print("PROBE_START")
print("impl:", repr(sys.implementation))
try:
    print("uname:", " ".join(os.uname()))
except Exception as e:
    print("uname ERR:", e)

print("root /:", os.listdir("/"))
for d in ("/fri3d", "/user", "/examples"):
    try:
        print(d, os.listdir(d))
    except Exception as e:
        print(d, "ERR:", e)

# fri3d version + boot + application + hw layer
try:
    import fri3d.version as v
    print("fri3d.version:", v.version)
except Exception as e:
    print("fri3d.version ERR:", repr(e))

try:
    from fri3d import boot
    print("from fri3d import boot: OK", [a for a in dir(boot) if not a.startswith("__")])
except Exception as e:
    print("from fri3d import boot ERR:", repr(e))

try:
    from fri3d.application import Application, App, AppInfo, Managers
    print("from fri3d.application import ...: OK")
except Exception as e:
    print("from fri3d.application ERR:", repr(e))

try:
    from fri3d.badge.leds import leds
    from fri3d.badge.buzzer import buzzer
    from fri3d.badge.buttons import buttons
    print("fri3d.badge hw: OK  leds.n=%d" % leds.n)
except Exception as e:
    print("fri3d.badge hw ERR:", repr(e))

# lvgl: init display (one-shot per boot) like hardware_test.py, then probe widgets
import lvgl as lv
import lvgl_esp32
from fri3d.badge.display import display

w = lvgl_esp32.Wrapper(display)
try:
    w.init()
    print("wrapper.init: OK")
except Exception as e:
    print("wrapper.init (already done?):", repr(e))

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)

for s in (8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32):
    print("font_montserrat_%d:" % s, hasattr(lv, "font_montserrat_%d" % s))

print("has COLOR_FORMAT:", hasattr(lv, "COLOR_FORMAT"))
if hasattr(lv, "COLOR_FORMAT"):
    print("  COLOR_FORMAT members:", [a for a in dir(lv.COLOR_FORMAT) if "RGB565" in a or a == "TRUE_COLOR"])
print("has OPA:", hasattr(lv, "OPA"))

# ---- canvas ----
print("has lv.canvas:", hasattr(lv, "canvas"))
try:
    c = lv.canvas(scr)
    buf = bytearray(8 * 8 * 2)
    ok = False
    try:
        c.set_buffer(buf, 8, 8, lv.COLOR_FORMAT.RGB565)
        print("canvas.set_buffer(buf,w,h,cf): OK")
        ok = True
    except Exception as e:
        print("canvas.set_buffer(buf,w,h,cf) ERR:", repr(e))
    if not ok:
        for m in ("set_draw_buf",):
            try:
                getattr(c, m)
                print("canvas has %s" % m)
            except Exception as e:
                print("canvas no %s: %s" % (m, e))
    if ok:
        for m_call in ("set_px", "fill_bg", "set_palette"):
            try:
                if m_call == "set_px":
                    c.set_px(0, 0, lv.color_hex(0xFF00FF))
                elif m_call == "fill_bg":
                    c.fill_bg(lv.color_hex(0), lv.OPA.COVER)
                print("canvas.%s: OK" % m_call)
            except Exception as e:
                print("canvas.%s ERR:" % m_call, repr(e))
    c.delete()
except Exception as e:
    print("canvas block ERR:", repr(e))

# ---- image ----
print("has lv.image:", hasattr(lv, "image"))
print("has lv.image_dsc_t:", hasattr(lv, "image_dsc_t"))
try:
    data = bytearray(8 * 8 * 2)
    dsc = None
    for variant, kw in (
        ("cf-in-header", {"header": {"cf": lv.COLOR_FORMAT.RGB565, "w": 8, "h": 8},
                          "data_size": len(data), "data": data}),
        ("magic-cf",     {"header": {"cf": lv.COLOR_FORMAT.RGB565, "w": 8, "h": 8, "always_zero": 0},
                          "data_size": len(data), "data": data}),
    ):
        try:
            dsc = lv.image_dsc_t(kw)
            print("image_dsc_t(%s): OK" % variant)
            break
        except Exception as e:
            print("image_dsc_t(%s) ERR:" % variant, repr(e))
    if dsc is not None:
        im = lv.image(scr)
        im.set_src(dsc)
        print("image.set_src(dsc): OK")
        try:
            im.set_scale(512)
            print("image.set_scale(512): OK")
        except Exception as e:
            print("image.set_scale ERR:", repr(e))
        try:
            im.set_pos(10, 10)
            print("image.set_pos: OK")
        except Exception as e:
            print("image.set_pos ERR:", repr(e))
        im.delete()
except Exception as e:
    print("image block ERR:", repr(e))

print("mem_free bytes:", gc.mem_free())
print("PROBE_END")
