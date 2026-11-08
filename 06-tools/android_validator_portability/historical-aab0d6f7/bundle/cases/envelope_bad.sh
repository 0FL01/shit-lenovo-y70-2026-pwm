set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/envelope/decode.sh" "$B/fixtures/envelope_bad" "$B/fixtures/plan" 012345abcdef 0 "$B/fixtures/empty" "$W/decoded"
