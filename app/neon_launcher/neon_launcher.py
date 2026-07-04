# neon_launcher.py — neon app-picker for the Fri3d badge.
#
# The shipped fri3d Launcher is a stub (no real menu), so this app IS the "selectable
# program" UX: it lists every non-hidden app discovered by AppManager plus an "Exit to
# REPL" entry, and runs the chosen one via app_manager.run_app(). When an app returns,
# the menu re-wipes the shared screen and waits for the next pick.
#
# Controls: X = down, Y = up, A = select  (working buttons; MENU not used).

import asyncio

import lvgl as lv

from fri3d.application import App, AppInfo, Managers
from fri3d.badge.leds import leds
from fri3d.badge.buttons import buttons

W, H = 296, 240


class NeonLauncher(App):
    def __init__(self, info, managers):
        super().__init__(info, managers)
        self._prev = {}
        self._markers = []
        self._names = []
        self._rows = []

    # ---- screen helpers (shared screen, wiped between apps) ----
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

    # ---- buttons ----
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

    # ---- entries / menu ----
    def _entries(self):
        apps = [a for a in self.app_manager.apps.values() if not a.hidden]
        apps.sort(key=lambda a: a.name.lower())
        rows = [(a.name, a.id) for a in apps]
        rows.append(("Exit to REPL", None))
        return rows

    def _build(self, scr, sel):
        self._wipe(scr)
        scr.set_style_bg_color(lv.color_hex(0x000000), 0)
        scr.set_style_bg_opa(lv.OPA.COVER, 0)
        self._label(scr, 0, 12, "BADGE", 0x00FFFF, font=lv.font_montserrat_24, center=True)
        self._label(scr, 0, 40, "select a program", 0x707080,
                    font=lv.font_montserrat_14, center=True)

        self._markers = []
        self._names = []
        y0 = 74
        rh = 24
        for i, (name, _id) in enumerate(self._rows):
            y = y0 + i * rh
            self._markers.append(self._label(scr, 26, y, " ", 0xFF00FF,
                                             font=lv.font_montserrat_16))
            self._names.append(self._label(scr, 48, y, name, 0xFFFFFF,
                                           font=lv.font_montserrat_16))
        self._label(scr, 0, H - 18, "X:down  Y:up  A:select", 0x707080,
                    font=lv.font_montserrat_14, center=True)
        self._update_sel(sel)

    def _update_sel(self, sel):
        for i in range(len(self._rows)):
            if i == sel:
                self._markers[i].set_text(">")
                self._names[i].set_style_text_color(lv.color_hex(0xFFE700), 0)
            else:
                self._markers[i].set_text(" ")
                self._names[i].set_style_text_color(lv.color_hex(0xFFFFFF), 0)

    def _led_hint(self, sel):
        leds.fill((0, 0, 0))
        leds[sel % leds.n] = (0, 255, 255) if (sel % 2 == 0) else (255, 0, 255)
        leds.write()

    async def start(self):
        self.logger.info("Starting neon launcher")
        scr = lv.screen_active()
        self._rows = self._entries()
        sel = 0
        for i, (_n, _id) in enumerate(self._rows):
            if _id and _id.endswith("name_badge"):
                sel = i
                break
        self._build(scr, sel)
        self._led_hint(sel)

        while True:
            ev = ''
            for n in ("a", "x", "y"):
                e = self._edge(n)
                if e:
                    ev = e
                    break
            if ev == "x":
                sel = (sel + 1) % len(self._rows)
                self._update_sel(sel)
                self._led_hint(sel)
            elif ev == "y":
                sel = (sel - 1) % len(self._rows)
                self._update_sel(sel)
                self._led_hint(sel)
            elif ev == "a":
                name, app_id = self._rows[sel]
                if app_id is None:
                    leds.fill((0, 0, 0))
                    leds.write()
                    self.logger.info("Exit to REPL selected")
                    return  # Application.run() ends -> REPL
                self.logger.info("Launching %s" % app_id)
                try:
                    await self.app_manager.run_app(app_id)
                except Exception as e:
                    self.logger.info("app error: %r" % e)
                # app drew on the shared screen -> wipe + rebuild menu
                scr = lv.screen_active()
                self._rows = self._entries()
                if sel >= len(self._rows):
                    sel = len(self._rows) - 1
                self._build(scr, sel)
                self._led_hint(sel)
            await asyncio.sleep_ms(30)

    async def stop(self):
        try:
            leds.fill((0, 0, 0))
            leds.write()
        except Exception:
            pass
