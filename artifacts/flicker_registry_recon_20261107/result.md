# STK6A2X: registry/config → таблица ADC

2026-11-07. **R3 active; OLED PWM ≥2000 Гц не доказан.** Новый вопрос после
закрытых polling-rate/message700 веток: может ли отдельная конфигурация менять
ADC timing без правки firmware? Это исследование измерительного канала, не
изменение частоты панели. Работа только offline: ADB, sensor activation,
calibration, DSI, settings writes, reboot/flash не выполнялись.

## Проверяемая гипотеза и источник

`hypothesis`: registry/private config меняет timing03/04/0E или таблицу mode2,
хотя обычный client request передаёт фиксированный table pointer.
Проверяются именно сохранённые **current-target** ADSP b21/b22/b27/mdt, с
происхождением из [первичного разбора](../flicker_sensor_recon_20261107.md).
CN config ниже — отдельный reference, не установленное равенство target файла.

## Состоявшееся свидетельство: таблицы writable, но merge ограничен

`reported`, static target bytes; воспроизводитель [verify.py](verify.py),
[table_validation.json](table_validation.json):

- MDT segment22: VA`0xb2597000`, filesz2457604, flags`0x08000006` =R/W, неX.
  Таблицы нельзя объявлять read-only только из-за literal pointer в caller.
- Initial table`0xb259dde0` содержит **8×3bytes** `(register,value,mask)`.
  Её адреса: **01,02,05,06,60,DB,6A,6B**. Mode2 начинается по`0xb259de00`,
  mode1 —`0xb259de10`. Mode2 по-прежнему`03 00 3F /04 1E FF /0E 17 37 /00 10 10`.
- Функция`0xb231daf8…0xb231db7c` действительно изменяет initial table.
  Outer`loop1(...,#8)` по`0xb231db00` ограничивает её восемью entries;
  inner loop перебирает входящие triples. При равном register byte:
  `value=(old_value & ~input_mask) | (input_value & input_mask)`,
  `mask=old_mask | input_mask`. Адресные bytes не изменяются.
- Записи по`0xb231db44/db54/db5c` достигают максимум`0xb259ddf7`;
  mode2 начинается дальше, поde00. Hexagon packet`db1c…db28` использует **старыйr6**
  для load, а новыйr6 получает base+index; это не двойное прибавление base.
- Модель всех256input register IDs сfull mask подтверждает именно эти8адресов
  и неизменность следующих36bytes, включающих обе mode tables. Она проверяет
  адресную границу, не исполняет DSP и не доказывает физические единицы/Hz.
- В двух сохранённых executable listings b21/b27 найдены6прямых callsites
  mode writer`0xb231d63c`: `d49c/d4c8/f330/f408/f508/f744` в областиb231xxxx.
  Два передают fixed mode2/de00, четыре —mode1/de10. Watchdog, flicker/ALS и
  другой enable разобраны; новой mode3/fast-table в этих callsites нет.

Последнее — **bounded direct-call search**, не доказательство отсутствия
indirect callers, несохранённых сегментов или любой другой записи в writableb22.
Наличие merge не стало интерфейсом произвольной записи register03/04/0E.

## Reference config, не live applicability

`extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/etc/sensors/config/stk6a2x_0.json`
строки186–220 содержат10private keys:
`als0_dgain/als1_dgain=4`, `als0_again/als1_again=0`, `wait1/wait2=0`,
`autogain/autogain0/autogain1=1`, `max_dgain=7`.
Текущие target config contents не читались этим опытом. Следующий разбор проверил
consumer, а не вывел назначение только из этих имён.

## Новый target callback: имя →10байт →6троек →initial table

[registry_validation.json](registry_validation.json), воспроизведение:
`/usr/bin/python3 artifacts/flicker_registry_recon_20261107/verify.py --registry <new-output.json>`.
Дополнительно проверены253freshrecords: callback, private-group synthesis и общий
client calibration tail. Первые532records остаются отдельным неизменённым evidence.

- Group compare`0xb231b678…0xb231b684` использует target string
  `0xb240b236 = stk6a2x_0_private.config`. Parse bits`01/01/01/11` подтверждают,
  что call и подготовка name/r0/r1/r2 находятся в одном Hexagon packet.
- В`0xb231b6b0` передаётся callback **`0xb231adb4`**, который **есть в сохранённом
  target b21**. Generic decoder`0xb20c854c` за пределами сохранённых segments,
  но это не препятствует проверке callback имён/масок. Entry сравнивает names,
  проверяет integer-present flag по+44 и кладёт masked value в fixed output byte.
- Consumer задаёт destination`state+557`; callback`adb4…af90` допускает:

| Имя из target bytes | State offset | Маска value |
|---|---:|---:|
|als0_dgain /als1_dgain|557 /558|07 /07|
|als0_again /als1_again|559 /560|03 /03|
|wait1 /wait2|561 /562|low8 /low8|
|autogain /autogain0 /autogain1|563 /564 /565|01 /01 /01|
|max_dgain|566|07|

Точные имена/VA проверены по target bytes, не только по CN JSON. Logs corroborate
offsets: descriptors`0xb256de18/de60/ded8` указывают на текстыdgain/again, als_wait1/2
иautogain/max_dgain. **Физическое влияниеwait05/06 на период ADC неизвестно**;
названиеwait само по себе не задаёт временные единицы.

