# Текущий msm_drm: PWM API и DC dispatch

2026-11-07, после подтверждённого перезапуска OpenCode. Только offline:
**ни ADB, ни DSI, ни перезагрузки телефона не выполнялись**.

## Гипотеза и результат

`hypothesis`: в установленном модуле есть отдельный runtime frequency-control,
который можно отличить от таблиц DC и использовать для крупного шага OLED PWM.

`reported`, offline-verified по сохранённому target ELF: найденные Linux PWM
calls относятся к альтернативному типу backlight, не выбранному на BOE. DC branch
выбирает только OFF/ON и не вычисляет emission count/period. В проверенных ветках
готовый frequency-control **не найден**. Это не доказательство отсутствия любых
возможных способов управления DDIC и не закрытие R3.

## Идентичность и способ воспроизведения

Input: `artifacts/kernel/gki_r59/target_vendor/msm_drm.ko`, ELF64 little-endian
AArch64 ET_REL, GNU BuildID `be0229cf369bc5a905ceb61ca429fa2075235c3a`.
SHA256 для идентификации исследуемого бинарника:
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
Все адреса ниже — **offset внутри ELF section**, не адреса живого ядра.

```sh
python3 artifacts/runtime_pwm_recon_20261107/analyze.py --output /path/to/NEW-directory
```

Существующий output не перезаписывается. Нужны Python stdlib, `readelf`, `nm`,
`aarch64-linux-gnu-objdump`; дополнительных dependencies нет.
[Evidence](evidence/evidence.json) включает все прямые `.text` relocations к
`pwm_apply_might_sleep` / `devm_pwm_get`, owners, исходные live DT properties.
В `evidence/` сохранено дизассемблирование12 выбранных функций с разрешением
печатных `.rodata` strings. Это не полный reverse всей библиотеки/всех callers.

Source reference только для объяснения: Motorola display pin
`fa008c43c070ff20faa33853649f5dfd4c427e99`, cache
`/home/stfu/.cache/opencode-tmp/opencode/pwm-source-recon-20261106/`.
Pin подтверждён `tree.json`; source-to-entire-target-module equality не заявляется.

## 1. Почему найденный PWM API не управляет этим OLED

В live snapshot `qcom,mdss-dsi-bl-pmic-control-type = "bl_ctrl_dcs\0"`.
В target `dsi_panel_parse_bl_config`:

- `.text 0x1bab68–0x1bac48`: `bl_ctrl_pwm` → type0, `bl_ctrl_dcs` → type2,
  запись `panel+1480`.
- `0x1bb008–0x1bb00c`: PWM period parser вызывается только при type0;
  property `qcom,bl-pmic-pwm-period-usecs` → `panel+1572` на `0x1bb130`.
  Этого property в выбранной панели нет.
- `dsi_panel_bl_register 0x1c6294–0x1c62f4`: type2 пропускает PWM device allocation;
  `devm_pwm_get` вызывается только для type0.

В target `dsi_panel_set_backlight`:

- `0x1b5654–0x1b5670`: branch по тому же `panel+1480`.
- Type0 → `0x1b5790`; period_usecs×1000 и duty=period×DBV/max;
  **все три** прямых вызова `pwm_apply_might_sleep` в `.text`:
  `0x1b57e4` (config), `0x1b582c` (enable), `0x1b59c0` (disable).
- Type2 → `0x1b5674`: capability-gated APL/ODC, затем DCS brightness;
  `mipi_dsi_dcs_set_display_brightness` на `0x1b58c0`, возможный double-write
  на `0x1b59e8`. При subtype nonzero — отдельный `mipi_dsi_dcs_write` на
  `0x1b5720`; выбранный DT subtype отсутствует, parser default0.

Источник согласуется по механизму: `msm/dsi/dsi_panel.c:1045–1094,1256–1307,
1346–1373,4285–4301,4314–4337,4429–4435`.

Следствие: менять `pwm_period_usecs` или подменять backlight type ради OLED
необоснованно. Подмена типа не создаст отсутствующую физическую PWM-проводку DDIC.

## 2. DC value — индекс, а не частота/множитель

`dsi_panel_set_param 0x1b5d10–0x1b5d14` dispatch index3 в веткуDC
`0x1b5eb8–0x1b5f48`: сохраняет запрос, вызывает `dsi_panel_send_param_cmd` на
`0x1b5ee0`, затем при flags выполняет PCD read. Формирования PWM period/count нет.

