# HORIZON R3 — реестр рычагов OLED emission timing

**TL;DR. Нового проверенного setter физической PWM ≥2000 Гц не найдено; R3 остаётся активной. Установлены три конкретных пути: ещё не испытанная совместная D×C ветвь при A9=OFF, зависимость состояния от доставки кадров/времени после команды и внешний Qualcomm ESYNC/EMSYNC с документированным генератором, но неизвестной применимостью к ILI97701A.**

Дата: 2026-11-08, UTC+3. База: `fffb0feeda534add90dfaf7056964d40adefc183`, последнее изменение main на момент восстановления — `Preserve vendor ALS XML line endings`, 09:53:03 UTC+3. Исходное рабочее дерево полученного checkout чистое; исследование отделено в `research/horizon-r3-leverage-20261108`. Несохранённое дерево прежнего рабочего компьютера и текущее состояние телефонов этим не проверены.

Все новые действия — offline: сохранённые данные, публичные первоисточники, собственные воспроизводители и независимое ревью. **Новых ADB/fastboot/DSI, изменений настроек, reboot/flash или съёмок не было. A0D1C1 — NOT AUTHORIZED / NOT RUN.**

## 1. Executive findings: что действительно новое

1. **Неиспытанное взаимодействие отделено от уже закрытых отрицательных опытов.** Семь сохранённых 875-byte программ разложены на A=`23:A9`, D=`24:9D`, C=остальные83 изменённых байта в32 пакетах. Шесть качественно наблюдённых вершин имеют ранг6 из8; отрицательные D-only и C-only оставляют свободным результат A0D1C1. Это новое формальное обоснование прежнего кандидата, не новый профиль и не расшифровка frequency register. Источник: [A: факторизация](horizon_r3_20261108/agent_a_ddic.md), §§1–2; [независимый пересчёт root](horizon_r3_20261108/root_offline_audit.json), `/qualitative_design`.

2. **Выявлен конкретный пробел наблюдения в историческом redraw.** Три probes существующего runner видят control-command transfer, но не pixel-frame kickoff. В публичном Motorola source command-mode путь идёт через `sde_encoder_phys_cmd_trigger_start → sde_encoder_helper_trigger_start → sde_hw_ctl_trigger_start → CTL_START` либо autorefresh. В архивном redraw также смешаны событие и время: post-redraw hold начинается через14.796735s после DBV replay, а pre-redraw hold заканчивается через7.357898s. Нет равноотложенного no-redraw sham. Следовательно, frame-latch, задержанная активация и refresh/maintenance history остаются различимыми гипотезами. [Исходники, symbols и хронология](horizon_r3_20261108/root_cadence.md), §§«Первичные source anchors», «Независимый временной confound».

3. **Внешний ESYNC доведён от имени свойства до физического канала.** Официальный Qualcomm/Motorola код вычисляет период EM в строках, программирует SDE MMIO и использует отдельный pinmux. Qualcomm описывает внешний AP→DDIC HSYNC, по которому DDIC формирует EM. Но сохранённая target-конфигурация — command mode без ESYNC gates; вход DDIC и разводка XT2611-1 неизвестны. Это сильный источник семантики альтернативного механизма, а не готовая настройка телефона. [B: источники и ограничения](horizon_r3_20261108/agent_b_sources.md), §§1–2,5.

4. **Построен явный предел камерной идентификации.** При одной выдержке даже известный row-time не исключает разные временные частоты, если неизвестна пространственная фаза эмиссии. Положительные синтетические поля с721.336/1441.336/2161.336Hz дали одинаковые rolling-shutter отсчёты с расхождением≤2.16×10⁻¹². Это контрпример к достаточности такого измерения, не fit видео и не три равновероятные модели телефона. [C: вывод, ограничения и независимый интегральный контроль](horizon_r3_20261108/agent_c_optics.md), §§2–3.

## 2. Восстановленное состояние и сила исходных данных

