# Agent B — новые первоисточники и внешний путь EM-sync

**TL;DR. Найдено конкретное аппаратное значение Qualcomm ESYNC: отдельный AP→DDIC сигнал, в котором периодически модулируется ширина HSYNC-импульса для передачи EM-синхронизации. Это более сильный источник семантики, чем одно поле `emsync_fps`, но применимость входа к физическому ILI97701A/XT2611-1 пока не доказана.**

Дата: 2026-11-08. База репозитория: `fffb0feeda534add90dfaf7056964d40adefc183`. Работа только с сохранёнными файлами и публичными первоисточниками; телефон не использовался. Исторические baseline и авторизация A0D1C1 не изменены.

## 1. Реально новый результат: физическая цепочка ESYNC

Ранее уже было известно, что `msm_drv.h:1000` называет `emsync_fps` частотой EM в герцах и что selected target DT не включает capability. Новое здесь — восстановленная цепочка от этого поля до конкретного генератора и вывода SoC, условия её использования и явный контрпример трактовке поля как универсального DDIC PWM-setter.

### 1.1. Откуда берётся период

Официальный Motorola driver pin `fa008c43c070ff20faa33853649f5dfd4c427e99`, `msm/sde/sde_encoder_phys_vid.c:861–939`, вычисляет:

```text
emsync_period_lines = floor(vtotal × vrefresh / emsync_fps)
emsync_pulse_width  = floor(emsync_milli_pulse_width × hsync_period_cycles / 1000)
```

Затем `msm/sde/sde_hw_intf.c:340–370` упаковывает период и ширину в два 16-битных поля `INTF_ESYNC_EMSYNC_CTL`, offset **0x418 внутри SDE interface block**. Backup-генератор использует `INTF_BKUP_ESYNC_EMSYNC_CTL`, offset **0x484**, строки390–412. Это **MMIO SoC, не DDIC page/register и не DSI payload**. Абсолютный MMIO-адрес целевого устройства здесь не вычисляется; эти сведения не являются командой записи.

Генератор имеет свои enable/reset, счётчики и timestamps: `sde_hw_intf.c:373–388,985–994,1553–1565`. Это потенциальная точка независимой временной проверки генератора, но его счётчик сам по себе не измеряет свет панели.

Первичный код и ссылки с сохранёнными исходными номерами строк: [agent_b_esync_primary_excerpts.md](agent_b_esync_primary_excerpts.md), разделы `msm/sde/*`.

### 1.2. Что выходит из SoC

Официальные bindings другого репозитория Motorola, pin `f088523dfba85c95c15f43726fcf972c0c7a957a`, `bindings/mdss-dsi-panel.yaml:685–700`, прямо описывают HSYNC-составляющую ESYNC и частоту, с которой ESYNC модулируется EM-импульсом. Параметр width задаётся в тысячных периода строки; это не непосредственный OLED duty в процентах.

Тот же pin содержит физический pinmux: `display/canoe-sde-display-pinctrl-common.dtsi:141–179` назначает `mdp_esync0_out` на **GPIO88**, `mdp_esync1_out` на **GPIO100**. В `canoe-sde-display.dtsi:120–133` отдельный `panel_active_with_esync` включает этот вывод. Это доказывает существование внешнего вывода в данной **reference board configuration**; разводка GPIO88/100 до FPC конкретного XT2611-1 не установлена. Числа GPIO нельзя переносить на телефон как готовое управление.

Драйвер выбирает ESYNC-pinctrl лишь при capability, `dsi_panel.c:578–593,916–933`. Значит, добавление числа частоты в конфигурацию без подтверждения входа DDIC и соединения не завершает причинную цепочку.

### 1.3. Независимый первичный источник физического смысла

Патент **Qualcomm US20250251773A1, “Esync hybrid mode”**, приоритет2024-02-07, публикация2025-08-07, Fig.4/5, описывает непрерывный внешний HSYNC от AP к DDIC. DDIC формирует EM-пульсы на его основе; допускается постоянный EM-период при меняющемся количестве периодов в видеокадре. Fig.5 отделяет ESYNC generator от DSI lanes. Это согласуется с bindings, отдельным pinmux и SDE MMIO-генератором.

URL: https://patents.google.com/patent/US20250251773A1/en

Первичный locator: описание Fig.4/5 по указанному URL; строки412–453 извлечённой страницы на дату исследования. Это описание архитектуры Qualcomm, **не доказательство реализации в ILI97701A**. Патент не даёт target-команд.

## 2. Почему найденное пока не готовый рычаг телефона

