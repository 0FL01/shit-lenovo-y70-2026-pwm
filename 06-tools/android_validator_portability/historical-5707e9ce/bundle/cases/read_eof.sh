set -u
umask 077
LC_ALL=C; export LC_ALL
v=; IFS= read -r v < "$B/fixtures/noLF"; r=$?; printf "%s:%s\n" "$r" "$v"