Прочитаны `AGENTS.md`, `.opencode/horizon-goal.md`, начало `WORKSTATE.md` от новых checkpoint, `artifacts/research_report.md`, selector-split, coupled-on, DDIC-regdump, state-marker и brightness-policy отчёты. Затем адресно проверены последние20261108 GN9/exposure/aliasing/codec, DT gates и UEFI selection результаты. Старое описание закрытия этапов в YAML не заменяет более поздние R3 checkpoint.

**Подтверждено на target в сохранённых сериях (`confirmed-on-target`), не перепроверено новым live-сеансом:**

- BOE ILI97701A selected `cmd_v4`, panel IDd2; software variant не расшифровывает physical silicon revision. Persistent KSU UID0 уже установлен; unlock/root не являются текущей задачей. [AGENTS.md](../AGENTS.md), строки6–9; [panel identity](panel_identity.md).
- A9-only: `23:A9=8E`, `24:9D=0E`, DBV3600; исправленная total-q93 ratio **0.22640672181213273** относительно соседних stock. Сигнал среднего изображения1.059×, широкая структура остаётся. Это сохранённый промежуточный baseline камерного эффекта. [selector result](dsi_selector_split_20261107/result.md), строки14–49,76–108; `analysis_spatial_v2.json`, `/stages/1`.
- 9D-only: q93 ratio **1.0214237646270794**; S0C1: **0.9363479490548708**, владелец отверг, stock восстановлен. Эти отрицательные результаты закрывают только испытанные контексты. [selector result](dsi_selector_split_20261107/result.md), строки21–35; [S0C1 result](dsi_coupled_on_20261107/result.md), строки8–33,52–64.
- `4F:81` принимает stock06/10; наблюдавшийся fine pattern не исчезает при обеих OFF-конфигурациях. C1/C9/D1 остаются06, D9 остаётся10. Буквальный «6/16 EM pulses» не установлен. [readback findings](ddic_regdump_20261107/readback_findings.md), строки32–82.
- Native ON до/после redraw имеет разные camera metrics; архив не квалифицирует физическую причину перехода. [прежний proposal](dsi_coupled_9d_20261107/proposal.md), строки29–34; `dsi_stock_on_control_20261106/with_redraw/run.json`.

**Source/reference evidence, а не подтверждённая работа этого телефона:** публичные ESYNC backend/pinctrl/modes, BOE patent mechanisms, UEFI reference selection и GN9 source mode. Для последних не переименовываем source match в установленное runtime состояние.

**Ограничение материализации:** в checkout есть425 selected-DT properties,52 command arrays/1101 packets, DDIC dumps, JSON summaries и часть spectrum artifacts. Нет target `msm_drm.ko`, исходных MP4 и private decoded-video caches. Новые ELF decompilation и повторное декодирование видео не заявляются. Это согласуется с [RECONSTRUCTION.md](../RECONSTRUCTION.md), разделами внешних inputs; каталог release `evidence-2026-11-08` при проверке не доступен (404). Результаты прежних raw-data проверок сохраняют свой исторический provenance, но не становятся повторёнными этим запуском.

## 3. Карта пробелов в причинной цепочке

### 3.1. Control register → emission mechanism

**Есть управляемость:** `23:A9`/`24:9D` byte/readback и full native ON/OFF programs. **Неизвестно:** selector, waveform shaping, duty, mask, bank или timing. Изменение изображения доказано; число EM-импульсов и период не декодированы.

**Есть составной native transaction:** во всех четырёх selected-DT writers `4F:81` присутствует последовательность `08:98=02 → 4F:81 → 4F:88=78 → … → 08:98=A6 → 4F:8B=78`; timing@4/@5 добавляет `4F:8A=78`. Это допускает bank/update/commit модель, но не подтверждает её. Для остальных запрошенных4F-пар, `07:EC`, `23:C1` writers среди1101 пакета не найдены. Отсутствие в DT не означает read-only или отсутствие иных runtime writers. [A](horizon_r3_20261108/agent_a_ddic.md), §2; `agent_a_factorization.json`, `/transaction_skeletons`.

