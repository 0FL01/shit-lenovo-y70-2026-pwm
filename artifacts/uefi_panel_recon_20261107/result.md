# UEFI/bootloader: отдельный источник panel init

2026-11-07. **R3 active, не решена.** `reported`: офлайн-разбор двух уже скачанных
reference ROM, не новая проверка текущего телефона. Гипотеза: загрузочная firmware
может содержать target-specific emission initialization, отсутствующую в Linux DT.
Ни один образ не предложен к загрузке/прошивке; ADB/DSI/reboot/settings не выполнялись.

## Источник и извлечение

- CN: XT2611-1 RETCN `W3WWL36.65-11-18`.
- GLOBAL: XT2611-3 RETEU `W3WW36.65-64-4` — **не** current OTA и не совместимый
  по умолчанию образ для физического XT2611-1.
- Обе записи `bootloader.img`,83563776bytes, извлечены из локальных service ZIP
  с проверкой ZIP CRC (`fb68b0f5` / `433ffd32`). Полные пути:[inputs.json](inputs.json).
  Подпись/совместимость не следуют из CRC.
- Контейнер `SINGLE_N_LONELY`: header256bytes, затем name[248]+LEu64 size,
  content padded до кратного4096. Проверены границы и нулевой padding всех36
  записей; последняя — `LONELY_N_SINGLE`,size0. Все32 firmware filenames
  совпали с `default.xml`; три XML manifest и terminal marker не являются
  flash partitions. [Container manifest](container.json).
- `uefi.elf` начинается в bootloader по0x683800; внутри него FV по0x1000,
  размер0x400000. Следовательно FV source offset —0x684800. GUID filesystem
  `8c8ce578-8a3d-4f1c-9935-896185c32dd3`; вложенные volumes LZMA-сжатые.
- Установленный **7-Zip26.04** разобрал FV; `7z t` прошёл на обоих:214files,
  7folders. Через `7z e -so` выбраны только девять ILI97 XML, DisplayDxe,
  BacklightDxe и PanelSimConfig, без исполнения EFI-кода и без извлечения
  недоверенных путей. [Extraction manifest](fv-extraction.json).

Все исходные binary/XML и diagnostic находятся в
`/home/stfu/.cache/opencode-tmp/opencode/uefi-panel-recon-20261107/`.
Ранее прямой `7z l uefi.elf` отказал: это ELF-контейнер, не FV; выделение
FV по валидированным offset/length устранило причину, не обошло проверку.

## Результат по выбранному v4

GLOBAL `Panel_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4.xml.raw`:

- Строки65–172: **95 init-команд**. Их тип, порядок, payload и контекст page
  полностью совпадают с сохранённым actual selected DT:
  `artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-on-command`.
- XML records `FF 78`/`FF 14` дают численные значения120/20, равные соответствующим
  DT wait fields. Это сравнение представления задержек, не измерение исполнения
  UEFI или подтверждение live timing. DT-only transport flags не объявляются
  эквивалентными XML metadata.
- Строки56–57: nominal refresh0x780000 и bitclock1234000000; строки181–184:
  BacklightType3, bitwidth14, default7001,max16180. Это **не OLED PWM Hz**.
- Новых page/payload, отсутствующих в current selected DT, в этой init-серии нет.
  Отдельная boot-time high-PWM серия гипотезой не подтверждена. Сам факт наличия
  XML не доказывает, что текущий target bootloader выбирает/исполняет именно её.

CN v2/v3/v4 отличаются от GLOBAL одинаковым маленьким блоком, XML128–140:
`2D:83 00 → 83 00 00`, добавлены `2D:98 03 00`, `99 05 00`, `A0 00 00`.
Эти GLOBAL payload уже присутствуют в current kernel init; это не новый регулятор
частоты. Остальные шесть из девяти ILI97 XML равны побайтно. PanelSimConfig также
равен, но это не доказательство одинакового panel selection на двух устройствах.

## Загрузочные display-драйверы

