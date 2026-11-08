set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/capture/validate_capture.sh" "$B/fixtures/capture_write" "$B/fixtures/nul" 012345abcdef write 0
