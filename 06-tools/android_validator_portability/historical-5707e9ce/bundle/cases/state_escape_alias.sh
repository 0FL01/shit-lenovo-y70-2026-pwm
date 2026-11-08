set -u
umask 077
LC_ALL=C; export LC_ALL
P85_OFFLINE_EXPECTED_BOOT=bootA awk -f "$B/components/capture/state.awk" "$B/fixtures/fields" "$B/fixtures/display" "$B/fixtures/boot_literal" "$B/fixtures/empty" "$B/fixtures/esd_synthetic"
