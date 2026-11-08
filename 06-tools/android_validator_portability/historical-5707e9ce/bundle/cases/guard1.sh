set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/snapshot/validate_snapshot.sh" GUARD_TIMING - "$W/guard1" "$B/fixtures/guard1" "$B/fixtures/empty" 0
