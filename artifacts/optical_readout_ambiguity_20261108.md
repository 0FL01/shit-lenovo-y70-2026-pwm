# Pacman rolling-skew timebase: stock q93 is not an absolute Hz measurement

**Status:** `confirmed-on-target` for the saved stock XT2611-1/Pacman video,
metadata and spatial image component; `hypothesis` for the modelled conversion
to physical emission; actual OLED PWM Hz **unknown**. Offline re-use of saved
captures only, no camera/ADB/DSI/device operation.

## Falsifiable check

Does the saved camera `android.sensor.rollingShutterSkew` by itself turn the
~93-row fine pattern into a measured temporal PWM frequency? **No:** the
effective active-array row span mapped to the video is not established by the
saved metadata. A numeric quotient needs that span *and* a qualified physical
harmonic order, neither of which is supplied by spatial stripes alone.

Evidence: `exposure_notch_20261107/supported/analysis.json` fixes the q93
reference period to **93.43 output-video rows**, ROI `[540,190,60,500]`, with
100-us bracketing controls. The untouched source is
`optical/pacman_exposure_notch_supported_20261107.mp4`;
`ffprobe -select_streams v:0` reports **1280×720**, ~30fps. Each phase of
`exposure_notch_20261107/supported/run.json` records
`rollingShutterSkew=15,047,630 ns`, `cropRegion=0 0 4080 3072` (the run also
kept exposure and ISO controlled). The archived private camera service dump
`/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/notch-prepared-camera.txt:1036–1047,2258–2271`
identifies the open camera-0 characteristics as active array **4080×3072**.
The Camera2 semantics and limitations of extrapolating a preview skew to a
different capture mode were previously cited from AOSP in
`nothing_reference_20261107/result.md:58–78`.

Under an **idealized** uniform-row/one-harmonic mapping, let `N_eff` denote
the active-array *row-coordinate span* effectively mapped onto the 720 video
rows. For period `P=93.43 rows`, skew `S=0.015047630 s` over `H=3072`
active-array rows and output height `V=720`, the conditional frequency is

```text
f = V·H / (P·S·N_eff);      N_eff = V·H / (P·S·f).
```

| Hypothetical time mapping | `N_eff` active-array row-coordinate span | Conditional `f`, not measured Hz |
|---|---:|---:|
| entire active-array height | 3072 | 512.13 Hz |
| geometric 16:9 crop at full active width (4080×2295) | 2295 | 685.51 Hz |
| hypothetical 720-row effective span | 720 | 2185.08 Hz |

Conversely, the same measured stripe period would require `N_eff≈2185.08`
for an assumed 720-Hz component, `≈1092.54` for 1440 Hz, or `≈728.36` for
2160 Hz. These are **inverse-model requirements**, not evidence that the
camera actually used those sensor spans. Full `cropRegion` and 1280×720
encoded dimensions do not specify binning, line skipping, stabilization-free
sensor mode, per-row readout mapping or whether the camera-service skew
applies to the encoded stream. The stripe might itself be a harmonic or an
ISP/content artifact; the idealized calculation cannot prove even its
physical origin.

Reproduce the arithmetic without opening the private dump or decoding video:

```sh
python3 - <<'PY'
P,S,H,V = 93.43,15047630e-9,3072,720
for N in (3072,2295,720): print(N,V*H/(P*S*N))
for f in (720,1440,2160): print(f,V*H/(P*S*f))
PY
```

This **does not invalidate** the separately measured exposure-notch/rebound:
`exposure_notch_20261107/supported/result.md:27–39` says its 500/1000-us
q93 attenuation favors a ~720-Hz *fine component* over ideal 2160 under
that model, with ISP/nonlinearity and integer-period caveats. The present
test rejects only a shortcut from *one* rolling-skew number and row spacing
to absolute fundamental PWM Hz. It creates no improved panel baseline;
A9-only remains the best measured intermediate panel setting, R3 remains
open, and A0D1C1 has no operation-specific approval or run.

## Follow-up: saved camera dump mode metadata (offline)

Проверена **уже сохранённая** копия camera-service dump размером 394719 байт
по названиям `sensor mode`, `binning`/`pixel skip`, `line/row time` и
`pixel clock`/`pclk`: таких явно именованных строк нет. Присутствуют поля
`cropRegion`, stream configuration и readout, но они не задают соответствие
активных строк 4080×3072 и 720 строк encoded video или `N_eff` в формуле выше.
Проверка выполнена локальным поиском имён и выводом только числовых токенов
выбранных строк; полный private dump не публиковался. Это закрывает только
гипотезу о **прямо указанной** калибровке sensor/video mode в сохранённом
camera-service тексте: vendor-поля с другими именами, внутренняя HAL-настройка
и аппаратная временная база не квалифицированы. Ни одно из трёх условных
значений частоты выше не становится измеренной PWM-частотой.
