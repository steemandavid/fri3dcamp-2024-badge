# Neon-Arcade "Name Badge" App — Design & Implementation Plan

**Project:** Fri3d Camp 2024 badge ("Badge 2024", board codename **fox**), ESP32-S3-WROOM-1
**Status:** **IMPLEMENTED & deployed (2026-07-04)** — the badge boots into the NeonLauncher
and the animation plays. This doc is the original spec (kept for reference); see
`changelog.md` (2026-07-04 entry) for what was actually built and the on-device findings.
Project source mirror: `app/` (`main.py`, `neon_launcher/`, `name_badge/`).
**Owner display:** **DAVID** (prominent) · **STEEMAN** (last name) · **ON4BDS** (amateur-radio callsign)
**Hobbies to feature (9):** high-power rocketry · beer brewing · 3D printing · lathe / metalworking · electronics · amateur radio · weather balloons · trumpet · Home Assistant

---

## 1. Context & goal

David wants the badge to play an animated, **neon-arcade** loop that introduces him and
shows off his hobbies, and he wants it reachable as a **selectable program inside the
existing badge OS** — ideally the "native" way. This document specifies exactly how to
build and integrate that, grounded in the badge's actual firmware source (the local clones
under `repos/`) and the proven-working `hardware_test.py`.

Everything here is **reversible**: a verified 16 MiB full-flash backup exists
(`backups/fri3d-badge-2024_full-flash_2026-07-02.bin`, SHA-256
`7c3c34b1…`), so any change to the badge can be undone with one `esptool write_flash`.

### Decisions locked (from the user)
| Topic | Choice |
|---|---|
| Name | **DAVID** large; **STEEMAN** and callsign **ON4BDS** smaller/secondary |
| Launch style | **App-launcher integration** — a proper `fri3d` App + a real app-picker menu (the built-in launcher is a stub) |
| Visual style | **Neon arcade** — black bg, glowing magenta/cyan/green, scanlines, fast motion, chiptune buzzer |

---

## 2. Ground-truth findings from the firmware source

These are facts verified by reading the source in `repos/badge_2024_micropython/`
(tag `v1.23.0-1+fri3d`; `fri3d` package version string `0.1.3-develop.1+build.0`),
not assumptions.

### 2.1 Hardware / display
- ESP32-S3, **296 × 240** LCD (GC9307/ST7789), driven through **lvgl v9** via `lvgl_esp32`.
- `LV_COLOR_DEPTH 16` → colours are **RGB565** (2 bytes/px). Display is BGR (handled by the wrapper).
- `lv_conf.h` enables: `LV_USE_CANVAS 1`, `LV_USE_IMAGE 1`, `LV_USE_ANIMIMG 1`, `LV_USE_LABEL 1`.
- **lvgl heap is only 64 KB** (`LV_MEM_SIZE`). Implication: never allocate a full-screen
  canvas (296×240×2 ≈ 142 KB) in lvgl's heap. Icon-sized buffers are fine; large buffers
  should live in the MicroPython heap (backed by the 8 MB PSRAM).
- **Fonts compiled in: Montserrat 14 / 16 / 24 only** (`LV_FONT_MONTSERRAT_{14,16,24}=1`; all
  others `0`; default font = montserrat 14). 24 px is the largest. This is why the big
  **DAVID** title will be **pixel-art**, not a built-in font.

### 2.2 Proven-working primitives (from `hardware_test.py` + `apps/splash/splash.py`)
| Capability | Confirmed call |
|---|---|
| Display init (standalone only) | `lvgl_esp32.Wrapper(display); wrapper.init()` — **one-shot per boot** |
| Screen / colour | `scr = lv.screen_active(); scr.set_style_bg_color(lv.color_hex(0x000000), 0)` |
| Text | `lbl = lv.label(scr); lbl.set_pos(x,y); lbl.set_text(...); lbl.set_style_text_color(lv.color_hex(0x00FFFF), 0); lbl.set_style_text_font(lv.font_montserrat_24, 0)` |
| Smooth animation | `a = lv.anim_t(); a.init(); a.set_var(obj); a.set_values(s,e); a.set_duration(ms); a.set_path_cb(lv.anim_t.path_ease_in_out); a.set_custom_exec_cb(lambda _,v: obj.set_y(v)); a.start()` (+ `lv.anim_delete(obj, None)` to clean up) |
| Layout | `obj.align(lv.ALIGN.CENTER, 0, 0)` |
| NeoPixels (5× WS2812) | `from fri3d.badge.leds import leds; leds[i] = (r,g,b); leds.fill((0,0,0)); leds.write()` (`leds.n == 5`) |
| Buzzer (raw tone) | `from fri3d.badge.buzzer import buzzer; buzzer.freq(440); buzzer.duty_u16(32768)`; off via `buzzer.duty_u16(0)` |
| Melodies | `from fri3d.rtttl import RTTTL, songs; RTTTL(songs.take_on_me_s).play(volume=80)` |
| Buttons | `from fri3d.badge.buttons import buttons`; `buttons.{a,b,x,y,menu,start}`; `.value()` is edge-oriented (1 on press, auto-clears ~200 ms); raw held level = `b._pin.value() == 0` (pull-up). |

