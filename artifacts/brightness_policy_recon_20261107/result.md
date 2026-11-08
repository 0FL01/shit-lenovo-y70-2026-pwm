# Яркость, digital dimming и LTPO — текущая ветка реверса

2026-11-07. **R3 active; ≥2000 Гц и приемлемый профиль не получены.**
Первый этап — офлайн: сохранённые target `msm_drm.ko`/selected DT, pinned source
и CN reference ELF. Затем выполнена объявленная **read-only ADB-сверка** пяти
userspace ELF, восьми display properties и dumpsys SurfaceFlinger (раздел6).
Новых DSI, flash, reboot, изменений настроек или съёмки не было.
Лучший panel baseline — прежний A9-only;
уменьшение его камерной компоненты не стало доказательством частоты.

## 1. Новый target-результат: LUT не меняет отправляемую яркость

`confirmed-on-target` для происхождения сохранённого модуля, `reported` для
проверенного офлайн dataflow. Модуль:
`../kernel/gki_r59/target_vendor/msm_drm.ko`, BuildID
`be0229cf369bc5a905ceb61ca429fa2075235c3a`, SHA256
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
Адреса ниже — **offset секции `.text`**, не live kernel VA.

В `dsi_display_set_backlight` (0x1a032c,612 bytes):

1. Входной `bl_lvl` сохраняется в `w21` по0x1a0354.
2. Scaling/LUT рассчитываются отдельно. Чтение `mapped_bl` по0x1a0454 загружает
   значение в **w5**, аргумент debug print по0x1a0464, а не в сохранённый DBV.
3. По0x1a0470–0x1a0488 min/max применяются к **исходному w21**.
4. При отложенном обновлении сохраняется тот же w21 по0x1a04d4; иначе
   `w1=w21` по0x1a04fc → `dsi_panel_set_backlight` по0x1a0500.
5. Единственные записи в w21/x21: вход, min-clamp, zero-branch и восстановление
   callee-saved регистра в epilogue. LUT не достигает аргумента panel setter.

[Полный аннотированный body](evidence/dsi_display_set_backlight.txt).
Это согласуется с pinned source commit
`fa008c43c070ff20faa33853649f5dfd4c427e99`, cache
`/home/stfu/.cache/opencode-tmp/opencode/pwm-source-recon-20261106/`:
`msm/dsi/dsi_display.c:297–309` вычисляет scaling/LUT, но **:312 вновь
присваивает `bl_temp = bl_lvl`**, затем :313–329 clamp/send.
Полного source-to-module совпадения из этого не следует.

**Вывод:** выставление `dimming_bl_lut` не является готовым способом изменить
DBV или включить иной emission-режим на исследуемом пути. Не исправляем этот
код «заодно»: удаление reset-присваивания меняло бы физическую яркость и поведение
существующих clients без проверенного оптического результата, но не создавало
бы известный PWM frequency setter.

## 2. DRM dimming controls — уведомления, не DSI frequency command

Pinned `msm/sde/sde_connector.c:976–1089`, target functions в `evidence/`:

- `_sde_connector_update_dimming_bl_lut`0xe64e0 сохраняет blob и повторно вызывает
  `ops.set_backlight` с прежним `bl_level`; применимо ограничение из раздела1.
- `_sde_connector_update_dimming_ctrl`0xe6618 меняет status/notification flags;
  `_sde_connector_update_dimming_min_bl`0xe66f4 меняет уведомляемый min_bl.
- Оба вызывают `sde_dimming_bl_notify`0xe5cfc. Тот проверяет регистрацию событий
  и user-disable, формирует `DRM_EVENT_DIMMING_BL=0x8000000d` и вызывает
  `msm_mode_object_event_notify` по0xe5e00. Здесь нет отправки panel command.

Это не утверждение, что userspace-получатель не может менять изображение.
Оно отделяет этот конкретный notification API от panel-specific PWM управления.

## 3. CN digital-dimming библиотека: отдельный уровень доказательства

Первый разбор — reference **XT2611-1 RETCN W3WWL36.65-11-18**. Последующая
сверка подтвердила побайтовое равенство именно `libdigital-dimming.so` current
GLOBAL (раздел6); это не blanket equivalence остальных библиотек. Reference файл:
`extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/lib64/libdigital-dimming.so`.
[Выборочный disassembly](cn-digital-dimming-selected.txt).

