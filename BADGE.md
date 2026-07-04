# Fri3d Camp 2024 Badge — Comprehensive Reference

Single-source handoff document for the **Fri3d Camp 2024 Badge** (official name
**"Badge 2024"**, internal board codename **"fox"**). Everything another Claude Code
session needs to understand the hardware, connect to it, back it up, load games, write
apps, and restore it. Consolidated from the 2026-07-02 sessions and cross-checked against
the official Fri3d documentation site.

> ⚠ **The badge is NOT called "Flamingo".** "Flamingo" / **Big Flamingo Gun 9000 (BFG)** is
> the name of an IR-blaster *add-on* ([`blaster_2024`](https://github.com/Fri3dCamp/blaster_2024)),
> a separate PCB you can plug into the badge. See §9.

> Cross-references in this project: `pinout.md` (maintained pin tables), `backups/RESTORE.md`
> (backup/restore), `changelog.md` (session log), `Pictures/` (board photos), `repos/`
> (local clones of the source repos).
> A verified full-flash backup exists — see §5 — so any experimentation is reversible.

> **Official sources** (read these first): product page <https://fri3d.be/en/badge/2024/> ·
> documentation site <https://fri3dcamp.github.io/badge_2024/en/> (MkDocs; source repo
> [`Fri3dCamp/badge_2024`](https://github.com/Fri3dCamp/badge_2024)).

---

## 1. Identity & quick facts

| | |
|---|---|
| **Device** | Fri3d Camp 2024 Badge — **"Badge 2024"** (board codename **"fox"**; `*_fox.*` firmware assets are for this board) |
| **SoC** | ESP32-S3-WROOM-1, **N16R8V** variant (QFN56, rev v0.1) |
| **CPU** | ESP32-S3, dual-core Xtensa LX7 + LP core, 240 MHz, Wi-Fi + BT 5 LE |
| **Flash** | **16 MB** (GigaDevice `c8:4018`), quad, 3.3 V |
| **PSRAM** | **8 MB** OPI (`AP_3v3`) |
| **MAC** | `34:85:18:ab:df:0c` (Espressif OUI — in eFuse, never in flash images) |
| **USB** | USB-C → **native USB-Serial/JTAG** (VID:PID `303a:1001`). No UART-bridge chip, so the device is `ttyACM*`, **not** `ttyUSB*`. |
| **Power** | USB-C + 2000 mAh LiPo (TP4056 charger). Battery voltage on GPIO13. |
| **Display** | 2" IPS LCD, GC9307 (ST7789-compatible), **296 × 240**, HSPI @ 80 MHz, BGR, no inversion |
| **Default software** | the **"Fri3d App"** — a main menu offering OTA Update / MicroPython / Retro-Go Gaming (see §4) |
| **Hardware rev** | Revision 01 = the version handed out at camp ([`badge_2024_hw`](https://github.com/Fri3dCamp/badge_2024_hw)) |

---

## 2. Connecting on this host (john-ai)

- **Port:** `/dev/ttyACM0`
- **Stable by-id path:** `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:AB:DF:0C-if00`
- **Permissions:** node is `root:dialout` mode `0660`. User `john` is in the `dialout` group → no sudo needed. If access fails: `sudo usermod -aG dialout $USER` then re-login.
- **Console baud:** 115200 8N1.
- **esptool:** `~/.local/bin/esptool`, **v5.3.1**. Note: v5.x uses **kebab-case** flags (`read-flash`, `flash-id`, `--before default-reset`, `--after hard-reset`); old snake_case still works but warns.
- **pyserial 3.5** is available to `/usr/bin/python3` for console scripting.
- `gh` and `curl` work for fetching from the Fri3dCamp GitHub repos.

### ⚠ Critical USB-Serial/JTAG gotcha (read this before any flash operation)
The ESP32-S3 **stub flasher drops packets over the native USB-Serial/JTAG link on reads
larger than ~512 KB** — fatal error `A fatal error occurred: Packet content transfer stopped`
(flaky even at default 115200 baud; worse at 921600). Implications:
- `flash-id` and small reads are fine with the stub.
- **Full-chip dumps must use ROM mode (`--no-stub`)** in ≤2 MiB chunks, chained with
  `--before no-reset` so the chip stays in download mode and the firmware never boots
  mid-read (keeps flash static). No-stub is ~70 KB/s but rock-solid. See §5.
- Writes (`write_flash`) are host-paced and usually reliable; if one fails, leave baud at
  default and retry.
- Manual download mode: hold **BOOT** (the START button = GPIO0), press **RESET**, release BOOT.

---

## 3. Pinout

Authoritative source: back-of-PCB silkscreen + official `Fri3dBadge_pins.h` / `pins_arduino.h`
in [`Fri3dCamp/badge_2024_arduino`](https://github.com/Fri3dCamp/badge_2024_arduino)
(variant `fri3d_2024_esp32s3`). The two agree on every pin. Maintained copy: `pinout.md`.

Highlights (full tables in `pinout.md`): 6 digital buttons (A=39, B=40, X=38, Y=41, MENU=45,
START=0), 1 analog 2-axis joystick (X=1, Y=3), LCD SPI 6/7/8 CS5 DC4 RST48, **5× WS2812**
(GPIO12), buzzer (GPIO46), IMU WSEN-ISDS I²C (SDA 9 / SCL 18, addr 0x6B, INT 21), microSD
(CS 14), battery monitor (GPIO13), UART0 (43/44).

The **audio/accessory jack** (silkscreen `IO10` / "Blaster") is where the **Big Flamingo Gun**
add-on plugs in (GPIO10) — it is an *add-on connector*, not a built-in blaster. The badge's
on-board IR receiver is GPIO11.

---

## 4. Firmware / operating system — the "Fri3d App"

The badge ships with the **"Fri3d App"** — firmware that presents a **main menu** on boot.
Navigate with **X** (up), **Y** (down), **A** (choose), **B** (back). Menu items:

- **OTA Update** — update the badge over Wi-Fi to the latest release (each partition is
  checked and updated if needed). *Note: this only works on the Fri3d Camp Wi-Fi network
  at the event.* After camp, update via the web flasher / esptool (§5.1).
- **MicroPython** — boot into the MicroPython environment (§6.2). Appears after the first
  OTA update; factory firmware shows a **"Hardware test"** item here instead.
- **Retro-Go Gaming** — the emulator launcher (§6.1).

> **What this specific badge actually boots into:** a serial probe (hard-reset to app, capture
> at 115200) caught the **Retro-Go launcher** booting directly:
> ```
> launcher v1.42-1+fri3d (Aug 13 2024)  built for: FRI3D-2024, type: dev   (ESP-IDF v5.2.2)
> tabs: nes, gb, gbc, doom, favorite, recent
> audio sink: Buzzer (GPIO46, 32 kHz)   battery: ~4126   storage: /sd (internal vfs, no SD card)
> ```
> So on this badge the active OTA slot is the `launcher` partition and it skips the menu (it is
> a `type: dev` build). **START+MENU** exits Retro-Go back to the Fri3d App menu.

**Retro-Go launcher** = an ESP32 retro-gaming frontend ([`ducalex/retro-go`](https://github.com/ducalex/retro-go)
fork; Fri3d derivative [`badge_retro-go`](https://github.com/Fri3dCamp/badge_retro-go)). It
emulates **Game Boy, Game Boy Color, NES, Sega Master System, Game Gear, ColecoVision, PC Engine,
Atari Lynx, Game & Watch**, and runs **Doom** (prboom). On the Fri3d badge only NES/GB/GBC/Doom
are activated. WiFi is configured (`/sd/retro-go/config/wifi.json`) for its web uploader / OTA.

### Live partition table (16 MB) — from the boot log
| # | Label | Offset | Size | Contents |
|--:|---|--:|--:|---|
| 0 | otadata | 0x9000 | 8 KB | OTA selection |
| 1 | nvs | 0xb000 | 20 KB | non-volatile storage |
| 2 | ota_0 | 0x10000 | 2 MB | OTA app slot |
| 3 | ota_1 | 0x210000 | 2 MB | OTA app slot |
| 4 | micropython | 0x410000 | 3 MB | MicroPython + `fri3d` package |
| 5 | launcher | 0x710000 | 1 MB | **Retro-Go launcher — active on this badge** |
| 6 | retro-core | 0x810000 | 640 KB | emulator cores |
| 7 | prboom-go | 0x8b0000 | 896 KB | Doom |
| 8 | vfs | 0x990000 | ~6.4 MB | LittleFS storage (ROMs, apps, saves) → mounted `/sd` |

ESP-IDF OTA scheme: `otadata` selects the active app partition.

---

## 5. Firmware backup & restore

### 5.0 — Your options at a glance
| Goal | Method |
|---|---|
| Restore **this exact badge's** flash (incl. your ROMs/saves/NVS) | §5 — write back the verified personal backup |
| Reset to the **latest official** "Badge 2024" firmware | §5.1 — web flasher or esptool `full_firmware_fox.img` |
| Update over the air | Fri3d App → OTA Update (**camp Wi-Fi only**) |

### 5.1 — Reset to official firmware (after camp / when things break)
Two official paths (from <https://fri3dcamp.github.io/badge_2024/en/reset/>):

**Web flasher** (Chrome/Edge only — not Firefox/Safari): download the latest
`full_webflasher_fox.zip` from <https://github.com/Fri3dCamp/badge_firmware/releases>, open
<https://fri3d-flasher.vercel.app/>, upload the zip, click "begin te flashen".

**esptool (command line)** — download `full_firmware_fox.img` from the
[`badge_firmware` releases](https://github.com/Fri3dCamp/badge_firmware/releases/latest):
```bash
esptool -p /dev/ttyACM0 -b 460800 --before default-reset --after no-reset --chip esp32s3 \
        write_flash --flash-mode dio --flash-size 16MB --flash-freq 80m \
        0x0 full_firmware_fox.img
```
Official docs use snake_case (`--before default_reset`); esptool v5 prefers kebab-case but
accepts both. If the badge keeps resetting, force download mode: **hold START (BOOT), press &
release RESET, release START.**

### 5.2 — Verified personal backup (restore *your* exact flash)
A **full 16 MiB chip dump** of this badge was made and **byte-for-byte verified** (re-read in
download mode, identical SHA-256). This is different from §5.1: it restores *your* flash
verbatim, including any games/saves/wifi config — not a clean official image.

- **File:** `backups/fri3d-badge-2024_full-flash_2026-07-02.bin` (16,777,216 bytes)
- **SHA-256:** `7c3c34b1eaf4fdd9918b86cb04421c0715af5d02c9699a4d7123cc6a0006c5c7`
- **Sidecar:** `backups/fri3d-badge-2024_full-flash_2026-07-02.bin.sha256`
- **Restore:**
  ```bash
  esptool --port /dev/ttyACM0 --before default-reset --after hard-reset \
          write_flash 0x0 backups/fri3d-badge-2024_full-flash_2026-07-02.bin
  ```
- **How the dump was made** (ROM mode, chunked, because of the §2 stub quirk):
  ```bash
  for i in 0 1 2 3 4 5 6 7; do
    off=$(( i * 2097152 ))
    b="no-reset"; [ "$i" = 0 ] && b="default-reset"
    esptool --port /dev/ttyACM0 --no-stub --before "$b" --after no-reset \
            read-flash --no-progress "$off" 2097152 "part_$(printf '%03d' $i).bin"
  done
  cat part_*.bin > fri3d-badge-2024_full-flash_2026-07-02.bin
  ```
  Full details in `backups/RESTORE.md`.

---

## 6. Loading games & writing apps

### 6.1 — Upload Game Boy (and NES) ROMs into Retro-Go

Retro-Go has a built-in **Wi-Fi Access Point + web file manager** — no SD-card reader or
`esptool` needed. ROMs go in folders under the `vfs` storage (mounted `/sd`):

- **Game Boy** → `roms/gb` (`.gb`)
- **Game Boy Color** → `roms/gbc` (`.gbc`)
- **NES** → `roms/nes` (`.nes`)
- **Doom** → drop a WAD (shareware `DOOM1.WAD`) for the `prboom-go` partition
- **Game Boy Advance is NOT supported.** You may zip a single ROM to save space.

**Method A — over Wi-Fi (recommended, no cable):**
1. In the Retro-Go launcher, press **X** → **Options** → **Wi-Fi options** → **Wi-Fi Access
   Point**, and pick a channel (e.g. `retro-go-channel-3`).
2. From your laptop/phone, join that Wi-Fi hotspot.
3. Browse to **<http://192.168.4.1/>** — a simple web file manager appears.
4. Upload your ROMs into `roms/gb`, `roms/gbc`, `roms/nes` (create folders / delete files there too).

**Method B — microSD card:** insert a card formatted **FAT32** (not exFAT/NTFS). Manage it via
the same hotspot, or pop the card out and copy files directly. On a fresh card, copy across the
default config (wifi networks etc.) and any games. *Note: the docs reference a
`default_files_config_and_games.zip`, but no such zip is actually published — the default
files/games/config live inside `vfs_fox.bin` (release **v0.1.5**), a LittleFS image; a local copy
is at `repos/badge_firmware/release-assets/v0.1.5/vfs_fox.bin`.* The badge tries the SD card
first, then falls back to internal `vfs`.

**Method C — friend-to-friend "Find games"** (no laptop/SD needed): your friend turns on their
hotspot (X → Wi-Fi options → Wi-Fi Access Point, e.g. `retro-go-channel-3`); you connect to it
(X → Wi-Fi options → Wi-Fi select → their channel); then press **Y → Find games** → pick a
folder. It scans and copies games you don't have yet (re-run on error; it skips what you have).
Tip: organise favourites into `roms/nes/best`, `roms/gb/best`, `roms/gbc/best`.

**Make your own Game Boy game:** use **GB Studio** (visual) or **GBDK** (C) → produces a `.gb`
ROM loaded like any other.

**Retro-Go controls:** START+MENU = exit to Fri3d App · Menu = prev screen · Start = next screen
· X = Options (volume, audio out Buzzer/Ext-DAC, Wi-Fi) · Y = Find games · A = action · B = back.
In-game: A/B = game buttons, Start = start, Menu = select.

### 6.2 — Add applications to the MicroPython environment

The MicroPython partition ships a **`fri3d` package** (hardware wrappers), a `user/` folder for
*your* code, and `main.py` as the entry point. It self-heals: delete `main.py`, the `fri3d`
package, or the `user` package and they are restored to their original state on next boot.

**Start MicroPython:**
1. Make sure the badge is on a recent firmware (OTA update at camp, or §5.1).
2. From the Fri3d App main menu, select **MicroPython** and press **A**.
3. The badge reboots and extracts files to the FAT partition — **do not interrupt** the boot.
4. After a while you get a `>>>` REPL. By default a reset returns to the main menu, not
   MicroPython; to make it **persist** in MicroPython, run once:
   ```python
   from fri3d import boot
   boot.persist()
   ```
   To go back to the menu: `boot.main_menu()` (you lose the menu once you `persist()`, so wire
   the MENU button to return — see the `main.py` pattern below).

**Edit & run code (pick one):**
- **Fri3d ViperIDE** — web editor over WebSerial. Connect, then on the badge select MicroPython
  + press A; you'll see the boot log; reconnect ViperIDE once the `>>>` prompt appears. Create
  files under `user/<yourname>/` (click `+` next to a folder; end a name with `/` to make a
  folder). Run with the blue play button (F5).
- **`mpremote`** (`pip install mpremote`) —
  `mpremote run local_file.py` · `mpremote resume fs cp local.py :remote.py` · `mpremote cp
  image.jpg :image.jpg`
- **Thonny** also works.

**A good `main.py`** (persist in MicroPython, but let MENU return to the main menu):
```python
import logging
from fri3d.badge.buttons import buttons
from fri3d import boot

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.Logger(__file__)

def menu_button(_):
    logger.warning("MENU pressed, rebooting to main menu")
    boot.main_menu()

buttons.menu.cb = menu_button   # MENU now returns to the Fri3d App menu
boot.persist()                  # stay in MicroPython across resets
```

**Things in the `fri3d` package:** `fri3d.badge.leds` (the 5× WS2812: `leds.fill((r,g,b))`,
`leds.write()`), `fri3d.badge.buttons`, `fri3d.application.Application` (`Application().run()`
launches the full Fri3d UI), `fri3d.boot`. **lvgl is built in.** (Caveat: the Display module
doesn't clean up perfectly — re-initialising it after first use errors; do a hard reset.)

**Other code paths (not MicroPython):** C++ via Arduino
([`badge_2024_arduino`](https://github.com/Fri3dCamp/badge_2024_arduino); board "Fri3d Badge
2024 (ESP32-S3-WROOM-1)", sketches need `ARDUINO_USB_CDC_ON_BOOT=1`) or PlatformIO · ESPHome for
Home Assistant · drag-blocks in Bipes.

**Ready-made hardware test:** `hardware_test.py` (project root) is a single-file MicroPython
demo (**verified running on the badge**) that exercises *everything* — a live LCD dashboard,
5× NeoPixel rainbow, buzzer (raw PWM tones + an RTTTL melody), all 6 buttons (live held-state),
the analog joystick (with re-centring), **live IMU accel + gyro** (WSEN-ISDS, driven directly
over I²C), battery monitor, IR receiver, microSD check, and system info. Controls: **A**=melody
· **B**=LED chase · **X**=hold for tone · **Y**=re-centre joystick · **START**=quit to REPL.

**Running MicroPython code — operational notes** (learned the hard way; see memory note
`fri3d-badge-running-micropython`):
- The MicroPython REPL is on `/dev/ttyACM0` (115200) but is **silent for ~60 s on first boot**
  while it unpacks the `fri3d` package — don't interrupt; send Enter to elicit `>>>`.
- **OTA anti-rollback is active:** after booting MicroPython, run `esp32.Partition.mark_app_valid_cancel_rollback()`
  once or it reverts to the menu on the next reset.
- **Interrupted extraction breaks imports** (`ImportError: fri3d.badge.*`): the `fri3d` package
  only re-extracts if absent from `/`. Fix = delete `/fri3d` + `machine.reset()` (re-extracts fully).
- This badge's **MENU button is broken**; reach MicroPython via the menu with **Y** (down) + **A**
  (choose) — MENU isn't needed for menu navigation.
- `mpremote` isn't installed here (PEP-668); drive the REPL with a pyserial paste-mode runner.
- Boot selection is ESP-IDF OTA: `otadata @0x9000` picks among `ota_0..3` (`ota_2`=micropython,
  `ota_3`=launcher/Retro-Go); both entries invalid → falls back to `ota_0` (menu).

> **Current badge state (2026-07-04):** boots into the **NeonLauncher** — a neon app-picker
> menu (`/main.py` runs `Application(default_app='user.neon_launcher').run()`). Select **DAVID**
> to play the neon-arcade name + hobby animation (`/user/name_badge/`); other entries: Example,
> Nametag (firmware stubs), Exit to REPL. To get back to a plain REPL: Ctrl-C, or menu → "Exit to
> REPL", or hold the SAO GPIO2→GND pin on boot (dev mode). To restore the original Retro-Go boot:
> `esptool --port /dev/ttyACM0 write_flash 0x0 backups/fri3d-badge-2024_full-flash_2026-07-02.bin`
> (verified full backup). To restore the original REPL-only MicroPython boot: delete `/main.py`
> and reset (self-healing re-extracts the stock `main.py`). See `name_badge_design.md` +
> `changelog.md` (2026-07-04) for the app; the menu still uses Y (down) + A (choose) — MENU is broken.

---

## 7. Key source repositories

Badge core:
- [`Fri3dCamp/badge_2024`](https://github.com/Fri3dCamp/badge_2024) — **this documentation
  site's source** (MkDocs; what's served at <https://fri3dcamp.github.io/badge_2024/>).
- [`Fri3dCamp/badge_2024_micropython`](https://github.com/Fri3dCamp/badge_2024_micropython) —
  the default firmware **source**: a fork of MicroPython **v1.23** (ESP-IDF v5.2.2) that adds
  the `fri3d` libraries. Build with `BOARD=FRI3D_BADGE_2024`, `PORT=/dev/ttyACM0`. Branches:
  `stable` (use this) and `develop`.
- [`Fri3dCamp/badge_firmware`](https://github.com/Fri3dCamp/badge_firmware) — prebuilt
  **releases** (latest `v1.0.1`): `full_firmware_fox.img`, `full_webflasher_fox.zip`,
  per-partition `*_fox.bin` (bootloader/fri3d_firmware/nvs/ota_data/partition_table), and
  `default_files_config_and_games.zip`. Web flasher: <https://fri3d-flasher.vercel.app/>.
- [`Fri3dCamp/badge_firmware_MicroPythonOS`](https://github.com/Fri3dCamp/badge_firmware_MicroPythonOS)
  — the MicroPythonOS firmware/app framework ("Firmware for the event badge").
- [`Fri3dCamp/badge_retro-go`](https://github.com/Fri3dCamp/badge_retro-go) — the Retro-Go
  derivative with Fri3d-specific features (upstream [`ducalex/retro-go`](https://github.com/ducalex/retro-go)).
- [`Fri3dCamp/badge_2024_arduino`](https://github.com/Fri3dCamp/badge_2024_arduino) — Arduino
  board package + examples; variant `fri3d_2024_esp32s3` has the authoritative pin map
  (`Fri3dBadge_pins.h` / `pins_arduino.h`). Helper lib: [`Fri3dCamp/Fri3dBadge`](https://github.com/Fri3dCamp/Fri3dBadge).
- [`Fri3dCamp/badge_2024_hw`](https://github.com/Fri3dCamp/badge_2024_hw) — **hardware** design
  files + production data (rev 01), datasheets, 3D models.

Add-ons (see §9):
- [`Fri3dCamp/blaster_2024`](https://github.com/Fri3dCamp/blaster_2024) — **Big Flamingo Gun
  9000 (BFG)** IR blaster. (The 2022 [`timeblaster-2020`](https://github.com/Fri3dCamp/timeblaster-2020) is also compatible.)
- [`Fri3dCamp/communicator_2024`](https://github.com/Fri3dCamp/communicator_2024) — Communicator.

Official docs: <https://fri3dcamp.github.io/badge_2024/en/> · product page <https://fri3d.be/en/badge/2024/>.

---

## 8. Add-ons

The badge is "eenvoudig te programmeren, en ook uit te breiden met een aantal add-ons" (easily
programmable, and expandable with add-ons). The official ones:

- **Flamingo / Big Flamingo Gun 9000 (BFG)** — `blaster_2024`. An IR-blaster gun: IR LED, 2× IR
  receivers, 4× WS2812 LEDs, team-selector switch, trigger, buzzer, built around the **LANA TNY**
  (RISC-V) module. Plugs into the badge's audio/accessory jack (IO10). *This is what "Flamingo"
  refers to — not the badge.*
- **Noisy Cricket** — a small "mini-blaster" SAO (Shitty Add-On).
- **Communicator** — `communicator_2024`: backlit QWERTY keyboard (Solder Party, on UART), TDK
  ICS43434 microphone, Analog Devices MAX98357A DAC + amplifier + speaker. As a USB keyboard
  when its LANA module is plugged into USB directly. This is the I²S audio cluster
  (GPIO15/47/17) and the "Ext DAC" audio-out option in Retro-Go.

---

## 9. Gotchas & non-obvious facts

1. **The badge is "Badge 2024" (codename "fox"), not "Flamingo".** "Flamingo"/BFG is the
   IR-blaster *add-on* (`blaster_2024`). Firmware assets for this board are named `*_fox.*`.
2. **Stub reads fail > ~512 KB over USB-Serial/JTAG** → always use `--no-stub` + chunking for dumps (§2, §5.2).
3. **esptool v5 uses kebab-case flags** (`read-flash`, `--before default-reset`); snake_case is deprecated but accepted.
4. **OTA update only works on the Fri3d Camp Wi-Fi.** Off-camp, use the web flasher or esptool (§5.1).
5. **P2 and SAO connector pinouts are UNVERIFIED** (see `pinout.md`) — inferred, not silkscreen-confirmed.
6. **GPIO13 is shared** (battery ADC + SAO "IO13"); **GPIO21 is shared** (LED_BUILTIN + IMU INT + SAO "LED").
7. **No SD card inserted** → storage is internal-flash `vfs` at `/sd`; a FAT32 microSD adds space (and is tried first).
8. The running build is `type: dev`; an OTA anti-rollback warning appeared at boot — benign, but OTA rollback logic is active.
9. The badge is `ttyACM*` (CDC), not `ttyUSB*` — there is no USB-UART bridge chip.
10. There are **5** WS2812 LEDs (not 1) on GPIO12.
11. Deleting `main.py` / `fri3d` / `user` in MicroPython restores the originals on next boot (self-healing).

---

## 10. Pointers for the next session

- **Memory** (auto-loaded via `MEMORY.md`): `fri3dcamp-2024-badge.md` (hardware + flash quirk),
  `fri3dcamp-2024-badge-firmware.md` (Fri3d App / Retro-Go / MicroPython + ROM/app mechanics).
- **This project dir:** `~/claudecode/projects/fri3dbadge2024/` — `BADGE.md`, `pinout.md`,
  `changelog.md`, `hardware_test.py` (full HW test/demo), `backups/`, `Pictures/`, `repos/`
  (**full** local clones of all source repos + firmware release assets).
- **Official docs:** <https://fri3dcamp.github.io/badge_2024/en/> (start here for anything not covered).
- **Suggested first task:** load a Game Boy ROM via the Retro-Go Wi-Fi hotspot (§6.1), or boot
  MicroPython and run the LED-blink example (§6.2) — both are non-destructive and reversible.
