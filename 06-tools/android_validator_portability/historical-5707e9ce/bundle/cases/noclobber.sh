set -u
umask 077
LC_ALL=C; export LC_ALL
set -C
: > "$W/exclusive"
( : > "$W/exclusive" )
