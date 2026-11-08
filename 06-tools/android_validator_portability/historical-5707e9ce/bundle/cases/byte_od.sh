set -u
umask 077
LC_ALL=C; export LC_ALL
od -An -v -tu1 < "$B/fixtures/bytes"
