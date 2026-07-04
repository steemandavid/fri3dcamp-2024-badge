# name_badge.py — neon-arcade name + hobby animation for the Fri3d badge.
#
# A fri3d `App` that plays under Application()'s asyncio loop. Shows DAVID big (pixel
# font) with STEEMAN + ON4BDS, then loops through 9 hobby "cards" (icon + label + tag)
# with a NeoPixel colour and a buzzer sting each.
#
# Controls (working buttons only; MENU is physically broken and unused):
#   A = next hobby   Y = previous   X = toggle sound   B / START = back to menu

import asyncio
import math
import time

import lvgl as lv

from fri3d.application import App, AppInfo, Managers
from fri3d.badge.leds import leds
from fri3d.badge.buzzer import buzzer
from fri3d.badge.buttons import buttons
from . import art

W, H = 296, 240


def _hsv(h, s=1.0, v=0.6):
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


# icon, label, tag, accent rgb, sting notes (freq_hz, ms)
HOBBIES = [
    ("rocket", "High-power rocketry", "98 mm airframe  -  HPR", art.ORANGE,
     [(523, 90), (0, 40), (784, 130)]),
    ("beer", "Beer brewing", "all-grain  -  malts & hops", art.AMBER,
     [(440, 100), (0, 40), (330, 120)]),
    ("printer", "3D printing", "FDM  -  PLA / PETG", art.CYAN,
     [(659, 80), (0, 40), (880, 120)]),
    ("lathe", "Metalworking", "lathe  -  turning steel", art.SILVER,
     [(330, 100), (0, 30), (392, 120)]),
    ("electronics", "Electronics", "KiCad  -  solder smoke", art.GREEN,
     [(587, 80), (0, 40), (698, 120)]),
    ("radio", "Amateur radio", "ON4BDS  -  HF / VHF", art.MAGENTA,
     [(523, 80), (0, 40), (659, 80), (784, 120)]),
    ("balloon", "Weather balloons", "near-space telemetry", art.YELLOW,
     [(440, 90), (0, 40), (659, 130)]),
    ("trumpet", "Trumpet", "Bb brass  -  bright tone", art.GOLD,
     [(392, 90), (0, 40), (523, 90), (659, 130)]),
    ("homeassistant", "Home Assistant", "smart-home automation", art.BLUE,
     [(523, 90), (0, 40), (440, 120)]),
]


