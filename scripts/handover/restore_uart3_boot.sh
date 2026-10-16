#!/bin/sh
# Runs on K7. Default is inspection only. No hard-coded eMMC partition number.
set -eu
image="${2:-/tmp/boot-resource-uart3.img}"
expected=bd62ad91bae99d28a5a0027bc8cb3ac9dab7d5079be40f9b50e5652ddd3860f2
[ "$(id -u)" = 0 ] || { echo 'ERROR: root required'; exit 1; }
model=$(tr -d '\000' </proc/device-tree/model)
[ "$model" = 'Rockchip RK3576 KICKPI K7 Board' ] || {
    echo 'ERROR: board model does not match original K7'; exit 1;
}
target=''
for candidate in /dev/disk/by-partlabel/boot /dev/block/by-name/boot; do
    if [ -b "$candidate" ]; then
        resolved=$(readlink -f "$candidate")
        if [ -n "$target" ] && [ "$target" != "$resolved" ]; then
            echo 'ERROR: boot labels disagree'; exit 1
        fi
        target=$resolved
    fi
done
[ -n "$target" ] || { echo 'ERROR: named boot partition not found; stop and inspect partition table'; exit 1; }
[ "$(blockdev --getsize64 "$target")" = 67108864 ] || {
    echo 'ERROR: expected 64 MiB boot partition'; exit 1;
}
[ -f "$image" ] && [ "$(stat -c %s "$image")" = 67108864 ] || {
    echo 'ERROR: image absent or wrong size'; exit 1;
}
actual=$(sha256sum "$image" | cut -d ' ' -f 1)
[ "$actual" = "$expected" ] || { echo 'ERROR: image SHA256 mismatch'; exit 1; }
current=$(sha256sum "$target" | cut -d ' ' -f 1)
printf 'MODEL=%s\nBOOT_DEVICE=%s\nCURRENT_SHA256=%s\nIMAGE_SHA256=%s\n' "$model" "$target" "$current" "$actual"
if [ "$current" = "$expected" ]; then
    echo 'Already installed; no write needed.'; exit 0
fi
case "$current" in
    558daedf814461965553ec4093f92ba8525d844b0929e1a5c34b9fd791ea6cca|73fef2e1d3630b121be3be2597b367c5e77069a0a5829a91057f4fd71171d22d) ;;
    *) echo 'ERROR: current boot is not a known official baseline; do not bypass this check'; exit 1 ;;
esac
if [ "${1:-}" != '--apply-I-CONFIRM-BOOT-OVERWRITE' ]; then
    echo 'Inspection passed. No partition was written.'
    echo 'Writing boot can prevent startup. Read the new-board guide before applying.'
    exit 0
fi
backup_dir="/root/k7-recovery-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
dd if="$target" of="$backup_dir/boot-before.img" bs=1M status=none
[ "$(sha256sum "$backup_dir/boot-before.img" | cut -d ' ' -f 1)" = "$current" ] || {
    echo 'ERROR: backup verification failed'; exit 1;
}
printf '%s\n' "$backup_dir" >/tmp/k7-boot-backup-location.txt
dd if="$image" of="$target" bs=1M conv=fsync status=progress
sync
[ "$(sha256sum "$target" | cut -d ' ' -f 1)" = "$expected" ] || {
    echo 'ERROR: write read-back verification failed; do not reboot'; exit 1;
}
echo "WRITE_VERIFIED BACKUP=$backup_dir/boot-before.img"
echo 'Copy the backup to your PC, then reboot manually. No automatic reboot performed.'
