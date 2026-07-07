# Group Nametag + Proximity Finder — Implementation Plan

**Status:** planning complete, not yet implemented. This document is a
self-contained handoff — everything a developer or LLM needs to build the
app without access to the conversation that produced it.

## 1. What this is

A MicroPython app for the **Fri3d Camp 2024 badge** ("Badge 2024", ESP32-S3)
that works as:

1. An **animated nametag**: shows a group's logo and the wearer's name.
2. A **proximity finder**: uses Bluetooth Low Energy to detect other badges
   running this same app that belong to the *same group*, and alerts the
   wearer when one comes within range — "who from my group is nearby."

It is **generic and redistributable**: any hackerspace/makerspace can flash
it onto their own Fri3d badges, set their own group name, member name, and
logo — via plain file edits, no code changes — and it will find *their*
people, filtering out badges from other groups. It was initially scoped
around a specific group ("Makerspace Baasrode") but has been deliberately
generalized so the group name, member identity, and logo are all
per-install configuration, not hardcoded.

It must coexist with this project's existing badge apps
(`../app/name_badge/`, a neon-arcade name badge; `../app/neon_launcher/`,
the app-picker that replaces the stock launcher) and be selectable from
that same picker — not replace it, not modify it.

## 2. Target hardware & firmware facts (verified, load-bearing)

These are hard constraints this plan was designed around — verify still
true before implementing if this doc is picked up much later.

- **Board**: Fri3d Camp 2024 Badge, ESP32-S3-WROOM-1 N16R8V (16 MB flash,
  8 MB PSRAM), MAC-addressed, USB-Serial/JTAG on `/dev/ttyACM0`.
- **Display**: GC9307 (ST7789-compatible), **296×240**, driven via lvgl
  (built into the firmware).
- **LEDs**: 5× WS2812 on GPIO12, exposed as `fri3d.badge.leds.leds`
  (`leds[i] = (r,g,b)`, `leds.fill((r,g,b))`, `leds.write()`, `leds.n == 5`).
- **Buzzer**: GPIO46, exposed as `fri3d.badge.buzzer.buzzer`
  (`buzzer.freq(hz)`, `buzzer.duty_u16(v)`, `0` = silent).
- **Buttons**: A/B/X/Y/MENU/START, exposed as `fri3d.badge.buttons.buttons`.
  **Read raw pin level for held-state**, not the debounced `.value()` (it
  auto-clears ~200 ms after press — edge-oriented). Pattern used by both
  existing apps:
  ```python
  def _held(name):
      b = getattr(buttons, name, None)
      return b is not None and b._pin.value() == 0   # pull-up: 0 = pressed
  ```