- Factory `GetDigitalDimmingInterface` экспортирован через CFI jump0x10228→0xa3e8.
  По0xa43c–0xa474 читает **`vendor.display.disable_stc_dimming`**. Если свойство
  отсутствует или atoi!=0, создаёт `DigitalDimmingDefault`; только присутствующее
  значение с atoi==0 выбирает полноценный `DigitalDimming` по0xa624–0xa698.
  CN `vendor_a/build.prop:289` содержит **`...=1`**. Последующий target getprop
  подтвердил это значение; создание объекта runtime не трассировалось.
- Default SetParameter0xa884 возвращает -95 после initialization, -13 до него;
  это не скрытая успешная команда DDIC.
- Полная `CalculateDimmingLuts`0xb928 нормирует яркость, вызывает `Dimming`, пишет
  double gain table и целочисленную brightness LUT (0xb9e4/0xb9f8,
  0xba9c/0xbac0–0xbac4). `Dimming` jump0x10220→0x9d74: clamp0..1, `pow` с gamma,
  float-коэффициенты и minimum brightness. Это арифметика яркости/цветового усиления,
  не найденный расчёт периода OLED.
- `SetPccAttn`0xbeb4 передаёт double attenuation через `ScPostBlendInterface`,
  virtual-call по0xbf7c, operation0x807. Дальнейшая реализация получателя этого
  virtual call здесь не объявлена полностью разобранной.
- В reference `libsnapdragoncolor-manager.so` найдены producer/factory интерфейсы
  `GetDimmingBlFactoryIntf`, `BlSubjectImp`, `BlScaleImp`, loader digital-dimming.
  Имена — указатели для следующего hop, не доказательство исполнения на target.

Наличие библиотеки и отключающего property **не обосновывает** включение её на
устройстве. Даже полноценный цифровой attenuation сам по себе не повышает OLED Hz.

## 4. APL/HBM: конкретный gate и перекрывающиеся команды

`confirmed-on-target` по ранее сохранённому selected DT:
`qcom,apl-enabled`; threshold16000, FUNC-ID0, DCS backlight, min460/max16180.
Default7001 — значение DT, не текущая яркость. В обычном clamp-пути ON-порог может
быть пересечён при DBV16001–16180, **не при DBV3600 прежних опытов**.

Target `dsi_panel_set_backlight`0x1b5588 вызывает APL по0x1b5688 после enable gate.
`dsi_panel_set_apl`0x1b5a3c: ON при DBV>threshold, state=false, `dobly_enable=0`;
OFF при DBV<=threshold и state=true. State обновляется и после send failure:
software-флаг отдельно не доказывает успешную запись панели.
Source: `dsi_panel.c:1194–1222,1256–1283`; parser:6076–6135.

| Массив selected DT | Payload после выбора page1e |
|---|---|
|APL ON|80 a9;85 08;возврат page00|
|APL OFF|80 89;возврат page00|
|HBM ON|тот же ON-prefix, затем page00:51 3f fc|
|HBM OFF|тот же OFF-prefix, затем page00:6e 00|

Payload-prefix равен, **batch headers и полные массивы не равны**; exact bytes
в [validation.json](validation.json). `51 3ffc` — brightness payload, не2160Hz.
Семантика page1e:80/85 как PWM не установлена. HBM может перехватывать обычный
backlight path; APL/HBM имеют разные software state, не считаются взаимозаменяемыми.

Dolby gate изменяемый: `dsi_display_set_moto_drm_command`0x1a06fc →
`dsi_panel_set_moto_drm_command`0x1c3ec4, совпадение command ID с FUNC-ID0 →
запись `dobly_enable` по0x1c3f30. Source `dsi_panel.c:8809–8824`.
Userspace sender id0/val впоследствии прослежен в current ELF (раздел6).

## 5. LTPO: реальные команды idle, но не найденный PWM множитель

Selected target timings0–5 имеют nominal120/144/90/60/30/24; @6/@7 nominal120
со special-idle10/1 flags. Horizontal front porch у @0/@6/@7:16/20/12.
Pinned `msm/dsi/dsi_display_mot_ext.h:54–88` объясняет номинальную90/120 частоту
для верхнего уровня и внутренние1/10; эти числа не являются OLED PWM.

