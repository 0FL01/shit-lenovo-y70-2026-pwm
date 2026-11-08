set -u
umask 077
LC_ALL=C; export LC_ALL
set -C
printf old > "$W/override"
printf new >| "$W/override"
cat "$W/override"
rm "$W/override"
