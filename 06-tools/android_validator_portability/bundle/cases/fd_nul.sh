set -u
umask 077
LC_ALL=C; export LC_ALL
set -C
: > "$W/audit" || exit 2
exec 8>> "$W/audit" || exit 2
rm "$W/audit" || exit 2
[ -f /proc/self/fd/8 ] && [ ! -s /proc/self/fd/8 ] || exit 2
cat "$B/fixtures/nul" >&8 || exit 2
[ -s /proc/self/fd/8 ] || exit 2
cat /proc/self/fd/8 || exit 2
exec 8>&-