### 2.3 Input model (`fri3d/indev/indev.py`)
`Indev` (created by `Application`) registers an lvgl **keypad indev** bound to a **default
group** and maps the buttons to lvgl keys:

| Button | lvgl key | Works on this badge? |
|---|---|---|
| A (`confirm`) | `lv.KEY.ENTER` | ✅ |
| B (`escape`) | `lv.KEY.ESC` | ✅ |
| X (`next`) | `lv.KEY.NEXT` | ✅ |
| Y (`previous`) | `lv.KEY.PREV` | ✅ |
| START (`end`) | `lv.KEY.END` | ✅ |
| MENU (`home`) | `lv.KEY.HOME` | ❌ **physically broken** |

The joystick (if present) also feeds UP/DOWN/LEFT/RIGHT. **Navigation therefore uses
A / X / Y / START only** — the broken MENU is never needed.

### 2.4 App framework (`fri3d/application/`)
- **Discovery:** `AppManager` scans, in order, `/remote/fri3d/apps`, `/remote/user`,
  `/fri3d/apps`, `/user`, `/sdcard/user`. Any directory containing **`app.json`** becomes an
  app; the package id is the dotted path (e.g. `/user/name_badge` → `user.name_badge`).
- **`app.json` schema:** `{"name": str (required), "cls": str (required), "hidden": bool, "config": {…}}`.
- **App contract:** subclass `App`; implement `async def start(self)` (and optionally
  `async def stop(self)`). Convenience properties: `self.id`, `self.name`, `self.config`,
  `self.app_manager`, `self.theme_manager`, `self.window_manager`, `self.logger`.
- **`Application(default_app='fri3d.apps.launcher').run()`** inits the display wrapper +
  indev + theme + window managers + app manager (which `scan()`s), then
  `await self._app_manager.run_app(self._default_app)` inside an asyncio loop that also drives
  `lvgl_tick` (caps lvgl refresh at ~25 fps). `run_app(id)` = `start_app` then `stop_app`.
- **`WindowManager` and `ThemeManager` are near-empty stubs.** Theme sets montserrat-16 /
  green palette — we override per-screen for the neon look (set bg black, label colours neon).

### 2.5 What the "OS" actually does on boot (important)
- **Frozen** `boot.py` runs `p0tat0.sys.flash.init_internal_flash()`: if `/main.py`, `/fri3d`,
  `/user`, or `/examples` are missing from `/`, it re-extracts them from the firmware's embedded
  gzip'd tar. → **Self-healing**: deleting any of those restores the originals on next boot.
- **Frozen** `main.py`: if SAO "dev mode" pin (GPIO2→GND) is active → drop to REPL; else if
  `/main.py` exists → `import main`.
- The **payload** (extracted) `/main.py` just prints a welcome and returns → **the badge
  currently boots to a blank-screen REPL** (matches the project memory note).
- The shipped **`Launcher` app is a stub**: its `start()` only runs the splash (LED flash +
  "SPLASH SCREEN" label for 3 s). It does **not** enumerate apps or draw a picker. `Nametag`
  is an empty stub too. → "Select an app from a menu" is **not** provided by the firmware; we
  must build it.

### 2.6 Deploy tooling
- `mpremote` is **not installed** (system Python is PEP-668 externally-managed). Prior session
  used a pyserial **paste-mode runner** (`/tmp/fri3d_run.py`, ephemeral) over `/dev/ttyACM0`
  with subcommands `probe`/`test`/`run`/`stop`. Paste mode (Ctrl-E … Ctrl-D) streams output and
  leaves long-running programs running after detaching.
