# Fri3d Camp 2024 badge — apps, tools & notes

Code, tools and reference notes for the **Fri3d Camp 2024 badge** ("Badge 2024",
board codename **fox**) — an ESP32-S3-WROOM-1 handheld with a 2" LCD, 5× WS2812
LEDs, buttons, joystick, buzzer, WSEN-ISDS IMU and microSD. Developed (and
reverse-engineered) with [Claude Code](https://claude.com/claude-code) as the
pair-programmer.

> 📝 **Companion blog post:** [Programming the Fri3d Camp 2024 badge with Claude Code](https://www.steeman.be/posts/programming-the-fri3d-badge-with-claude-code/)

## What's in here

| Path | What |
|---|---|
| `app/` | A complete selectable MicroPython app: a neon app-picker (`neon_launcher/`) and an animated name/hobby "name badge" (`name_badge/`), plus the boot `main.py`. |
| `app/name_badge/art.py` | Tiny RGB565 framebuffer engine (pixel/line/circle/triangle), a 5×7 bitmap font, and 9 procedural pixel-art icons. |
| `tools/` | `badge_run.py` (paste / upload / run / reset over USB) and probe/test scripts. |
| `hardware_test.py` | A single-file MicroPython demo that exercises **every** on-board subsystem (LCD, LEDs, buzzer, buttons, joystick, IMU, battery, IR, SD). |
| `BADGE.md` | Comprehensive self-contained reference: identity, connection, full pinout, firmware, backup/restore, how to write apps. **Start here.** |
| `pinout.md` | Maintained GPIO tables + connectors. |
| `name_badge_design.md` | The design doc for the name-badge app (spec + on-device findings). |
| `Pictures/` | Board photos. |

## The badge

- ESP32-S3-WROOM-1, **N16R8V** (16 MB flash, 8 MB PSRAM), 240 MHz.
- 2" IPS LCD, GC9307/ST7789, **296×240**, BGR, via lvgl v9.
- USB-C → native USB-Serial/JTAG, appears as `/dev/ttyACM*` (CDC, **not** ttyUSB).
- Ships with the **"Fri3d App"**: a menu offering OTA Update / MicroPython / Retro-Go (GB/GBC/NES/Doom).

Official sources (these are the authoritative reference — go read them):

- Docs site: <https://fri3dcamp.github.io/badge_2024/en/>
- [`Fri3dCamp/badge_2024`](https://github.com/Fri3dCamp/badge_2024) — documentation source
- [`Fri3dCamp/badge_2024_micropython`](https://github.com/Fri3dCamp/badge_2024_micropython) — MicroPython fork + the `fri3d` libraries (default firmware source)
- [`Fri3dCamp/badge_firmware`](https://github.com/Fri3dCamp/badge_firmware) — prebuilt releases + web flasher
- [`Fri3dCamp/badge_2024_arduino`](https://github.com/Fri3dCamp/badge_2024_arduino) — Arduino board package + the authoritative pin map

## Using the tools

`tools/badge_run.py` talks to the badge over `/dev/ttyACM0` (115200). It uses
**paste mode** so long-running programs keep running after it detaches.

```bash
python3 tools/badge_run.py paste  tools/hello.py        # run a local script
python3 tools/badge_run.py upload local.py /user/x.py   # write a file to the badge
python3 tools/badge_run.py run_for tools/hello.py 10     # run & capture for N seconds
python3 tools/badge_run.py reset                          # soft reboot
python3 tools/badge_run.py cat   /user/x.py              # print a file from the badge
```

> ⚠️ MicroPython caches imported modules — **reset the badge after uploading** changed
> code, or you'll be running the old version. And don't paste/upload while an app is
> running; get to the REPL first (Ctrl-C, or the app's "Exit to REPL", or hold the SAO
> GPIO2→GND pin on boot for dev mode).

## Installing the name-badge app

Copy `app/` onto the badge so the paths are:

```
/main.py                              boot entry → runs the launcher
/user/neon_launcher/{__init__,app.json,neon_launcher.py}
/user/name_badge/{__init__,app.json,name_badge.py,art.py}
```

Then reset. The badge boots into a neon menu; pick **DAVID** to play. Controls:
**A** next hobby, **Y** previous, **X** toggle sound, **B**/START back to menu.

## Safety / recovery

Everything is reversible:

- **Back to a plain REPL:** Ctrl-C, or menu → "Exit to REPL", or SAO GPIO2→GND on boot.
- **Restore the original Retro-Go boot:** reflash your verified full-flash backup with
  `esptool --port /dev/ttyACM0 write_flash 0x0 <your-backup.bin>`.
- **Reset to the latest official firmware:** see
  [`badge_firmware` releases](https://github.com/Fri3dCamp/badge_firmware/releases) +
  the [web flasher](https://fri3d-flasher.vercel.app/).

## License

My code (`app/`, `tools/`, `hardware_test.py`) is MIT. The Fri3d firmware and docs
belong to the Fri3dCamp project — see their repos.
