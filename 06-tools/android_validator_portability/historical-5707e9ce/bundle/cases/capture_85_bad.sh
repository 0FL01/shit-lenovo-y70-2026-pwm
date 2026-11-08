set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/capture/validate_capture.sh" "$B/fixtures/capture_85_bad" "$B/fixtures/empty" 012345abcdef 85 0