Путь: `dsi_panel_get_mode` → selected child/command sets →
`dsi_display_set_mode`/cur_mode → DMS `dsi_display_enable` → `dsi_panel_switch` →
`DSI_CMD_SET_TIMING_SWITCH`. Target DMS call0x1ad580 → switch0x1c3380 →
sender0x1c3458. Численный userspace brightness gate впоследствии прослежен
в current SurfaceFlinger (раздел7), без заявления о текущем DDIC timing.

Idle @6/@7 switch arrays по140bytes **отличаются** page2d:83 (`0b 00`/`77 00`).
Это не просто переименование режима, но назначение83 как PWM не установлено.
Source annotation-файл
`pwm-primary-followup-20261106/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi`
**не совпадает** с target timing-switch@0,3,4,5,6,7 (равны только@1,2).
Поэтому source idle comments нельзя превращать в точное описание target bytes.
Не повторяем уже выполненный120/144/90 опыт как новую гипотезу.

## 6. Current userspace: идентичность и Dolby sender

Read-only preflight вновь подтвердил XT2611-1/W3WWS36.65-64-4-1, UID0 иEnforcing.
Source/copy SHA256 проверены для всех пяти файлов:
[comparison](target_userspace_comparison.json). `libsdmcore.so` и
`libdigital-dimming.so` целиком равны CN. **Client, DAL и SurfaceFlinger различаются**;
равный размер файла не использован как доказательство.

Current `libsdmclient.so`, `SDMDisplayBuiltIn::CommitOrPrepare` VA0xa1258,size992:
gate0xa13e8–0xa144c совпадает с CN, но полные functions различаются22 инструкциями.
Слои проверяются по byte`layer+168==1` и bit1 halfword по`*(layer+16)+120`.
Log называет вычисленный boolean `dolby present`. **При его изменении** cached
state записывается до отправки;0xa1494–0xa14a4 вызывают virtual slot+0x3f8 с
`id=0,val=boolean`. Не утверждается отправка на каждом commit.

Producers metadata10018/10029 отдельно проверены в current SetLayerBuffer/
SetMetaData; их enum names не выдумываются. Dolby boolean init0 —0x9c6f4.
Другое изменившееся constructor поле+2044 не объявлено эквивалентным CN.

Далее current core `DisplayBuiltIn::SetMotoDrmCmd`0x8e534 → virtual slot+0x248 →
current DAL `HWDeviceDRM::SetMotoDrmCmd`0x3c7d0 (все220bytes равны CN0x3c7a0) →
`drmIoctl(0x4008649b, {uint32 id,int32 val})` → target kernel descriptor
`.rodata+0x8cb18`, handler relocation+0x8cb20 →`msm_ioctl_set_moto_drm_command`
0x1d6110 → KMS0xd285c → display0x1a06fc → panel0x1c3ec4.
FUNC-ID0 выбирает запись `dobly_enable`.

APS2 vtables и PLT проверены, не угаданы по соседним symbols: target client
0xcd070→GOT0xd4ab8→`__cfi_slowpath`; DAL0x61e18→GOT0x657a8→`drmIoctl`.
Evidence: [target disassembly](target_sdm_apl_gate.disasm.txt),
[byte comparisons](target_cn_gate_byte_comparison.txt),
[vtable mapping](cn_vtable_slots.txt), [target ioctl](target_moto_ioctl.txt).
Это подтверждает **код текущих файлов**, не runtime исполнение Dolby gate,
не оптический эффект и не frequency setter.

## 7. Current SurfaceFlinger: владелец LTPO brightness gate

Target SF отличается от CN:8297480bytes,
SHA256`5da0b89ba3a4cfaac5684aa4a4c7ea51076f5235c6adfcd202e0d430302baca3`.
[Разобраны собственные target VA](target-surfaceflinger-selected.txt), не CN offsets.
Reader0x2cabac–0x2cacac:

| Property | Field | Target getprop |
|---|---:|---:|
|debug.sf.1hz_nit_lower_limit|this+0x160c|0|
|debug.sf.10hz_nit_lower_limit|this+0x1614|9999999|
|debug.sf.1hz_nit_lower_limit_cli|this+0x1610|absent|
|debug.sf.10hz_nit_lower_limit_cli|this+0x1618|absent|

Fallback string99999; primary parseatof→int, CLIatoi. Независимый runtime dump
подтверждает **уже загруженные** `1/10Hz NitLowerLimit: 0 9999999`,
`mSpecialIdleFlag=1`, оба special modes nominal120 с метками10Hz/1Hz:
[только выбранные policy-строки](target-surfaceflinger-policy.txt).
Полный raw dump остаётся private; уникальные identifiers не опубликованы.

