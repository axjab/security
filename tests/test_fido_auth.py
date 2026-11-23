#!/usr/bin/env python3
"""Offline PTY and Linux-PAM control-flow tests. No key/system changes."""
import ctypes
import os
import pathlib
import pty
import signal
import subprocess
import tempfile
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def simulate(name, fake_return, interrupt=False):
    with tempfile.TemporaryDirectory(prefix='fido-auth-test-') as temp:
        folder = pathlib.Path(temp)
        notices = folder / 'notices'
        mock = folder / 'pamtester'
        mock.write_text('#!/usr/bin/python3\nimport os,time,sys\n'
                        'time.sleep(float(os.environ.get("MOCK_DELAY", 0)))\n'
                        'sys.exit(int(os.environ["MOCK_RESULT"]))\n')
        mock.chmod(0o755)
        notice = folder / 'prompt'
        notice.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$TEST_NOTICES"\n')
        notice.chmod(0o755)
        auth = folder / 'auth'
        auth.write_text((ROOT / 'fido-auth').read_text()
                        .replace('"/usr/bin/pamtester"', repr(str(mock)))
                        .replace('"/usr/local/libexec/fido-prompt"', repr(str(notice))))
        auth.chmod(0o755)
        master, slave = pty.openpty()
        tty = os.ttyname(slave)
        before = termios.tcgetattr(slave)
        env = os.environ.copy()
        env.update(PAM_USER='root', PAM_TTY=tty,
                   MOCK_RESULT=str(fake_return), TEST_NOTICES=str(notices),
                   MOCK_DELAY='20' if interrupt else '0.1')
        proc = subprocess.Popen((str(auth),), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        if interrupt:
            time.sleep(0.4)
            os.write(master, b'\x03')
        try:
            code = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise AssertionError((name, 'stuck, Ctrl+C not handled'))
        after = termios.tcgetattr(slave)
        assert before == after, (name, 'TTY was not restored')
        expected_notice = 'skipped' if interrupt else ('accepted' if fake_return == 0 else 'wrong')
        assert notices.read_text().splitlines() == [expected_notice], (name, notices.read_text())
        assert (code == 0) == (fake_return == 0 and not interrupt), (name, code)
        os.close(master)
        os.close(slave)
        print('PASS', name)


simulate('verified FIDO gives success', 0)
simulate('failed FIDO never gives success', 1)
simulate('SIGINT touch watcher falls back', 0, interrupt=True)

# Validate real Linux-PAM control actions, replacing the executable with a mock.
LIBPAM = ctypes.CDLL('libpam.so.0')
class Conv(ctypes.Structure):
    _fields_ = [('conv', ctypes.c_void_p), ('appdata_ptr', ctypes.c_void_p)]
LIBPAM.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.POINTER(Conv), ctypes.c_char_p,
                                    ctypes.POINTER(ctypes.c_void_p)]
LIBPAM.pam_start_confdir.restype = ctypes.c_int
LIBPAM.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
LIBPAM.pam_authenticate.restype = ctypes.c_int
LIBPAM.pam_end.argtypes = [ctypes.c_void_p, ctypes.c_int]
LIBPAM.pam_end.restype = ctypes.c_int
MODULES = '/usr/lib/x86_64-linux-gnu/security'


def pam_scenario(name, gate, worker, password, expected):
    with tempfile.TemporaryDirectory(prefix='fido-pam-test-') as td:
        d = pathlib.Path(td)
        marker = d / 'marker'
        trace = d / 'trace'
        marker.write_text('#!/bin/sh\n'
                          f'echo "$1" >> "{trace}"\n'
                          f'case "$1" in gate) exit {gate} ;; auth) exit {worker} ;; esac\n')
        marker.chmod(0o755)
        pw = 'permit' if password else 'deny'
        (d / 'test').write_text('\n'.join([
            f'auth [success=ignore default=1] {MODULES}/pam_exec.so quiet quiet_log {marker} gate',
            f'auth [success=done default=ignore] {MODULES}/pam_exec.so quiet quiet_log {marker} auth',
            f'auth [default=ignore] {MODULES}/pam_exec.so quiet quiet_log {marker} password',
            f'auth required {MODULES}/pam_{pw}.so',
        ]) + '\n')
        handle = ctypes.c_void_p()
        assert LIBPAM.pam_start_confdir(b'test', b'root', ctypes.byref(Conv()),
                                       os.fsencode(d), ctypes.byref(handle)) == 0
        code = LIBPAM.pam_authenticate(handle, 0)
        LIBPAM.pam_end(handle, code)
        assert (code == 0) == expected, (name, code)
        got = trace.read_text().splitlines()
        wanted = ['gate'] + ([] if gate else ['auth'])
        if not (gate == 0 and worker == 0):
            wanted += ['password']
        assert got == wanted, (name, got, wanted)
        print('PASS', name)


pam_scenario('PAM FIDO success short-circuits', 0, 0, False, True)
pam_scenario('PAM FIDO failure falls to password', 0, 1, True, True)
pam_scenario('PAM FIDO failure incorrect password denied', 0, 1, False, False)
pam_scenario('PAM skipped gate uses password', 130, 0, True, True)
pam_scenario('PAM no key and incorrect password denied', 1, 0, False, False)
