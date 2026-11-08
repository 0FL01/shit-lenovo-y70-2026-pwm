set -u
umask 077
LC_ALL=C; export LC_ALL
printf "%s\n" "$((16777216 + 25165824))"
