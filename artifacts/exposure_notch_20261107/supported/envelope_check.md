# Проверка широкополосного остатка на старом stock exposure sweep

2026-11-08, только офлайн. Вопрос: разрешает ли подавление fine-train выдержкой
`1428.571us` объявить исчезновение остальных полос или выбрать между условными
720/1440/2160Hz? **Нет.** Это не повтор съёмки и не новое изменение панели:
[envelope_check.py](envelope_check.py) анализирует сохранённые
`/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz`,
которые были вырезаны из полного оригинального видео
`artifacts/optical/pacman_exposure_notch_supported_20261107.mp4`.
Источник, проверка видеопотока/камеры и исходные условия
DBV3600/DC0/requested120/ISO1600: [основной результат](result.md).

В [envelope_check.json](envelope_check.json) заново выбран **тот же** центральный
75-frame интервал каждой из шести фаз, ROI60×500, PTS/средние Y совпали с
оригинальным `analysis.json`. Спектр сохраняет stationary component:
`total=coherent+incoherent`, без temporal demeaning. Для четырёх вариантов
polynomial detrend0…3 берётся максимум квадратного корня total power в заранее
заданных **пространственных** полосах `0.0097…0.0119` (fine, около93px) и
`0.0023…0.0037 cycles/camera-row` (broad, около270–435px), делится на
mean(Y)−16 и сравнивается со средним двух100us controls. Это кодовые значения
камеры и band maxima, **не физическая яркость, envelope Hz или степень PWM**.

| Детрэнд | Fine на1428.571us / controls100us | Broad / controls100us |
|---:|---:|---:|
|0|0.04052|0.46088|
|1|0.04065|0.41510|
|2 (исходный анализ)|0.04063|0.45232|
|3|0.04000|0.46478|

Исходный fixed-frequency анализ измерял fine0.0328, здесь искали максимум в
полосе, поэтому числа не должны искусственно совпасть. При1428.571us fine
maximum упирается в нижнюю границу выбранной полосы; даже небольшое расширение
может повысить оценку. Broad пик сдвигается и нередко оказывается на границе
полосы при смене степени полинома. Во всей широкой полосе умещается только
**1.15–1.85 пространственных цикла на ROI500 строк**. Статический контент,
наклон кадра, фон/ISP и отвязка rolling-shutter от физических строк могут
давать такой остаток: **из него нельзя утверждать существование или отсутствие
низкочастотной envelope**. Но уже сам разный отклик двух полос показывает,
почему исчезновение fine-stripes при одной выдержке не квалифицирует весь экран.

Ещё один проверяемый предел метода: идеальная интеграция синусоиды предсказывает
при1428.571us относительно100us **0.028/0.029/0.030** для условных
720/1440/2160Hz: фактическая выдержка **близка**, но не равна общей
целопериодной нулевой точке `1388.889us`. Похожие малые ненулевые значения
не различают эти три модели. При500us модель
предсказывает0.807/0.353/0.079; реальная fine-мера0.889 в оригинальном отчёте,
но это **не количественная подгонка частоты**: camera code нелинеен по выдержке,
skew/harmonic order и осциллограмма неизвестны. При последующей попытке
численной оптической квалификации полезно смотреть **оба** spatial bands и
несколько неодинаковых выдержек, а не полагаться на один notch; добавлять
выдержки к уже подготовленной exact DSI-серии
без нового scope/подтверждения нельзя. A9-only baseline остаётся сохранённым;
профиля≥2000Hz здесь нет.

## Второй сохранённый контроль: стабильность broad spatial period

Ту же гипотезу о *фиксированном* широком пространственном периоде проверили на
[ранее завершённом stock 120→144→120→90→120](../../stock_base_rates_20261107/result.md),
без повтора аппаратного опыта. Его пять `phase-*-spectrum.npz` записаны из
другого оригинального видео при постоянных100us/ISO6400, DBV3600/DC0,
одинаковом ROI60×500 и quadratic detrend. Амплитуды с ISO1600-съёмкой **не**
сравниваются. Выбор широкой полосы расширен до`0.0015…0.005 cycles/row`, чтобы
все пять максимумов оказались внутри неё, а не на границе узкой полосы выше.

| Этап | requested Hz (refresh, не PWM) | Broad maximum, cycles/row | Period, px |
|---|---:|---:|---:|
|1|120|0.00433350|230.76|
|2|144|0.00415039|240.94|
|3|120|0.00274658|364.09|
|4|90|0.00262451|381.02|
|5|120|0.00415039|240.94|

В одинаковых120-этапах broad peak сдвигается на~58% по периоду между1→3 и
возвращается ближе к исходному в5; fine train в сохранённом отчёте остаётся
в узком классе~94.16/93.62/92.56px. Это наблюдение отвергает использование
**одного** broad peak как стабильной частотной калибровки в этих съёмках, но
не отвергает существования физической низкочастотной огибающей и не доказывает,
что источник broad — только камера/контент. Ни reset, ни DC/DBV/DSI профиль в
этом offline follow-up не менялись. Даже расширенный диапазон охватывает лишь
0.75–2.5 spatial cycles на500 строк; detrending и time/phase remain confounds.