class NameBadge(App):
    def __init__(self, info, managers):
        super().__init__(info, managers)
        self._quit = False
        self._sound = True
        self._prev = {}
        self._keep = []          # keep FBs / dscs alive against gc
        self._scr = None
        self._intro_widgets = []
        self._icon_dscs = []

    # ---- screen helpers (single shared screen, wiped between apps) ----
    def _wipe(self, scr):
        try:
            scr.clean()
            return
        except Exception:
            pass
        try:
            n = scr.get_child_count()
            for k in range(n - 1, -1, -1):
                scr.get_child(k).delete()
        except Exception:
            pass

    def _setup_screen(self):
        scr = lv.screen_active()
        self._wipe(scr)
        scr.set_style_bg_color(lv.color_hex(0x000000), 0)
        scr.set_style_bg_opa(lv.OPA.COVER, 0)
        self._scr = scr
        return scr

    def _rect(self, scr, x, y, w, h, color):
        o = lv.obj(scr)
        o.remove_style_all()
        o.set_pos(x, y)
        o.set_size(w, h)
        o.set_style_bg_color(lv.color_hex(color), 0)
        o.set_style_bg_opa(lv.OPA.COVER, 0)
        return o

    def _label(self, scr, x, y, text, color, font=None, center=False, w=W):
        lbl = lv.label(scr)
        lbl.set_text(text)
        lbl.set_style_text_color(lv.color_hex(color), 0)
        if font:
            lbl.set_style_text_font(font, 0)
        if center:
            lbl.set_width(w)
            lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            lbl.set_pos(0, y)
        else:
            lbl.set_pos(x, y)
        return lbl

    def _img(self, scr, fb, x, y):
        dsc = art.fb_image(fb)
        self._keep.append(fb)
        self._keep.append(dsc)
        im = lv.image(scr)
        im.set_src(dsc)
        im.set_pos(x, y)
        return im

    def _frame(self, scr):
        self._rect(scr, 0, 0, W, 2, art.MAGENTA)
        self._rect(scr, 0, H - 2, W, 2, art.MAGENTA)
        self._rect(scr, 0, 0, 2, H, art.MAGENTA)
        self._rect(scr, W - 2, 0, 2, H, art.MAGENTA)

    # ---- buttons (raw pin level, independent of the indev latch) ----
    def _held(self, name):
        b = getattr(buttons, name, None)
        if b is None:
            return False
        try:
            return b._pin.value() == 0
        except Exception:
            return False

    def _edge(self, name):
        cur = self._held(name)
        prev = self._prev.get(name, False)
        self._prev[name] = cur
        return name if (cur and not prev) else ''

    def _poll(self):
        for n in ("b", "start", "a", "y", "x"):
            ev = self._edge(n)
            if ev:
                return ev
        return ''

    # ---- buzzer / leds ----
    async def _sting(self, notes):
        if not self._sound:
            return
        for f, ms in notes:
            if f:
                buzzer.freq(f)
                buzzer.duty_u16(16000)
            else:
                buzzer.duty_u16(0)
            await asyncio.sleep_ms(ms)
        buzzer.duty_u16(0)

    async def _jingle(self):
        if not self._sound:
            return
        for f in (523, 659, 784, 1047):
            buzzer.freq(f)
            buzzer.duty_u16(16000)
            await asyncio.sleep_ms(110)
        buzzer.duty_u16(0)

    def _leds_solid(self, rgb):
        r, g, b = ((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF)
        for i in range(leds.n):
            leds[i] = (r, g, b)
        leds.write()

    def _leds_pulse(self, rgb, t):
        k = 0.55 + 0.45 * math.sin(t / 220.0)
        r = int(((rgb >> 16) & 0xFF) * k)
        g = int(((rgb >> 8) & 0xFF) * k)
        b = int((rgb & 0xFF) * k)
        for i in range(leds.n):
            leds[i] = (r, g, b)
        leds.write()

    def _leds_off(self):
        leds.fill((0, 0, 0))
        leds.write()

    # ---- scenes ----
    async def _intro(self, scr):
        self._frame(scr)
        david = art.render_text("DAVID", art.CYAN, scale=8, glow=art.BLUE)
        last = art.render_text("STEEMAN", art.WHITE, scale=3)
        call = art.render_text("ON4BDS", art.MAGENTA, scale=3)
        self._intro_widgets.append(self._img(scr, david, (W - david.w) // 2, 26))
        self._intro_widgets.append(self._img(scr, last, (W - last.w) // 2, 98))
        self._intro_widgets.append(self._img(scr, call, (W - call.w) // 2, 126))
        self._intro_widgets.append(self._label(scr, 0, 210, "A: skip", art.GREY,
                                               font=lv.font_montserrat_14, center=True))

        jingle = asyncio.create_task(self._jingle())
        end = time.ticks_add(time.ticks_ms(), 3000)
        hue = 0
        while True:
            now = time.ticks_ms()
            if time.ticks_diff(end, now) <= 0:
                break
            if self._poll() in ("a", "b", "start"):
                break
            hue = (hue + 9) % 360
            for i in range(leds.n):
                leds[i] = _hsv(hue + i * (360 // leds.n))
            leds.write()
            await asyncio.sleep_ms(30)
        await jingle

    def _delete_intro(self):
        for w in self._intro_widgets:
            try:
                w.delete()
            except Exception:
                pass
        self._intro_widgets = []

    async def _show_hobby(self, idx):
        icon_name, label, tag, accent, notes = HOBBIES[idx]
        self.logger.info("hobby %d/%d: %s" % (idx + 1, len(HOBBIES), icon_name))
        self._icon_im.set_src(self._icon_dscs[idx])
        self._icon_im.set_scale(256)
        self._lbl.set_text(label)
        self._lbl.set_style_text_color(lv.color_hex(accent), 0)
        self._tag.set_text(tag)
        self._idx.set_text("%d / %d" % (idx + 1, len(HOBBIES)))

        self._leds_solid(accent)
        await self._sting(notes)

        # entrance: scale-in with ease-out, ~360 ms
        t0 = time.ticks_ms()
        while True:
            dt = time.ticks_diff(time.ticks_ms(), t0)
            if dt >= 360:
                self._icon_im.set_scale(256)
                break
            p = dt / 360.0
            e = 1 - (1 - p) * (1 - p)
            self._icon_im.set_scale(int(70 + (256 - 70) * e))
            ev = self._poll()
            if ev == "a":
                return 1
            if ev == "y":
                return -1
            if ev in ("b", "start"):
                self._quit = True
                return 0
            await asyncio.sleep_ms(30)

        # hold ~2.6 s with nav
        end = time.ticks_add(time.ticks_ms(), 2600)
        while True:
            now = time.ticks_ms()
            ev = self._poll()
            if ev == "a":
                return 1
            if ev == "y":
                return -1
            if ev == "x":
                self._sound = not self._sound
            if ev in ("b", "start"):
                self._quit = True
                return 0
            self._leds_pulse(accent, now)
            if time.ticks_diff(end, now) <= 0:
                return 1
            await asyncio.sleep_ms(30)

    async def start(self):
        self._quit = False
        self.logger.info("Starting neon name badge")
        scr = self._setup_screen()
        try:
            await self._intro(scr)
            if self._quit:
                return
            self._delete_intro()

            # build all icon descriptors once
            for h in HOBBIES:
                fb = art.build_icon(h[0])
                dsc = art.fb_image(fb)
                self._keep.append(fb)
                self._keep.append(dsc)
                self._icon_dscs.append(dsc)

            # persistent card widgets
            self._icon_im = lv.image(scr)
            self._icon_im.set_src(self._icon_dscs[0])
            self._icon_im.set_pos((W - art.ISZ) // 2, 52)
            self._lbl = self._label(scr, 0, 132, "", art.WHITE,
                                    font=lv.font_montserrat_24, center=True)
            self._tag = self._label(scr, 0, 164, "", art.GREY,
                                    font=lv.font_montserrat_14, center=True)
            self._idx = self._label(scr, 0, 188, "", art.SILVER,
                                    font=lv.font_montserrat_14, center=True)
            self._label(scr, 0, 220, "A:next  Y:prev  X:sound  B:menu", art.DGREY,
                        font=lv.font_montserrat_14, center=True)

            i = 0
            while not self._quit:
                d = await self._show_hobby(i)
                if self._quit:
                    break
                i = (i - 1) % len(HOBBIES) if d == -1 else (i + 1) % len(HOBBIES)
        finally:
            self.logger.info("Name badge start() returning")

    async def stop(self):
        self.logger.info("Stopping neon name badge")
        try:
            self._leds_off()
            buzzer.duty_u16(0)
        except Exception:
            pass
        # screen is shared; leave it (next app wipes it). just drop our refs.
        self._scr = None
        self._keep = []
        self._icon_dscs = []
