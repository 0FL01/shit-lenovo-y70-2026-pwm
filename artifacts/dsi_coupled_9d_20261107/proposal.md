# A0D1C1 — следующий условный selector/control опыт, только offline

**NOT AUTHORIZED / NOT SENT.** Target и неизменённый kernel/module — как в
`../dsi_coupled_on_20261107/proposal.md`. PWM Hz неизвестны. Это проверка одного
ранее не проверенного взаимодействия, не обещание увеличения частоты в2–3 раза.

## Почему это не повтор S0C1 или 9D-only

Обозначения: A=high bit `23:A9`, D=high bit `24:9D`, C=остальные32 изменяемых
payload-пакета native ON. «0/1» здесь означает заводской OFF/ON, не число импульсов.

| Проверенный контекст | A | D | C | Fine-train после корректного redraw |
|---|---:|---:|---:|---|
| stock |0|0|0|сохраняется|
| A9-only |1|0|0|подавлен, широкая структура остаётся|
| 9D-only |0|1|0|сохраняется|
| selector pair |1|1|0|подавлен, широкая структура остаётся|
| full native ON |1|1|1|подавлен после redraw, не до него|
| S0C1 |0|0|1|сохраняется; владелец отклонил|
| **Новый A0D1C1** |**0**|**1**|**1**|**не проверен**|

Проверяемая гипотеза: D может выбирать другой режим только при загруженной C1,
пока A не принуждает к прежнему подавленному-train состоянию. Отдельно D1 на C0
и отдельно C1 при D0 этой гипотезы не проверяют. Это новый фон селектора, не
маленькая численная прибавка к frequency-регистру. Его назначение не декодировано.
Нельзя заранее назвать этот режим «high PWM», обещать ×3 или приписать новый
рисунок конкретному emission count без дальнейших измерений.

Full native ON перепроверен без temporal demeaning по361 исходным cached frames:
`../optical_repair_20261107/native_on_cached_spatial_v2.json`. После redraw total
q93 ratio0.3849304, до него1.0058686; прежний вывод не был следствием удаления
стационарных полос. Исторические окна и исходный cache не изменялись. A9-only
0.2264067 остаётся сохранённым intermediate baseline, не выполнением≥2000Hz.

## Точные байты и будущая конечная серия

`on_keep_a9_off.bin`: полный native ON, **только offset68/A9 оставлен0E**.
9D=8E. От S0C1 отличается только offset97; от OFF —33 пакета/84 байта.
875bytes/75packets, исходные headers/order/74batch+final flush/page0 сохранены.

- Candidate SHA256: `8604d62cb74646105413c94105a5d66273e865bda2be0e0225f5dc3f69eac62e`.
- Stock return SHA256: `b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193`.
- Chunk ranges: `[0,253) [253,500) [500,754) [754,864) [864,875)`.
- Два независимых packet parser подтвердили структуру; сравнение с семью
  сохранёнными875-byte кандидатами не нашло идентичного предыдущего профиля.

Если отдельно согласовано: **stock → A0D1C1 → stock**, одна проба кандидата,
DBV3600/requested120/providerDC0, одинаковые DBV replay/redraw,7s camera holds
100us/ISO6400 с неизменными focus/geometry/AE/AF/OIS/EIS. Readback кандидата
A9/9D/DBV =0E/8E/0E10, stock =0E/0E/0E10. Полный native trace и full spatial
spectrum/phase; сравнить с текущими stock и историческим A9, не объявляя разные
съёмки simultaneous head-to-head. Никакого автоматического promotion baseline.

Нет крупного изменения — закрыть именно эту условную гипотезу, не повторять.
Новый рисунок — сохранить как наблюдение, не присваивать автоматически Hz.
Неприемлемый для владельца профиль не считать решением.

Возврат: полная исходная OFF таблица, DBV/redraw, readback, ESDreg_read/logger0,
удаление собственных probes/files, captured native DBV и Android policy.
При неопределённой очереди не дописывать новый batch: emergency ordinary reboot
в неизменённую stock display initialization, затем identity/root/Enforcing checks.
Такой reboot входит в запрашиваемую точную серию; повреждение панели может быть
необратимым. Ни flash/AVB/slot/kernel, ни persistence, ни повтор A9 сюда не входят.

Выполнены только offline compile, syntax и byte checks. Авторизации/run нет.
Новый бинарник не подставлялся в прежний запуск с использованным разрешением.
Подготовлены `run_dsi_mode_trial.py --coupled-9d` и соответствующий analyzer option:
отдельные outputs/marker/labels и readback9D=8E только у кандидата. Авторизация
должна указывать этот proposal, `candidates=["a0d1c1"]`,
`sequence=["stock","a0d1c1","stock"]`, собственные `program_sha256.stock/a0d1c1`,
actual owner confirmation/time и `emergency_reboot_approved=true`.
Старое разрешение S0C1 отвергается.16 unit tests, CLI refusal без разрешения/при
Python-O и независимое ревью прошли; аппаратная квалификация нового профиля отсутствует.

Дополнение к transport-ограничениям: [офлайн ревью short-read guards](../ddic_state_marker_20261107/result.md)
отделило корректные short responses для запросов1/1/2 от long-copy, не проверяющего
response WC. Точное сравнение длин/байтов сохранено. Один requested≤2 не доказывает
целостность ответа: неожиданный long type в4-byte buffer ведёт к`__fortify_panic`,
не к безопасному отказу. Такого ответа наA9/9D/52 в проверенных данных не установлено;
это ограничение транспорта, а не live qualification или новое разрешение запуска.
Candidate/stock bytes и scope неизменны, kernel/runner не правились.

Offline контроль выбранного DT перед опытом: `audit_pwm_archive.parse_packets`
разобрал все 52 packet-array properties (1101 packets) в
`../device_tree/selected_boe_v4/`. Все **33 различающихся от stock пакета**
кандидата имеют разные пары (page, opcode); каждая из этих пар встречается
только один раз в `dc-off-command` и один раз в `dc-on-command`, и **ни разу
в остальных 50 массивах**, включая on/off и timing-switch для всех восьми
timing. В частности, `23:A9` и `24:9D` присутствуют только в DC-массивах:
OFF=`0E/0E`, ON=`8E/8E`. Гипотеза, что готовая смена timing перезапишет часть
C1, в пределах *выбранного статического DT* опровергнута. Другой runtime
writer/неожиданное переключение DC и удержание DDIC state после redraw этим не
исключены; точные readbacks, DSI trace и stock-return обязательны. Это не
частота PWM и не основание запускать опыт: NOT AUTHORIZED / NOT SENT.

Сохранённый **исторический S0C1**, не A0D1C1: по маркерам в приватных
`dsi-coupled-on-20261107/{baseline,s0c1,return_s0c1}-kernel.txt` каждая из
трёх стадий имеет75 native table writes, ровно один `51 0e 10` при DBV replay,
**0 зафиксированных DSI writes** между DBV_END и READ_BEGIN (redraw) и после
READ_END до конца stage log (hold). `run.json` подтверждает redraw и7 short-read
callbacks на каждой стадии; сохранённые readback traces без `LOST`. Это
`confirmed-on-target` лишь для той завершённой серии с работающим logger;
порядок/результат несогласованной A0D1C1 и неизвестные другим путём writers
отсюда не следуют. Эксперимент и его scope не менялись.
