
# PAM Security

> Core security components for Linux systems, including custom Pluggable Authentication
Modules (PAM) configuration fragments, authentication scripts, and their dependencies. This
package provides foundational security enhancements and flexible authentication workflows
for critical services such as `sudo`, `ssh`, and `login`.

From here shall originate the package `core-sec` intended for my core package suites.

## Content

- pam.d/fido: FIDO2 authentication module imported by pam.d/sudo
- fido-prompt: Nice prompts, encapsulates UI and UX, invoked by fido module
- /etc/u2f_mappings

Dependencies:
- libpam-u2f
- pamu2fcfg
- lsusb
- stty
- dd

Recommended:
- ykman

## References

- https://developers.yubico.com/pam-u2f/#moduleArguments
