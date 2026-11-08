set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/snapshot/validate_snapshot.sh" GUARD_TIMING - "$W/guard5" "$B/fixtures/guard5" "$B/fixtures/empty" 0
