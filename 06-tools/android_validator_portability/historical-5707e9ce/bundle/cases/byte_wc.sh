set -u
umask 077
LC_ALL=C; export LC_ALL
wc -c < "$B/fixtures/bytes"
