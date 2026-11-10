# Offline verification

Eight tests passed with `python3 -B -m unittest -v test_protocol` and again
with `python3 -B -O -m unittest -v test_protocol` from the new tools directory.
These are inert protocol/timeline fault tests, not device or transport tests.
No physical stop timing, native camera limit, setup/rollback, capture or custody
was executed or qualified. Tracked runtime files remain unchanged.
