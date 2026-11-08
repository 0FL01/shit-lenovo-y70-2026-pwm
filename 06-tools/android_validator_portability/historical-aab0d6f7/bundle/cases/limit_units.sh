set -u
umask 077
LC_ALL=C; export LC_ALL
(ulimit -f 1 || exit 2; cat "$B/fixtures/finite2048" > "$W/limited")
r=$?
printf "%s\n" "$r"
wc -c < "$W/limited"
