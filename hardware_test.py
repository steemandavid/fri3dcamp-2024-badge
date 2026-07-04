# -*- coding: utf-8 -*-
#
# Fri3d Camp 2024 Badge ("Badge 2024", board codename "fox") - hardware test & demo
# =============================================================================
#
# A single-file MicroPython program that exercises and demonstrates EVERY on-board
# capability of the badge:
#
#   * LCD display            (296x240, driven via lvgl)
#   * 5x NeoPixel LEDs       (WS2812 on GPIO12)
#   * Piezo buzzer           (PWM on GPIO46) -- raw tones + an RTTTL melody
#   * 6 buttons              (A / B / X / Y / MENU / START)
#   * 2-axis analog joystick (ADC GPIO1=X, GPIO3=Y)
#   * I2C bus                (scan) + IMU WSEN-ISDS @ 0x6B (WHO_AM_I)
#   * Battery monitor        (ADC GPIO13)
#   * IR receiver            (GPIO11)
#   * microSD                (is /sd mounted?)
#   * System info            (firmware, free memory, hardware capabilities)
#
# It draws a LIVE dashboard on the LCD that updates several times a second and reacts
# to the controls:
#
#   A      -> play a short melody on the buzzer (RTTTL "Take On Me")
#   B      -> white "chase" animation across the 5 LEDs
#   X      -> hold for a continuous A4 (440 Hz) tone; release to stop
#   Y      -> re-calibrate the joystick centre (centre the stick first)
#   MENU   -> turn LEDs/buzzer off and return to the Fri3d App main menu
#
# How to run
# ----------
#   # over USB, without copying anything to the badge:
#   mpremote connect /dev/ttyACM0 run hardware_test.py
#
#   # or copy it into the MicroPython "user" area and run from Fri3d ViperIDE:
#   mpremote connect /dev/ttyACM0 cp hardware_test.py :user/test/hardware_test.py
#   # then in ViperIDE open user/test/hardware_test.py and press the play button (F5).
#
# NOTE: initialising the LCD is a one-shot per boot -- the lvgl display driver cannot
# be torn down cleanly. If you run this twice, hard-reset the badge (RESET button)
# between runs. Pressing MENU cleanly hands control back to the Fri3d App.
#
# Tested against the fri3d MicroPython API in:
#   Fri3dCamp/badge_2024_micropython  (MicroPython v1.23, ESP-IDF v5.2.2)

import gc
import machine
import os
import struct
import sys
import time

import lvgl as lv
import lvgl_esp32

from fri3d.badge.buttons import buttons
from fri3d.badge.buzzer import buzzer
from fri3d.badge.capabilities import capabilities
from fri3d.badge.display import display
from fri3d.badge.i2c import i2c
from fri3d.badge.joystick import joystick
from fri3d.badge.leds import leds
from fri3d.rtttl import RTTTL, songs


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------

def hsv_to_rgb(h, s=1.0, v=0.6):
    """h in degrees (0..359), s/v in 0..1 -> (r, g, b) each 0..255."""
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


# Battery monitor on GPIO13 (ADC1_CH12). read_uv() returns micro-volts at the pin
# after calibration; /1000 gives mV. This tracks the value the launcher reports.
_battery = machine.ADC(machine.Pin(13), atten=machine.ADC.ATTN_11DB)


def battery_mv():
    return _battery.read_uv() // 1000


# IR receiver input on GPIO11.
_ir = machine.Pin(11, machine.Pin.IN)


def i2c_devices():
    try:
        return i2c.scan()
    except Exception:
        return []


IMU_ADDR = 0x6B  # WSEN-ISDS (2536030320001), SAO tied high

def imu_who_am_i():
    """Read the WSEN-ISDS device-ID register (0x0F); expected 0x6A."""
    try:
        return i2c.readfrom_mem(IMU_ADDR, 0x0F, 1)[0]
    except Exception:
        return None