1. Сохранённый selected live subtree содержит425 properties и `qcom,mdss-dsi-panel-type = "dsi_cmd_mode"`. Во всех425 отсутствуют `qcom,mdss-esync`, `qcom,mdss-esync-emsync-fps`, `qcom,mdss-dsi-panel-esync-emsync-switch-enabled`, `qcom,mdss-dsi-esync-post-on-commands` и `qcom,mdss-dsi-em-pulse-switch-command`. Provenance сохранённого дерева: `artifacts/device_tree/selected_boe_v4_acquisition.json:2–7`; текущий повторный анализ: [agent_b_esync_audit.json](agent_b_esync_audit.json).

2. На public DT pin проверен новый вопрос, не повтор regional diff: какие файлы **описывают ESYNC**. Из407 файлов19 содержат это имя; все пять точных ILI97701A v0–v4 его не содержат. Это ограниченный результат одного pin, не утверждение об отсутствии скрытой capability в кремнии. Generic pinctrl встречается независимо от выбранной панели.

3. `emsync_fps` DRM property появляется только при `emsync_switch_enabled`, а диапазон берётся из существующих display modes (`sde_connector.c:4244–4264`). `dsi_display_find_mode` требует совпадения EM frequency с одним из этих modes и возвращает `-ENOENT`, если соответствующего mode нет (`dsi_display.c:9194–9197,9255–9259,9275–9297`). Поэтому это выбор описанного режима с нужными параметрами, а не подтверждённый произвольный scalar-setter частоты OLED.

4. Переход может дополнительно отправлять **panel-specific** `DSI_CMD_SET_EM_PULSE_SWITCH`, если команда определена (`sde_connector.c:1533–1537`; `dsi_panel.c:3461`). Resume может требовать `qcom,mdss-dsi-esync-post-on-commands` после включения генератора (`bindings:737–741`). Готовые значения для ILI97701A не найдены.

5. В reference source реально есть отдельные ESYNC modes120/360/90Hz для **NT37802 video-PSR**, `canoe-sde-display-common.dtsi:480–518`, с capability в `canoe-sde-display.dtsi:373–382`. Это хороший контроль, что framework умеет разные EM schedules. Это **не BOE ILI97701A profile**, не оптически измеренный результат и не разрешение переносить его байты.

6. Source сообщает отдельное ограничение обновления: ESYNC generator double-buffered; на idle-exit нельзя выполнять второе DB-update между enable и первым ESYNC-vsync (`sde_encoder_phys_vid.c:897–903`). Это реальный latch condition **host-генератора**, а не расшифровка `53:F0` или других target-DDIC latch.

Сходство отдельных блоков target `msm_drm.ko` с этим source pin, подтверждённое прежними исследованиями, не превращает все перечисленные source-функции в независимо проверенный target binary path. Для данной записки статусы: **source-confirmed mechanism**, **saved-target capability absence**, **target wiring/DDIC capability unknown**.

## 3. Новый BOE countermodel для broad/fine: refresh versus maintenance

В **BOE/Chengdu BOE US20250014518A1**, “Pulse width modulation method, pulse width modulation module, and display device”, приоритет2022-10-12, публикация2025-01-09, описано разное управление шириной EM-пульсов в refresh-кадрах и maintenance-кадрах. При равной ширине импульсов эти два типа кадров могут давать разную яркость; коррекция ширины компенсирует мерцание. Описанный low-refresh пример ≤40Hz не следует автоматически переносить на target nominal120Hz.

URL: https://patents.google.com/patent/US20250014518A1/en

Первичный locator: Fig.3–6 и описание refresh/maintenance frames по указанному URL (строки169–201 извлечённой страницы); granted member US12354554B2,2025-07-08. Здесь **нет ILI97701A или адресов регистров**. Это первичный контрпример выводу “изменился amplitude/fine-компонент ⇒ изменилась carrier-frequency”. Он делает проверку зависимости оптики от refresh/maintenance scheduling содержательной; эту software-cadence ветку отдельно исследует оркестратор.

Дополнительный BOE/Chengdu BOE источник **US20240404470A1**, “Timing controller, display device, and pixel driving method”, приоритет2022-08-30, публикация2024-12-05, показывает фиксированный internal driving-start120Hz при image-refresh120/60/30/10/1Hz, с различным числом hold frames. `STV1` там связан с **hysteresis reduction**, поэтому его импульсы нельзя переименовывать в OLED EM carrier.

URL: https://patents.google.com/patent/US20240404470A1/en

Первичный locator: Fig.6A–7B и описание fixed internal driving-start в указанном патенте (строки901–907 извлечённой страницы). Это второй независимый countermodel единственной “частоты экрана”, а не адресный target-рычаг.

