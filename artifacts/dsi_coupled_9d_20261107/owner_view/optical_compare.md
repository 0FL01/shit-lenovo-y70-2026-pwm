# A001 stock versus A0D1C1: saved-video comparison

`confirmed-on-target` for the **camera image**, not for OLED PWM Hz. The owner
requested this offline comparison, then explicitly requested stock return.
[Manual application](run.json) captured one A0D1C1 stage; the later
[return](return/run.json) verified the stock DSI program. Do not repeat either
application. The phone is **not intentionally left on A0D1C1**.

Inputs are the saved Nothing A001/Galaga Open Camera recordings:

- [Stock camera-only video](../../optical/a001_stock_dbv3584_camera_only_20261108.mp4):
  original target native DBV **3584**, H.264 1280×720, 168 frames/5.599933 s.
  This is an earlier camera-only test, not a simultaneous stock stage of the
  manual A0D1C1 run.
- [A0D1C1 manual video](../../optical/a001_a0d1c1_manual_20261108.mp4):
  target native DBV **3600**, H.264 1280×720, 358 frames/11.933100 s.

Both were made with nominal camera shutter 100 µs, ISO6400, manual focus
2.03874850 diopters, AE/AF/OIS/EIS OFF; the screen is inside ROI
`[x=540,y=190,w=60,h=500]`. The camera recordings have no audio. Image pixels
are **native limited-range encoded Y**, not calibrated emitted light.

## Spatial comparison

For each 75-frame window, average the ROI across its 60 columns, subtract a
degree-2 Legendre trend **per frame** (do not remove the temporal mean), then
apply a Hann window. The fixed `q=1/93.43` camera-row component is reported as
`sqrt(mean(|complex Fourier coefficient|²)) / (mean(Y)−16)`; its numerator and
the strongest interior fine/broad peaks are in camera Y codes. The peak search
uses 8192-point zero-padded FFT, fine `0.008…0.014` and broad
`0.0023…0.0053` cycles per output camera row. Overlapping windows are
**not** independent trials.

| Profile | Frames `[start:end)` | Mean Y | Fixed q93 RMS/(Y−16) | Fine peak, rows / Y | Broad peak, rows / Y |
|---|---:|---:|---:|---:|---:|
| Stock DBV3584 | 30:105 | 34.0925 | 0.303081 | 95.26 / 5.5285 | 234.06 / 1.6855 |
| Stock DBV3584 | 65:140 | 34.3432 | 0.280367 | 96.38 / 5.2059 | 372.36 / 1.0018 |
| A0D1C1 DBV3600 | 70:145 | 32.8919 | 0.265617 | 95.26 / 4.5134 | 227.56 / 1.2547 |
| A0D1C1 DBV3600 | 150:225 | 32.7790 | 0.292633 | 97.52 / 5.0184 | 240.94 / 1.8871 |
| A0D1C1 DBV3600 | 230:305 | 32.9446 | 0.260602 | 97.52 / 4.5246 | 372.36 / 1.1351 |

The fine image pattern **remains** near 95–98 camera rows in the candidate
footage; the normalized fixed-q amplitudes **overlap** the two stock windows.
There is no large, reproducible suppression in these unmatched recordings.
Broad peaks shift even within stock, and only ~1–2 broad cycles fit the 500-row
ROI. All ROI pixels are unsaturated (Y range stock14–44, candidate14–43).

**Limits:** the DBV differs by16 (3584→3600), clips are separated in time and
not a same-DBV simultaneous stock/candidate pair; screen content, focus,
camera ISP/codec and panel scan can affect the image. This comparison cannot
establish a causal PWM-frequency change, a low-frequency envelope's presence
or absence, owner comfort, or physical Hz. In particular, it cannot be
numerically compared with the historical **A9-only 0.2264067** ratio obtained
with a *different* Pacman camera and adjacent stock controls. A9-only remains
the best previously confirmed intermediate panel baseline. **R3 ≥2000 Hz is
unresolved.** The actual stock DSI return is evidenced by `return/run.json`,
not by these camera bands.

## Read-only reproduction

From the repository root with existing FFmpeg, ffprobe, Python and NumPy:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 python3 - <<'PY'
from pathlib import Path
import json, subprocess, sys
import numpy as np
sys.path.insert(0, '06-tools')
from optical_spectrum import analyze_profiles

sources = {
    'stock': ('artifacts/optical/a001_stock_dbv3584_camera_only_20261108.mp4',
              168, ((30, 105), (65, 140))),
    'a0d1c1': ('artifacts/optical/a001_a0d1c1_manual_20261108.mp4',
               358, ((70, 145), (150, 225), (230, 305))),
}
for name, (path, count, windows) in sources.items():
    video = Path(path)
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_type,codec_name,width,height:format=duration',
        '-of', 'json', str(video)], text=True))
    assert info['streams'] == [{'codec_name': 'h264', 'codec_type': 'video',
                                 'width': 1280, 'height': 720}]
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(video), '-vf',
        'crop=60:500:540:190,extractplanes=y', '-fps_mode', 'passthrough',
        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
    assert len(raw) == count * 500 * 60
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(count, 500, 60)
    print(name, count, int(frames.min()), int(frames.max()))
    for start, end in windows:
        profiles = frames[start:end].mean(axis=2)
        fixed = analyze_profiles(profiles, frequencies=[1 / 93.43])
        grid = analyze_profiles(profiles, n_fft=8192,
                                frequency_min=.0023, frequency_max=.014,
                                peak_count=0)
        q, amplitudes = grid['frequencies_cycles_per_row'], grid['total_rms_amplitude']
        fine = np.flatnonzero((q >= .008) & (q <= .014))
        broad = np.flatnonzero((q >= .0023) & (q <= .0053))
        fi, bi = fine[np.argmax(amplitudes[fine])], broad[np.argmax(amplitudes[broad])]
        mean = fixed['raw_mean']
        assert mean > 16 and end - start == 75 and not np.any(frames[start:end] >= 235)
        print(name, start, end, f'{mean:.4f}',
              f'{fixed["total_rms_amplitude"][0] / (mean - 16):.6f}',
              f'{1 / q[fi]:.2f}', f'{amplitudes[fi]:.4f}',
              f'{1 / q[bi]:.2f}', f'{amplitudes[bi]:.4f}')
PY
```
