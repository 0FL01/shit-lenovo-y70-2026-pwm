# DDIC: CRC и полный 40-byte repeated-read путь

2026-11-07; binding follow-up 2026-11-08. **R3 active, не решена.** Новая проверяемая гипотеза: сохранённые
CRC-хвосты позволят квалифицировать длинуEC/C1 replies. Это data-level анализ
старых архивов и новый ARM64 code-level RE через утверждённый Ghidra helper,
не повтор прежнего small-copy контрпримера. Новых ADB/DSI/sensor/settings/flash
действий нет, unsafe legacy reader не запускается.

Источники: четыре завершённых40-byte архива в`artifacts/ddic_regdump_20261107/`,
current target`msm_drm.ko`, known native OFF payloads выбранной BOEv4.
Воспроизводитель: [analyze_ddic_transport.py](../../06-tools/analyze_ddic_transport.py).
Узкая regression-проверка: [test_ddic_transport.py](../../06-tools/test_ddic_transport.py).

Ghidra12.1.4 exports получены через`06-tools/ghidra_decompile.py` из
`/home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python`, selectors
`dsi_ctrl_cmd_transfer` и`dsi_ctrl_hw_cmn_get_cmd_read_data`. Projects/JVMtemp были
в external approved cache; оба jobs завершены. C/manifest/provenance:
`/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/ddic-response-20261107/{controller-transfer,read-data}/`.
ET_REL import address не является live kernel VA. Decompiler output — материал
для независимой проверки, не доказательство framing или DDIC semantics.

## Сохранение raw и CRC census

`06-tools/ddic_regdump.sh:39,45–46` сохранял stdout`cat rx_cmd` без собственного
дополнения нулями; host`run_ddic_regdump.py:123–130` записывал полный stdout вraw.
Это **не доказательство**, что сам kernel/DDIC не добавляет нули. Старые runners
прочитаны как source и не исполнялись.

[analysis.json](analysis.json):38912rawreads,8passes,684различные40-byte строки.
Проверены возможные CRC boundaries1…38 с seedFFFF/reflectedpoly8408/LSB-first;
битовый код сверяется с независимой`binascii.crc_hqx` через отражение битов.
Known answers:`00→0F87`,ASCII`123456789→6F91`.

- Для07:EC и23:C1 нет совпадений ни в одном из8наблюдений каждого адреса.
- Единственная различная строка с совпадением —63:DD: prefix`9A A6`, следующие
  bytes`A9 D4` математически равныCRC; затем идут ещё12ненулевыхbytes.
  Она повторяется8раз (rawlines9439/9695), но это **не8независимых подтверждений**
  границы packet и не квалифицированный двухбайтовый ответ.
- Все80known-native prefix controls совпали с исходными OFF payloads; сразу
  после этих prefixes CRC не наблюдается ни в одном случае. Write payload length
  не приравнивается к response WC. ОтсутствиеCRC не доказывает payload length.

## Новый repeated-read разбор через Ghidra

`reported`, compiled target functions и условная FIFO-модель:

| Проход | MRPS | Нормализованный count приP40 | Destination offset | Skip | Copied |
|---|---:|---:|---:|---:|---:|
|1|10|16|0|0|16|
|2|24|30|14|0|16|
|3|38|44|28|0|16|
|4|40|46|42|12|4|

Allocation=`max(16,(requested+9)&~3)=48`; pinned GKI flags0xDC0 равны
`GFP_KERNEL|__GFP_ZERO` (0xCC0|0x100). Helper сохраняет возвращаемое16 даже при
частичном copy/отсутствииcopy. Поэтому pointer/counter шагают на16−2=14,
а не на фактическое число новых payload bytes. При normalizedC>16:
`skip=prior_counter+16−C`; приC≤16skip0.

При полномP40 последующие chunks перекрывают предыдущиеCRC. Финальныйparser
копирует assembled[4:44] —40payloadbytes безCRC. Сохранённый первый header имеет
**WC10**, не40: егоWC не используется как предел финальногоcopy. Это объясняет,
почему простой CRC-search вraw не является способом восстановить framing.

**Риск короткого ответа в этой модели:** дляфиксированногоP1…10 helper каждый раз
пишет16bytes в offsets0/14/28/42. Последний интервал[42,58) выходит на10bytes за
**requested allocation [0,48)**. Clamp/уменьшенияrx_byte на последнем проходе
в проверенных функциях нет. Реальныйslab bucket, KASAN и live corruption не
установлены. Модель останавливается`BufferError`, не объявляет kernel-safe refusal.
ДляP1…5 finalfortify был бы ещё одним поздним нарушением, но helper store происходит
раньше. Это обнаружено первой упавшей regression-проверкой; граница не ослаблялась,
исправлена классификация порядка событий. В доменеэтоймодели finalfortify/None
после helper уже недостижим: P≤10 останавливаются раньше, остальные проходят.

