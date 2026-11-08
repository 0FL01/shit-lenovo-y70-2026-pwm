set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/capture/validate_capture.sh" "$B/fixtures/capture_C1_bad" "$B/fixtures/empty" 012345abcdef C1 0
