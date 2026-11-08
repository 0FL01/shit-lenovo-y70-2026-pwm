set -u
umask 077
LC_ALL=C; export LC_ALL
tail -c 1 < "$B/fixtures/bytes"
