# Manual verification checklist (Debian 13 / sudo)

**Do not install directly on a machine without recovery access.** First inspect
`/etc/pam.d/sudo`, `/etc/pam.d/fido`, `common-auth`, and any `sudo-i` service.
Confirm `sudo` imports `fido` **before** the password fallback, and that the
fallback still works. Keep a separate, already authenticated root shell open.
Preserve the backup path printed by `install.sh`.

## Preconditions

- [ ] Both YubiKeys are enrolled for the **current host** and mapped to the
      correct local username in `/etc/u2f_mappings`.
- [ ] Dependencies installed: `libpam-u2f`, `usbutils`, `fido2-tools`,
      `pamtester`, and `python3` (plus the standard core utilities).
- [ ] `fido2-token -L` (read-only) enumerates the inserted YubiKey as
      `vendor=0x1050` and `/dev/hidrawN`.
- [ ] Review `fido`, `fido-worker`, `fido-prompt`, and `fido-auth` on disk.
- [ ] Test with a separate `sudo -k; sudo -v` for every scenario, so an existing
      sudo timestamp cannot conceal authentication failures.

## Scenarios

- [ ] **Correct key already inserted**: prompt `TOUCH THE KEY`; touch; green
      `KEY ACCEPTED`; sudo succeeds without Linux password.
- [ ] **Correct key inserted during `KEY REQUIRED`**: countdown yields `TOUCH
      THE KEY` after a short readiness check; touch after prompt; green
      `KEY ACCEPTED`, not a premature `WRONG KEY`. Repeat several times.
- [ ] **Second registered key**: test both preinserted and inserted during
      countdown. Both should succeed independently.
- [ ] **Unregistered key**: touch if requested; red `WRONG KEY`; Linux password
      fallback; incorrect Linux password must not grant access.
- [ ] **No key**: countdown expires; no false `WRONG KEY`; Linux password
      fallback; password must succeed when correct.
- [ ] **Ctrl+C during countdown**: `Key skipped`; immediate Linux password
      fallback; no stuck raw terminal or pending FIDO process.
- [ ] **Ctrl+C while `TOUCH THE KEY` is displayed**: `Key skipped`;
      immediate Linux password fallback. Repeat after a successful key use.
- [ ] **Correct key but do not touch**: after bounded touch wait, `Key skipped`,
      password fallback; verify no orphaned `pamtester` processes.
- [ ] **Remove key during touch wait**: authentication fails or times out;
      password fallback; never show `KEY ACCEPTED`.
- [ ] **Incorrect password after FIDO rejection**: sudo must deny access.
- [ ] **Missing/nonfunctional `/usr/bin/pamtester`** (isolated test only):
      FIDO must not authorize; password fallback must still work.
- [ ] **TTY restored**: after each Ctrl+C and timeout run `stty -a`; confirm
      canonical input and echo work normally.
- [ ] **Other sudo variants**: test `sudo -i`/`sudo -v` only after inspecting
      their PAM service selection; avoid assuming they share identical rules.
- [ ] **Noninteractive or remote context**: verify failure of the FIDO gate
      does not block the existing password/recovery policy.
- [ ] **Independent root access** still works after all tests.

## Install and recovery

Run from the checked-out repository with separate root recovery session open:

```sh
# Read-only syntax checks; no changes to system or key:
sh -n fido-prompt install.sh
python3 -c 'import ast;ast.parse(open("fido-auth").read())'

# Persistent changes: copy four repo-controlled files; backup originals.
sudo ./install.sh --apply
```

The installer **does not** touch YubiKey credentials, `/etc/u2f_mappings`,
`/etc/pam.d/sudo`, or `common-auth`. It changes root-owned files in
`/usr/local/libexec` and `/etc/pam.d`, affecting new authentication attempts
immediately. Root access is required; there is no daemon to restart.

To roll back, using the preserved independent root shell, restore each backed-up
file from the private backup directory printed by the installer. Files newly
created by the installer have no backup: remove only those new files when
reverting. Restore `/etc/pam.d/fido` **first** to its known-good content.
Do not edit `common-auth` or remove other existing recovery rules.

**Limitations:** This implementation is for touch-only keys; the isolated
`pamtester` worker has no interactive PIN conversation. A wrong-key notice
can reflect any FIDO verification failure, not just an unregistered key.
FIDO enumeration confirms a Yubico HID interface, not its authorization.
The initial, newly-inserted USB readiness race is mitigated with repeated
FIDO enumeration; real hardware is required to verify elimination.
