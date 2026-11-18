# XT2611-1: stock Extra Dim, 18 November 2026

**Android transform confirmed and restored; optical comparison rejected at the first ON photo.** No physical brightness or PWM conclusion.

The freshly identified target was awake, unlocked on ZRamSettingsActivity, manually set to brightness 105, with DIM policy and `manual [ dim ]` (not a lockscreen reading). User 0 stayed selected. No target UI interaction, brightness/refresh/DC change, raw DSI command, reboot or flash.

| Observed field | OFF | ON | Returned OFF |
|---|---|---|---|
| Secure reduce_bright_colors_activated | absent | 1 | absent |
| Secure level / persist_across_reboots | absent / absent | unchanged | unchanged |
| ColorDisplayService activated / strength | false / 50 | true / 50 | false / 50 |
| SF RGB matrix diagonal (alpha 1) | 1.000 | 0.522 | 1.000 |
| Sysfs brightness / actual_brightness / bl_power / panelDC | 828 / 0 / 0 / 0 | unchanged | unchanged |
| Active SF mode, vsync | id 0, 120.00 Hz | unchanged | unchanged |
| SF reported brightness / SDR white point | 4.835865 / 4.835865 nits | unchanged | unchanged |
| HDR layer present | false | false | false |

The Nothing PHOTO camera showed the oscilloscope raster, not the Lenovo screen. Coupling of that signal to the phone was not established. The camera's stock Auto exposure was left intact; a gate accepted only matching capture EXIF and required abort at the first failure. All 3 OFF JPEGs: ISO 9827; first ON: **ISO 12681 (+29%)**; 3 return JPEGs: ISO 9117. All seven had 69.99804 ms, f/1.87, 5.56 mm and flash off. The ON phase stopped at one photo instead of three. Fixed shutter time alone was insufficient; gain/ISP was not locked. No physical or raster contrast is admitted. Neither the zero-valued actual_brightness node nor the SF nits estimate is an optical measurement.

Host UTC: OFF shutters at 18:39:55/18:41:29/18:41:38. Activated 18:43:02 with bounded phone-side rollback and separate host inverse. ON snapshot at 18:43:05, shutter at 18:43:07. Inverse rehearsed beforehand while the key was absent. On EXIF rejection, temporary key deleted at 18:43:15; phone-side inverse exited 0. Independent literal comparison of all recorded state fields except timestamp passed at 18:43:49 and again at 18:44:16 after the return photos. All three color settings were again absent; same app, settings, DIM reason, inactive HDR, identity matrix, active SF mode and panel state. Camera and target clocks disagreed: shutter events are host-ordered, not cross-device synchronized measurement timestamps.

Private originals are outside the repository. No hardware PWM rate or 2 kHz claim. A future comparison needs fixed camera controls, replicated phases and an independent control tying the scope input to the phone.

### Dead ends and limits retained

- **Idle policy, not lockscreen.** The low current brightness node (828, not a historical 6879) does not identify a locked display. The live keyguard was not showing, the activity was in front, the power policy was DIM, and the target was not awakened for this contrast.
- **Camera false negative.** Several numbered camera devices were closed, but the full Active Camera Clients section showed the Nothing stock camera using ID 4. A preliminary one-line parser stopped before pressing the shutter, because the client record followed a bracket line. Direct UI dumps to shell stdout/tty also did not yield XML. A private temporary UI snapshot confirmed PHOTO/flash off and the shutter control; it was removed after use.
- **First OFF photo indexing.** The first photo existed, but the initial directory watcher selected a transient JPEG name and the stat failed. No extra shutter press was substituted. The uniquely new final IMG JPEG observed for that shutter was recovered privately and decoded in full; later frames required a new final-name JPEG and two matching nonzero sizes. The first JPEG does not have the same automated finalization receipt as the other six.
- **Clock mismatch.** The camera date was not the host date. Shutter-command times establish ordering, not synchronized optical acquisition or latency.
- **Signal-source correction.** The first photo shows an instrument raster rather than the Lenovo UI. That is the intended bench arrangement, not a bad framing diagnosis. Its labels/trace alone establish neither coupling nor sensor geometry. The raster crop was inspected before ON; no optical metric was admitted or rescued after the ISO failure.
- **Exposure gate, not missing data.** Only one ON image exists by design. ISO equality on three OFF files did not lock Auto exposure, and the three return files did not restore the original ISO. No repeat, alternative threshold, change of camera mode, or inference of causation from ISO drift was substituted. Sharpness, focus, gain processing and other ISP state are not proved invariant by identical EXIF.
- **Restore scope.** The two reported matches are for the explicitly captured Android fields only. The temporary secure activation key was deleted, not left present with value 0. This does not prove physical waveform restoration or a locked/identical camera ISP. The trial was not a full overlay/jitter survey, nor a threshold test at DBV 3600/3601.

The [sanitized evidence table](STOCK_EXTRA_DIM_20261118_data.json) contains all seven JPEG EXIF summaries, host-side shutter times, four target snapshots and rollback timestamps. Offline replay read the private original files, decoded all seven JPEGs, checked two exact raw snapshot comparisons (except time), and found only the activation key, service activation, RBC flag and RGB matrix changed in the exported ON snapshot. Photos, phone-specific identifiers and raw dumps remain outside Git.