- **MicroPython**: v1.23 fork ([`badge_2024_micropython`](https://github.com/Fri3dCamp/badge_2024_micropython)),
  board `FRI3D_BADGE_2024`.
- **Bluetooth is compiled in and central+peripheral capable.** Confirmed by
  reading the actual board build config in the repo:
  - `ports/esp32/boards/FRI3D_BADGE_2024/mpconfigboard.cmake` includes
    `boards/sdkconfig.ble` in `SDKCONFIG_DEFAULTS`.
  - `boards/sdkconfig.ble` sets `CONFIG_BT_ENABLED=y`,
    `CONFIG_BT_NIMBLE_ENABLED=y`, `CONFIG_BT_CONTROLLER_ENABLED=y`.
  - `ports/esp32/mpconfigport.h` sets `MICROPY_PY_BLUETOOTH (1)`,
    `MICROPY_BLUETOOTH_NIMBLE (1)`, and critically
    `MICROPY_PY_BLUETOOTH_ENABLE_CENTRAL_MODE (1)` — i.e. the MicroPython
    `bluetooth` module (standard `bluetooth.BLE()` API, IRQ-based) supports
    scanning as well as advertising.
  - No `fri3d` package wrapper exists for BLE — talk to `bluetooth.BLE()`
    directly.
- **Image decoders are compiled into lvgl.** Confirmed in
  `fri3d/lvgl_esp32_mpy/binding/lv_conf.h`: `LV_USE_TJPGD 1` (JPEG),
  `LV_USE_LODEPNG 1` (PNG), `LV_USE_GIF 1`. **However** lvgl's filesystem
  layer (`lv_fs`) is *not* enabled for any real filesystem — only
  `LV_USE_FS_MEMFS 1` — `LV_USE_FS_STDIO/POSIX/FATFS/LITTLEFS` are all `0`.
  This means: decoding must happen from an **in-memory byte buffer**
  handed to lvgl (`lv.image_dsc_t`), not from an `lv_fs`-style path string
  like `"S:logo.png"`. This exact in-memory-decode call pattern is
  **unverified on this MicroPython binding** — see §7 Risks, spike this
  first.
- **A known-working raster image technique already exists** in this repo:
  `../app/name_badge/art.py`'s `fb_image()` wraps a raw RGB565 byte buffer
  in `lv.image_dsc_t` and it's been verified rendering on real hardware:
  ```python
  lv.image_dsc_t({
      "header": {"cf": lv.COLOR_FORMAT.RGB565, "w": w, "h": h},
      "data_size": len(buf),
      "data": buf,
  })
  im = lv.image(scr)
  im.set_src(dsc)
  im.set_pos(x, y)
  im.set_scale(256)   # 256 == 1.0x
  ```
  This is the **fallback** raster path if raw-PNG/JPEG-buffer decoding
  doesn't work out (§7).

## 3. Framework conventions to reuse (read these files before coding)

This app must follow the existing `fri3d.application` framework exactly
like the two existing apps do — reference implementations:

- `../app/name_badge/name_badge.py` — full example of: screen setup/wipe,
  label/rect helpers, raw-button polling, LED/buzzer helpers, an
  intro-then-loop `start()`/`stop()` structure, keeping image descriptors
  alive against GC (`self._keep.append(...)`).
- `../app/name_badge/art.py` — the `fb_image()` raster helper (§2) and a
  палитра of RGB565 colors.
- `../app/neon_launcher/neon_launcher.py` — the app-picker; **no changes
  needed here** — it lists every non-hidden app `AppManager` discovers, so
  a new app just needs a valid `app.json` in a scanned path.
- `../app/name_badge/app.json` and `../app/main.py` — the per-app config
  and boot-entry conventions.

Key framework facts, read directly from the framework source in
`repos/badge_2024_micropython/fri3d/fri3d_application/src/payload/fri3d/application/`:

- **`App` base class** (`app.py`): subclass it, implement `async def
  start(self)` (required) and `async def stop(self)` (optional cleanup).
  `self.config` is a read-only property returning exactly the `"config"`
  dict from that app's `app.json` — **this is the per-install
  configuration mechanism to use for group/name/handle/etc.**, no need to
  invent a separate config-file parser.
- **`AppManager`** (`app_manager.py`): on `.scan()`, walks
  `/remote/fri3d/apps`, `/remote/user`, `/fri3d/apps`, `/user`,
  `/sdcard/user`; any subfolder containing `app.json` becomes an app,
  keyed by its dotted path (e.g. `user.group_nametag`). It reads `app.json`
  once at boot — **editing `app.json` requires a device reset to take
  effect** (no hot-reload).
- **`app.json` schema**: `{"name": <menu label>, "cls": <class name to
  import from the package>, "hidden": <bool>, "config": {...}}`.

## 4. New project layout

Everything for this app lives in this folder
(`fri3dbadge2024/group-nametag/`), independent of the existing `app/` and
`tools/` trees at the project root:

```
group-nametag/
  PLAN.md                    (this file)
  README.md                  quick-start for any group adopting the app
  DESIGN.md                  BLE protocol spec + calibration notes
  app/
    group_nametag/
      app.json                 per-group/member config (see §5)
      __init__.py               from .group_nametag import GroupNametag
      group_nametag.py          the App: idle screen, alerts, buttons, lifecycle
      ble_proximity.py          BLE advertise/scan + group-aware state machine
      logo.png                  placeholder logo; each group replaces this file
  tools/
    convert_logo.py           fallback host-side (Pillow) image → RGB565 .bin
                               converter, used only if on-device decode (§7
                               risk 1) doesn't pan out
```

On-device this uploads to `/user/group_nametag/...`. Use this project's
existing `tools/badge_run.py upload <local> <remote>` (or ViperIDE /
mpremote) — it takes independent local/remote paths, so this folder's
location doesn't need to mirror the device path.

## 5. Config schema (`app.json`)

```json
{
  "name": "NAMETAG",
  "cls": "GroupNametag",
  "hidden": false,
  "config": {
    "group": "My Hackerspace",
    "name": "David",
    "handle": "ON4BDS"
  }
}
```

- `group` — free text, identifies the group for BLE filtering (hashed
  locally into a 2-byte ID, never transmitted as text — see §6). Two
  badges only alert on each other if this hash matches.
- `name` — display name, shown big on the idle screen and in proximity
  alerts.
- `handle` — optional secondary line (e.g. a callsign/nickname); may be
  empty string.

**Provisioning a new group or member — no code edits, ever:**
1. Copy the `app/group_nametag/` folder (rename if running multiple
   configs side by side isn't needed — one badge only needs one copy).
2. Edit `group`, `name`, `handle` in `app.json`.
3. Replace `logo.png` with the group's own logo image (see §7 for size
   guidance).
4. Upload the folder to `/user/group_nametag/` on the badge, reset.

## 6. BLE protocol (`ble_proximity.py`)

Isolate all BLE and wire-format logic from UI code so the encode/decode
functions are unit-testable on a host with plain `bluetooth`-module-free
Python (mock the byte-manipulation functions independently of the actual
`bluetooth.BLE()` calls).

### 6.1 Advertising payload

Non-connectable legacy advertising (31-byte budget). One manufacturer-
specific AD structure (AD type `0xFF`):

| Field | Size | Notes |
|---|---:|---|
| AD length | 1 | standard AD structure header |
| AD type | 1 | `0xFF` (Manufacturer Specific Data) |
| Company ID | 2 | placeholder `0xFFFF` (reserved/testing range — this is a hobby beacon, not seeking an assigned company ID) |
| App magic | 4 | fixed ASCII `b"HSNT"` ("Hackerspace NameTag") — identifies *any* badge running this app, regardless of group |
| Group ID | 2 | `fnv1a_16(group.strip().lower().encode())` — see §6.2 |
| Name length | 1 | length in bytes of the following field |
| Name | ≤17 | UTF-8 `name` (+ optionally `" " + handle`), **truncated** to fit the remaining legacy-adv budget (31 − 3 flags − 2 mfg-header − 2 company − 4 magic − 2 group − 1 namelen ≈ 17 bytes) |

Advertise with `gap_advertise(interval_us, adv_data=<payload>,
connectable=False)`.

### 6.2 Group hashing

```python
def fnv1a_16(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF
```
Normalize (`.strip().lower()`) before hashing so trivial formatting
differences between two members typing the same group name still match.
Document in `DESIGN.md` that this is a **collision-tolerant identifier,
not a security mechanism** — 16 bits is plenty at the scale of "a few dozen
hackerspaces show up to the same camp," not adversarial-safe.

### 6.3 Scanning & state machine

- Foreground-only: `gap_scan()` runs only while this app's `start()` loop
  is active; call `ble.active(False)` in `stop()` to fully release the
  radio.
- Duty-cycled, not continuous: e.g. active scan ~1.5 s every ~4 s (tunable
  constants), leaving headroom for the render loop and simultaneous
  advertising.
- `IRQ_SCAN_RESULT` handler: parse the manufacturer AD; verify the 4-byte
  magic; compare the 2-byte group ID against this badge's own
  `fnv1a_16(config.group)` — **mismatches are silently dropped** (this is
  the "find your own people" filter). On match, update a table:
  ```python
  seen[addr] = {
      "name": <decoded name>,
      "rssi_ewma": <exponential moving average of RSSI>,
      "last_seen_ms": <time.ticks_ms()>,
      "notified": <bool>,
  }
  ```
- **Range hysteresis**: two tunable RSSI thresholds, e.g.
  `RSSI_ENTER = -85`, `RSSI_EXIT = -95` (placeholder values — ~20 m indoor
  BLE RSSI is weak/noisy; these **must be field-calibrated** at the actual
  venue — document the calibration procedure in `DESIGN.md`: walk to the
  desired max alert distance, note the RSSI shown by the `A`-button detail
  view (§8), set `RSSI_ENTER` a few dB above it, `RSSI_EXIT` a few dB
  below).
- **Eviction**: entries with `last_seen_ms` older than a timeout (e.g. 8–10
  s of no adv seen) are dropped from `seen` even if RSSI was fine —
  handles the case of someone walking out of range faster than RSSI drops.
- **Notify-once-per-encounter**: crossing `rssi_ewma >= RSSI_ENTER` for an
  address with `notified == False` is a "new arrival" event → UI alert,
  then set `notified = True`. Eviction or dropping below `RSSI_EXIT`
  clears `notified` so a later return re-triggers.

## 7. Logo handling (`group_nametag.py`)

**Primary path — on-device decode (spike this first, §9):**
```python
data = open('logo.png', 'rb').read()   # or .jpg / .gif — whatever the group supplied
dsc = lv.image_dsc_t({
    "header": {"cf": lv.COLOR_FORMAT.RAW, "w": 0, "h": 0},   # exact cf/flags TBD by the spike
    "data_size": len(data),
    "data": data,
})
im = lv.image(scr)
im.set_src(dsc)
im.set_scale(<computed to fit a target box, e.g. 120x120>)
```
The exact `cf` enum value / whether width+height must be pre-known for the
registered PNG/JPEG decoders to pick up the buffer is **the thing the spike
must determine** — lvgl v9's decoder `info_cb` is supposed to sniff
dimensions from the encoded header, but the exact MicroPython binding
surface (`lv.COLOR_FORMAT.RAW` availability, whether `image_dsc_t` accepts
0/0 dimensions) is unverified here.

**Fallback path — host-side pre-conversion:** `tools/convert_logo.py`
(Pillow, run on a dev machine, not on the badge) resizes/quantizes any
image to RGB565 and writes `logo.bin`, decoded on-device with the
already-verified `fb_image()`-style raw-buffer technique from
`name_badge/art.py` (§2). Loader logic should try the raw image file
first, and use `logo.bin` if present/if raw decode raises.

**Robustness**: if decoding fails outright (bad file, unsupported format,
memory pressure), fall back to a small bundled placeholder image and log
the failure — a badge with a broken logo file should still boot as a
usable nametag, not crash.

**Size guidance** (document in `README.md`): keep source logos
≲300×300 px and ≲150 KB — the badge has 8 MB PSRAM so this is comfortable
headroom, not a hard limit, but keeps decode time and RAM snappy on a
microcontroller. `set_scale()` fits whatever resolution is supplied to the
actual on-screen box, so exact pixel dimensions don't matter.

## 8. UI / animation (`group_nametag.py`)

- **Idle screen**: logo centered upper-half, gentle continuous "breathing"
  scale animation (period ~2–3 s, e.g. `set_scale(240 + 16*sin(t))`) plus a
  fade/scale-in intro on `start()` — reuse the same time-based-loop pattern
  `name_badge.py`'s `_show_hobby()` intro animation already demonstrates,
  no new animation framework needed. `name`/`handle` rendered below as
  `lv.label` (Montserrat, reusing the `_label` helper pattern from
  `neon_launcher.py`/`name_badge.py`). A small muted-color line pinned near
  the bottom (`"nearby: Alice, Bob"`), refreshed every frame from
  `ble_proximity`'s current in-range set (empty → hidden or "nobody
  nearby").
- **Alert overlay**: on a new-arrival event, show a banner (`lv.label` +
  background rect, `name_badge`'s `_rect()` pattern) for ~2.5 s, flash the
  5 NeoPixels (reuse `leds`/`leds.fill`/`leds.write()` exactly as
  `name_badge.py` does for its hobby-card color), a short buzzer sting
  (reuse `buzzer.freq()`/`duty_u16()` + the `_sting()` pattern), then fade
  back to idle. The persistent nearby-list line is independent of this
  transient banner and keeps showing everyone currently in range.
- **Buttons** (raw-pin held-state polling, per §2):
  - `X` — toggle sound (mute/unmute alert buzzer, mirrors `name_badge`).
  - `A` — toggle a detail view of the nearby list (name + smoothed RSSI +
    seconds-since-last-seen per entry) — useful for on-site range
    calibration (§6.3).
  - `B` / `START` — return to the app-picker (mirrors both existing apps).
- **Lifecycle**:
  - `start()`: wipe/setup the shared screen (reuse the `_wipe()` pattern —
    `scr.clean()` with a manual child-delete fallback), load the logo
    (§7), read `self.config` for `group`/`name`/`handle`, call
    `ble.begin(group, name, handle)` (activates BLE, starts advertising,
    launches the periodic-scan `asyncio.Task`), then run the main
    poll/render `while True` loop (buttons → alerts → idle animation →
    `await asyncio.sleep_ms(30)`, matching the ~30 ms tick both existing
    apps use).
  - `stop()`: cancel the scan task, `ble.end()` (`BLE.active(False)`) so
    the radio is fully released before another app runs, clear LEDs/buzzer
    (mirrors `name_badge.stop()`), drop image/descriptor references so GC
    can reclaim them.

## 9. Build order / spikes

Do these two **before** building the full UI, since both are unverified
assumptions the rest of the design leans on:

1. **Logo decode spike**: paste a standalone script on-device that reads a
   real PNG (and separately a JPEG) file's raw bytes and attempts the
   §7 primary-path decode. Confirm it renders correctly. If it fails after
   reasonable troubleshooting, commit to the `convert_logo.py` fallback
   path instead and adjust `group_nametag.py`'s loader accordingly.
2. **Concurrent advertise+scan spike**: paste a standalone script that
   calls `gap_advertise()` and `gap_scan()` at the same time and confirms
   both work without crashing/hanging the NimBLE stack, over at least a
   few duty cycles. If unstable, fall back to alternating: advertise for a
   window, stop, scan for a window, repeat — instead of running both
   continuously.

Then build `ble_proximity.py` (with its own off-device unit tests for the
pure encode/decode/hash functions), then `group_nametag.py`'s UI on top,
then wire up `app.json` + `__init__.py`, then do the full on-device
integration test.

## 10. Verification checklist

- [ ] Logo decode spike passes (or fallback path is implemented and used)
- [ ] Concurrent adv+scan spike passes (or sequential fallback implemented)
- [ ] Off-device unit tests for `ble_proximity.py`: AD payload round-trip
      encode/decode, `fnv1a_16` group hashing (same name → same hash after
      normalization; different names → different hash in practice), name
      truncation at the byte-budget boundary
- [ ] Single-badge smoke test: idle screen renders (logo animates, name/
      handle shown); a phone BLE scanner (e.g. nRF Connect) sees the
      advertisement with correct magic/group-hash/name in the manufacturer
      data
- [ ] Proximity round-trip: a phone BLE advertiser (or second badge)
      broadcasting a **matching** group hash triggers the alert exactly
      once, shows up in the nearby list, and leaving+returning re-triggers
      exactly once
- [ ] A **mismatched** group hash is correctly ignored (no alert, not
      listed)
- [ ] Responsiveness: scan/advertise duty cycle doesn't visibly stutter
      the idle animation or delay button input
- [ ] App appears correctly in `neon_launcher`'s picker and returns
      cleanly to it on `B`/`START` (no leaked BLE activity — verify with a
      phone scanner that advertising stops after exiting)

## 11. Explicitly out of scope (for this iteration)

- Any fleet-provisioning tooling beyond copy-folder-and-edit-three-fields
  (fine at hobbyist/single-hackerspace scale; revisit if this sees wider
  adoption).
- Background/always-on detection while another app is in the foreground —
  by design (David's explicit choice): this app's BLE only runs while it's
  the active screen.
- Any authentication/security around group membership — the group hash is
  a convenience filter, not a trust mechanism; anyone can advertise a
  colliding/spoofed payload.
- Scan-response payload extension for longer names — not needed at the
  ~17-byte name budget for now; noted as a future option in `DESIGN.md` if
  it ever becomes a real constraint.