DisplayDxe.efi442368bytes и BacklightDxe.efi45056bytes в CN/GLOBAL отличаются
**ровно11 байт каждый**, только Jenkins workspace ID
`f82eeb47aa7a → 378d0c4ff757` внутри **PE CodeView NB10 debug path**.
PE32+/ARM64 headers, debug-directory type2/RVA/file pointer и диапазон path
разобраны структурно. Все остальные байты, включая машинный код и данные,
равны; нельзя приписывать эти11байт отдельному региональному PWM setter.
Это не сравнение всего bootloader, текущей OTA или DDIC NVM.

В DisplayDxe есть generic parser string `BacklightPmicPWMFrequency`; одно её
наличие не устанавливает OLED emission control. Здесь не делается вывод о всех
возможных bootloader overrides и не предлагается менять PMIC frequency.

## Follow-up 2026-11-08: сравнение v2/v3/v4 *между* вариантами

`reported`, только offline reference: [variant_compare.py](variant_compare.py)
сверил тип, порядок, payload и численные задержки UEFI XML с `timing@0` публичного
Motorola `kernel-display-devicetree` на pin
`f088523dfba85c95c15f43726fcf972c0c7a957a`. Все **92/133/92** пакета
CN v2/v3/v4 соответственно равны source timing@0. GLOBAL v2/v3/v4 содержат
**95/136/95** пакетов; отличие от CN в `2D` уже описано выше. Выбранный GLOBAL
v4 также сверён со **сохранённым actual selected** DT timing@0 (95 пакетов).

- Между GLOBAL v2 и v4 меняются только три одноимённых пакета в позициях
  44–46 (`1E:CA/CB/CC`); этот блок в
  [init-payload reverse](../init_payload_recon_20261107/result.md) отнесён к
  source-labelled LHBM. Это не доказательство PWM-семантики трёх байтовых таблиц.
- У GLOBAL v3 тот же префикс, кроме тех же трёх позиций. Перед последним `29`
  вставлены 41 пакет: `53:F0=01 → 63:F1..F4/F8..FA → 53:F0=00`, затем
  page `2F:99=E4`, 24 пакета `2F:80..97` с тремя двухбайтовыми группами в
  каждом и `2F:99=00`. Переключения страниц входят в число 41. Это **v3
  variant**, не подтверждённая команда для выбранной v4; смысл 2F-таблицы и
  фактическая физическая revision панели неизвестны.
- Все четыре payload `63:F1..F4` в этом v3 bootstrap побайтно равны их
  сохранённым значениям в выбранном v4 `qcom,mdss-dsi-dc-off-command`. Они
  не открывают новую карту Hz или новую высокочастотную настройку.

[Проверяемые счётчики/источники](variant_comparison.json). В проверенном объёме
не обнаружено отдельной UEFI-only программы и не найден переносимый на selected
v4 регулятор реального PWM. Вывод ограничен этими XML/init массивами: не
квалифицирует исполнение UEFI на текущем target, код DisplayDxe, DDIC NVM или
физическую частоту. R3 остаётся открытой, A9-only baseline сохранён;
stock→A0D1C1→stock всё ещё **не разрешён и не запускался**.

## Воспроизводимость и границы

```sh
python3 artifacts/uefi_panel_recon_20261107/analyze.py \
  /home/stfu/.cache/opencode-tmp/opencode/uefi-panel-recon-20261107 \
  NEW_NONEXISTENT_OUTPUT.json
```

[Analyzer](analyze.py) и [результат](analysis.json):9XML,95packets,2PEs.
Выполнены syntax check, повторное точное воспроизведение JSON в памяти,
отказ перезаписи existing evidence в normal/`-O` (bytes/mtime неизменны),
in-memory отказ неверной PE signature. ZIP CRC, полный container walk и два
`7z t` — отдельные проверки извлечения. Новых dependencies нет.

