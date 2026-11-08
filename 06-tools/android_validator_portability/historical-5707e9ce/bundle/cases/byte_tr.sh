set -u
umask 077
LC_ALL=C; export LC_ALL
tr -cd '\011\012\040-\176' < "$B/fixtures/bytes"
