# GN9 source versus archived Pacman camera skew — offline lead

Status: `confirmed-other-device` for the archived PacmanPro Camera2 metadata;
`confirmed-other-device` for the public NothingOSS *Pacman* source;
`reported` for [Phone (2a) Plus main-camera GN9 identification](https://en.techreviewer.de/nothing-phone-2a-plus-test/);
`unknown` for the installed PacmanPro sensor driver, selected mode, sensor→video
row mapping, and physical Lenovo OLED PWM Hz. No camera/device operation here.

## Input and reproducible arithmetic

Public [NothingOSS kernel](https://github.com/NothingOSS/android_kernel_5.15_nothing_mt6886/tree/c09392da48d41a814258665c617249fa765ab222/drivers/misc/mediatek/imgsensor/src-v4l2/common),
branch `mt6886/Pacman/t`, commit `c09392da48d41a814258665c617249fa765ab222`:

- `s5kgn9_mipi_raw/s5kgn9mipiraw_Sensor.c`, Git blob
  `3b88cfd28d6bb53dbe0c4bb2d41b4a6e61d8803c`, lines 90–101,
  2631–2647. `s5kgn9stech_mipi_raw/s5kgn9stechmipiraw_Sensor.c`, blob
  `bb023c17d3a52d24fb4ffafc81be32d9caa0ed57`, has identical
  15,481-character `addr_data_pair_video_gn9` register table and mode numbers.
  Both exact blobs were retrieved into the approved external cache
  `/home/stfu/.cache/opencode-tmp/opencode/pacman-gn9-source-20261108/`;
  Git blob IDs were checked against downloaded bytes.
- Later `mt6886/Pacman/16b` commit `95262af69c8afe7f3323a03e965b1aff332fcffa`
  has stech blob `a9b5b95c336031bfba1643d1d99caafcb76f4593`:
  the same video register table and mode clock/geometry; its only source diff
  from the stech `t` version adds an exposure-start-offset feature.
- Negative source control: `s5kjn1_mipi_raw/s5kjn1mipiraw_Sensor.c`, blob
  `ceab583254ff4dbebb90cdd78da8c9b65db5f5cb`, was also checked;
  its normal-video output-span product is 24,140,800 ns, not 15,047,630 ns.

For GN9 `normal_video`, `.pclk=1,040,000,000`, `.linelength=6816`,
`.grabwindow_height=2296`, width=4080, `.framelength=5056`.
The programmed video table independently has `0x0342=0x1AA0` (6816),
`0x034E=0x08F8` (2296), `0x034C=0x0FF0` (4080), and
`0x0340=0x13C0` (5056). **Nominal** line time is
`6816/1040000000 = 6.553846154 μs`; nominal output-height span is
`6816 × 2296 × 10⁹ / 1040000000 = 15,047,630.769 ns`.

The **active** `#if 1` `imgsensor_winsize_info[2]` entry (same GN9 file,
lines 281–294) describes `8160×6144 → 4080×3072`, then a video crop
`x=0, y=388, 4080×2296`, with final output `4080×2296`. Independently,
the video register table (lines 2639–2651) programs raw horizontal bounds
`0x0010..0x1FEF` (8160 samples) and vertical bounds `0x0318..0x1507`
(4592 samples), output `4080×2296`, and `0x0900=0x2222` / `0x0380..0386=2`.
The raw vertical start is consistent with the source crop offset:
`(0x0318−0x0010)/2=388`. All three pinned GN9 source versions checked above
contain the same window entry and register values. Thus a **full** reported
Camera2 cropRegion `4080×3072` is compatible with an *internal* 2296-line
video window in this public source; it does not establish which window or
sensor-to-encoded-row resampling actually ran on PacmanPro. The meaning of
`0x0900` bits and the physical row-time mapping are not independently decoded.

The saved [stock capture](pacman_readout_capture_20261106.json) reports
`android.sensor.rollingShutterSkew=15,047,630 ns` at both ends of all three
720p→4K→720p clips, while `android.scaler.cropRegion` remains
`0 0 4080 3072`. Thus the *truncated* GN9 video output-height calculation
matches **all six** saved skew values to <1 ns. Among the ten listed GN9
mode-height × line-time products, only `normal_video` matches that integer;
for example `pre` gives 15,596,307.692 ns, `custom4` 11,656,615.385 ns.
The checked JN1 modes do not have this exact match (closest listed
`slim_video`: 14,570,057.143 ns). These are source/metadata comparisons,
not execution traces or measured sensor clocks.

## What the match does *not* establish

The published driver is for the Pacman family, **not** a verified hash of the
installed PacmanPro camera module/HAL. Public GN9 attribution and the striking
numeric match make `normal_video` a useful, falsifiable candidate; they do not
prove which sensor or mode Open Camera used in either output resolution. The
recorded full-active-array crop does not specify internal video-mode cropping,
pixel binning, resampling or the effective number of rows mapped to each
encoded line. AOSP Camera2 documents rolling-shutter skew across the *active
array* (`nothing_reference_20261107/result.md:73–78`); whether the vendor HAL
derived this particular number from GN9 **2296 output rows** rather than the
advertised 3072 active-array rows has not been established. Do not insert
6.553846 μs or 2296 unconditionally into the spatial-period→Hz conversion.

Even with a proven camera row map, the fine spatial train may be a harmonic or
ISP artifact, and a low-frequency emission envelope remains possible. This
test yields **no measured PWM frequency**, ≥2000-Hz proof, or new DSI setter.
R3 stays active; [A9-only](dsi_selector_split_20261107/result.md) is still
the best intermediate panel baseline (q93 ratio 0.2264067, not Hz).
The [A0D1C1 trial](dsi_coupled_9d_20261107/proposal.md) remains
NOT AUTHORIZED / NOT RUN; no flash, phone or camera I/O took place.

## Проверка простейшей GN9-модели против сохранённых выдержек (offline)

`hypothesis`: если PacmanPro действительно использовал указанный GN9
`normal_video`, все 2296 строк его окна равномерно заняли 720 строк видео,
а fine-полоса с периодом 93.43 строки — изображение **одной** физической
синусоиды без гармонического alias/ISP-нелинейности, её условная частота была бы
`720 / (93.43 × 2296 × 6816 / 1040000000) = 512.12741 Hz`.
Это **предсказание совместной модели**, не измеренные PWM Hz и не проверенный
sensor→video mapping. Для идеальной линейной интеграции амплитуда при выдержке
`t` относительно100 мкс равна `|sinc(π f t)/sinc(π f × 100 мкс)|`.

В уже сохранённом [stock exposure sweep](exposure_notch_20261107/supported/analysis.json)
при DBV3600/DC0/requested120 и ISO1600 нормированная fixed-q93 camera-Y
амплитуда сравнивалась с двумя100-мкс controls:

| Выдержка, мкс | Архивная Y-code ratio | Идеальная модель 512.127 Hz | Для сравнения идеальная 720 Hz |
|---:|---:|---:|---:|
| 500 | 0.8891 | 0.8995 | 0.8069 |
| 1000 | 0.3403 | 0.6238 | 0.3436 |
| 1428.571 | 0.0328 | 0.3263 | 0.0280 |
| 2000 | 0.1725 | 0.0238 | 0.2190 |

В частности, минимум с последующим rebound **не согласуется со всем
комплексом допущений** простейшей модели512 Hz: отношение при1428.571 мкс
отличается почти в10 раз, при2000 мкс — более чем в7 раз. Из этого нельзя
заключить, какое именно допущение нарушено: установленный sensor/mode, охват
его строк, alias/harmonic order, меняющийся источник или нелинейный ISP. Числа
для720 Hz — иллюстрация, **не** подбор/доказательство фундаментала720 Hz и не
опровержение≥2000 Hz у будущего профиля. Камерная метрика `Y−16` не является
калиброванной линейной оптической амплитудой, соседние окна сняты не одновременно;
физическая низкочастотная огибающая остаётся `unknown`.

Воспроизвести без телефона и повторного декодирования видео:

```sh
python3 - <<'PY'
import json, math
from pathlib import Path
s = json.loads(Path('artifacts/exposure_notch_20261107/supported/analysis.json').read_text())['stages']
f = 720 / (93.43 * 2296 * 6816 / 1040000000)
def sinc(x):
    return math.sin(x) / x if x else 1.0
for a in s[1:5]:
    t = a['exposure_ns'] * 1e-9
    ideal = abs(sinc(math.pi*f*t) / sinc(math.pi*f*100e-6))
    print(a['exposure_ns'], a['normalized_harmonic_ratios_to_bracketing_100us'][0], ideal)
PY
```

Независимое scoped review восстановило архивные отношения из RMS/`mean Y−16`,
пересчитало оба sinc-столбца и подтвердило фактор расхождения9.95/7.26 для
1428.571/2000 мкс без замечаний. Это проверка условной арифметики, не измерение Hz.

### Может ли округление выдержки до строки объяснить расхождение?

В закреплённом **публичном** GN9 source `s5kgn9mipiraw_Sensor.c:416–477`
`write_shutter()` принимает целое число строк, ограничивает минимум четырьмя и
в обычной ветке пишет его в `0x0202`. Source не доказывает, что установленный
PacmanPro использует эту ветку, как HAL переводит requested nanoseconds в строки
или что encoded кадры действительно имеют requested exposure. Проверим более
узкое условие: **если** все фактические выдержки отличаются от архивных запросов
не более чем на *одну* номинальную GN9 video-строку `6816/1040000000 s`
(≈6.554 мкс), включая100-мкс reference, может ли **только это округление**
спасти прежнюю совместную single-sine модель512.127 Hz?

В этой дополнительной модели `|sinc(πft)|` монотонна на каждом из трёх
рассмотренных коротких интервалов (около100,1428.571,2000 мкс); границы
отношения получаются из краёв интервала числителя и противоположных краёв
100-мкс знаменателя:

| Requested exposure | Идеальная ratio при ±1 GN9 video-строке | Архивная Y-code ratio |
|---:|---:|---:|
| 1428.571 мкс | 0.32157…0.33106 | 0.032795 |
| 2000 мкс | 0.02053…0.02697 | 0.172537 |

Даже допущенный с запасом однострочный сдвиг не покрывает архив: первый
минимальный model/observed фактор≈9.81, второй минимальный observed/model≈6.40.
Это исключает **только** однострочное округление как единственное объяснение
провала **всего** условного GN9-full-window/одной синусоиды/линейной камеры.
Не установлены installed driver, фактические выдержки и их погрешности,
sensor→video mapping, гармоники, ISP и физические PWM Hz; требовать от них
однострочной точности на основании этого source нельзя.

Воспроизведение границ стандартной библиотекой (без новых capture/DSI):

```sh
python3 - <<'PY'
from fractions import Fraction
from math import pi, sin
line = Fraction(6816, 1040000000)
f = 720 / (93.43 * 2296 * float(line))
def endpoints(ns):
    t = Fraction(ns, 10**9)
    return [abs(sin(pi*f*float(v))/(pi*f*float(v))) for v in (t-line, t+line)]
control = endpoints(100000)
for ns in (1428571, 2000000):
    a = endpoints(ns)
    print(ns, min(a)/max(control), max(a)/min(control))
PY
```

Независимое scoped review проверило монотонность sinc на всех трёх интервалах,
пересчитало границы и архивные Y-code ratios из RMS/`mean Y−16`: замечаний нет.

### Что говорит публичный camera-adaptor о масштабе выдержки?

Отдельный pinned NothingOSS `adaptor-ctrls.c` из commit
`c09392da48d41a814258665c617249fa765ab222`, Git blob
`383a7dbc76979f37f48cc40562574cbf3d4ff7dd`
(`drivers/misc/mediatek/imgsensor/src-v4l2/adaptor-ctrls.c:967–981,993–1015,2044–2077`)
предлагает **два** разных V4L2 пути: `V4L2_CID_EXPOSURE` передаёт
целочисленный `ctrl->val` в `SENSOR_FEATURE_SET_ESHUTTER` как число строк;
`V4L2_CID_EXPOSURE_ABSOLUTE` имеет шаг1 в единицах **100 мкс** и преобразует
`ctrl->val × 100000 / linetime_in_ns` с целочисленным делением до того же
sensor feature (при fine-integration возможен дополнительный множитель1000).
Какой путь использовал **установленный** HAL PacmanPro для архивных Camera2
exposure requests, не установлено. Поэтому предыдущая ±1-строчная граница —
только явно условная; её нельзя выдать за гарантию фактической выдержки.

Проверим более широкую иллюстративную границу для прежней **совместной** модели
512.127 Hz: допустим ошибку **±100 мкс** отдельно у requested100,1428.571 и
2000 мкс. Это покрывает округление до ближайших/соседних 100-мкс единиц как
возможность, но **не** доказывает реальную ошибку ≤100 мкс или выбор absolute
control. На100–200 мкс и1328.571–1528.571 мкс sinc монотонна; интервал
1900–2100 мкс включает идеальный нуль `1/f≈1952.639 мкс`, поэтому нижняя
граница здесь **0**, а не минимум из двух концов:

| Requested exposure | Идеальная ratio при ±100 мкс, включая control | Архивная Y-code ratio |
|---:|---:|---:|
| 1428.571 мкс | 0.25640…0.40158 | 0.032795 |
| 2000 мкс | 0…0.07073 | 0.172537 |

Воспроизвести обе границы (здесь известный внутренний нуль учтён отдельно):

```sh
python3 - <<'PY'
from math import pi, sin
f = 720 / (93.43 * 2296 * 6816 / 1040000000)
def sinc(us):
    x = pi * f * us * 1e-6
    return abs(sin(x) / x) if x else 1.0
control_min = sinc(200)  # |sinc| монотонна на [0,200] мкс
for t in (1428.571, 2000):
    endpoints = [sinc(t-100), sinc(t+100)]
    low = 0.0 if t-100 <= 1e6/f <= t+100 else min(endpoints)
    print(t, low, max(endpoints)/control_min)
PY
```

Даже этот более широкий допуск не покрывает обе архивные точки: минимальные
расхождения≈7.82 и≈2.44 раза. Он исключает *только* дискретизацию выдержки
такой величины как единственное объяснение провала условной модели;
реальные sensor/HAL, mapping, linearity, harmonic/alias и физические PWM Hz
по-прежнему `unknown`. Никакая частота панели из этих sinc-границ не измерена.

### Как публичный адаптер вычисляет время строки readout?

Ещё одна проверка **только публичного исходника**: NothingOSS `adaptor-drv.c`
на том же pin `c09392da48d41a814258665c617249fa765ab222`, Git blob
`04bda7003461c82bd02f078f5d2eab33ba202641`
(`drivers/misc/mediatek/imgsensor/src-v4l2/adaptor-drv.c:120–146,149–155,181–216,231–245`),
запрашивает `SENSOR_FEATURE_GET_PERIOD_BY_SCENARIO` дважды — с
`SENSOR_GET_LINELENGTH_FOR_READOUT` и без него. GN9 `feature_control` в трёх
сохранённых вариантах (обычные `s5kgn9*mipiraw_Sensor.c:10076–10130`,
`s5kgn9stechmipiraw_Sensor_16b.c:10079–10133`) в этой ветке использует
только scenario и возвращает одинаковый `normal_video.linelength`:
флаг readout не проверяется. `get_resolution` берёт высоту из active
`winsize_info` (`s5kgn9mipiraw_Sensor.c:9430–9445`), то есть для условного
GN9 normal_video — **2296** строк.

Адаптер округляет обе величины `linetime_in_ns` и
`linetime_in_ns_readout` **вверх до целого ns**: для `6816/1.04 GHz` это
`ceil(85200/13)=6554 ns`. Поэтому произведение именно *этого округлённого
поля* на2296 равно **15 047 984 ns**, а архивный Camera2 skew —
**15 047 630 ns** (разница354 ns). Архивное значение совпадает с усечением
*неокруглённого* произведения `2296×85200/13=15 047 630+10/13 ns`,
как показано выше. Это отвергает только гипотезу «архивный skew непосредственно
равен `mode->linetime_in_ns_readout × mode->height` данного адаптера» при
предположении GN9 normal_video; другой расчёт HAL мог использовать исходные
clock/line/height. **Установленный** драйвер, HAL, sensor→encoded row mapping,
физические PWM Hz и низкочастотная огибающая этим не установлены.

## Дополнительный контроль четырёх пространственных гармоник (offline)

В [сохранённой stock-серии](exposure_notch_20261107/supported/analysis.json)
есть нормированные к двум100-мкс controls camera-Y ratios для `q=h/93.43`,
`h=1…4`. Ранее сравнивался только `h=1`; здесь проверяется более сильная
**совместная гипотеза**: все четыре полосы — линейно снятые временные гармоники
одной стабильной синусоидальной частоты `f`, и относительная амплитуда каждого
`h` меняется с выдержкой только как
`|sinc(π h f t)/sinc(π h f × 100 мкс)|`. В том числе это требует считать
**пространственные** гармоники физическими временными; данные этого не доказывают.

| Выдержка, мкс | Архивный `h=3` | Условная512.127Hz | Иллюстрация720Hz |
|---:|---:|---:|---:|
| 500 | 0.072584 | 0.286792 | 0.079240 |
| 1000 | 0.045212 | 0.214044 | 0.076750 |
| 1428.571 | 0.014504 | 0.086654 | 0.029668 |
| 2000 | 0.026518 | 0.024412 | 0.067257 |

По всем16 archived `h=1…4` ratios при500/1000/1428.571/2000 мкс
среднее абсолютное отклонение этой **идеальной** формулы:512.127Hz —
0.126349,720Hz —0.025371,1440Hz —0.088481,2160Hz —0.146042.
На500 мкс близость условной720Hz модели есть и у `h=2` (0.371632 против
0.352544), и у `h=4` (0.233799 против0.249854), но это **не** устойчивое
побайтовое соответствие: например, при2000 мкс `h=3` даёт0.026518 против
0.067257. Числа720/1440/2160 взяты для иллюстрации, не получены подбором
частоты или независимой калибровкой; ошибка — не confidence interval и не
медицинская/панельная мера. Различие показывает ограничение условной512Hz
совместной модели, но **не** физические720 Hz, не отсутствие огибающей и не
запрет получить≥2000Hz в другом режиме. Неизвестны installed GN9/HAL,
sensor→encoded mapping, реальная линейность ISP/Y-кодов, темпоральный порядок
гармоник и стабильность рисунка между разнесёнными окнами.

Воспроизвести только из сохранённого JSON (без телефона/видео):

```sh
python3 - <<'PY'
import json, math
from pathlib import Path
stages = json.loads(Path('artifacts/exposure_notch_20261107/supported/analysis.json').read_text())['stages'][1:5]
def sinc(x):
    return math.sin(math.pi*x)/(math.pi*x) if x else 1.0
for f in (720/(93.43*2296*6816/1040000000), 720, 1440, 2160):
    diffs = []
    for stage in stages:
        t = stage['exposure_ns']*1e-9
        for h, actual in enumerate(stage['normalized_harmonic_ratios_to_bracketing_100us'], 1):
            ideal = abs(sinc(h*f*t)/sinc(h*f*.0001))
            diffs.append(abs(actual-ideal))
            if h == 3:
                print(round(f, 6), stage['exposure_ns'], round(actual, 6), round(ideal, 6))
    print(round(f, 6), 'MAE16', round(sum(diffs)/len(diffs), 6))
PY
```

Независимое офлайн-ревью пересчитало все16 архивных ratios и четыре MAE16
другой формулой интегрирования: значения и ограниченная интерпретация совпали.

## Четыре гармоники после обращения Y' (offline)

Предыдущий контроль [попиксельной обратной BT.709](exposure_notch_20261107/supported/envelope_check.md)
на **тех же шести stock-окнах** проверял только `h=1`. Здесь этот же
ограниченный camera-code sensitivity transform применён до x-усреднения к
`h=1…4`, без новой съёмки: `c=clip((Y−16)/219,0,1)`, затем `c/4.5`
при `c≤0.081`, иначе `((c+0.099)/1.099)^(1/0.45)`. Метод q, detrend2,
Hann и нормировка на среднее двух отдельно нормированных100-мкс controls
остались прежними. Из исходных13 500 000 Y-пикселей6×75 кадров получены:

| Выдержка, мкс | После inverse Y', `h=1` | `h=2` | `h=3` | `h=4` |
|---:|---:|---:|---:|---:|
|500|0.993399|0.392693|0.104128|0.265281|
|1000|0.509525|0.248087|0.075694|0.040970|
|1428.571|0.049325|0.024849|0.017969|0.025692|
|2000|0.294819|0.044461|0.043619|0.033139|

С теми же **условными** идеальными формулами
`|sinc(πhft)/sinc(πhf×100µs)|` из предыдущего раздела:

| Условная `f`, Hz | MAE16 исходного Y-кода | MAE16 после inverse Y' |
|---:|---:|---:|
|512.127411 (GN9/full-window допущения)|0.126349|0.131789|
|720 (иллюстрация)|0.025371|0.038611|
|1440 (иллюстрация)|0.088481|0.115448|
|2160 (иллюстрация)|0.146042|0.170402|

Порядок этих **четырёх заранее взятых модельных ошибок** сохраняется,
но ошибки меняются; например, `h=3` при2000µs становится0.043619,
а иллюстративная модель720Hz давала0.067257. Это **не** выбор
физических720Hz и не исключение≥2000Hz: исходное допущение о временном
порядке *пространственных* гармоник, неизменности излучения и линейной
камере не проверено. Применение обратной RGB-функции к одному encoded Y'
также не калибрует радиометрию или фактическую выдержку. Физический
фундаментал и низкочастотная огибающая остаются `unknown`.

Воспроизвести read-only из тех же видео/архива, без телефона и новых файлов:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 python3 - <<'PY'
from pathlib import Path
import json, math, subprocess, sys
import numpy as np
sys.path.insert(0, '06-tools')
from optical_spectrum import analyze_profiles
src = json.loads(Path('artifacts/exposure_notch_20261107/supported/analysis.json').read_text())
with np.load('/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz', allow_pickle=False) as a:
    pts, profiles = a['pts_s'], a['profiles']
idx = [np.flatnonzero((pts >= s['window_s'][0]) & (pts <= s['window_s'][1])) for s in src['stages']]
if profiles.shape != (5939, 500) or any(len(i) != 75 or i[-1]-i[0] != 74 for i in idx):
    raise ValueError('Archive window changed')
select = '+'.join(f'between(n,{i[0]},{i[-1]})' for i in idx)
cmd = ['ffmpeg','-v','error','-noautorotate','-i',
       'artifacts/optical/pacman_exposure_notch_supported_20261107.mp4',
       '-map','0:v:0','-an','-sn','-vf',
       f"select='{select}',crop=60:500:540:190,extractplanes=y",
       '-fps_mode','passthrough','-pix_fmt','gray','-f','rawvideo','pipe:1']
raw = subprocess.run(cmd,check=True,capture_output=True,timeout=240).stdout
if len(raw) != 6*75*500*60: raise ValueError('Native Y byte count')
frames = np.frombuffer(raw,np.uint8).reshape(6,75,500,60)
original, inverse = [], []
for stage, indexes, pixels in zip(src['stages'], idx, frames):
    rows = pixels.mean(axis=2)
    if not np.array_equal(rows, profiles[indexes]): raise ValueError('Archived Y profile')
    a = analyze_profiles(rows, frequencies=[h/93.43 for h in range(1,5)])
    if abs(a['raw_mean']-stage['raw_mean_Y'])>1e-9 or not np.allclose(
            a['total_rms_amplitude'], stage['q_harmonic_total_amplitudes'],rtol=0,atol=1e-9):
        raise ValueError('Archived original spectrum')
    original.append(np.array(a['total_rms_amplitude'])/(a['raw_mean']-16))
    c = np.clip((pixels.astype(np.float64)-16)/219,0,1)
    y = np.where(c<=.081,c/4.5,((c+.099)/1.099)**(1/.45))
    b = analyze_profiles(y.mean(axis=2),frequencies=[h/93.43 for h in range(1,5)])
    inverse.append(np.array(b['total_rms_amplitude'])/b['raw_mean'])
original, inverse = np.array(original), np.array(inverse)
original = original[1:5]/((original[0]+original[5])/2)
inverse = inverse[1:5]/((inverse[0]+inverse[5])/2)
for stage, a, b in zip(src['stages'][1:5], original, inverse):
    if not np.allclose(a, stage['normalized_harmonic_ratios_to_bracketing_100us'],rtol=0,atol=1e-9):
        raise ValueError('Archived original ratios')
    print(stage['exposure_ns'], ' '.join(f'{x:.6f}' for x in b))
def sinc(x): return math.sin(math.pi*x)/(math.pi*x) if x else 1.0
for f in (720/(93.43*2296*6816/1040000000),720,1440,2160):
    model = np.array([[abs(sinc(h*f*s['exposure_ns']*1e-9)/sinc(h*f*.0001))
                       for h in range(1,5)] for s in src['stages'][1:5]])
    print(round(f,6),'MAE16',round(float(np.abs(original-model).mean()),6),
          round(float(np.abs(inverse-model).mean()),6))
PY
```

Независимое офлайн-ревью декодировало13 500 000 исходных Y-пикселей и
пересчитало все16 ratios и четыре MAE16 через QR detrend и прямые Fourier
проекции: опубликованные значения и ограниченный вывод подтверждены.
