set -u
umask 077
LC_ALL=C; export LC_ALL
cmp -s "$B/fixtures/bytes" "$B/fixtures/ascii"
