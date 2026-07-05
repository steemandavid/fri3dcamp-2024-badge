# Fri3dcamp 2024 badge — backup, full pinout, firmware ID & reference docs — 2026-07-02

Connected a **Fri3d Camp 2024 badge** ("Badge 2024", ESP32-S3) over USB, identified its serial port, and
made a **verified full-chip flash backup** so the stock firmware can be reflashed freely and later
restored byte-for-byte. The dump had to work around an ESP32-S3 USB-Serial/JTAG reliability quirk
(the stub flasher drops packets on large reads) — solved with ROM-mode (`--no-stub`) chunked reads.

Then documented the complete pinout (back-of-PCB silkscreen, cross-checked against the official Fri3d
pin files), identified the running firmware by probing the serial console — it boots the **Retro-Go**
emulator launcher alongside a **MicroPython** partition — and wrote a comprehensive reference doc
(`BADGE.md`) plus memory notes for future sessions.

## System Info
- **Device:** Fri3d Camp 2024 badge — "Badge 2024" (board codename "fox"; not "Flamingo" — that's the BFG add-on), ESP32-S3-WROOM-1, **N16R8V** variant
- **Chip:** ESP32-S3 (QFN56), rev v0.1 · **MAC `34:85:18:ab:df:0c`** · 240 MHz, Wi-Fi + BT5 LE
- **Flash:** **16 MB** (GigaDevice `c8:4018`), quad data lines, 3.3 V
- **PSRAM:** 8 MB (OPI, `AP_3v3`)
- **USB port:** **`/dev/ttyACM0`** — Espressif USB JTAG/serial debug unit, **VID:PID `303a:1001`**
  - Stable by-id path: `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:AB:DF:0C-if00`
  - Native **USB-Serial/JTAG** (ESP32-S3 built-in USB peripheral — no UART bridge chip, so `ttyACM*` not `ttyUSB*`)
- **Access:** user `john` is in the `dialout` group (node is `root:dialout`, mode `0660`) — opens without sudo
- **Tool:** `esptool` **v5.3.1** at `~/.local/bin/esptool` (note: v5.x uses kebab-case flags — `read-flash`, `flash-id`, `--before default-reset`, `--after hard-reset`; old snake_case still works but warns)

## 1. Identified the badge + port
- Researched the badge: ESP32-S3-WROOM-1 N16R8V (16 MB flash, 8 MB PSRAM), USB-C, 115200 baud console;
  board "Fri3d Badge 2024 (ESP32-S3-WROOM-1)" in the `badge_2024_arduino` package. Arduino sketches need
  `ARDUINO_USB_CDC_ON_BOOT=1`; main firmware + MicroPython partition at `0x410000`.
- Found it on the bus: `Bus 003 Device 061: ID 303a:1001 Espressif USB JTAG/serial debug unit` → `/dev/ttyACM0`.
  Triple-confirmed via VID:PID, the Espressif `34:85:18` MAC OUI in the by-id name, and CDC (`ttyACM`) vs bridge (`ttyUSB`).
- `esptool flash-id`: ESP32-S3, 16 MB flash detected, MAC matches.

## 2. Full-chip backup (the non-trivial part)
A naive `read-flash 0 0x1000000` **failed**: the ESP32-S3 **stub flasher drops packets over the
USB-Serial/JTAG link on reads > ~512 KB** — fatal error `A fatal error occurred: Packet content transfer
stopped` (flaky even at default 115200 baud, worse at 921600; the dump died anywhere from 0 % to 4.7 %).
Empirically the threshold is between 512 KB (ok) and 1 MB (fail) for the stub.

**Working method:** ROM mode (`--no-stub`, which is reliable but slower ~70 KB/s) in **8 × 2 MiB chunks**,
chained with `--before no-reset` so the chip stays in download mode between reads and the **firmware never
boots** mid-backup (flash stays static → consistent dump):
```bash
mkdir -p parts && cd parts
for i in 0 1 2 3 4 5 6 7; do
  off=$(( i * 2097152 ))
  b="no-reset"; [ "$i" = 0 ] && b="default-reset"
  esptool --port /dev/ttyACM0 --no-stub --before "$b" --after no-reset \
          read-flash --no-progress "$off" 2097152 "part_$(printf '%03d' $i).bin"
done
cat part_*.bin > ../fri3d-badge-2024_full-flash_2026-07-02.bin
```
**Verification:** re-read all 8 chunks *still in download mode* (no app boot) and `cmp`'d each —
**all 8 matched byte-for-byte**, and the re-assembled image produced the **identical SHA-256** as the dump.
Image header begins `e9 04 02 4f …` (valid ESP32 image magic `0xE9`).

## 3. Artifacts
All under `~/claudecode/projects/fri3dbadge2024/backups/`:
| File | Size | Notes |
|---|---|---|
| `fri3d-badge-2024_full-flash_2026-07-02.bin` | 16 MiB (16,777,216 B) | full chip `0x0`–`0x1000000` |
| `fri3d-badge-2024_full-flash_2026-07-02.bin.sha256` | — | `7c3c34b1eaf4fdd9918b86cb04421c0715af5d02c9699a4d7123cc6a0006c5c7` |
| `RESTORE.md` | 3.1 K | restore command + re-dump recipe + gotchas |

Chunk dirs (`parts/`, `verify/`) were removed after verification — the single `.bin` is the verified artifact.

## 4. Restore (flash the original firmware back)
```bash
esptool --port /dev/ttyACM0 --before default-reset --after hard-reset \
        write_flash 0x0 fri3d-badge-2024_full-flash_2026-07-02.bin
```
Rewrites bootloader + partition table + all partitions exactly. **eFuses/MAC are not in the image and are
never modified** — badge keeps `34:85:18:ab:df:0c`. Writes are host-paced and usually reliable; if a write
hits the same `Packet content transfer stopped`, leave baud at default and just retry. Manual download mode:
hold **BOOT**, press **RESET**, release **BOOT**.

## 5. Full pinout (silkscreen + official source)
Read the back-of-PCB silkscreen off the photos in `Pictures/` (3× JPG, analyzed visually) and
**cross-checked every pin against the official** `Fri3dBadge_pins.h` + `pins_arduino.h` in
[`Fri3dCamp/badge_2024_arduino`](https://github.com/Fri3dCamp/badge_2024_arduino) (variant
`fri3d_2024_esp32s3`, fetched via `curl`/`gh`) — they match exactly, including USB VID:PID `303a:1001`.

| Subsystem | GPIO(s) |
|---|---|
| Buttons | A=39, B=40, X=38, Y=41, MENU=45, START=0 (=BOOT) |
| Joystick | X=1, Y=3 (analog, ADC1) |
| LCD (GC9307/ST7789, 296×240, HSPI 80 MHz, BGR) | MOSI=6, SCLK=7, MISO=8, CS=5, DC=4, RST=48 |
| NeoPixels | **5× WS2812** on GPIO12 |
| Audio / IR | buzzer ("Zoemer")=46; IR blaster=10 (via audio jack); IR receiver=11 |
| IMU WSEN-ISDS (I²C addr 0x6B) | SDA=9, SCL=18, INT=21 |
| microSD | CS=14 (shared SPI) |
| Battery monitor | 13 (ADC1_CH12) |
| UART0 | TX=43, RX=44 |

**12-pin expansion pinheader** (bottom edge, silkscreen "AREA 3001"):
`1 SCL(18) · 2 VSYS · 3 17 · 4 SDA(9) · 5 16 · 6 15 · 7 2 · 8 47 · 9 43 · 10 44 · 11 3.3V · 12 GND`
— the addon bus: power, I²C, UART, and the I²S mic cluster (15/47/17) for the Communicator addon.

**Other connectors:** audio/accessory jack (IO10, for the Blaster IR peripheral); microSD slot;
**P2 — 4-pin I²C STEMMA** (temp/humidity icon); **SAO 2×3 header** (`IO13 · LED · SCL · SDA · GND · V+`).
→ Full tables live in **`pinout.md`** (maintained).

## 6. Firmware / OS identification (what "GameBoy" is)
Probed the live console: hard-reset to app (RTS pulse via pyserial), captured boot log at 115200.
The badge boots into the **Retro-Go launcher** ([ducalex/retro-go](https://github.com/ducalex/retro-go) fork):
```
launcher v1.42-1+fri3d (Aug 13 2024)  built for: FRI3D-2024, type: dev   (ESP-IDF v5.2.2)
tabs: nes, gb, gbc, doom, favorite, recent   audio: Buzzer(46,32kHz)   batt:~4.13V   storage:/sd
```
The "GameBoy" screen is its `gb` tab — it emulates **GB/GBC/NES/SMS/Game Gear/ColecoVision/PC Engine/
Atari Lynx/Game & Watch** and runs **Doom**. Shipped firmware = [`badge_firmware_MicroPythonOS`](https://github.com/Fri3dCamp/badge_firmware_MicroPythonOS) = **MicroPythonOS** + **Retro-Go**.

**Live partition table (16 MB):**
| # | Label | Offset | Size | Contents |
|--:|---|--:|--:|---|
| 4 | micropython | 0x410000 | 3 MB | MicroPython / MicroPythonOS |
| 5 | launcher | 0x710000 | 1 MB | **Retro-Go — boots by default** |
| 6 | retro-core | 0x810000 | 640 KB | emulator cores |
| 7 | prboom-go | 0x8b0000 | 896 KB | Doom |
| 8 | vfs | 0x990000 | ~6.4 MB | LittleFS storage → `/sd` |

(plus otadata `0x9000`, nvs `0xb000`, ota_0 `0x10000`/2 MB, ota_1 `0x210000`/2 MB). ESP-IDF OTA scheme;
`otadata` selects the active app. **No SD card inserted** → storage is the internal `vfs` partition.
Audio plays via the buzzer (GPIO46, 32 kHz); WiFi is configured (`/sd/retro-go/config/wifi.json`).

## 7. Writing games / apps
Yes — multiple paths: load `.gb/.gbc/.nes` **ROMs** into `vfs`/microSD (or build your own GB ROM with
**GB Studio**/**GBDK**); write **MicroPython** apps (boot the `micropython` partition, drive the REPL over
`/dev/ttyACM0`); flash **Arduino C++** (`badge_2024_arduino`); **ESPHome** for Home Assistant; drop a
`DOOM1.WAD` for Doom. Fastest to a working game: MicroPython or GB Studio.

## 8. Documentation & memory artifacts
- **`pinout.md`** — full, maintained pin tables + connectors (P2/SAO flagged UNVERIFIED).
- **`BADGE.md`** — comprehensive self-contained handoff reference (identity, connection, pinout, firmware,
  backup, game-writing, repos, gotchas, next-session pointers).
- **Memory:** `fri3dcamp-2024-badge.md` (HW + flash quirk), `fri3dcamp-2024-badge-firmware.md`
  (Retro-Go + MicroPythonOS + games), both indexed in `MEMORY.md`.
- Serial probe script left at `/tmp/probe_badge.py` (pyserial: reset + boot capture + REPL poke).

## Notes / gotchas
- **Stub read unreliability** (§2): always `--no-stub` + chunked reads for dumps over USB-Serial/JTAG;
  the stub is fine for `flash-id`/small reads but not multi-MB ones.
- Speeds: stub ≈ 1.4 Mbit/s but unreliable on sustained reads; `--no-stub` ≈ 0.56 Mbit/s (~70 KB/s) but
  solid — a full 16 MB no-stub read in one session exceeds the 10-minute cap, hence the 2 MiB chunking.
- `--before no-reset` chaining is what keeps flash static across chunked reads (no app boot → no NVS writes).
- **esptool v5 kebab-case flags** (`read-flash`, `--before default-reset`); snake_case is deprecated.
- **P2 and SAO connector pinouts are UNVERIFIED** — inferred (no GPIO numbers on P2's silkscreen; SAO
  `LED`→21 and `IO13`→13 come from the pin file, not silkscreen). Confirm against the schematic before use.
- **Shared pins:** GPIO13 = battery ADC + SAO "IO13"; GPIO21 = LED_BUILTIN + IMU INT + SAO "LED".
- **5 WS2812 LEDs** (not 1) on GPIO12 — silkscreen just says "WS2812 LED".
- Firmware is a `type: dev` build; an OTA anti-rollback warning appeared at boot (benign, but rollback
  logic is active).
- **No SD card currently** → storage on internal-flash `vfs`; microSD slot available for more ROM space.
- **Not yet done:** actual reflashing / writing a game, or a round-trip restore test (write the backup back
  to confirm the restore path end-to-end). Paths offered; awaiting direction.

---

# Name correction + official-docs integration + local source clones — 2026-07-02 (cont.)

User flagged that the badge is **NOT called "Flamingo"**. Pulled authoritative info from the
product page (<https://fri3d.be/en/badge/2024/>) and followed its links to the official docs
site (<https://fri3dcamp.github.io/badge_2024/en/>) and the GitHub repos. Integrated the
findings into all project docs + the two auto-loading memory notes.

## Key correction
- The badge's official name is **"Badge 2024"** (internal board codename **"fox"** — firmware
  assets are `*_fox.*`). **"Flamingo"** = the **Big Flamingo Gun 9000 (BFG)** IR-blaster
  *add-on* ([`blaster_2024`](https://github.com/Fri3dCamp/blaster_2024)), a separate PCB.
  Removed every "Flamingo"→badge attribution across `BADGE.md`, `pinout.md`, and both memory files.

## Integrated from fri3d.be + docs site + repos
- **"Fri3d App"** is the default software — a main menu (OTA Update / MicroPython / Retro-Go;
  factory also shows "Hardware test"), navigated with X/Y/A/B. OTA update only works on the
  Fri3d Camp Wi-Fi. (This badge's probe still showed the Retro-Go launcher booting directly — a
  `type: dev` build whose active slot is the `launcher` partition.)
- **Reset/reflash paths** (docs `reset/`): web flasher <https://fri3d-flasher.vercel.app/> with
  `full_webflasher_fox.zip`, or esptool `write_flash ... 0x0 full_firmware_fox.img` from the
  [`badge_firmware`](https://github.com/Fri3dCamp/badge_firmware) releases (v1.0.1). Added as §5.1,
  distinct from the personal backup restore (§5.2).
- **Game Boy ROM upload** (`Retro--Go-Gaming/`): documented the Retro-Go Wi-Fi AP →
  <http://192.168.4.1/> web file manager → `roms/gb|gbc|nes` flow, plus microSD (FAT32, seed
  with `default_files_config_and_games.zip`) and friend-to-friend "Find games", and GB Studio.
  GBA is unsupported. (BADGE.md §6.1.)
- **MicroPython apps** (`micropython/`): documented the `main.py` + `fri3d` package + `user/`
  workflow, Fri3d ViperIDE / `mpremote` / Thonny editing, `boot.persist()` / `boot.main_menu()`,
  self-healing on delete, and the improved `main.py` pattern. (BADGE.md §6.2.)
- **Add-ons** (`onboarding/`, `flamingo/`): added §8 — Flamingo/BFG (`blaster_2024`, LANA TNY),
  Noisy Cricket (SAO), Communicator (`communicator_2024`, keyboard+mic+MAX98357A DAC).
- **Repo list** corrected/expanded (§7): added `badge_2024` (docs source), `badge_firmware`
  (releases), `badge_firmware_MicroPythonOS`, `badge_retro-go`, `badge_2024_hw`; clarified
  `badge_2024_micropython` = MicroPython v1.23 fork (the default firmware source).

## Local source clones
Cloned the relevant Fri3d repos into `repos/` so the project holds a local copy of all badge
info (shallow `--depth 1`, ~606 MB total): `badge_2024` (docs/MkDocs source), `badge_2024_micropython`,
`badge_2024_arduino`, `badge_2024_hw` (design files + datasheets), `badge_firmware` (ESP-IDF
build source), `badge_firmware_MicroPythonOS`, `badge_retro-go`, `blaster_2024` (BFG),
`communicator_2024`, `Fri3dBadge`.

The prebuilt **firmware binaries** are GitHub Release assets (not in the git tree), so also
downloaded the `*_fox.*` (Badge 2024) assets from `badge_firmware` v1.0.1 into
`repos/badge_firmware/release-assets/v1.0.1/` — incl. `full_firmware_fox.img` (16 MB, the
official restore image; sha256 `53ad83492cbbe8f737d635d4b6ec44e645d1ecdf9bf5f8804cba0262126e51fe`,
distinct from the personal backup `7c3c34…`), `full_webflasher_fox.zip`, and the per-partition
`*_fox.bin` files. (`default_files_config_and_games.zip`, referenced for SD seeding, is not
attached to v1.0.1 — fetch from the docs/repo if needed.)

---

# Full repo history, SD-seed file, MicroPython hardware test — 2026-07-02 (cont. 2)

## 1. Un-shallowed all repos to full Git history
Converted every `repos/` clone from `--depth 1` to **full history** (no octopus-badge content
involved — none of the cloned repos are octopus; the octopus assets are firmware binaries, which
were not downloaded). All 10 repos now carry complete history + tags; `repos/` grew from ~606 MB
to ~996 MB. Verified none remain shallow.

## 2. SD-card seed files
The docs' `default_files_config_and_games.zip` is **referenced but never published** in any
`badge_firmware` release (checked v1.0.1 / v1.0.0 / v0.1.5 / v0.1.4) nor in the `badge_retro-go`,
`badge_2024_micropython`, `badge_2024_arduino`, or `badge_2024_hw` releases. The actual default
files + games + wifi config are baked into the LittleFS image **`vfs_fox.bin`** (release v0.1.5) —
downloaded to `repos/badge_firmware/release-assets/v0.1.5/vfs_fox.bin` (6.5 MB). Updated BADGE.md
§6.1 to state this plainly instead of pointing at a non-existent zip.

## 3. MicroPython hardware test/demo — `hardware_test.py`
Wrote a single-file MicroPython program (project root) that tests & demonstrates all on-board
hardware. Studied the authoritative `fri3d` package API from the cloned source
(`badge_2024_micropython/fri3d/.../payload/fri3d/badge/*` + `examples/*`) rather than guessing:
- **LCD** via lvgl v9 (`lvgl_esp32.Wrapper(display); lv.screen_active()`; loop with
  `lv.timer_handler()`), live dashboard updating ~5 Hz.
- **5× NeoPixels** (`fri3d.badge.leds.leds`, NeoPixel subclass) — continuous rainbow + B-triggered chase.
- **Buzzer** (`fri3d.badge.buzzer.buzzer`, PWM) — raw `duty_u16` tones (X held = 440 Hz) + an RTTTL
  melody via `fri3d.rtttl.RTTTL(...).play()` (A button).
- **Buttons** (`fri3d.badge.buttons.buttons`; `.value()` → 1=pressed), edge-detected.
- **Joystick** (`fri3d.badge.joystick.joystick.{x,y}.read()`) + Y-button re-centre.
- **I²C** (`fri3d.badge.i2c.i2c`) scan + WSEN-ISDS WHO_AM_I @0x6B.
- **Battery** (ADC GPIO13), **IR receiver** (GPIO11), **microSD** mount check, **system info**.
- MENU → cleanup (LEDs/buzzer off) + `boot.main_menu()`. Syntax-checked with `py_compile`.
Run: `mpremote connect /dev/ttyACM0 run hardware_test.py`. Documented in BADGE.md §6.2.

---

# Ran the MicroPython HW test on the badge + live IMU — 2026-07-03

Goal: actually run `hardware_test.py` on the badge and demonstrate every subsystem; then add a
live IMU (accel/gyro) readout. This turned into a deep dive on the badge's boot/OTA scheme
because the **MENU button is physically broken**.

## 1. Boot selection is ESP-IDF OTA (the key to everything)
Parsed the partition table (from backup @0x8000 and `partition_table_fox.bin`): the app slots are
`ota_0`/`ota_1` = the Fri3d App **menu** app (identical images), `ota_2` = label **"micropython**",
`ota_3` = label **"launcher"** (Retro-Go). `otadata @0x9000` selects the slot
(`slot = (ota_seq-1) % 4`); if both entries are invalid the bootloader falls back to `ota_0`.
The badge originally booted Retro-Go because the menu app (ota_0) auto-launches it. All four app
partitions are populated/valid (magic 0xE9).

## 2. Broken MENU workaround
MENU is only used to (a) exit Retro-Go (START+MENU) and (b) as the menu app default — **menu
navigation itself uses Y (down) + A (choose)**, so the broken MENU doesn't block selecting
MicroPython. Writing `ota_data_fox.bin` (0xFF) to 0x9000 made the menu app *show* the menu
(instead of auto-launching Retro-Go); from there Y+A selected MicroPython.

## 3. OTA anti-rollback bit me
After my first manual otadata→ota_2 attempt (and after a `machine.reset()`), the badge rolled
**back to the menu** — a newly-selected OTA app boots "pending verify" and reverts unless
`esp32.Partition.mark_app_valid_cancel_rollback()` is called. Fix: after entering MicroPython,
run that once to persist it. (Confirmed stable resets afterward.)

## 4. Interrupted fri3d extraction → ImportError
My manual otadata attempt had interrupted the first MicroPython boot, leaving `/fri3d/badge/`
**empty** → `ImportError: no module named 'fri3d.badge.*'` (`fri3d.rtttl` still imported — it's
frozen into the firmware). Root cause in `p0tat0/sys/flash.py`: extraction only re-runs if a
top-level item is *absent* from `/`. **Fix: delete `/fri3d` recursively + `machine.reset()`** →
boot.py re-extracted the full package; all `fri3d.badge.*` imports then worked.

## 5. Driving the REPL without mpremote
`mpremote` isn't installed (system Python is PEP-668 externally-managed). Wrote a small pyserial
**paste-mode runner** (`/tmp/fri3d_run.py`, ephemeral): subcommands `probe`/`test`/`run`/`stop`.
Paste mode (Ctrl-E … Ctrl-D) streams output and the program keeps running after detaching (raw-REPL
exec would block on the infinite loop). Note: the REPL is on the USB-Serial/JTAG (ttyACM0) but is
**silent for ~60 s** on first boot during package extraction — send Enter to elicit `>>>`.

## 6. Got the full dashboard running — all hardware verified
`hardware_test.py` now runs cleanly on the badge. Verified working: LCD live dashboard, 5×
NeoPixel rainbow + B-triggered chase, buzzer (X-hold tone + A RTTTL "Take On Me"), all 6 buttons,
2-axis joystick (X/Y), I²C scan, battery (GPIO13 ADC), IR receiver (GPIO11), microSD check,
system info. Controls: A=melody, B=LED chase, X=hold-tone, Y=re-centre, START=quit-to-REPL.
- **Quirk:** `fri3d`'s `DebouncedButton.value()` returns 1 on press then auto-clears after ~200 ms
  (edge-oriented) — for a live held-level read the raw `b._pin.value()` (pull-up: 0 = pressed).

## 7. Added live IMU (WSEN-ISDS) accel + gyro
The `fri3d` package has no IMU driver, so drove the WSEN-ISDS directly over I²C using registers
from the cloned Arduino driver (`badge_2024_arduino/.../artificial_horizon/lib/WSEN_ISDS/`):
- Addr **0x6B**, device-ID reg 0x0F = **0x6A** (confirmed live), accel block @**0x28**, gyro block
  @**0x22** (6 bytes each, signed int16 LE).
- Enable: CTRL3(0x12)=0x44 (BDU+IF_INC), CTRL1(0x10)=0x50 (accel 208 Hz ±2 g),
  CTRL2(0x11)=0x50 (gyro 208 Hz ±250 dps). Scale: ±2 g → 16384 LSB/g; ±250 dps → 8.75 mdps/LSB.
- Verified at rest: accel `(-0.00, -0.03, -0.99) g` (gravity on Z), gyro ≈ 0 dps. Dashboard now
  shows two live lines (Acc g / Gyro dps) that respond to tilt/rotation.

## Artifacts / state
- `hardware_test.py` (project root) — verified-working all-hardware MicroPython demo (LCD, LEDs,
  buzzer, buttons, joystick, IMU live, battery, IR, SD, sysinfo).
- Memory note added: `fri3d-badge-running-micropython.md` (+ indexed in MEMORY.md).
- `BADGE.md` §6.2 updated with operational notes + current-state/revert guidance.
- **Badge currently boots into MicroPython** (otadata→ota_2, persisted) — LCD blank at power-on
  (REPL on USB). Revert to original Retro-Go boot:
  `esptool --port /dev/ttyACM0 write_flash 0x0 backups/fri3d-badge-2024_full-flash_2026-07-02.bin`
  (or write `ota_data_fox.bin` 0xFF to 0x9000 for the menu fallback).

## Notes / gotchas
- ESP32-S3 bootloader logs go to UART0 (GPIO43/44), **not** the USB-Serial/JTAG — so a failed boot
  is *silent* on ttyACM0; use `esptool flash-id` to confirm the chip is alive in download mode.
- `from fri3d import boot` fails on this build — use `esp32.Partition` directly for boot control.
- LCD init is one-shot per boot (can't tear down); reset between runs of the dashboard.

---

# Built the neon-arcade name-badge app (DAVID / ON4BDS) — 2026-07-04

Implemented and deployed the neon-arcade name + hobby animation as a real, selectable
program in the badge's MicroPython OS, per `name_badge_design.md`. Owner: **David
Steeman**, callsign **ON4BDS**. The badge now boots straight into a neon app-picker menu.

## 1. On-device probe (spec §6) — all green
- `from fri3d.application import …` imports cleanly; `from fri3d import boot` works (the
  old "fails" note is **stale** — a prior `/fri3d` re-extract fixed it). `fri3d.version`
  = `0.1.3-develop.1+build.0` (matches the repo). `/fri3d/application` present.
- Fonts: Montserrat **14/16/24** only (24 = max) → big title is pixel-art.
- **`lv.image` works**: `lv.image_dsc_t({"header":{"cf":RGB565,"w","h"},"data_size","data"})`
  + `set_src` + `set_scale` + `set_pos`. (`lv.canvas` also works; `set_px` needs a 5th
  `opa` arg.) RGB565/16-bit. `gc.mem_free()` ≈ 8.1 MB.

## 2. What was built (neon arcade)
- **`art.py`** — RGB565 framebuffer engine (`FB`: pixel/rect/line/circle/triangle/arc),
  a 5×7 bitmap font (`render_text` with optional glow halo), and 9 procedural hobby icons
  (rocket, beer, printer, lathe, electronics, radio, balloon, trumpet, homeassistant).
- **`name_badge.py`** (`App`) — intro: big pixel **DAVID** (cyan + blue glow), **STEEMAN**
  + **ON4BDS**, neon border, rainbow LEDs, ascending jingle (~3 s). Then loops 9 hobby
  cards: icon scale-in (ease-out), montserrat-24 label in the hobby's accent, tag +
  "n/9", NeoPixel pulse in accent colour, a 2-note buzzer sting. **Controls:** A=next,
  Y=prev, X=sound, B/START=back to menu (working buttons; MENU unused).
- **`neon_launcher.py`** (`App`) — the real app-picker (the shipped Launcher is a stub):
  lists all non-hidden apps + "Exit to REPL", X=down / Y=up / A=select, runs the chosen
  app via `app_manager.run_app()`, then re-wipes the shared screen and redraws.
- **`/main.py`** boot entry: `Application(default_app='user.neon_launcher').run()`.

## 3. Layout on the badge
```
/main.py                              boot entry (was: REPL-only; delete to restore)
/user/neon_launcher/{__init__,app.json,neon_launcher.py}
/user/name_badge/{__init__,app.json,name_badge.py,art.py}
```
Project-side mirror: `app/{main.py, neon_launcher/, name_badge/}`. Deploy/run tool:
`tools/badge_run.py` (paste / upload / run_for / reset / intr / cat).

## 4. Key engineering decisions
- **Single shared screen** (`lv.screen_active()`) + child-wipe between apps — NOT
  per-app `lv.obj()`/`screen_load`/`delete` (deleting the *active* screen crashes).
  `screen.clean()` confirmed working.
- Apps are **async + cooperative** (`await asyncio.sleep_ms`) because `Application` owns
  the lvgl tick loop; entrance motion is driven manually per-frame (no `lv.anim` needed).
- Buttons read via **raw pin level** (`b._pin.value()==0`) with own edge detection —
  independent of the indev's debounced latch.
- Icons rendered once to RGB565 bytearrays → `image_dsc_t`; animation = move/swap image
  widgets (cheap). Icons authored at 64×64, transparent→black on the black bg (no alpha
  needed). `fill_rect` bounds-clamped (the glow halo writes 1 px outside glyph bounds).

## 5. Verification (over serial — screen/buttons confirmed by ASCII previews + logs)
- All 9 icons + DAVID/STEEMAN/ON4BDS render correctly (ASCII previews captured).
- `NameBadge` under `Application` plays the intro then cycles hobbies 1→9 at the right
  ~3 s cadence, no errors (`hobby 1/9: rocket … 4/9: lathe` logged).
- `NeonLauncher` builds its menu cleanly (clean() works).
- **Badge boots into the launcher** on reset (Ctrl-C interrupts asyncio in
  `application.run` → REPL, confirming it was running).

## 6. Operational notes / gotchas
- **Module cache:** MicroPython caches imported modules; **reset the badge after any
  upload** to pick up changes (or `del sys.modules[…]`).
- **Don't talk to a badge mid-app** — paste/upload needs the REPL listening. Get to REPL
  first (Ctrl-C, or menu → "Exit to REPL", or the SAO dev-mode pin GPIO2→GND on boot).
- Recovery is always safe: `esptool --port /dev/ttyACM0 write_flash 0x0
  backups/fri3d-badge-2024_full-flash_2026-07-02.bin` restores the original Retro-Go
  state. Deleting `/main.py` + reset restores the original REPL-only boot.
- Menu shows "DAVID / Example / Nametag / Exit to REPL" (Example & Nametag are firmware
  stubs — selecting them is a no-op then returns). Could filter to user apps later.

## Artifacts
- `app/` — project-side source mirror (main.py, neon_launcher/, name_badge/).
- `tools/badge_run.py` (paste/upload/run_for/reset/intr/cat), `tools/probe.py`,
  `tools/render_test.py`, `tools/run_namebadge.py`, `tools/run_launcher.py`.
- Badge currently **boots into the NeonLauncher**; press **A** on DAVID to play.
- **Confirmed working by the user (2026-07-04):** the animation plays and the controls
  behave as intended. Neon name-badge app is complete and live on the badge.

---

# Published the code + wrote a companion blog post — 2026-07-04 (cont.)

## 1. GitHub repo
Published the project to **[steemandavid/fri3dcamp-2024-badge](https://github.com/steemandavid/fri3dcamp-2024-badge)**
(public). `git init` in the project dir with a `.gitignore` that excludes the 1.7 GB
`repos/` (upstream clones) and `backups/` (personal full-flash dump with ROMs/wifi).
Committed `app/`, `tools/`, `hardware_test.py`, `BADGE.md`, `pinout.md`,
`name_badge_design.md`, `changelog.md`, `Pictures/` + a new `README.md` (links the blog
post + the official Fri3dCamp repos). Pushed via `gh` (SSH, account `steemandavid`).

## 2. Blog post (steeman.be)
Wrote a general guide — *"Programming the Fri3d Camp 2024 Badge with Claude Code"* — at
`content/posts/programming-the-fri3d-badge-with-claude-code.md` (categories: Electronics,
ESP32, AI, DIY). Links **both** the official Fri3dCamp repos and the new app repo.
- Copied 2 board photos to `static/images/Fri3dBadge/`, resized with PIL (2.1 MB→212 KB,
  1.4 MB→110 KB). Hero = front; back silkscreen shot inline in the body.
- Published: `hugo --gc --minify` + `./scripts/deploy.sh --verify` (incremental FTP).
  Live: <https://www.steeman.be/posts/programming-the-fri3d-badge-with-claude-code/>.

## 3. Image-caption fix
First deploy had the two photos' captions swapped (I'd guessed wrong which source photo
was front vs back when copying). The markdown was internally consistent (filename matched
caption), so the fix was to **swap the two image files** (`badge-front.jpg` ↔
`badge-back.jpg`) — direction-agnostic, restores front-first ordering. Rebuilt + redeployed.

---

# Flashed the badge with ESPHome + integrated into Home Assistant — 2026-07-05

Turned the badge into a **Home Assistant** device by writing a full ESPHome 2026.6.2 firmware
config (`esphome/fri3d-badge.yaml`), flashing it over USB, and bringing up every peripheral —
including the GC9307 display (v2). The camp firmware is restored from the verified 16 MiB backup,
so the whole thing is reversible. Wi-Fi creds were recovered from an existing local ESP build
(`~/esp221-build/secrets.yaml`) — the badge's own Retro-Go `wifi.json` only held defaults.

## System / device state
- **Firmware now on the badge:** ESPHome 2026.6.2 (was: Fri3d NeonLauncher / Retro-Go). Board
  `esp32-s3-devkitc-1`, Arduino framework, 16 MB flash. App partition `0x10000`.
- **Network:** joins SSID **`politiezone-0526`** (FRITZ!Box mesh), gets ~`192.168.1.194`,
  hostname `fri3d-badge`. API `fri3d-badge.local:6053` (Noise encryption), OTA `:3232`.
- **HA:** FRITZ!Box integration shows `device_tracker.fri3d_badge`; ESPHome integration added by
  the user with the API key → ~20 live entities.

## 1. v1 — config, compile, flash, verify
- Wrote `esphome/fri3d-badge.yaml` + gitignored `esphome/secrets.yaml` (ESPHome auto-created
  `esphome/.gitignore` to exclude secrets + `.esphome/` build dir). Generated a fresh API key.
- Compiled, then `esphome upload … --device /dev/ttyACM0` (writes bootloader @0x0, partitions
  @0x8000, `boot_app0` @0x9000, app @0x10000). Verified boot + Wi-Fi join + API up via serial,
  and reachability (ping, ports 6053/3232, mDNS).

## 2. Driver gotchas discovered (all fixed in-config)
| Subsystem | Problem | Fix |
|---|---|---|
| **IMU** (WSEN-ISDS) | No `lsm6ds3` component; `lsm6ds:` isn't a YAML domain | Unified `motion` platform: `motion: - platform: lsm6ds` + `sensor: - platform: motion`. Chip = ST LSM6DS3 (WHO_AM_I `0x6A`) @ I²C `0x6B` |
| **NeoPixels** | `neopixelbus` pulls in legacy RMT → clashes with `remote_receiver`'s new RMT (`rmt_channel_t` redefined) → compile fail | `light: esp32_rmt_led_strip` (chipset WS2812, GRB, use_psram:false) + `addressable_rainbow`/`pulse`/`strobe` effects |
| **SPI keys** | `mosi`/`clk`/`miso` rejected | This version uses `mosi_pin`/`clk_pin`/`miso_pin` |
| **Battery** | GPIO13 is **ADC2_CH2** (pinout.md's "ADC1_CH12" is wrong) | Verified ADC2 reads fine on the S3 with Wi-Fi up; divider 2.0, 3.15–4.15 V = 0–100 % (template sensors for V + %) |
| **Display** | `st7789v` deprecated + fixed-model; its 240×320 native makes 296-wide fail "invalid offsets" | `mipi_spi` CUSTOM model — see §3 |

Confirmed live in HA: accel Z = −0.976 g (flat), gyro ~0, IMU temp 22.5 °C, joystick 1.3/1.7 V,
battery 3.92 V / 77 %, 6 buttons, NeoPixel light with effects.

## 3. v2 — GC9307 display bring-up (the hard part)
Iterated against photos the user dropped in `/storage/fileshare/`. The init/orientation was wrong
until I mined the **ground truth** from the running firmware:
- Source: `repos/badge_retro-go/components/retro-go/targets/fri3d-2024/config.h` — exact MADCTL,
  dimensions, SPI speed and init for this panel.
- Winning config: `mipi_spi`, `model: CUSTOM`, `dimensions: 296×240`,
  `transform: {swap_xy: true, mirror_x/y: false}` → **MADCTL 0x28** (MV|BGR), `data_rate: 40MHz`,
  `color_order: BGR`, `invert_colors: false`, ILI9341-style `init_sequence` (0xCF/0xED/0xE8/0xCB/
  0xF7/0xEA/0xC0/0xC1/0xC5/0xC7/0xB1/0xB6/0xF6/0xF2/0xE0/0xE1; ESPHome auto-adds SLPOUT/COLMOD/
  MADCTL/INVOFF/DISPON). User confirmed: text right-side-up, correct fill.
- SPI 80 MHz caused a 3.4 s main-loop stall on the first draw; dropping to **40 MHz** (Retro-Go's
  speed) cut it to 70 ms.

## Notes / gotchas
- **Wi-Fi:** first connection attempt auth-fails vs the strongest mesh BSSID then succeeds on
  retry every boot (~5 s, PMF quirk, self-heals).
- **Serial log quirk:** on this S3's USB-Serial/JTAG, log output stops after Wi-Fi connects (the
  full ~205-line boot dump prints, then silence). Read live sensor values from HA, not serial.
- **Restore camp firmware:** `esptool --port /dev/ttyACM0 write_flash 0x0 backups/fri3d-badge-2024_full-flash_2026-07-02.bin`
- **Docs updated:** `README.md` (ESPHome how-to + table row), `BADGE.md` §11 (driver notes),
  memory `fri3d-badge-esphome.md` (deep detail).