def imu_init():
    """Enable accel + gyro. CTRL1 accel 208 Hz / +-2 g, CTRL2 gyro 208 Hz / +-250 dps,
    CTRL3 BDU + register-address auto-increment (for multi-byte reads)."""
    try:
        i2c.writeto_mem(IMU_ADDR, 0x12, b"\x44")  # CTRL3: BDU + IF_INC
        time.sleep_ms(10)
        i2c.writeto_mem(IMU_ADDR, 0x10, b"\x50")  # CTRL1: accel 208 Hz, +-2 g
        i2c.writeto_mem(IMU_ADDR, 0x11, b"\x50")  # CTRL2: gyro  208 Hz, +-250 dps
        time.sleep_ms(20)
        return True
    except Exception:
        return False


def imu_read():
    """Return (ax, ay, az, gx, gy, gz) as signed int16. Accel block @0x28, gyro block @0x22."""
    a = i2c.readfrom_mem(IMU_ADDR, 0x28, 6)
    g = i2c.readfrom_mem(IMU_ADDR, 0x22, 6)
    return struct.unpack_from("<hhh", a) + struct.unpack_from("<hhh", g)


def sd_mounted():
    try:
        os.stat("/sd")
        return True
    except Exception:
        return False


def button_pressed(b):
    """fri3d DebouncedButton.value() returns 1 when pressed, 0 when released."""
    return b is not None and b.value() == 1


def button_level(b):
    """Live held-level (1 = currently pressed) read straight from the raw pin.

    fri3d's DebouncedButton.value() is edge-oriented: it latches 1 on press then
    auto-clears after the ~200 ms debounce window, so it's useless for showing the
    held state. The buttons are wired pull-up, so pin low (0) == pressed.
    """
    if b is None:
        return -1
    try:
        return 1 if b._pin.value() == 0 else 0
    except Exception:
        return -1


# -----------------------------------------------------------------------------
# Dashboard UI
# -----------------------------------------------------------------------------

def make_label(x, y, text="", color=0xFFFFFF):
    lbl = lv.label(lv.screen_active())
    lbl.set_pos(x, y)
    lbl.set_text(text)
    lbl.set_style_text_color(lv.color_hex(color), 0)
    return lbl


