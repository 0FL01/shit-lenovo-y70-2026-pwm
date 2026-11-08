# ELVSS/HBM DIM OFF: не готовый PWM-профиль выбранной BOE v4

`confirmed-on-target` только для сохранённых selected DT и кода текущего
`msm_drm.ko`; реальная OLED PWM-частота `unknown`. Проверка выполнена офлайн,
без ADB, DSI и изменения телефона.

**Гипотеза:** именованный ELVSS-путь с заменой DCS `B7` внутри HBM DIM OFF
может быть уже доступным управлением излучением выбранной панели. Проверяемый
предел: существует ли у выбранного BOE v4 готовый DT gate/command set для
этого пути и действительно ли target-код его требует.

- Публичный Motorola source reference
  `/home/stfu/.cache/opencode-tmp/opencode/pwm-source-recon-20261106/msm/dsi/dsi_panel.c:6485–6490,8262–8331,8369–8404,8976–9015`
  читает boolean `qcom,mdss-dsi-hbm-dim-off`; при post-enable и успешной
  подготовке ELVSS заменяет четвёртый descriptor набора `HBM_DIM_OFF` на DCS
  `B7`, у которого второй байт берётся из `elv_vl & 0x7f`.
  в том же каталоге `dsi_display.c:10874–10886` вызывает подготовительное ELVSS-чтение только
  при том же gate. Reference source **не** доказывает семантику `B7` на DDIC.
- В сохранённом **текущем target-модуле**
  [`msm_drm.ko`](kernel/gki_r59/target_vendor/msm_drm.ko), SHA256
  `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`,
  Ghidra12.1.4 `dsi_panel_get` `.text+0x1b7b98` читает ровно это DT-имя
  через `of_find_property` и пишет результат в `panel+0xbea`
  (`get-mid/excerpt.c:40–43`; буквальный xref `.text+0x1b81fc`).
  `dsi_panel_post_enable` `.text+0x1c486c` отправляет обычный POST_ON,
  а к замене descriptor допускает только условие **`panel+0xbea == 1` И
  `read_elvss == 1`** (`post-head/excerpt.c:25–63`); набор обозначен `0x31`,
  замена относится к descriptor с индексом 3. В отчёте использованы только
  Ghidra `brief`/`decompile --lines` excerpts и xref manifest из внешнего
  approved cache `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/elvss-hbm-20261108/`, не полный C;
  import offsets — не live VA.
- В [`selected_boe_v4`](device_tree/selected_boe_v4/) среди всех **425** файлов
  root+8 timing отсутствуют `qcom,mdss-dsi-hbm-dim-off`, его
  `-command`/`-command-state` и любой `elvss` property. Проверенные
  `audit_pwm_archive.parse_packets` **52 массивов / 1101 пакетов** не содержат
  ни одной записи с opcode `B7`. Следовательно, этот gate не даёт готового
  ELVSS/HBM-DIM-OFF DSI-профиля в сохранённом выбранном DT. Само присутствие
  общего кода в модуле не делает путь включённым на данном дисплее.

Это **не** доказательство отсутствия других runtime writers/overlay,
назначения `B7`, физической низкочастотной огибающей или PWM ≥2000 Гц.
Статический тест не выполнял HBM, ELVSS-read или DSI-запись. Лучший
промежуточный panel baseline A9-only (q93 total ratio0.2264067) не менялся;
`dsi_coupled_9d_20261107` A0D1C1 остаётся без отдельной авторизации/run.
