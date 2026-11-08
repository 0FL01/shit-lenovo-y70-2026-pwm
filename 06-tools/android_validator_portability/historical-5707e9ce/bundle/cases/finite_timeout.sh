set -u
umask 077
LC_ALL=C; export LC_ALL
timeout -k 1 1 sh -c "sleep 2"
r=$?
printf "INNER_TIMEOUT_RC=%s\n" "$r"
[ "$r" = 124 ] || exit 3