Consumer`0xb231b700…0xb231b7a0` строит state+628..645, гдеbN — перечисленные bytes:

| Register | Value | Mask |
|---|---|---|
|01|`(b557<<4)\|b558`|77|
|DB|`(b559<<4)\|(b560<<2)`|3C|
|05 /06|`b561 /b562`|FF /FF|
|6A|`(b563<<3)\|(b565<<1)\|b564`|FB|
|6B|`b566<<4`|70|

Всеvalue хранятся какbytes. Packet`0xb231b80c…0xb231b814` имеетparse bits`01/01/11`:
**call merge получаетr0=state+628,r1=6**, не старые аргументы логгера. Таким образом,
конкретная цепочка group→callback→6triples→bounded initial merge восстановлена.
CN reference defaults дают6triples, после которых **все24initial bytes равны
сохранённой target таблице**. Это полезная consistency check, не доказательство
текущего загруженного registry или live ADC состояния.

## Общий calibration tail: не подменять неизвестный вызов доказательством

`0xb2319e10…0xb2319e70` проверяетstate+2747, вызывает indirect method, затем
`0xb231bcd8` и дважды`0xb231bac8` сr2=2/8, после чего очищаетflag.
Packet-bound аргументы этих трёх прямых вызовов проверены. По сохранённому listing
bcd8 сравнивает/копирует24-byte calibration blocks (2644/2668↔508/532), но его
indirect iterator и первый indirect method хвоста полностью не разрешены.
Нельзя из отсутствия прямого timing-write в хвосте исключать все побочные эффекты.

Отдельная поправка к RECON: string группы дляbac8 — **`0xb240b3d0`**, неb240b328
(тамNUL). Bac8 **кодирует/отправляет message513** с`stk6a2x_0_platform.als` и
callbackbbec/item`fac_cal`; это не подтверждённое «чтение группы». Wire schema и
enum-name513 для этого registry-stream здесь не устанавливались. Никакой такой
request не отправлялся; именование стандартногоsensor513 не переносится между
протоколами. Этот tail не используется как найденный ADC-setting interface.

## Проверки

- 532fresh LLVM Hexagon records из6диапазонов совпали с сохранённым target listing,
  безundecoded; raw bytes включены вJSON. MDT sizes/flags и все три таблицы проверены.
- 6directcall locations и256bounded merge cases проверены. Сохранённые binary
  inputs не изменялись; никакой firmware patch не подготовлен.
- Точное повторное сериализованное вычислениеJSON совпало; syntax и отказ
  перезаписи existing output в normal/`-O` прошли, bytes/mtime сохранены.
  Первый diagnostic сравнил int-ключи Python dict сstr-ключами прочитанногоJSON;
  это была ошибка проверки представления, не nondeterminism. Повторная проверка
  сравнила **точные сериализованные bytes**, без изменения expected output.
- Независимое ревью подтвердило packet semantics/8entry bound/stores, все6callers
  по свежему decoder и MDT flags. In-memory воспроизведение дало точные66047bytes
  сохранённогоJSON; замечаний нет. Ревью не включало ещё разбираемый registry consumer
  и не является аппаратной квалификацией.
- После добавления callback режима обаJSON воспроизведены побайтно; normal/`-O`
  refusal и bytes/mtime preservation проверены для обоих outputs. Всего785fresh
  records в9диапазонах (532+253). Два новыхJSON и4локальные report links валидны.
  Generic decoder VA`0xb20c854c/0xb20c7d44` поactualMDT попадают в несохранённый
  b29: VA`0xb20c7000`,filesz181836,flags`0x08000005`. Это точная граница доступного
  offline кода, не отсутствие ADB/root и не препятствие уже проверенному callback.
- Отдельное независимое ревью новых253records подтвердило callback/destination
  binding (oldr3 поsp+152 противnewr3 поsp+156), все10names/masks, halfword stores
  при сборке6triples и оба call packets. In-memory JSON совпал с34544bytes;
  замечаний нет. Это ревью **не квалифицировало** дальнейшиеbcd8/bac8indirect effects;
  перечисленныеunknown не снимаются.

## Ограниченный результат и следующий переход

Закрыт **конкретный** путьprivate.config как интерфейс переписывания mode2 и
timing03/04/0E: он меняет только шесть указанных entry из восьмиinitial slots.
Это не отрицание возможностей железа, не исключение иных writers/indirect paths
и не заявление, чтоwait05/06 вообще не влияет на sample timing. Точныйwire schema,
другие target segments и текущие registry values остаютсяunknown. Публичная
[страница производителя](https://www.sensortek.com.tw/index.php/en/products/optical-sensor/)
не далаSTK6A2X register documentation; это не доказательство отсутствия документации.

Нового достижимого и квалифицированного быстрого ADC mode или panel-frequency
setter эта цепочка не дала. Следующий причинный panel-опыт остаётся подготовленным
A0D1C1 с отдельным exact-operation gate; offline расширение именно registry-ветки
требует другого конкретного writer/параметра, а не повторного анализа этого callback.
A9-only baseline сохранён; A0D1C1 не авторизован/не запускался, R3 не закрыта.