Sender `0x1c456c` использует panel lock, initialized guard и `param_cmds`:

- `0x1c45f4–0x1c4608`: если request≥val_max, request=val_max−1;
- `0x1c460c–0x1c4614`: повтор кешированного значения ничего не отправляет;
- `0x1c4688–0x1c46d0`: выбирает map[index].cmds;
- `0x1c46ec–0x1c472c`: цикл исходных descriptors → `dsi_host_transfer_sub`;
- `0x1c47b4–0x1c485c`: кеш/DC state обновляется после успешной передачи.

[Независимая проверка initial DC table](dc_table_validation.json):
`.data+0xa2e0` = primary DC entry, val_max2, default0; relocations имени на
`.rodata+0x13045="DC"`, map на `.data+0xa158`. Две записи по16байт:
value0/command-set54, value1/command-set53. Null command pointers — до DT parsing,
не отсутствие runtime таблицы; initial support=false не означает отсутствия liveDC.
Для воспроизведения raw bytes/relocations:

```sh
aarch64-linux-gnu-objdump -s -j .data --start-address=0xa2e0 --stop-address=0xa2f8 artifacts/kernel/gki_r59/target_vendor/msm_drm.ko
aarch64-linux-gnu-objdump -s -j .data --start-address=0xa158 --stop-address=0xa178 artifacts/kernel/gki_r59/target_vendor/msm_drm.ko
aarch64-linux-gnu-objdump -r -j .data artifacts/kernel/gki_r59/target_vendor/msm_drm.ko
```

Source reference `dsi_panel.c:123–130,147–171,1728–1795` согласуется.
Следовательно, native positive DC2/3 не представляет дополнительный режим или
×2/×3; upper layers могут нормализовать ещё раньше. Ничего из этого не отправлялось.

## 3. Другие разобранные ветки и граница вывода

- APL/ODC меняют выбранные таблицы при пороге DBV, не вычисляют частоту:
  `dsi_panel_set_apl 0x1b5a3c`, `dsi_panel_set_odc 0x1b5b2c`.
  Live APL threshold16000, существенно выше рабочего DBV3600; `qcom,odc-enabled`
  отсутствует. APL не объявляется никогда не выполняющимся: переход из ранее
  включённого APL мог отправить OFF. Семантика его DDIC bytes здесь не декодировалась.
- DRM dimming ctrl/min/lut в12-функциональном scope меняют flags/threshold/LUT,
  уведомляют и переотправляют brightness через callback; самостоятельного поля
  frequency в этих setters нет. Downstream compositor целиком не разобран.
- Настоящие именованные `esync-emsync-fps`/pulse-width есть в target parser
  `0x1c0e7c`, но в выбранном live DT нет ни одного esync property. Это уже известный
  capability-gated след, не вновь обнаруженный готовый переключатель панели.

## Решение для следующего шага

Не тратить аппаратную пробу на DC=2/3 или изменение неиспользуемого PMIC PWM.
Дальнейший предметный путь — panel-specific таблица/поля DDIC, а не эти setters.
**A9-only сохраняется как экспериментальный baseline** уменьшения q93 total до
0.2264067 соседнего stock; его не сбрасываем из учтённых результатов. Это не
доказанные Hz и не постоянно включённый профиль.

S0C1 по существующему proposal по-прежнему не согласован/не отправлен. Для
аппаратного продолжения нужны exact-operation approval и сравнение с baseline
либо явно мотивированный stock control; до этого допустим только независимый
offline следующий вопрос, не повтор этого уже закрытого runtime-PWM поиска.

## Выполненные проверки

[validation.json](validation.json): синтаксис collector проверен; второй запуск
в новом approved cache воспроизвёл все15 output-файлов побайтно. Повтор с уже
существующим output корректно отказал без изменения байтов/mtime. Независимый
`readelf -rW` подтвердил те же4 PWM-related call relocations, что `objdump`.
Проверено отсутствие S0C1 `run.json`/`authorization.json`. Ранее прошедшие12
оптических unit tests не запускались заново: код/метод оптического анализа здесь
не менялся, новая проверка относится только к offline binary extraction.