Воспроизведение из сохранённого анализа (только чтение NPZ/JSON):

```sh
python3 - <<'PY'
import json, numpy as np
from pathlib import Path
p = Path('artifacts/stock_base_rates_20261107')
for stage in json.loads((p/'analysis.json').read_text())['stages']:
    n = stage['phase']
    with np.load(p/f'phase-{n}-spectrum.npz', allow_pickle=False) as data:
        freq, power = data['frequencies_cycles_per_row'], data['total_power']
        bins = np.flatnonzero((freq >= .0015) & (freq <= .005))
        peak = bins[np.argmax(power[bins])]
        assert peak not in (bins[0], bins[-1]) and stage['frames'] == 75
        print(n, stage['requested_refresh'], freq[peak], 1/freq[peak])
PY
```

## Дополнение: кодировка яркости на тех же шести stock-окнах

`ffprobe` исходного HEVC указывает `color_range=tv`, `color_transfer=bt709`,
`color_space=smpte170m`, `color_primaries=bt470bg`. Проверена гипотеза, что
нелинейная кодировка Y' сама создала экспозиционный минимум: каждый исходный
пиксель ограниченного Y переведён в `c=clip((Y−16)/219,0,1)`, затем применена
обратная BT.709-функция (`c/4.5` при `c≤0.081`, иначе
`((c+0.099)/1.099)^(1/0.45)`) **до** усреднения пикселей по x. В обоих
вариантах использованы одни и те же 6×75 исходных кадров и fixed-q=1/93.43,
degree2/Hann/total RMS; нормировка — амплитуда/среднее значение данного
представления, затем относительно среднего первого и последнего100µs окон.
Пересчёт исходного Y в точности воспроизвёл [архивные](analysis.json)
`raw_mean_Y` и `q_harmonic_total_amplitudes[0]` перед преобразованием.

| Выдержка, µs | Исходный Y: относительно controls | Обратная BT.709 на Y': относительно controls |
|---:|---:|---:|
|500|0.889092|0.993399|
|1000|0.340327|0.509525|
|1428.571|0.032795|0.049325|
|2000|0.172537|0.294819|

После преобразования минимум с rebound остаётся, хотя отношения изменились.
Даже при **условной** прежней GN9-full-window/одной синусоиде512.127Hz
идеальная линейная интеграция дала бы0.326305 при1428.571µs и0.023760
при2000µs; одна обратная кодировка Y' эти точки не согласует. Это **только
проверка чувствительности**: BT.709 маркирует encoded video, но функция
переноса применяется к RGB перед формированием Y', ISP/тональная кривая,
шум/black level и экспозиция сенсора неизвестны. Обращение *одного Y'* не
калибрует световой поток, не выбирает512/720/2160Hz, не доказывает источник
полос или отсутствие низкочастотной огибающей. В выбранных центральных ROI
доля кодов Y<16 не превышает0.000019, Y>235 отсутствуют; отсечение не
объясняет большой notch. Панель/камера не переключались, новой съёмки нет.
Встроенный reproducer воспроизвёл все четыре пары ratios и архивные Y-профили;
независимый пересчёт по native YUV, QR-detrend и прямому Fourier подтвердил
таблицу (расхождение исходного RMS ≤4.44e−16 Y-кода) без замечаний.

Воспроизведение только с сохранённым видео и профилями (файлы не создаёт):

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 python3 - <<'PY'
from pathlib import Path
import json, subprocess, sys
import numpy as np
sys.path.insert(0, '06-tools')
from optical_spectrum import analyze_profiles
src = json.loads(Path('artifacts/exposure_notch_20261107/supported/analysis.json').read_text())
with np.load('/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz', allow_pickle=False) as archive:
    pts, profiles = archive['pts_s'], archive['profiles']
indices = [np.flatnonzero((pts >= s['window_s'][0]) & (pts <= s['window_s'][1])) for s in src['stages']]
if profiles.shape != (5939, 500) or any(len(i) != 75 or i[-1]-i[0] != 74 for i in indices):
    raise ValueError('Archived windows changed')
selection = '+'.join(f'between(n,{i[0]},{i[-1]})' for i in indices)
cmd = ['ffmpeg', '-v', 'error', '-noautorotate', '-i',
       'artifacts/optical/pacman_exposure_notch_supported_20261107.mp4',
       '-map', '0:v:0', '-an', '-sn', '-vf',
       f"select='{selection}',crop=60:500:540:190,extractplanes=y",
       '-fps_mode', 'passthrough', '-pix_fmt', 'gray', '-f', 'rawvideo', 'pipe:1']