- Files can be uploaded by pasting `with open('/user/…','wb') as f: f.write(bytes(…))`.
- The REPL is on USB-Serial/JTAG (`ttyACM0`) but is **silent ~60 s** on first boot while the
  `fri3d` package extracts — send Enter to elicit `>>>`.
- **OTA anti-rollback is active:** after any boot-slot change, call
  `esp32.Partition.mark_app_valid_cancel_rollback()` once or it reverts. (The badge already
  boots the `micropython` partition and this was persisted in the prior session.)

### 2.7 Unverified — must be confirmed on the live device
The `lvgl_esp32_mpy` binding generates its C module **at build time** from the lvgl headers
(via pycparser); there are no pre-baked method tables to grep. So the exact MicroPython
spellings of the following cannot be confirmed from the repo and must be probed on-device:
- `lv.canvas`: `set_buffer(buf,w,h,cf)` vs the newer `set_draw_buf(...)`, `set_px(x,y,color)`,
  `fill_bg(color,opa)`, and the colour-format constant (`lv.COLOR_FORMAT.RGB565` etc.).
- `lv.image` + `lv.image_dsc_t({...})` + `set_src(...)`, and `set_scale(...)` for zooming.
- `lv.OPA.COVER` etc.
- Whether `from fri3d.application import …` actually imports on **this** badge (a stale note
  says `from fri3d import boot` once failed — possibly predating a `/fri3d` re-extract; must
  re-verify).

**Step 1 of implementation is a small on-device probe that nails all of the above** (see §6).

---

## 3. Architecture overview

Three pieces, all installed under `/user/` on the badge, plus a new boot `/main.py`. A
project-side mirror lives under `~/claudecode/projects/fri3dbadge2024/name_badge/` so the
source is versioned on disk and deployed via the paste runner.

```
/main.py                      NEW — boot entry: runs Application(default_app='user.neon_launcher')
/user/neon_launcher/          NEW — the app-picker menu (the "selectable" UX)
    __init__.py
    app.json
    neon_launcher.py
/user/name_badge/             NEW — the animation app (the core deliverable)
    __init__.py
    app.json
    name_badge.py
    art.py                    pixel-art definitions (title + 9 icons) + RGB565 encoder
```

Boot flow after install: power-on → frozen boot re-extracts (no-op, nothing missing) →
frozen `main.py` → `import main` → our `/main.py` runs
`Application(default_app='user.neon_launcher').run()` → `Application` inits display/indev/
managers, scans apps → runs **NeonLauncher** → user picks **DAVID** → **NameBadge** runs →
B/START returns to the menu → "Exit to REPL" ends `Application.run()` → `>>>`.

> Note: `Application` initialises the lvgl display wrapper **once**. Apps run *under*
> `Application` must **not** call `wrapper.init()` themselves (unlike the standalone
> `hardware_test.py`). They just use `lv.screen_active()` etc. and must be **async +
> cooperative** (`await asyncio.sleep_ms(...)`, never blocking `time.sleep`), because
> `Application` owns the `lvgl_tick` loop.

---

## 4. Visual & UX design (Neon arcade)

### 4.1 Palette (RGB565 via `lv.color_hex`)
| Role | Hex | Name |
|---|---|---|
| Background | `0x000000` | black |
| Title / primary accent | `0xFF00FF` | magenta |
| Secondary accent | `0x00FFFF` | cyan |
| Tertiary / "go" | `0x39FF14` | neon green |
| Highlight | `0xFFE700` | yellow |
| Warm accent | `0xFF8800` | orange |
| Text | `0xFFFFFF` | white |
| Home Assistant blue | `0x18BCF2` | HA blue |
| Gold (trumpet) | `0xFFD000` | gold |

Per-hobby accent colours drive both the on-screen icon glow and the 5 NeoPixels.

### 4.2 CRT / scanline treatment
A faint overlay of horizontal lines (e.g. every 2 px, alpha ~12 %) for arcade-CRT feel.
Implementation TBD by probe: either a static `lv.canvas`/image drawn once, or faint `lv.obj`
lines. Slow vertical scroll is a nice-to-have, not required.