ДляP11…38 модель даёт`payload[P]+CRC[2]+zero[38−P]`; P39 даётpayload39+CRC_low,
P40 —payload40. Из684строк679 совместимы только сP40,5 —сP39/40; EC/C1 —толькоP40.
**Это не live WC qualification:** P40 воспроизводит input по построению, а модель
предполагает правильный long header, стабильный payload между4чтениями, точный
normalizedHWcount и right-aligned last16FIFO. ACK/ECC/error/count corruption не
моделируются. Реальные headers/WC/HWcounts отсутствуют вархивах; writable/Hz смысла
уC1/EC отсюда не появляется.

## Независимая проверка и граница decompiler

Ревью подтвердило MRPS/offsets/skip, постоянныйrx_byte16, отсутствиеclamp дляC≤16,
conditional allocation overrun и GFP_ZERO по pinned kernel HEAD
`09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`. CRC census этим ревью не перепроверялся;
двеCRCреализации и archive/native controls — отдельные выполненные проверки.

Ghidra import address =`.text offset+0x1A6A70`, **не liveVA**:

- Controller entry`.text+0x1970c0`→import`0x33db30`; manifest515instructions,
  rawfunction539words. Не вошли24allocation-tagging fallbackinstructions:
  `0x1976f0…0x197714` и`0x197790…0x1977c4`. Не утверждатьполный539-word decompile.
- Helper entry`.text+0x19161c`→import`0x33808c`,211instructions.
- Ghidra C с`readl_relaxed(); extraout_var &0xffff` нельзя читать буквально:
  `.text+0x191678` содержит`lsr w9,w0,#16`; аппаратныйcount —верхние16bits.
  Затем ACK-normalization и clamp доMRPS+6 даютcount дляskip/header alignment.
- Repeatedhelpercall:`0x1974d4…0x197504`; longcopy:`0x1975f8…0x197628`;
  helperwordstore:`0x19179c…0x1917b4`. Raw evidence сверялось независимо от C.

Новая regression-проверка прошла, включая все условныеP11…39; analyzerJSON
воспроизводится побайтно; normal/`-O`
refusal сохраняетbytes/mtime; оба новыхPythonфайла проходятsyntax. Старые archives
и frozen extractors не менялись, runtime/kernel patch не создавался.

## Binding follow-up и следующий переход

Сохранённые [Ghidra brief/structured xrefs](ghidra_distill/README.md) указали
обе DATA-ссылки из `dsi_catalog_ctrl_setup`; excerpts строк50…135 и135…210
подтвердили store `ops+0x1F8=helper` в обеих ветках выбора версии. ELF
relocations для ADRP/ADD по `.text+
0x19bdb4/0x19bdb8` указывают на helper `.text+0x19161c`, следующая instruction
`0x19bdbc` — `str x9,[x0,#0x1f8]`. Для другого входа `.text+
0x19c080/0x19c084` указывает на того же helper, `0x19c088` — такой же store.
Controller вызывает slot `ctrl+0x258+index*8` с аргументом `ctrl+0x60`;
при `ops=ctrl+0x60` и **index=0** это `ops+0x1F8`. При index1/2 адреса
`ops+0x200/+0x208`: в данном `setup` не найдены их записи. Значение индекса
в live вызове и альтернативные источники записи пока `unknown`; две ссылки на
helper не дают безусловной привязки. Независимый review подтвердил именно
`setup→helper` и conditional `disp_op=0`, не нашёл overclaim или blocker в этом
узком scope; тесты CRC/модели он не ревьюил (они пройдены отдельно).
Cached original Ghidra
сырьё было удалено по ранее зафиксированной причине; новые excerpts во внешнем
approved cache, агент не читает полный decompiler listing.
Новой причины менять A0D1C1 short1/1/2 из этого не следует. R3 active, A9baseline
сохранён, A0D1C1 не авторизован/не отправлен; PWM Hz неизвестны.
Следующий различающий **panel**-тест — уже подготовленная точная
[stock→A0D1C1→stock серия](../dsi_coupled_9d_20261107/proposal.md). Её нельзя
подменять безусловным выводом из CRC или исполнять без отдельного точного
согласия владельца. До согласия работа здесь остаётся offline.
