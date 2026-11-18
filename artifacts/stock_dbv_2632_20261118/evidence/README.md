# Offline evidence checks

These scripts read private evidence; they do not import acquisition scripts, connect to ADB, or modify the evidence. Python with NumPy and Pillow is required. Run from this directory, substituting each privately held evidence directory:

```sh
python -B replay.py FIRST_RUN --allow-aborted
python -B test_replay.py FIRST_RUN
python -O -B test_replay.py FIRST_RUN
python -B replay_prospective.py FROZEN_GEOMETRY_RUN --allow-aborted
python -B test_prospective.py FROZEN_GEOMETRY_RUN
python -O -B test_prospective.py FROZEN_GEOMETRY_RUN
```

Without `--allow-aborted`, both reject these incomplete 17×3 experiments. They intentionally support the two observed **aborted** packets, not a hypothetical successful series. A fabricated complete marker is rejected. The second verifier does not retroactively reclassify the first trial.

- First run: zero complete phases or bracketed samples. The first DBV 2632 raster fails the original wide-window right-edge-position gate. The float-to-native-code reachability probes and exact observed state return are checked separately. Raw target snapshots independently check baseline and return, not every calibration plateau; per-level controls were live-guarded and only parsed brightness readbacks survive.
- Prospective run: one complete DBV 2632 plateau with three bracketed rasters, followed by one bracketed same-DBV sham raster. The next raster fails the frozen top-left relative-contrast gate. Neither optical acquisition reached the 2633 imaging phase. The separate earlier reachability calibration did apply and read back 2632 → 2633 → 2634 → 2631 without recording comparison rasters. The rejected raster has no post-camera bracket or late phase readback; neither is invented.
- Both: camera ID 0, manual request/result controls, strictly advancing frameCount and sensor timestamps, original PNG dimensions and measured geometry, channel-zero counts, original scene crop, OC/stock controls and advancing restores. Hidden preferences are not verified bytewise; sole-camera ownership is a live-guard attestation rather than archived full camera-service output.
- Prospective: source SHA-256 identifies the frozen geometry implementation, commissioning reference is recomputed from the three PNGs, and saved fixtures are compared to actual pixels. Early/late raw display files verify native DBV, float brightness, 120 Hz, SDR and DC off where present; provider DC readbacks are checked separately.

Log UTCs are host timestamps, while Camera2 sensor timestamps use a different clock. Their monotonic order is checked within each domain, not treated as synchronization. Raw display files have no embedded capture timestamp: identical same-DBV file substitutions cannot be distinguished independently. Negative tests detect stale/copied frames, changed pixels or fixtures, inconsistent/transplanted event timing, wrong plateau values, camera/control substitutions, missing brackets and fabricated completion; they are not tamper-proof provenance.

Processed preview, 500 µs exposure, auto white balance and ISP do not measure optical PWM frequency, physical modulation depth, photometric amplitude or channel linearity. JSON summaries contain no private paths or images.