raw = subprocess.run(cmd, check=True, capture_output=True, timeout=240).stdout
if len(raw) != 6*75*500*60:
    raise ValueError('Unexpected HEVC Y byte count')
frames = np.frombuffer(raw, np.uint8).reshape(6, 75, 500, 60)
old, new = [], []
for i, (stage, chunk) in enumerate(zip(src['stages'], frames)):
    original = chunk.mean(axis=2)
    if not np.array_equal(original, profiles[indices[i]]):
        raise ValueError('Archived original Y profiles changed')
    y = analyze_profiles(original, frequencies=[1/93.43])
    if (abs(y['raw_mean'] - stage['raw_mean_Y']) > 1e-9 or
        abs(y['total_rms_amplitude'][0] - stage['q_harmonic_total_amplitudes'][0]) > 1e-9):
        raise ValueError('Original fixed-q metric changed')
    old.append(float(y['total_rms_amplitude'][0] / (y['raw_mean'] - 16)))
    c = np.clip((chunk.astype(np.float64) - 16)/219, 0, 1)
    inverted = np.where(c <= 0.081, c/4.5, ((c+0.099)/1.099)**(1/0.45))
    transformed = analyze_profiles(inverted.mean(axis=2), frequencies=[1/93.43])
    new.append(float(transformed['total_rms_amplitude'][0]/transformed['raw_mean']))
for i in range(1, 5):
    print(src['stages'][i]['exposure_ns'],
          f'{old[i]/((old[0]+old[5])/2):.6f}',
          f'{new[i]/((new[0]+new[5])/2):.6f}')
PY
```

## Третий сохранённый контроль: фаза вблизи экспозиционного минимума

Отдельная гипотеза: при переходе `1000 → 1428.571 µs` знак fine-компоненты
мог бы различить простые sinc-модели, даже если неизвестно время строки камеры.
На том же непрерывном stock-видео взята фиксированная пространственная
`q=1/93.43` после quadratic detrend; фрагменты по50–60 кадров подобраны **после
просмотра** среднего Y. Первый кадр со средним Y>66 среди индексов3270…3319 —
3297, но это граница *изображения*, **не доказанный кадр переключения сенсора**.
Рядом с ней есть также переходные всплески/UI. Ни одна новая команда панели или
съёмка не выполнялась.

| Кадры (нуль-базированные, конец не включён) | Модуль fine, Y-код | Coherence одного фазового наклона | Экстраполированная фаза относительно3210:3270, рад |
|---|---:|---:|---:|
|3210:3270, до перехода|4.547|0.999|0|
|3300:3360|0.338|0.929|+2.517|
|3320:3380|0.302|0.710|−2.397|
|3350:3400|0.259|0.420|+2.792|
|3400:3460|0.604|0.971|−2.421|

Разные разумные post-hoc окна дают сдвиги фазы, различающиеся минимум на
**1.37 рад по окружности** (первые два после перехода), при ослаблении
fine-модуля более чем в13 раз и падении coherence вплоть до0.42. Часть оценок
близка к `π`, но знак фазового перехода **не квалифицирован**: датчик мог менять
момент экспозиции, источник/ISP и временной alias дрейфуют, а метка3297
определена по изображению. Это отвергает использование **данных фрагментов**
как самостоятельного измерения фундаментальной частоты или выбора между
условными512/720/2160Hz; не исключает физическую низкочастотную envelope.

Воспроизведение только из сохранённых профилей (ничего не записывает):

```sh
OPENBLAS_NUM_THREADS=2 python3 - <<'PY'
import numpy as np
p = '/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz'
with np.load(p, allow_pickle=False) as data:
    x = data['profiles']
    assert x.shape == (5939, 500)
mean = x.mean(axis=1)
cut = 3270 + int(np.flatnonzero(mean[3270:3320] > 66)[0])
assert cut == 3297
y = np.arange(500)
basis = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), 2)
corrected = x - (basis @ np.linalg.lstsq(basis, x.T, rcond=None)[0]).T
window = np.hanning(500)
z = (corrected * window) @ np.exp(-2j*np.pi*y/93.43) * (2/window.sum())
def fit(a, b):
    frames = np.arange(a, b)
    phase = np.unwrap(np.angle(z[a:b]))
    slope, intercept = np.polyfit(frames-cut, phase, 1)
    coherence = abs(np.exp(1j*(phase-slope*(frames-cut)-intercept)).mean())
    return float(abs(z[a:b]).mean()), float(coherence), float(intercept)
pre = fit(3210, 3270)
for a, b in ((3210,3270),(3300,3360),(3320,3380),(3350,3400),(3400,3460)):
    amp, coh, phase = fit(a,b)
    delta = float(np.angle(np.exp(1j*(phase-pre[2]))))
    print(a,b,round(amp,3),round(coh,3),round(delta,3))
PY
```
