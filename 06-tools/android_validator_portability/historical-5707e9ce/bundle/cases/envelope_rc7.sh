set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/envelope/decode.sh" "$B/fixtures/envelope" "$B/fixtures/plan" 012345abcdef 7 "$B/fixtures/empty" "$W/decoded_rc7"
