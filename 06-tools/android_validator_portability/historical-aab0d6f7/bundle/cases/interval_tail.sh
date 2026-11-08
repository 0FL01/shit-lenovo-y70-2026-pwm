set -u
umask 077
LC_ALL=C; export LC_ALL
sh "$B/components/interval/validate.sh" quiet PWM_TEST_BEGIN PWM_TEST_END 120 012345abcdef "$B/fixtures/interval_tail" OFFLINE