Следствие для следующего действия: переносить bootloader XML на панель незачем —
проверенная v4 init-серия уже есть в target DT. Нужны новые target-specific
register semantics либо причинный оптический опыт. Подготовленная точная
[stock→A0D1C1→stock серия](../dsi_coupled_9d_20261107/proposal.md) по-прежнему
не имеет отдельного разрешения и не отправлялась; этот офлайн-результат его
не заменяет. A9-only сохранён как промежуточный baseline, не объявлен≥2000Hz.

## Узкий follow-up к v3 page `2F` (2026-11-08, offline)

Отдельная проверяемая гипотеза: 24 строки `2F:80..97` из v3-only UEFI
bootstrap уже доступны как один из runtime-профилей в **выбранном v4** DT.
Используя `xml_init`/`parse_packets` из `variant_compare.py:12–13,34–37,69–75`,
побайтно прочитаны все **52 packet arrays / 1101 packets** сохранённого
`artifacts/device_tree/selected_boe_v4/` (`**/*command`, кроме единственного
скалярного `qcom,mdss-dsi-te-dcs-command`). Результат: **0 packets на page2F**,
следовательно, 0 совпадений с 24 строками v3. В частности, проверенные
`dc-on`/`dc-off` по 75 packets также не содержат page2F. Это закрывает лишь
гипотезу о *готовой selected-DT runtime-копии* этой v3-таблицы; не доказывает
её семантику, отсутствие других writer-ов или частоту PWM. Бинарники/устройство
не менялись, вариант v3 не переносился на физическую панель.
Дополнительно тем же `xml_init` проверены все девять GLOBAL reference XML из
сохранённого FV: 24 строки `2F:80..97` есть **только** у ILI97701A v3; v0/v1/v2/v4
и четыре ILI97680A vantage-variant не содержат их. Это узкое ограничение
переносимости, не расшифровка таблицы и не свидетельство её live-исполнения.

Расширенный офлайн-контроль того же *boot-reference corpus*: через `7z e -so`
по одному извлечены и структурно прочитаны `DSIInitSequence` всех **82 XML**
сохранённого GLOBAL64 FV (встречаются и записи DSI type `07`, поэтому
выборку нельзя ограничивать BOE-parser-ом, принимающим лишь `05/15/39`).
Page выбиралась только командами `39 FF 5A A5 xx`, поиск не зависел от регистра
или от регистра букв в исходном XML. Записи на page `2F` встречаются ровно в
одном XML — ILI97701A **v3**: `99 E4`, 24 строки `80..97` по три big-endian
16-bit значения, `99 00`. Все три последовательности строго возрастают;
крайние значения: `04BA→1FF7`, `05E3→1D9B`, `06DD→252A`.
Побайтный разбор этих 24 строк совпал с pinned публичным Motorola DT v3
(`variant_compare.py:20–31`); в остальных81 XML нет даже page2F init-записей.
Форма трёх монотонных колонок **не устанавливает** их назначение: назвать
таблицу gamma либо частотой излучения без decoder-а нельзя. У выбранного
target software v4 готовой копии нет; boot execution и физические Hz неизвестны.
Новых команд на устройство, DSI-записей или разрешения A0D1C1 этот поиск не даёт.

Отдельный контроль **именованных настроек** тех же 82 XML: `7z e -so` и
`xml.etree.ElementTree` дали 84 различных имени элемента; по именам элементов
и атрибутов с `pwm|flicker|dimm|frequency|freq` (без учёта регистра) совпал
только `DSIBitClockFrequency` у 17 профилей. У ILI97701A v4 его значение
`1234000000` задаёт битовую частоту DSI-транспорта, **не** частоту излучения
OLED. Среди имён атрибутов (`id`, `units`) совпадений нет. Таким образом,
готового *именованного* PWM-frequency поля в этом сохранённом UEFI XML-корпусе
не найдено; это не поиск семантики бинарных DSI payload, не проверка иных
firmware-компонентов и не доказательство отсутствия настройки в DDIC.