### 4.3 Scene 1 — Name / intro screen (≈3 s on launch, then enters the hobby loop)
```
╔══════════════════════════════════════╗
║   ░░▓▓▓  D A V I D  ▓▓▓░░            ║   ← big pixel-art title, magenta glow + pulse
║                                      ║
║            S T E E M A N             ║   ← montserrat_24, white
║               ON4BDS                 ║   ← montserrat_16, cyan
║   ─────────────────────────────      ║   ← neon divider
║   A:next  B:menu  X:sound  START:menu║   ← hint line, montserrat_14, grey
╚══════════════════════════════════════╝
```
- **DAVID** rendered from a hand-built pixel-art bitmap (~200 × 56), with a glow pulse via
  `lv.anim` (e.g. cycle a secondary outline's colour or a subtle Y bob).
- **STEEMAN** / **ON4BDS** as `lv.label`s (montserrat 24 / 16).
- Neon border frame + scanlines. LED rainbow during the intro. Short opening jingle (RTTTL).

### 4.4 Scene 2 — Hobby cards (auto-advance ≈2.5 s, loop forever)
Each card:
- The hobby **icon** (~48 × 48), sliding/scaling in with `lv.anim` (ease-out), with a glow pulse.
- Hobby **label** (montserrat_24, accent colour) centred under the icon.
- Index + tag line (montserrat_14): e.g. `3 / 9   HPR · 98 mm airframe`.
- **NeoPixels** set to the hobby's accent (solid or slow pulse).
- A 1–2 note **buzzer sting** (RTTTL fragments) on card enter.

| # | Hobby | Icon | Accent | Example tag line |
|---|---|---|---|---|
| 1 | High-power rocketry | rocket | orange `0xFF8800` | `HPR · 98 mm airframe` |
| 2 | Beer brewing | beer mug | amber `0xFFB000` | `all-grain · malts & hops` |
| 3 | 3D printing | printer hot-end | cyan `0x00FFFF` | `Voron · PLA/PETG` |
| 4 | Lathe / metalworking | lathe + swarf | silver `0xC0C0C0` | `turning steel` |
| 5 | Electronics | PCB / resistor | green `0x39FF14` | `KiCad · solder smoke` |
| 6 | Amateur radio | radio waves | magenta `0xFF00FF` | `ON4BDS · HF/VHF` |
| 7 | Weather balloons | balloon + payload | yellow `0xFFE700` | `near-space telemetry` |
| 8 | Trumpet | trumpet | gold `0xFFD000` | `Bb · bright tone` |
| 9 | Home Assistant | HA logo | HA blue `0x18BCF2` | `smart home automation` |

### 4.5 Controls (working buttons only; MENU not used)
| Button | Action |
|---|---|
| **A** | next hobby |
| **B** | back to menu (NeonLauncher) |
| **X** | toggle sound on/off |
| **Y** | previous hobby |
| **START** | back to menu (NeonLauncher) |

---

## 5. File-by-file specification

### 5.1 `/main.py` (new boot entry)
```python
# Fri3d Badge boot entry — runs the neon launcher menu as the default program.
# Delete this file and reset to restore the original REPL-only main.py (self-healing).
import logging
from fri3d.application import Application
logging.basicConfig(level=logging.WARNING, force=True)
Application(default_app='user.neon_launcher').run()
```

### 5.2 `/user/neon_launcher/`
**`app.json`**
```json
{ "name": "Badge Menu", "cls": "NeonLauncher", "hidden": true }
```
**`__init__.py`** — `from .neon_launcher import NeonLauncher`

**`neon_launcher.py`** — `NeonLauncher(App)`:
- `async start()`:
  1. `apps = [a for a in self.app_manager.apps.values() if not a.hidden]` + an explicit
     "Exit to REPL" entry.
  2. Build a neon vertical list (title "BADGE" + one focusable row per app). Use the
     **default lvgl group** already created by `Indev`, so X/Y (`PREV`/`NEXT`) move focus and
     A (`ENTER`) activates — no MENU involved.
  3. On select of an app: `await self.app_manager.run_app(app.id)`. When it returns, **rescan
     + redraw** the menu (apps loaded once per boot won't hot-replace) and loop.
  4. "Exit to REPL": `return` so `Application.run()` ends → `>>>`.
- Draw with neon styles (black bg, cyan rows, magenta highlight on focus).

### 5.3 `/user/name_badge/`
**`app.json`**
```json
{
  "name": "DAVID",
  "cls": "NameBadge",
  "hidden": false,
  "config": {
    "first": "DAVID",
    "last": "STEEMAN",
    "callsign": "ON4BDS"
  }
}
```
**`__init__.py`** — `from .name_badge import NameBadge`

**`art.py`** — pixel-art data + encoder (see §5.4).

**`name_badge.py`** — `NameBadge(App)`:
- `async start()`:
  1. Read `self.config` for name strings.
  2. Pre-render the **DAVID** title bitmap + the 9 icons to RGB565 bytearrays via `art.py`
     (once, at entry).
  3. Show the intro scene (~3 s) with animations, LEDs, jingle.
  4. Enter the hobby-card loop: for each hobby, animate icon in, set label/tag/LEDs/buzzer,
     `await asyncio.sleep_ms(2500)` (unless A/Y preempt), repeat forever.
  5. Watch buttons each tick (raw pin level for responsiveness, per §2.2): A→next, Y→prev,
     X→toggle sound, B/START→`return` (back to launcher).
- `async stop()`: clear LEDs, silence buzzer, delete the screen objects/animations it created
  (so the launcher can redraw cleanly).

### 5.4 `art.py` — pixel-art encoding scheme
Icons and the title are authored as **lists of equal-length strings** over a 1-character
palette alphabet, then converted to RGB565 once. Example (rocket, schematic — final art
authored during implementation):

```python
PALETTE = {
    '.': None,            # transparent
    'k': 0x000000,        # black outline
    'o': 0xFF8800,        # orange body
    'y': 0xFFE700,        # yellow flame
    'w': 0xFFFFFF,        # white highlight
}

ROCKET = [
    "......w......",
    ".....www.....",
    "....wooooow..",
    "...wooooooow.",
    "...wookkooow.",
    "...wooooooow.",
    "...wooooooow.",
    "....wooooow..",
    ".o..w.oo.w..o",
    "oo..w.oo.w.oo",
    ".....yyyy....",
    "......yy.....",
]
```

```python
def _rgb565(rgb):
    r, g, b = (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def to_rgb565(grid, palette):
    h = len(grid); w = len(grid[0])
    buf = bytearray(w * h * 2)
    i = 0
    for row in grid:
        for ch in row:
            rgb = palette.get(ch)
            if rgb is None:
                buf[i] = 0x00; buf[i+1] = 0x00   # black/transparent placeholder
            else:
                c = _rgb565(rgb)
                buf[i] = c >> 8; buf[i+1] = c & 0xFF   # byte order confirmed in Step-1 probe
            i += 2
    return buf, w, h
```

Rendering uses the **Step-1-confirmed** API:
- **Preferred:** `lv.image` + `lv.image_dsc_t({header:{cf:…, w:w, h:h}, data_size:len(buf), data:buf})`
  + `img.set_src(dsc)`. Swap `dsc` to change icon (cheapest path for animation; keeps all 9
  ~4.6 KB bytearrays alive in µPy heap).
- **Fallback:** `lv.canvas` + `set_buffer(buf,w,h,cf)` then `set_px`/`fill_bg`.
- Icons authored **at display size (~48 × 48)** so no `set_scale` zoom is required (avoids an
  extra unverified API). The **DAVID** title authored ~200 × 56 the same way.

---

## 6. Step 1 — On-device verification gate (run before writing app code)

Connect to `/dev/ttyACM0`; wait ~60 s, send Enter for `>>>`. Via the paste runner, run a probe
that prints:

1. `os.listdir('/')`, `/fri3d`, `/user`, `/examples`; `import fri3d.version` (if present).
2. `from fri3d.application import Application, App, AppInfo, Managers` — does it import?
3. Fonts: `hasattr(lv,'font_montserrat_{14,16,24}')`.
4. Canvas/image API: try in turn and echo the exact working call:
   - `c = lv.canvas(scr); c.set_buffer(bytearray(8*8*2),8,8,lv.COLOR_FORMAT.RGB565); c.set_px(0,0,lv.color_hex(0xFF00FF)); c.fill_bg(lv.color_hex(0), lv.OPA.COVER)`
     (also try the `draw_buf` variant if `set_buffer` is absent);
   - `d = lv.image_dsc_t({'header':{'cf':lv.COLOR_FORMAT.RGB565,'w':8,'h':8},'data_size':128,'data':bytearray(128)}); im = lv.image(scr); im.set_src(d)`
     (probe the exact dict key names; v9 uses `header.cf/w/h`);
   - `im.set_scale(512)` if zooming is wanted.
5. `gc.mem_free()`.

**Branching logic:**
- **App framework imports + a canvas *or* image path works** → proceed with the full design (§3–5).
- **`fri3d.application` broken/missing** → `import os, machine; os.chdir('/'); ` delete `/fri3d`
  (recursively) + `machine.reset()` to force a clean re-extract. If still broken, reflash the
  MicroPythonOS partition from `repos/badge_firmware/release-assets/` (restore is safe via the
  verified backup), then re-probe.
- **Neither canvas nor image works** → render icons procedurally with lvgl vector primitives
  (`lv.draw_*` on a canvas layer) or, last resort, fall back to Launch-option-B (a standalone
  boot `main.py` that runs the animation directly, no menu) so the core ask still ships.

---

## 7. Deployment & iteration

1. Recreate the paste-mode runner as **`tools/badge_run.py`** (subcommands: `probe`,
   `upload <local> <remote>`, `run <remote>`, `reset`). (The prior `/tmp/fri3d_run.py` was
   ephemeral; make a permanent copy in the project.)
2. Author the three packages in the project-side mirror `name_badge/{main.py, neon_launcher/*,
   name_badge/*}`, then upload each file to the matching `/user/…` (+ `/main.py`) path.
3. Hard-reset, confirm it boots into NeonLauncher, select **DAVID**, watch the animation.
4. Tune timings/colours/sounds by editing `name_badge.py`/`art.py` and re-uploading, then
   **reset between edits** (loaded modules aren't hot-replaced — see `AppManager.scan`
   docstring).

---

## 8. Verification checklist (end-to-end)

1. **Probe (§6)** prints clean `fri3d.application` import + a working canvas/image call + free mem.
2. Reset → **NeonLauncher** shows the menu; X/Y moves the highlight, A selects.
3. Select **DAVID** → intro name screen plays → hobby cards cycle 1→9 and loop; LEDs + buzzer
   sync with each card; controls work (A next, Y prev, X mute, B/START back to menu).
4. Select **Exit to REPL** → drops to `>>>`; re-`import main` re-runs the menu.
5. Power-cycle → menu is still the default boot program (persistence).
6. **Restore path confirmed available** (not run unless requested):
   `esptool --port /dev/ttyACM0 write_flash 0x0 backups/fri3d-badge-2024_full-flash_2026-07-02.bin`
   returns the badge to its original Retro-Go-booting state.

---

## 9. Risks & fallbacks

| Risk | Mitigation |
|---|---|
| `fri3d.application` broken on-device | Re-extract `/fri3d`; else reflash MicroPythonOS (verified backup makes it safe). Last resort: standalone boot `main.py` (no menu). |
| canvas/image µPy API differs from expectation | Step-1 probe picks the working call; procedural lvgl drawing as further fallback. |
| 24 px font too small for secondary text | Title is pixel-art; montserrat 16/24 is sufficient for labels/callsign. |
| lvgl heap (64 KB) pressure | Keep icons small; hold buffers in µPy heap (PSRAM); never a full-screen canvas. |
| Modules not hot-replaced after edits | Reset between edits (documented constraint). |
| Broken MENU button | Navigation uses A/X/Y/START only; MENU never required. |

---

## 10. Out of scope (unless requested later)

- Interactive games / GBA-style content; Wi-Fi; the SAO / P2 connectors (pinouts still
  UNVERIFIED); reflashing official firmware (only if the §6 probe forces it); sound via the
  Communicator I²S DAC (using the on-board buzzer only).

---

## 11. Pointers

- Proven reference: `hardware_test.py` (project root). Animation reference:
  `repos/badge_2024_micropython/fri3d/fri3d_application/src/payload/fri3d/apps/splash/splash.py`.
- Framework source: `repos/badge_2024_micropython/fri3d/fri3d_application/src/payload/fri3d/application/`
  (`app.py`, `app_manager.py`, `application.py`, `app_info.py`).
- Badge hardware API: `…/payload/fri3d/badge/{buttons,buzzer,leds,display,i2c,joystick}.py`.
- This project's master reference: `BADGE.md`; pinout: `pinout.md`; session log: `changelog.md`.
