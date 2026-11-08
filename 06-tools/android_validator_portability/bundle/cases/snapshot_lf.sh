set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/snapshot/validate_snapshot.sh" STATE_ONLY 00000000-0000-0000-0000-000000000000 "$W/state" "$B/fixtures/fields" "$B/fixtures/lf" 0 "$B/fixtures/display" "$B/fixtures/lf" 0 "$B/fixtures/boot" "$B/fixtures/lf" 0 "$B/fixtures/empty" "$B/fixtures/lf" 0