`07:EC` и `23:C1` остаются markers неизвестной семантики; их зависимости от DBV/content/config/checksum не разделены. Старый длинный reader не квалифицирует response length. Повтор его запуска не является безопасным способом узнать semantics. [state-marker result](ddic_state_marker_20261107/result.md); [readback findings](ddic_regdump_20261107/readback_findings.md).

### 3.2. Mechanism → optical waveform

Значения readback недостаточны для определения динамического состояния. Нужно различить delivery пикселей, задержку после программы и настоящий latch. Контрольный DSI logger не измеряет scan, TE или actual pixel cadence. Settings repaint из runner временно меняет content; это не изолированное повторение идентичных пикселей. [root cadence](horizon_r3_20261108/root_cadence.md); `06-tools/run_dsi_mode_trial.py:24–28,371–429`.

В BOE [US20250014518A1](https://patents.google.com/patent/US20250014518A1/en), Fig.3–6 и описание refresh/maintenance frames, одинаковая ширина EM может сопровождаться разной яркостью; предлагается менять ширину для компенсации. Это первичный контрпример тождеству «меньше камерная компонента ⇒ выше carrier». Патент не идентифицирует ILI97701A и не даёт target bytes; пример low-refresh≤40Hz нельзя присвоить текущему nominal120.

### 3.3. Optical waveform → verified PWM frequency

В сохранённых данных не квалифицированы одновременно sensor-row mapping, temporal harmonic order, panel spatial phase, ISP response и абсолютная временная база. Exposure sweep ограничивает отдельные модели; GN9/full-window simple model имеет конкретные противоречия. Это не превращает оставшуюся условную720Hz модель в измеренную частоту. [GN9 report](pacman_gn9_readout_20261108.md), §§совместного harmonic/BT.709 контроля; [оптическая неоднозначность](optical_readout_ambiguity_20261108.md).

Fine и broad могут принадлежать одному локальному временно́му процессу с разной пространственной фазой либо нескольким процессам. Новый двухкомпонентный counterexample даёт одинаковую картинку для одной локальной частоты721.336Hz и пары721.336/241.336Hz. Он не описывает реальное видео, но запрещает вывод о low-frequency envelope из одной ширины полосы. Возможность такой огибающей **остаётся открытой**. [C](horizon_r3_20261108/agent_c_optics.md), §§2–4.

Минимальный независимый измерительный канал для численного Hz: локальный малый optical spot → фотодиод/линейный DC-coupled front end → raw ADC с квалифицированной временной базой. Требования и их смысл приведены в [C](horizon_r3_20261108/agent_c_optics.md), §4: ≥100ksample/s, clock error≤1%, характеризованная полоса DC–10kHz с anti-alias, отсутствие AGC/clipping, ≥5s и dark/noise trace. Это не обязательно осциллограф. Наличие такого recorder у владельца неизвестно; согласно `AGENTS.md:15`, его отсутствие **не блокирует сравнительную камерную пробу**, но блокирует объявление точных Hz по её результатам.

### 3.4. Что больше не повторять без нового противоречия

- Unlock/root, CN48-7 vs GLOBAL selected-v4 regional diff: готового high-PWM массива не дали; status уже актуализирован в `WORKSTATE.md`.
- S0C1, D-only, isolated mode90/page53/page63: их контексты испытаны; новая серия тех же действий не добавит независимой переменной. [A](horizon_r3_20261108/agent_a_ddic.md), §§1,4.
- Generic PMIC PWM при BOE `bl_ctrl_dcs`, clamp DC2/3→1, LUT как frequency control, отсутствующие selected-DT PRR/freq-step/ELVSS-HBM gates. [brightness recon](brightness_policy_recon_20261107/result.md); [ELVSS gate](elvss_hbm_gate_20261108.md); [runtime recon](runtime_pwm_recon_20261107/result.md).
- Бесконечная подгонка одного camera sweep или декодирование чисел06/10/78 как pulses/Hz. Новое измерительное ограничение или exact-panel semantics нужны раньше новой такой итерации.
- Второй пустой поиск datasheet не доказывает невозможность. Для ESYNC следующая полезная единица знания — конкретный interface/FPC артефакт, а не ещё один поиск слова `pwm`.

## 4. TOP-3 technical leverage points

Оценки ниже качественные; статистики для честных процентов успеха нет. **Вероятность meaningful physical change и вероятность конечных ≥2000Hz различаются.** Ни одному неизвестному регистру не присвоен множитель×2–3.

### TOP-1 — A0D1C1: условная D×C ветвь при A9=OFF

**Точка:** существующий `dsi_coupled_9d_20261107/on_keep_a9_off.bin`, native ON с единственным возвратом byte68/`23:A9` в0E; `24:9D=8E`. C содержит32 изменяемых пакета; профиль отличается от OFF на33 пакета/84 байта.

**Причинная гипотеза:** D выбирает emission/control режим только на фоне C1, а A9=ON маскирует его уже известным подавлением fine. Альтернатива: вся наблюдавшаяся suppression определяется A, а D×C не даёт существенного эффекта. Два отрицательных одиночных опыта совместимы с обеими гипотезами.

**Минимальная проверка:** одна уже подготовленная `stock → A0D1C1 → stock` при одинаковых DBV/replay/redraw/камера. Она измеряет **эффект целого профиля**. D×C interaction contrast дополнительно требует исторических010/001/000 и предположения сопоставимости состояния; отдельно причинность9D она не доказывает. Следующая операция подробно ограничена в [horizon_next_experiment.md](horizon_next_experiment.md).

**Подтверждение:** обратимый новый optical state при точных readbacks и успешном stock-return. Frequency-версия гипотезы требует независимой waveform timebase, pulse intervals и проверки гармоник/огибающей. **Опровержение:** при валидном delivery/readback и достаточной чувствительности нет существенного отличия от соседних stock — закрывается эта реализация D×C при данных условиях; R3 не закрывается.

**Оценка:** доказанность intervention высокая, emission semantics низкая; novelty формального обоснования средняя, сам профиль исторический. Information gain высокий для отсутствующего A=0 контекста, ограниченный для Hz без независимого канала. Шанс физического изменения открыт, численно не оценим; уверенность в достижении≥2000 низкая. Feasibility высокая после exact approval; стоимость — уже выполненный offline audit и одна кандидатная стадия/два stock controls. Риск смешанного DDIC state и transport fault; нормальный rollback — полный native OFF+DBV replay+redraw, при неопределённой очереди только согласованный emergency reboot. Детали transport limits обязательны, не скрыты за словом «short read».

**Почему первый:** готовые target-origin bytes, ранее проверенная процедура stock-return, одна новая вершина без повторения отвергнутого S0C1. Возврат именно из A0D1C1 ещё не испытан. Ранг6/8 не доказывает превосходства этой вершины над101: под искусственным равномерным prior обе дают1bit. Приоритет инженерный — A=0 убирает известный маскирующий путь и для011 уже подготовлен scoped runner.

### TOP-2 — доставка кадров / active–idle history / момент активации

**Точка:** штатные frame-data submissions и фактический SDE command-mode kickoff при постоянных DBV, final content и requested refresh. Это управление входной историей DDIC, не команда увеличить refresh rate.

**Доказательства:** историческое изменение camera state после repaint; существующий control logger не покрывает source pixel path; target-origin symbol archive содержит соответствующие SDE symbols. Source pin не доказывает тождество всех target function bodies; текущий ELF недоступен. [root cadence](horizon_r3_20261108/root_cadence.md), все точные функции/строки и symbol offsets.

**Гипотезы:** data-event latch; delayed activation после DSI/DBV; разный active/maintenance schedule; эффект transient content/ISP. **Минимальное различение:** одинаковая задержка в sham и событии, постоянные пиксели, подтверждённый frame-transfer observer и независимая оптика. Сначала single event vs no event; continuous cadence — отдельный следующий вопрос только при положительном основании. Текущий Settings repaint не является готовым строгим harness.

**Подтверждение:** изменение возникает после подтверждённого data event и отсутствует в равноотложенном sham, обратимо при удержании остальных условий. **Опровержение event-latch:** такое же изменение до event либо в sham; сужение cadence-гипотезы — неизменная waveform при реально различающихся cadence. Негатив не устанавливает назначениеA9.

**Оценка:** средняя evidence о скрытой переменной, низкая о frequency effect; высокая novelty observer/time confound; высокий information gain для механизма, не оценённый шанс≥2000. Offline feasibility высокая, будущий harness/observer ещё нужен. Стоимость — одна bounded разработка harness и минимальная matched пара после новой авторизации. Риск ниже неизвестных DDIC writes при штатном frame path, но используемый panel profile сохраняет собственные риски. Возврат: прекратить generator submissions, штатный static content и полный native OFF, если профиль был изменён. Нет разрешения писать CTL_START/MMIO напрямую.

### TOP-3 — внешний Qualcomm ESYNC/EMSYNC

**Точка:** host generator period/width → отдельный ESYNC pin → согласованный external-sync input DDIC → EM pulses. В driver pin `fa008c43c070ff20faa33853649f5dfd4c427e99`, `sde_encoder_phys_vid.c:861–939`: `period_lines=floor(vtotal×vrefresh/emsync_fps)`; width задаётся в тысячных line period и переводится в clock cycles. `sde_hw_intf.c:340–370` пишет два16-bit поля `INTF_ESYNC_EMSYNC_CTL`, offset0x418; это **SoC MMIO, не DDIC register**.

**Доказательства:** pinned bindings/pinctrl (DT pin `f088523dfba85c95c15f43726fcf972c0c7a957a`) и [Qualcomm US20250251773A1](https://patents.google.com/patent/US20250251773A1/en), Fig.4/5. [Сохранённые исходные excerpts](horizon_r3_20261108/agent_b_esync_primary_excerpts.md), source sections `sde_encoder_phys_vid.c:890–939`, `sde_hw_intf.c:340–388`, bindings685–700, pinctrl141–179.

**Критический blocker:**425 target properties — cmd-mode без ESYNC gates; во всех пяти точных ILI97701A public variants на выбранном pin ESYNC отсутствует. Reference GPIO88/100 не доказывают target wiring. DRM frequency property выбирает существующий mode и может требовать panel-specific `EM_PULSE_SWITCH`; это не произвольный Hz setter. Байты NT37802 не переносимы.

**Минимальная проверка:** точный IL97701A interface/pinout/init документ вместе с FPC/board mapping, который подтверждает вход, соединение и mode. Это offline semantic gate; hardware enable пока не подготовлен. **Опровержение внешнего пути:** подтверждённое отсутствие входа или соединения на точной ревизии. **Подтверждение применимости:** документированная замкнутая цепочка до DDIC; затем нужны source/binary verification, допустимые времена и optical test.

**Оценка:** высокая evidence reference-механизма, низкая target transferability; высокая novelty относительно старого «capability отсутствует». Potential leverage прямо относится к периоду EM, допустимый диапазон и≥2000 неизвестны. Information gain точного wiring/input документа высокий, ещё одного enable-guess низкий. Feasibility сейчас заблокирована; численная вероятность необоснованна. Offline risk нулевой, blind hardware enable неквалифицирован. Stock-return должен быть доказан вместе с документированным mode switch; готового безопасного rollback для неизвестного входного режима пока нет.

## 5. TOP-1: выполненный research plan и остающийся gate

1. **Доказать новизну контекста. Выполнено.** Byte-level factorization семи программ и исторических labels; rank6/8, четыре допустимых boolean completions. A-парсер сопоставлен с существующим `audit_pwm_archive.parse_packets` на1101 пакетах; root независимо проверил bytes/rank. Это проверка входов и логики, не statistical trial.
2. **Доказать точные границы intervention. Выполнено.** Candidate875B/75packets; от native ON отличается толькоoffset68; от OFF84bytes/33packets. Candidate SHA256 `8604d62c…ac62e`, stock `b5ed66ba…acd193` сверены только для конкретного hardware proposal. Новых binary payload не создавали.
3. **Пересчитать baseline арифметику. Выполнено по сохранённым summaries.** q93 A9=0.22640672181213267, D-only=1.0214237646270796, S0C1=0.9363479490548713; максимум расхождения с записанными ratios по семи стадиям4.44×10⁻¹⁶. Это не повторный raw-video анализ. [root audit](horizon_r3_20261108/root_offline_audit.json), `/archived_summary_arithmetic`.
4. **Проверить запрет неавторизованного запуска. Выполнено.** Существующий unit test exact A0D1C1 scope прошёл. В отдельных процессах runner отказал без `authorization.json` и при Python `-O` до любого `subprocess.Popen`; mock фиксирует0 вызовов. Никакой approval record не создавался. [runner checks](horizon_r3_20261108/runner_offline_checks.json).
5. **Разделить treatment effect и physical Hz. Выполнено.** Новый constructive counterexample и прямое численное интегрирование; источники кадрового пути и задержки. Это заранее устраняет ложный критерий успеха «новая полоса=2160Hz».
6. **Независимое adversarial review. Выполнено.** A/B/C отвечали за отдельные вопросы; D отдельно проверил strongest claims и ограничения. Другой parser подтвердил программы, Walsh Gram-матрица дала точный rank6/8.8-node Gauss–Legendre интегрировал все3×37,500 synthetic samples без sinc/Simpson реализации C: max difference2.47646×10⁻¹². Дополнительный falsifier: те же emitters при400µs уже отличаются до0.1712809218; fixed-exposure counterexample не распространяется на весь sweep. Итог: [agent_d_review.md](horizon_r3_20261108/agent_d_review.md), §§1,4–6. Замечания о compound effect, reference/target границе и измерительном scope включены в этот отчёт и proposal.
7. **Остаётся одна операция, требующая устройства:** отдельно подтвердить и выполнить точную stock→A0D1C1→stock серию из [proposal](horizon_next_experiment.md). До неё аппаратная часть закрыта. После валидного положительного optical результата — сохранить отдельный baseline и проверить carrier/огибающую независимым временным каналом; после отсутствия существенного эффекта — закрыть эту комбинацию и перейти к matched frame-event/sham механизму, не повторять опыт.

## 6. Воспроизведение новых вычислений

Из корня репозитория, без телефонов:

```sh
python3 artifacts/horizon_r3_20261108/agent_a_factorization.py
python3 artifacts/horizon_r3_20261108/root_offline_audit.py
python3 artifacts/horizon_r3_20261108/agent_c_identifiability.py --output NEW_OPTICS_JSON
python3 artifacts/horizon_r3_20261108/agent_d_verify.py --output NEW_REVIEW_JSON
```

Первые два читают сохранённые программы/JSON и выводят результаты; optics строит явно обозначенную синтетическую модель. Параметры output/no-overwrite описаны в самих воспроизводителях. ESYNC source audit с pinned public cache/`--fetch` описан в [B](horizon_r3_20261108/agent_b_sources.md), §6; доступ к сети только для публичных источников, device I/O отсутствует.

Полный машиночитаемый реестр, включая резервы/опровержения/blockers: [horizon_leverage_candidates.json](horizon_leverage_candidates.json). Исторические первичные результаты, утверждённые baseline, runner и panel code не изменены. **Ни source counter, ни DSI readback, ни камерный пик не объявлены измерением физической PWM.**