def led_rainbow(hue):
    """Spread a rainbow across the LED string and write it out."""
    n = leds.n
    for i in range(n):
        leds[i] = hsv_to_rgb(hue + i * (360 // n))
    leds.write()


def led_chase():
    """Blocking one-shot white chase (triggered by B)."""
    for k in range(leds.n * 2):
        leds.fill((0, 0, 0))
        leds[k % leds.n] = (255, 255, 255)
        leds.write()
        time.sleep_ms(80)
    leds.fill((0, 0, 0))
    leds.write()


def calibrate_joystick():
    if joystick.x is not None:
        joystick.x.calibrate_center()
    if joystick.y is not None:
        joystick.y.calibrate_center()
    # tiny "ack" beep
    buzzer.freq(880)
    buzzer.duty_u16(16000)
    time.sleep_ms(60)
    buzzer.duty_u16(0)


def cleanup():
    """Leave the hardware in a quiet state."""
    try:
        leds.fill((0, 0, 0))
        leds.write()
    except Exception:
        pass
    try:
        buzzer.duty_u16(0)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Startup banner (to the REPL)
# -----------------------------------------------------------------------------

print("=" * 48)
print(" Fri3d Camp 2024 Badge - hardware test & demo")
print("=" * 48)
try:
    print("system:", " ".join(os.uname()))
except Exception:
    pass
print("implementation:", getattr(sys, "implementation", "?"))
print("mem free: %d kB" % (gc.mem_free() // 1024))
caps = [k for k in dir(capabilities) if not k.startswith("_")]
print("capabilities:", caps)
print("joystick present:", joystick.x is not None and joystick.y is not None)
print("LEDs:", leds.n, "| buttons:", [b for b in ("a", "b", "x", "y", "menu", "start")
                                       if getattr(buttons, b) is not None])


# -----------------------------------------------------------------------------
# Set up the display + screen
# -----------------------------------------------------------------------------

# The lvgl display driver is one-shot per boot; tolerate a second initialisation.
wrapper = lvgl_esp32.Wrapper(display)
try:
    wrapper.init()
except Exception as e:
    print("display wrapper already initialised:", e)

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)

title    = make_label(4,   1, "Fri3d Badge 2024 - HW Test", 0x55FF55)
joy_lbl  = make_label(4,  20)
btn_lbl  = make_label(4,  38)
bat_lbl  = make_label(4,  56)
i2c_lbl  = make_label(4,  74)
imu_lbl  = make_label(4,  92)
gyro_lbl = make_label(4, 110)
sd_lbl   = make_label(4, 128)
ir_lbl   = make_label(4, 146)
sys_lbl  = make_label(4, 164)
make_label(4, 198, "A:melody B:LEDs X:tone Y:ctr START:quit", 0xAAAAAA)

# One-time probes.
devs = i2c_devices()
who = imu_who_am_i()
imu_ok = imu_init()
sd_ok = sd_mounted()

# Calibrate the joystick (assumes it is centred at boot; press Y to redo).
calibrate_joystick()


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------

_button_names = ("a", "b", "x", "y", "menu", "start")
_prev = {n: 0 for n in _button_names}
_hue = 0
_last_ui = 0


def falling_edge(name):
    """True on the loop iteration where button `name` goes from up -> down."""
    b = getattr(buttons, name)
    cur = 1 if button_pressed(b) else 0
    prev = _prev.get(name, 0)
    _prev[name] = cur
    return cur == 1 and prev == 0


def refresh_dashboard():
    global _hue
    # joystick
    jx = joystick.x.read() if joystick.x is not None else 0
    jy = joystick.y.read() if joystick.y is not None else 0
    joy_lbl.set_text("Joystick  X:%+5d  Y:%+5d" % (jx, jy))

    # buttons (live held-state from the raw pins)
    states = " ".join("%s:%d" % (n.upper(), button_level(getattr(buttons, n)))
                      for n in _button_names)
    btn_lbl.set_text("Buttons: " + states)

    # battery
    bat_lbl.set_text("Battery: %d mV (GPIO13)" % battery_mv())

    # i2c scan
    i2c_lbl.set_text("I2C devs: " + (",".join("0x%02X" % d for d in devs) if devs else "none"))

    # IMU (WSEN-ISDS): accel in g (+-2g => 16384 LSB/g), gyro in dps (+-250dps => 8.75 mdps/LSB)
    try:
        ax, ay, az, gx, gy, gz = imu_read()
        imu_lbl.set_text("Acc g  X:%+5.2f Y:%+5.2f Z:%+5.2f" % (ax / 16384, ay / 16384, az / 16384))
        gyro_lbl.set_text("Gyro dps X:%+4.0f Y:%+4.0f Z:%+4.0f" % (gx * 0.00875, gy * 0.00875, gz * 0.00875))
    except Exception as e:
        imu_lbl.set_text("IMU read err: " + str(e)[:20])
        gyro_lbl.set_text("")

    # SD card
    sd_lbl.set_text("microSD /sd: " + ("mounted" if sd_ok else "not present"))

    # IR receiver
    ir_lbl.set_text("IR receiver (GPIO11): %d" % _ir.value())

    # system
    sys_lbl.set_text("Mem free: %d kB   fw: %s" % (gc.mem_free() // 1024,
                                                   getattr(sys.implementation, "name", "micropython")))

    # rainbow LEDs (continuous LED demo)
    _hue = (_hue + 12) % 360
    led_rainbow(_hue)


try:
    while True:
        lv.timer_handler()

        # --- button-triggered demos ---
        if falling_edge("a"):
            # Blocking: plays the whole tune, then returns. (Dashboard pauses briefly.)
            RTTTL(songs.take_on_me_s).play(volume=80)

        if falling_edge("b"):
            led_chase()

        if falling_edge("y"):
            calibrate_joystick()

        # X = continuous tone while held.
        if button_pressed(buttons.x):
            buzzer.freq(440)
            buzzer.duty_u16(32768)  # 50% duty ~= max volume
        else:
            buzzer.duty_u16(0)

        # Quit on START or MENU (the MENU button may be broken, so START also works).
        if falling_edge("menu") or falling_edge("start"):
            print("Quit pressed - cleaning up and returning to the REPL.")
            break

        # --- periodic dashboard + LED refresh (~5 Hz) ---
        now = time.ticks_ms()
        if time.ticks_diff(now, _last_ui) >= 200:
            _last_ui = now
            refresh_dashboard()

        time.sleep_ms(5)
finally:
    cleanup()
    # Return to the MicroPython REPL (>>>), so the demo can be re-run without a reset.
