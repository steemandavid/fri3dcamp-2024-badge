#!/usr/bin/env python3
"""Fri3d Camp 2024 badge — paste-mode runner over USB-Serial/JTAG (/dev/ttyACM0).

Usage:
  badge_run.py paste <file.py> [settle_s]   paste a local file, capture+echo output
  badge_run.py upload <local> <remote>      write a local file to the badge fs (base64/paste)
  badge_run.py reset                         soft-reboot the badge (Ctrl-D)
  badge_run.py intr                          send Ctrl-C (interrupt a running program)
  badge_run.py cat <remote_path>             print a file from the badge filesystem

Paste mode (Ctrl-E ... Ctrl-D) is used because it streams output and leaves long-running
programs running after we detach (unlike raw REPL, which blocks on infinite loops).
"""
import sys
import time
import binascii

import serial

PORT = "/dev/ttyACM0"
BAUD = 115200


def open_port():
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    time.sleep(0.05)
    ser.reset_input_buffer()
    return ser


def to_repl(ser):
    """Interrupt any running program and confirm friendly REPL (>>>)."""
    ser.write(b"\r\x03\x03")      # Ctrl-C twice: stop a running program
    time.sleep(0.25)
    ser.write(b"\r\x02")          # Ctrl-B: ensure friendly REPL
    time.sleep(0.2)
    ser.write(b"\r")              # elicit a prompt
    time.sleep(0.15)
    ser.reset_input_buffer()


def read_until_quiet(ser, settle=1.2, hard_timeout=180, echo=True):
    buf = bytearray()
    last = time.time()
    start = time.time()
    while True:
        n = ser.in_waiting
        if n:
            chunk = ser.read(n)
            buf.extend(chunk)
            last = time.time()
            if echo:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
        else:
            if time.time() - last > settle:
                break
        if time.time() - start > hard_timeout:
            sys.stderr.write("\n[hard timeout reached]\n")
            break
        time.sleep(0.02)
    return bytes(buf)


def paste(ser, code, settle=1.2):
    to_repl(ser)
    ser.write(b"\x05")            # Ctrl-E: enter paste mode
    time.sleep(0.15)
    for i in range(0, len(code), 64):
        ser.write(code[i:i + 64])
        time.sleep(0.004)
    time.sleep(0.1)
    ser.write(b"\x04")            # Ctrl-D: execute the pasted block
    return read_until_quiet(ser, settle=settle)


def run_for(ser, code, seconds):
    """Paste code and read for exactly `seconds` (for long-running programs), then return."""
    to_repl(ser)
    ser.write(b"\x05")
    time.sleep(0.15)
    for i in range(0, len(code), 64):
        ser.write(code[i:i + 64])
        time.sleep(0.004)
    time.sleep(0.1)
    ser.write(b"\x04")
    end = time.time() + seconds
    buf = bytearray()
    while time.time() < end:
        n = ser.in_waiting
        if n:
            chunk = ser.read(n)
            buf.extend(chunk)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        else:
            time.sleep(0.05)
    return bytes(buf)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    ser = open_port()

    if cmd == "paste":
        path = sys.argv[2]
        settle = float(sys.argv[3]) if len(sys.argv) > 3 else 1.2
        with open(path, "rb") as f:
            code = f.read()
        out = paste(ser, code, settle=settle)
        ser.close()
        return

    if cmd == "reset":
        to_repl(ser)
        ser.write(b"import machine; machine.reset()\r")
        read_until_quiet(ser, settle=2.0)
        ser.close()
        return

    if cmd == "intr":
        ser.write(b"\r\x03\x03")
        time.sleep(0.2)
        read_until_quiet(ser, settle=0.6)
        ser.close()
        return

    if cmd == "run_for":
        path = sys.argv[2]
        seconds = float(sys.argv[3])
        with open(path, "rb") as f:
            code = f.read()
        run_for(ser, code, seconds)
        ser.close()
        return

    if cmd == "upload":
        local = sys.argv[2]
        remote = sys.argv[3]
        with open(local, "rb") as f:
            data = f.read()
        b64 = binascii.b2a_base64(data).decode().strip()
        chunks = [b64[i:i + 1500] for i in range(0, len(b64), 1500)]
        parent = remote.rsplit("/", 1)[0]
        script = ("import os,binascii as _b\n"
                  "try:\n    os.mkdir('%s')\nexcept OSError:\n    pass\n" % parent)
        script += "_d=_b.a2b_base64(" + "+".join('"%s"' % c for c in chunks) + ")\n"
        script += ("_f=open('%s','wb')\n_f.write(_d)\n_f.close()\n"
                   "print('WROTE', len(_d), 'bytes to', '%s')\n" % (remote, remote))
        paste(ser, script.encode(), settle=1.5)
        ser.close()
        return

    if cmd == "cat":
        remote = sys.argv[2]
        code = ('with open(%r,"rb") as f:\n'
                '    import sys\n'
                '    sys.stdout.write(f.read().decode("utf-8","replace"))\n' % remote)
        paste(ser, code.encode(), settle=1.0)
        ser.close()
        return

    print("unknown command:", cmd)
    sys.exit(1)


if __name__ == "__main__":
    main()
