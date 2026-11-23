#!/usr/bin/env python3
"""Offline insertion-gate tests, mocked USB/FIDO detection, real pseudo-terminal."""
import os
import pathlib
import pty
import subprocess
import tempfile
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def scenario(name, key_delay, ready_delay, expected, interrupt=False):
    with tempfile.TemporaryDirectory(prefix='fido-gate-test-') as td:
        d = pathlib.Path(td)
        lsusb = d / 'lsusb'
        lsusb.write_text('#!/usr/bin/python3\nimport os,sys,time\n'
                         'sys.exit(0 if time.monotonic()-float(os.environ["TEST_START"]) >= '
                         'float(os.environ["TEST_KEY_DELAY"]) else 1)\n')
        lsusb.chmod(0o755)
        fido = d / 'fido2-token'
        fido.write_text('#!/usr/bin/python3\nimport os,time\n'
                        'if time.monotonic()-float(os.environ["TEST_START"]) >= '
                        'float(os.environ["TEST_READY_DELAY"]):\n'
                        '    print("/dev/hidraw5: vendor=0x1050, product=0x0407 (Yubico)")\n')
        fido.chmod(0o755)
        gate = d / 'fido-prompt'
        gate.write_text((ROOT / 'fido-prompt').read_text()
                        .replace('/usr/bin/lsusb', str(lsusb))
                        .replace('/usr/bin/fido2-token', str(fido))
                        .replace('POLL_INTERVAL=0.25', 'POLL_INTERVAL=0.02'))
        gate.chmod(0o755)
        master, slave = pty.openpty()
        old = termios.tcgetattr(slave)
        env = os.environ.copy()
        env.update(PAM_TTY=os.ttyname(slave), TEST_START=str(time.monotonic()),
                   TEST_KEY_DELAY=str(key_delay), TEST_READY_DELAY=str(ready_delay))
        proc = subprocess.Popen((str(gate), '9'), env=env)
        if interrupt:
            time.sleep(.15)
            os.write(master, b'\x03')
        try:
            ret = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise AssertionError((name, 'gate stuck'))
        assert ret == expected, (name, ret, expected)
        assert termios.tcgetattr(slave) == old, (name, 'TTY not restored')
        os.close(master)
        os.close(slave)
        print('PASS', name)


scenario('preinserted YubiKey detected', 0, 0, 0)
scenario('hotplug waits for FIDO HID readiness', .08, .25, 0)
scenario('absent key falls back to password', 5, 5, 1)
scenario('enumerated USB but missing FIDO HID falls back', .02, 5, 1)
scenario('Ctrl+C during key insertion falls back', 5, 5, 130, True)
