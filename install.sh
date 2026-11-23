#!/bin/sh
# Install the reviewed FIDO PAM components only. Does not edit sudo/common-auth.
set -eu

if [ "${1:-}" != '--apply' ] || [ "$#" -ne 1 ]; then
    printf 'Usage: sudo ./install.sh --apply\n' >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    printf 'Run as root, with a separate recovery root session open.\n' >&2
    exit 1
fi

cd -- "$(dirname -- "$0")"
for file in fido-prompt fido-auth fido fido-worker; do
    if [ ! -f "$file" ]; then
        printf 'Missing repository file: %s\n' "$file" >&2
        exit 1
    fi
done
for bin in /usr/bin/python3 /usr/bin/pamtester /usr/bin/fido2-token /usr/bin/lsusb /usr/bin/timeout /usr/bin/stty /usr/bin/dd /usr/bin/grep /usr/bin/sleep; do
    if [ ! -x "$bin" ]; then
        printf 'Missing dependency: %s\n' "$bin" >&2
        exit 1
    fi
done
[ -r /etc/u2f_mappings ] || { echo 'Missing /etc/u2f_mappings' >&2; exit 1; }
/bin/sh -n fido-prompt
/usr/bin/python3 -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read())' fido-auth

# Do not install if the worker would be authenticated by anything other than U2F.
if [ "$(grep -Ec '^[[:space:]]*auth[[:space:]]+' fido-worker)" -ne 1 ]; then
    echo 'fido-worker must contain exactly one active auth rule.' >&2
    exit 1
fi

backup_dir="/var/backups/security-fido/$(date +%Y%m%dT%H%M%S)-$$"
install -d -o 0 -g 0 -m 0700 "$backup_dir"
install -d -o 0 -g 0 -m 0755 /usr/local/libexec

# Save the original files before making any changes; names match destinations.
for entry in \
    'fido-prompt:/usr/local/libexec/fido-prompt' \
    'fido-auth:/usr/local/libexec/fido-auth' \
    'fido:/etc/pam.d/fido' \
    'fido-worker:/etc/pam.d/fido-worker'; do
    name=${entry%%:*}
    destination=${entry#*:}
    if [ -e "$destination" ]; then
        cp -a -- "$destination" "$backup_dir/$name"
    fi
done

# Install the new worker and helpers before changing the live PAM entry point.
install -o 0 -g 0 -m 0644 fido-worker /etc/pam.d/.fido-worker.new
mv -f /etc/pam.d/.fido-worker.new /etc/pam.d/fido-worker
install -o 0 -g 0 -m 0755 fido-prompt /usr/local/libexec/.fido-prompt.new
mv -f /usr/local/libexec/.fido-prompt.new /usr/local/libexec/fido-prompt
install -o 0 -g 0 -m 0755 fido-auth /usr/local/libexec/.fido-auth.new
mv -f /usr/local/libexec/.fido-auth.new /usr/local/libexec/fido-auth
install -o 0 -g 0 -m 0644 fido /etc/pam.d/.fido.new
mv -f /etc/pam.d/.fido.new /etc/pam.d/fido

printf 'Installed /usr/local/libexec/{fido-prompt,fido-auth} and /etc/pam.d/{fido,fido-worker}\n'
printf 'Previous files backed up in %s\n' "$backup_dir"
printf 'No changes made to sudo, common-auth, /etc/u2f_mappings or hardware.\n'
printf 'Keep root recovery open; now run manual tests from TESTING.md.\n'
