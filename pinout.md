# Fri3d Camp 2024 Badge ("Badge 2024", codename "fox") — Pinout

> Not "Flamingo" — that's the Big Flamingo Gun (BFG) IR-blaster *add-on*
> ([`blaster_2024`](https://github.com/Fri3dCamp/blaster_2024)), a separate PCB. This is the
> badge itself. Official docs: <https://fri3dcamp.github.io/badge_2024/en/>.

ESP32-S3-WROOM-1, N16R8V (16 MB flash, 8 MB PSRAM). MAC `34:85:18:ab:df:0c`.
USB-C → native USB-Serial/JTAG (VID:PID `303a:1001`, appears as `/dev/ttyACM*`).
USB port on this host: `/dev/ttyACM0`.

Sources: badge back-PCB silkscreen + official `Fri3dBadge_pins.h` / `pins_arduino.h`
([Fri3dCamp/badge_2024_arduino](https://github.com/Fri3dCamp/badge_2024_arduino),
variant `fri3d_2024_esp32s3`). The two agree on every pin.

## Master GPIO map

| GPIO | Function | Notes |
|--:|---|---|
| 0 | **START** button | = BOOT; hold + press RESET → download mode |
| 1 | Joystick **X** (horizontal) | analog, ADC1_CH0 |
| 2 | expansion header pin 7 | spare analog, ADC1_CH1 / touch T2 |
| 3 | Joystick **Y** (vertical) | analog, ADC1_CH2 |
| 4 | LCD **DC** | |
| 5 | LCD **CS** | display SPI select |
| 6 | SPI **MOSI** | display + SD |
| 7 | SPI **SCLK** | display + SD |
| 8 | SPI **MISO** | display + SD |
| 9 | **I²C SDA** | IMU + expansion (ADC1_CH8) |
| 10 | **Blaster** (IR) — via the audio/accessory jack | addon jack, see Connectors |
| 11 | **IR Receiver** | |
| 12 | **WS2812** NeoPixel string | **5 LEDs** |
| 13 | **Battery monitor** | analog, ADC1_CH12; also on SAO header |
| 14 | **SD card CS** | |
| 15 | expansion header pin 6 | I²S mic DIN (Communicator addon), ADC1 |
| 16 | expansion header pin 5 | spare analog, ADC1_CH15 |
| 17 | expansion header pin 3 | I²S mic SCLK (Communicator addon), ADC1 |
| 18 | **I²C SCL** | IMU + expansion (ADC1_CH17) |
| 21 | built-in **LED** / **IMU interrupt** | `LED_BUILTIN`; SAO "LED" pin |
| 38 | button **X** | |
| 39 | button **A** | |
| 40 | button **B** | |
| 41 | button **Y** | |
| 42 | **AUX power** output | |
| 43 | UART0 **TX** / expansion header pin 9 | |
| 44 | UART0 **RX** / expansion header pin 10 | |
| 45 | **MENU** button | |
| 46 | **Buzzer** ("Zoemer") | |
| 47 | expansion header pin 8 | I²S mic LRCK/WS (Communicator addon) |
| 48 | LCD **RSTn** | |

## 12-pin expansion pinheader (bottom edge, silkscreen "AREA 3001")

| Pin | Label | GPIO | Function |
|--:|---|---|---|
| 1 | SCL | 18 | I²C clock |
| 2 | VSYS | — | system/battery power rail |
| 3 | 17 | 17 | I²S mic SCLK; ADC1 |
| 4 | SDA | 9 | I²C data |
| 5 | 16 | 16 | spare analog (ADC1_CH15) |
| 6 | 15 | 15 | I²S mic DIN; ADC1 |
| 7 | 2 | 2 | spare analog (ADC1_CH1) / touch T2 |
| 8 | 47 | 47 | I²S mic LRCK/WS |
| 9 | 43 | 43 | UART0 TX |
| 10 | 44 | 44 | UART0 RX |
| 11 | 3.3V | — | regulated 3.3 V |
| 12 | GND | — | ground |

The addon/expansion bus: power (VSYS, 3.3V, GND), I²C (SCL/SDA), UART (43/44),
the I²S audio cluster for the Communicator microphone addon (15/47/17), and two
spare analog GPIOs (2, 16).

## Other connectors

**Audio / accessory jack** (silkscreen `IO10` / "Blaster") — TRRS-style jack used to plug in
the **Big Flamingo Gun 9000 (BFG)** IR-blaster add-on ([`blaster_2024`](https://github.com/Fri3dCamp/blaster_2024);
the 2022 [`timeblaster-2020`](https://github.com/Fri3dCamp/timeblaster-2020) is also compatible).
Signal line = GPIO10 (same net as the back-silkscreen "Blaster : IO10"). It is an *add-on
connector* — the badge's own on-board IR receiver is GPIO11.

**⚠ UNVERIFIED — P2 — 4-pin I²C STEMMA/Qwiic connector** (silkscreen: water-droplet +
thermometer icon → intended for a temperature/humidity sensor, e.g. SHT4x). Believed
to be the standard 4-pin on the shared I²C bus: `GND · V+ (3.3 V) · SDA (GPIO9) · SCL (GPIO18)`.
**This pinout is inferred, not confirmed** — the silkscreen lists no GPIO numbers next
to P2. Confirm against the official schematic or a real sensor before wiring.

**⚠ PARTIALLY UNVERIFIED — SAO header (Shitty Add-On), 2×3 footprint** — 6 pins.
Silkscreen literally reads `IO13 · LED · SCL · SDA · GND · V+`. The `SCL`/`SDA`/`V+`/`GND`
labels are taken at face value; the **`LED`→GPIO21 and `IO13`→GPIO13 mappings are
inferred** from the firmware pin file (`LED_BUILTIN=21`, and "IO13" = GPIO13), **not
read as numbered GPIOs on the silkscreen** — verify before relying on them.

| SAO signal | Badge net | Note |
|---|---|---|
| V+ | 3.3 V | power |
| GND | GND | |
| SDA | GPIO9 | I²C data |
| SCL | GPIO18 | I²C clock |
| LED | GPIO21 | badge `LED_BUILTIN` / IMU INT (silkscreen just says "LED") |
| IO13 | GPIO13 | **shared** with the battery-monitor ADC line |

## Subsystem notes
- **Display:** GC9307 (ST7789-compatible), **296 × 240**, HSPI @ 80 MHz, BGR pixel
  order, no inversion. RST on GPIO48.
- **IMU:** WSEN-ISDS (Würth accel + gyro) on shared I²C (SDA 9 / SCL 18),
  silkscreen address **0x6B**, interrupt on GPIO21.
- **Input:** 6 digital buttons (A/B/X/Y/MENU/START) + 1 analog 2-axis joystick.
- **LEDs:** 5× WS2812 on GPIO12.
- **Storage:** microSD on shared SPI bus, CS=GPIO14.
- **Buttons:** START = GPIO0 (also BOOT). RESET is a dedicated button (right ear).