`updateSpecialFlagByBrightnessZone`0x2a5574–0x2a56e8 выбирает primary/CLI thresholds,
затем задаёт flag1 при `policy_field+0x14 > threshold1 || mode_field+0xa4 == 1`;
иначе flag2 при `policy_field+0x14 > threshold10`, иначе0.
Store selector+0x4a8 по0x2a5614. Filter0x25d438–0x25d468 связываетflag1 с
mode-group **bit3**, flag2 с **bit4**, как1/10Hz flags в target DT.
Прямое равенство policy field текущемуDBV/калиброваннымnits не установлено.
Отдельные `prim_perf_90hz_base_brightness_zone` и`prim_perf_120hz_base_brightness_zone`
прочитаны как`40:24:120`, но не подменяют ими special-idle thresholds.

**Flag1 — policy/control state, не доказательство фактического DDIC1Hz.**
Один nominal120 наверху не исключает специальный idle-профиль; ни одно из этих
чисел не является измерением PWM. Property не менялись.

Архивный [cross-check](archived_timing_crosscheck.json) проверил этот возможный
confound без новых опытов: перед90Hz hold был **timing@7 → timing@2**, как уже
учитывал исходный stock-base-rate отчёт. Во всех пяти base-rate holds и пяти
selector-split holds нет новых logged DSI writes. Начальное абсолютное состояние
не доказано, но скрытая смена LTPO во время этих holds не подтверждается.
Оснований отменять A9-only fine-component improvement нет.

## Проверка и продолжение

- Расширен существующий `../runtime_pwm_recon_20261107/analyze.py` всего двумя
  функциями; выполнен в новый output `artifacts/brightness_policy_recon_20261107/evidence`.
- Dataflow всех153 instructions target backlight проверен; перевод clamp-ветвей
  совпал с source для65536 uint16 входов. Это static/model check, **не эмуляция
  модуля и не испытание панели**. Первый диагностический проход ошибочно ожидал
  min1 и доверял Capstone `CMP` register-write metadata; исправлено по raw DT460,
  actual epilogue0x1a0540 и ISA (`CMP` пишет NZCV, не первый operand). Ошибка не
  превращена в hardware claim; детали в validation.
- APL/HBM payload-prefix и различие headers проверены отдельным packet parser.
- Независимый source/ELF разбор подтвердил APL/LTPO путь и source/target расхождение.
- Независимое ревью §1–4/CN sender подтвердило все153 instructions,65536 clamp
  cases, AAPCS-preserved DBV и APS2 chain; блокирующих замечаний нет.
- Отдельное ревью current SF сверило все195 опубликованных instructions с ELF,
  VA/GOT/imports,16 finite branch-model cases и архивные native logs; замечаний нет.
- Extractor rerun в новый private output побайтно равен первому; refusal existing
  output и py_compile прошли. Это проверка инструмента, не оптический тест.

Не получены ни активный panel patch, ни доказательство≥2000Hz. Никаких новых
авторизаций не создано; A0D1C1 unapproved/unrun. R3 остаётся **active**, а не
«blocked целиком»: owner Dolby/APL gate и LTPO policy теперь прослежены, но
panel-specific emission count/period остаются unknown. Свежая внешняя проверка
нашла upstream ILI7836A driver с тем же page-unlock prefix, но без PWM-регистров;
это другой DDIC, байты не переносятся. Источник: torvalds/linux commit
`8a78143d94bbc9ed471d57599563bee0757493f4`,
`drivers/gpu/drm/panel/panel-ilitek-ili7836a.c`; branch master прочитан до pin lookup.
Exact indexed ILI97701A/ILI97701 searches не дали register map — это ограничение
поиска, не доказательство отсутствия документации.

**Последующий разрешённый шаг выполнен:** DTBO более позднего CN
`W3WWL36.65-48-7` получен через Range и [сравнен](../cn_48_7_recon_20261107/result.md).
Все52packetarrays+TEscalar выбранногоBOEv4 равныcurrentDT; готового отличающегося
профиля нет. Source-ветки не подменяли этот binary check. R3 всё ещё active;
аппаратный A0D1C1 gate остаётся отдельным, новых последовательностей не отправлено.