Ранее известный CN119811288A с примером ILI97680a и18 импульсами повторным открытием не стал новым результатом; его значения не используются для target payload.

## 4. Точная ILITEK-линейка: узкое положительное и отрицательное свидетельство

Официальная ILITEK страница https://www.ilitekholding.com/en/product/Mobile идентифицирует **IL97701A** как AMOLED1440×3360, D-PHY/C-PHY30bit, LTPO и “Supports zoned variable frequency display” (раздел IL97701A, строки177–183 извлечённой страницы). Новая полезная деталь — заявленная зональная переменная частота. Страница не уточняет, относится ли это к image-refresh, scan, EM, внешнему ESYNC, и не содержит схемы pinout/register map. Она не обосновывает изменение PWM сама по себе.

Два ограниченных раунда поиска точного ILI97701A/IL97701A и два узких подхода к ESYNC/BOE не нашли нового публичного target register-map/alternative high-PWM profile. GitHub code-search вернул пустой ответ; это только отрицательный результат инструмента, не доказательство отсутствия кода. Затем метод изменён на целевой анализ public bindings, pinmux и самого ESYNC backend, описанный выше.

## 5. Кандидат для общего реестра: внешняя EM-синхронизация

**Управляющая точка:** SDE ESYNC/EMSYNC period+width в source и его внешний вывод, с согласованным режимом входа DDIC.

**Гипотеза:** если точный ILI97701A умеет external emission synchronization и этот вход разведён, управление периодом внешних EM markers может менять реальную последовательность эмиссии независимо от image-refresh. Это кандидат на значительное изменение периода, но найденные источники не задают разрешённый target диапазон и не обещают ×2–3 или≥2000Hz.

**Сила доказательств:** высокая для source архитектуры Qualcomm; низкая для применимости к панели. **Novelty:** выше прежнего “capability отсутствует”: теперь известны физический канал, units, MMIO backend, mode-table gate и необходимость согласования panel state. **Information gain:** высокий у проверки наличия входа/соединения; низкий у ещё одного поиска `pwm` в stock v4. **Вероятность конечного успеха:** не поддаётся численной оценке; до доказательства соединения и DDIC input mode — слабый, заблокированный кандидат. **Риск:** offline нулевой; неподготовленное включение внешней синхронизации может нарушить scan/emission и потребовать reset. Поэтому hardware enable proposal здесь не формируется. **Стоимость:** один точный документ/пин-сопоставление дешевле неподтверждённого kernel patch и серии телефонных опытов.

**Минимальное следующее доказательство:** достать board/FPC schematic либо точный IL97701A interface/pinout/init документ, который связывает вход emission/HSYNC с реально разведённой линией XT2611-1 и описывает способ входа в этот режим. Достаточно одного положительного, версионно точного артефакта; одно generic GPIO name не подходит.

**Критерий опровержения этой реализации:** подтверждённое отсутствие внешнего sync-input/соединения на точной панели/плате закроет host-ESYNC путь на этом устройстве. Оно не закроет внутренний DDIC emission controller. При наличии входа следующим этапом станет source/binary audit режима и допустимых времён; до этого нельзя составить обоснованные новые DSI bytes. Возврат к stock должен быть проектирован вместе с документированным panel mode switch, а не принят по умолчанию.

## 6. Воспроизводимость и проверка

[agent_b_esync_audit.py](agent_b_esync_audit.py) повторно читает только сохранённый target subtree и pinned public source archive, создаёт JSON и компактные source excerpts. Сам скрипт не имеет device I/O. Пример повторения в текущем workspace:

```sh
python artifacts/horizon_r3_20261108/agent_b_esync_audit.py \
  --cache /workspace/scratch/ffb9e198c17f/b_source_cache \
  --archive /workspace/scratch/ffb9e198c17f/b_source_cache/display_f088.tar.gz
```

Для воспроизведения после удаления cache есть явный `--fetch`, скачивающий только pinned публичные GitHub source files. Полные исходники оставлены в scratch-cache; в git-артефакты попали только релевантные фрагменты и provenance.

Выполнено отдельное второе чтение без использования audit-result для выбора данных: actual file-count совпал с acquisition425; `dsi_cmd_mode` подтверждён исходными13 байтами `64 73 69 5f 63 6d 64 5f 6d 6f 64 65 00`; все5 exact ILI97701A source-файлов лишены `esync`; target property names лишены `esync`/`em-pulse-switch`. Прямые raw.githubusercontent версии DT excerpts побайтно сверены с соответствующими членами pinned tar. Это проверка воспроизводимости источников, **не измерение физической частоты и не независимый эксперимент на устройстве**. Существенных новых численных моделей PWM эта ветка не вводит.
