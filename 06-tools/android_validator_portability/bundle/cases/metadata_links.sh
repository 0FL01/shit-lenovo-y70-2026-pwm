set -u
umask 077
LC_ALL=C; export LC_ALL
stat -c %h "$B/fixtures/bytes"
