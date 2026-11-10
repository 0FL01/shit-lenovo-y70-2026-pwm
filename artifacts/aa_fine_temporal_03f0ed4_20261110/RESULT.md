# Source03: конечная временная диагностика сохранённых профилей

**Статус: наблюдаемая вариация подтверждена в saved-data; причина не установлена.** Только OFFLINE, без нового декодирования, камеры, ADB, DSI, изменения настроек или устройств. Исходная acquisition остаётся rejected; diagnostic projection не является acquisition. Историческая created-inode custody отсутствует. Нет допуска AA10, optical-return approval, измерения физических Hz или вывода о переносимости/комфорте.

## Неподменяемый первичный результат

Исходные 180 кадров, окна 861–920 / 1534–1593 / 2171–2230, три ранее просмотренных 20×330 strips. q=0.019775390625 cycles/camera-row. Независимая реализация в `analyze.py` воспроизводит все девять исходных amplitudes до 1e−13. Primary sham: left +4.974169%, main +4.756525%, right **+5.390428%**. Старый all-ROI 5% criterion **не выполнен**. Ни одно исследовательское окно, weighting или модель ниже не заменяет его.

## Что меняется внутри окна

- Sham amplitude first→last20: left −13.499%, main −14.347%, right −12.425%. Return, напротив: +7.659%, +6.958%, +7.221%. Блоки не являются независимыми испытаниями или CI.
- Межполосовая корреляция sham amplitudes 0.940–0.963; фазовые различия между полосами имеют SD 0.022–0.031 rad. Это общая пространственная вариация, а не только локальный шум right ROI. Корреляции descriptive, без p-value.
- Main mean-Y по кадрам: baseline 43.567–44.995, sham 43.643–45.166, return 43.746–44.999. Межоконное среднее меняется мало, но это не означает постоянство каждого кадра. Sham amplitude↔mean-Y r=0.103; простое изменение среднего уровня не объясняет форму по одному этому показателю.
- Фаза движется: main median step 0.246 / 0.253 / 0.263 rad/frame; coherent fraction лишь 1.17 / 1.44 / 1.95%. Primary использует RMS индивидуальных комплексных coefficients, НЕ spectrum среднего профиля. Межкадровое взаимопогашение фазы не объясняет его вариацию. Phase-equivalent row displacement в JSON не является движением сцены, скоростью или PWM Hz.

## Ограниченные проверки моделей

1. **Fixed-q mismatch.** Per-frame maxima остаются внутри прежнего search-band; observed q от 0.01953125 до 0.02014160 cycles/row. Замена fixed-q каждым максимумом увеличила бы RMS всего на 0.145–0.197%. Это только диагностический верхний вариант выбора на той же сетке, не новый estimator. Разрешение записи остаётся ~1/330 rows, zero-padding его не улучшает.
2. **Pure-sinusoid phase/q null.** Синтетический синус с постоянной amplitude и измеренными фазами даёт менее 0.065% coefficient range. С измеренными q maxima и фазами диапазон ≤0.981%; sham first→last20 surrogate лишь +0.123…+0.163%, против наблюдаемых −12…−14%. В рамках single-sinusoid модели это не достаточное объяснение; неверная модель или bias q estimate остаются возможны.
3. **Leakage в ограниченных nuisance моделях.** Совместный least-squares polynomial2 + fine + fine/6 даёт fitted broad contribution в primary coefficient 0.047–0.054% RMS. Отдельная polynomial2 + fine + 2fine + 3fine модель даёт harmonic contribution 0.098–0.104%. Эти выбранные синусы не объясняют большую вариацию простой утечкой. Fine/6 всё ещё занимает 1.088 cycles и НЕ разрешён как физическая компонента. Непроизвольные broad shapes, sidebands, ISP и compression этим не исключены.
4. **Пространственная неоднородность важна.** Заранее заданные поддиапазоны только внутри просмотренных полос: full[0,330), inset[30,300), upper[0,220), lower[110,330). Main sham Hann degree2: +4.757%, +7.148%, +14.706%, −4.686%. Full rectangular: −0.949%. Те же знаки upper/lower наблюдаются во всех трёх полосах. Одним усреднением ROI получить «pass» нельзя.
5. **Модель envelope.** Polynomial2 плюс fine cosine/sine с quadratic пространственными coefficients воспроизводит main sham +4.503% и first→last20 −15.273%. Constant-amplitude joint model даёт main sham −0.850%; добавление broad −1.043%. Это демонстрирует чувствительность к пространственному weighting и совместимость с меняющейся spatial envelope, НЕ доказывает конкретный beat/envelope механизм. Residual RMS envelope 6.27–6.77 Y, так что модель не полная. Подгонка не является out-of-sample validation.

## Что не определено

Из усреднённых строк нельзя отличить перемещение сцены/освещения от движения полос, temporal panel variation, ISP gain/spatial processing и compression. Стационарный экран и снимки controls не доказывают отсутствие subpixel движения или per-frame camera variation. Видимые координаты трёх strips не расширялись. Повтор декодирования одних encoded bytes доказывает воспроизводимость, не отсутствие codec effects.

Независимый camera audit находится в соседнем artifact `aa_camera_factors_03f0ed4_20261110`: все окна имеют 2 I+58P, полный одинаковый GOP-age состав; snapshots неизменны, PTS gaps не выявлены. Его packet-size correlations остаются confounded whole-frame показателем и не устанавливают codec causality.

## Воспроизведение и проверки

`analyze.py` читает только private `final_profiles.npz` с закреплённым SHA256 c674abc2a36f9549651cda4248b917dcc34008cd31dcd062bb8392198037b963. Все raw profiles, full-precision индивидуальные arrays и промежуточные результаты остаются private; SVG публикует только округлённые координаты производных amplitude curves. `summary_final.json` содержит только сводки. Скрипт требует новые имена выходов; private-series нельзя писать за пределы private directory.

Запуск: `OPENBLAS_NUM_THREADS=1 python3 -B analyze.py --summary <new-summary.json> --private-series /home/opencode/.cache/legion-y70-aa-optical-media-03f0ed4-01/<new-series.npz>`.

10 focused tests прошли обычным Python и `-O`, включая независимое сравнение pinned module, rotating-phase null, точное восстановление synthetic envelope, неизменность входов и сохранение primary failure. Повтор финальной версии дал identical summary и все 54 private arrays. Original profiles SHA и старый committed diagnostic artifact unchanged. Исходные pinned modules не редактировались.

Следующий проверяемый шаг, пока **не выполненный; этот отчёт не предоставляет разрешение на запуск**, описан в `NEXT_STEP.md`.

`fine_temporal.svg` — sanitized figure только из численных профилей; `figure.py` проверяет тот же input SHA и границы plotting. Девять curves, общая шкала,20-frame boundaries. Не снимок экрана; phase не переведена в Hz.
