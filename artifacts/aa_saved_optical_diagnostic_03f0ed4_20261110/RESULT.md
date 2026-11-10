# Saved source03 stock optical diagnostic

Status: **diagnostic complete; control repeatability unresolved**. The original acquisition remains rejected. No AA10/P85-14, new capture, device command or physical experiment occurred.

## Actual result

The private 96,172,619-byte recording has 2,553 original decoded frames. Fixed 60 windows are baseline 861–920, sham 1534–1593 and return 2171–2230. Conditional margins exceed 1.09 seconds; the stronger 0.5 second / 3 frame timing budget also retains 60 frames per stage. Timing is not sensor-to-file calibration.

The whole image contains Settings text/icons. Native-resolution inspection and independent lossless-crop review established only three clean background strips: left [225, 245, 20, 330], main [255, 245, 20, 330], right [285, 245, 20, 330]. Baseline selected these coordinates before comparative spectra; the same strips were then inspected in all nine first/middle/last frames. Subvisual blur cannot be excluded. Display-only contrast stretch was never applied to numerical inputs.

Baseline-only search 0.012–0.03 cycles/row selects q=0.019775390625, or 50.5679 rows per fine period. Degree 2 normalized fine / mean-Y changes relative to baseline:

| ROI | Sham fine | Return fine | Sham mean-Y | Return mean-Y |
|---|---:|---:|---:|---:|
| main | +4.7565% | +0.7124% | +0.3238% | +0.2001% |
| left | +4.9742% | +1.3471% | +0.2849% | +0.0900% |
| right | **+5.3904%** | +1.1941% | +0.3014% | +0.1541% |

**The existing all-ROI nominal 5% criterion is not met.** Right sham exceeds it; no ROI averaging, threshold change or post-result ROI/band reselection is permitted. Even without the acquisition/provenance blockers, these measurements would not satisfy that criterion.

Right sham stays +5.385…5.448% across None/1/2/3 detrending. Left without detrending is +5.052%, so its degree 2 result has no useful margin. Main sham 20-frame blocks are +13.484%, +2.822%, −2.798% relative to whole baseline. Blocks are not independent trials or confidence intervals. No high-Y clipping occurred; approximately 0.17–0.24% of pixels are at/below Y16.

The broad fine/6 component occupies only 1.088 cycles in 330 rows and is unresolved; 8192-point FFT interpolates, not adds resolution. Full spectra/profiles remain private. No full-waveform, physical-Hz, modulation-depth, comfort or restoration claim follows.

## Provenance and verification

Original source03 report SHA256 remains unchanged. A bounded, separately identified in-memory diagnostic projection adds only `/before/boot_id` from a hash-bound original event. Original strict validation still rejects the report; the unchanged source03 validator passes only the explicitly supplemented diagnostic projection. No accepted acquisition or qualification record is created. Source03 analysis blobs are pinned independently of later producer code.

Current source/destination digest, identity and bounded transfer checks passed. Historical created-inode/sink custody is unavailable and is not reconstructed by this transfer. No-concurrent-writers remains an explicit trusted assumption.

Independent numerical recomputation of all 9 mean-Y/fine amplitudes agrees within 1e−12. Repeated full native decodes, including the final publication revision, reproduce every measurement and every saved array exactly. Eleven focused boundary tests pass normally and under `-O`. Review records and concise machine-readable findings are in `review.json` and `summary.json`.

## Reproduction and next boundary

Private inputs and complete outputs are intentionally not committed. `diagnostic.py` defines exact local input locations and hashes. Materialize only the three files listed in `source_pins.json` from `git show 03f0ed4774052e843e22e03ff85e2997e9293828:06-tools/<name>` into the private `pinned_tools` directory, verify their declared SHA256, and preserve directory 0700 / files 0600. Do not substitute current working-tree tools.

Run the harness with the private video, `--review roi_review.json`, fresh private `--output` and `--profiles` paths, and `--no-concurrent-writers`. A fresh preview-only invocation omits review/profiles and uses `--preview-dir`, a new child of the video directory. Never overwrite evidence. Tests: `python3 -B -m unittest test_diagnostic` and the same command with `-O`.

The producer correction d5a522c was separately code-only deployed and verified; see `deployment.json`. Last physical source remains 03f0ed4, and d5a522c has not been physically run. Next work must address unresolved stock-control repeatability and source-bound acquisition validity before any candidate admission. This report authorizes no new physical operation.
