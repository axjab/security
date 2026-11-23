# PAM security (FIDO for sudo)

This repository contains a **touch-only YubiKey authentication path** for sudo,
with a Linux-password fallback in the caller's existing PAM stack.

| File | Installed destination | Role |
|---|---|---|
| `fido` | `/etc/pam.d/fido` | Two-rule PAM entrypoint; gate then cancellable FIDO auth |
| `fido-prompt` | `/usr/local/libexec/fido-prompt` | Countdown and colored status notices |
| `fido-auth` | `/usr/local/libexec/fido-auth` | Runs isolated FIDO auth and watches Ctrl+C during touch |
| `fido-worker` | `/etc/pam.d/fido-worker` | Isolated `pam_u2f.so` credential verification, no fallback |
| `install.sh` | Run from checkout | Copies files with backups; leaves sudo and mappings untouched |
| `TESTING.md` | Not installed | Manual testing and recovery checklist |

## Authentication flow

```text
sudo -> @include fido
       -> fido-prompt: detect Yubico USB AND enumerated FIDO HID readiness
          no device / Ctrl+C / timeout -> next auth module (password)
       -> fido-auth (pam_exec): run pamtester fido-worker $PAM_USER
          -> fido-worker: pam_u2f verifies FIDO credential and touch
          -> watcher is armed first, then TOUCH THE KEY is displayed
          -> while child is running, Ctrl+C is read from the terminal
             and cancels child; normal exit 0 succeeds; other results fail
       -> return PAM_SUCCESS only if isolated pam_u2f succeeded;
          otherwise continue into common-auth password fallback
```

`fido-auth` is necessary because a shell `pam_exec` gate cannot interrupt a
blocking `pam_u2f.so` running inside the sudo PAM process. It delegates **actual
credential verification** to the unchanged Yubico PAM module in a separate,
killable process. It does not inspect or store private credentials.

Read [TESTING.md](TESTING.md) before installation. Keep a working independent
root session throughout deployment. No changes are made to hardware keys.

## Dependencies

Debian: `libpam-u2f`, `usbutils`, `fido2-tools`, `pamtester`, `python3`.
Standard utilities: `stty`, `dd`, `grep`, `sleep`, `timeout`. Optional `ykman`
for credential inspection. The public key mapping file is
`/etc/u2f_mappings` (existing, never committed to this repository).

The isolated child service is intended for enrolled `+presence` (touch-only)
credentials; if a key requires an interactive PIN, the worker will fail and the
existing password fallback applies. USB vendor detection is not a substitute
for cryptographic verification. `WRONG KEY` also covers other FIDO failures.

**Scope:** The installer does not edit `/etc/pam.d/sudo`, `/etc/pam.d/sudo-i`,
or `common-auth`. The existing sudo service must import `fido` before its
password fallback. This is a significant PAM architecture change and must be
hardware-tested before relying on it across hosts.

## References

- [Yubico pam_u2f](https://developers.yubico.com/pam-u2f/Manuals/pam_u2f.8.html)
- [PAM syntax](https://man7.org/linux/man-pages/man5/pam.d.5.html)
- [pamtester](https://manpages.debian.org/testing/pamtester/pamtester.1.en.html)
- [fido2-token](https://developers.yubico.com/libfido2/Manuals/fido2-token.html)
