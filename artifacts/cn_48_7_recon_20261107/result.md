# CN W3WWL36.65-48-7: actual DTBO против текущего BOE v4

2026-11-07. **R3 active, PWM≥2000Hz не достигнут.** Проверена новая конкретная
гипотеза: более поздний доступный CN archive содержит отличающийся штатный BOE v4
профиль, не представленный старым CN W3WWL36.65-11-18/pinned source.

## Получение и область доверия

`reported`: зеркало lolinet вновь перечислило exact XT2611-1 RETCN archive
`XT2611-1_AVR_RETCN_16_W3WWL36.65-48-7_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip`.
[URL и проверенные ranges](acquisition.json). Archive size15,019,660,678bytes,
ETag`"6a8b97ec-37f3dd586"`; HTTPS Range/If-Match проверялись на каждом чтении,
неожиданный200/full-download запрещён инструментом. ZIP64 содержит58entries.

В первом этапе извлечены **только** `dtbo.img`, signing-info и build-info; ни flashfile/erase
recipe, ни FSG, ни весь super не исполнялись/не извлекались. Final acquisition
скачал **150616bytes** (предварительные probes/inventory — отдельно). Все три
ZIP CRC проверены полным чтением entries. Подписи/authenticity chain **unknown**;
это reference для сравнения, **не доверенный flash/recovery image**.

Build-info подтверждает заявленные archive model/build:
`Lenovo/avr_cn/avr:16/W3WWL36.65-48-7/660f5-d1e8f0:user/release-keys`,
build date2026-07-17. Это данные пакета, не независимая аутентификация поставщика.

DTBO75497472bytes, SHA256 для идентификации бинарного сравнения:
`5ef9e58f075e6735cca1ab7fd698283f6db95c426e001554780ecd83e50d3bf5`.
Header: total617183, one entry, DTB offset64,size617119. Panel найден по **node path**,
не по display-name (последний не содержит номера IC):
`/fragment@169/__overlay__/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4`.

## Результат

Reference subtree415properties против425 в ранее сохранённом live subtree
`artifacts/device_tree/selected_boe_v4` текущего GLOBAL W3WWS36.65-64-4-1.

- **412 общих свойств побайтно равны**.
- **Все53 свойства с суффиксом `-command` равны:** это **52 сериализованных
  packet arrays и один u32 `qcom,mdss-dsi-te-dcs-command=1`**. Уточнение счётчика
  существенно: последнее не DSI packet array, source `dsi_panel.c:3274` читаетu32.
  Первоначальное обозначение всех53 как«массивов» было неточным; код исправлен
  по схеме, а не путём игнорирования ошибки парсера.
- Остались10 live-generated `name` properties и3 отличающихся reference fields:
  `phandle e4→74d`, `panel-supply-entries db→744`, reset GPIO phandle
  `ffffffff→29` с одинаковыми остальными cells146/0. Полного разрешения overlay
  противbaseDT здесь нет: равенство питания/всей платформы/flash-совместимость
  **не выводятся** из этих трёх чисел.
- От старого CN11-18 новая CN48-7 имеет12 изменённых v4 command arrays
  (@0,3,4,5,6,7 init иtiming-switch). Эти изменения уже присутствуют в current
  GLOBAL выбранном subtree; нового готового DSI-профиля они не дают.

[Полный byte comparison](comparison.json). Это сужает региональную гипотезу:
для проверенного software-profile новые CN tables уже равны target, а не
«CN имеет отличные команды, которые достаточно перенести». Равенство не
доказывает одинаковый kernel/userspace, DDICsilicon/NVM или физический PWM.

## Независимая проверка и воспроизведение

- Существующий FDT parser переиспользован без изменения; новый `compare.py`
  воспроизводит JSON точно и отказывается перезаписывать существующий output.
- Независимый **DTC1.7.0-Android-build**, DTB→DTB round-trip: все**14631property
  values /1943nodes** равны оригиналу. Overlay безbase выдаёт warnings; это
  не использовано как validation для загрузки на устройство.
- Первый DTB→DTS→DTB round-trip изменил6 непанельных properties из-за NUL перед
  ASCIIoctal digits (`\0` рядом с`2`/`3`); его bytes не использовались в сравнении
  или как образ. Полный binary round-trip сохранил исходные значения, проверка
  не ослаблялась: [validation](independent-validation.json).
- py_compile обоих новых локальных scripts прошёл. Acquisition не перезапускался
  ради теста: файлы/CRC сохранены; network bytes не скачивались повторно.
- Независимое ревью повторно воспроизвело comparison, проверило52arrays вторым
  packet parser, все14631properties независимымDTC и CRC cachedmembers; ошибок нет.
  Network ranges reviewer не повторял и не выдавал за собственную загрузку.

```sh
python3 artifacts/cn_48_7_recon_20261107/compare.py \
  /home/stfu/.cache/opencode-tmp/opencode/cn-48-7-dtbo-20261107/members/dtbo.img \
  /path/to/new-output.json
```

Acquisition script, original selected ZIP members, independent DTBs и warnings:
`/home/stfu/.cache/opencode-tmp/opencode/cn-48-7-dtbo-20261107/`.

## Продолжение: исполняемый модуль, а не только tables

После совпадения tables проверяется иная гипотеза: драйверCN48-7 может содержать
дополнительный emission setter. Для неё отдельно range-извлечён `vendor_boot.img`,
100663296bytes /7367257compressedbytes /CRC32`e12a38e5`:
[acquisition](vendor_boot_acquisition.json). Это не boot/flash candidate.
Официальный сохранённый AOSP unpacker прочитал VNDRBOOTv4, один ramdisk fragment.
LZ4→newc CPIO:342entries; извлечён только `lib/modules/msm_drm.ko`.
Нативный `cpio --extract --to-stdout` дал ровно те же module bytes, не создавая
файлов по архивным путям: [validation](module_extraction_validation.json).

CN48 module6071656bytes, BuildID`8c58ca326e99f7c98644d723230b40a7686dee81`,
SHA256`d3519a51bf9a74e02448c455349f8e69fccca1aa316a7be4951ada76c6b8b52d`.
Он **не равен current target**, но **побайтно равен GLOBAL reference W3WW36.65-64-4**:
модуль независимо извлечён из сохранённого
`artifacts/firmware/w3ww_base_36.65-64-4/vendor_boot.img` и сравнен целиком,
не только поBuildID: [comparison](global64_module_comparison.json).
Таким образом, это не новый уникальный CN binary относительно этого GLOBALreference.
Сопоставление с текущимOTA выполнено отдельно:
[module comparison](module_comparison.json), [all-section validation](module_sections_validation.json).
`.text/.rodata/.data` и их relocations побайтно равны; все**21RELA sections /
103589 resolvedentries** равны с учётом целей symbol table. Из46 изменённых
symbol entries каждое — только другое имя локального `__UNIQUE_ID_*`, остальные
поля равны. Всеsection names/sizes/attributes совпали; отличаются только содержимое
`.note.gnu.build-id`, `.symtab`, `.strtab`. BuildID difference не является другим
PWM-алгоритмом. Это бинарное сравнение, не reproducible source build/ABI approval.

Восемь owning functions (display/panelbacklight, APL, DCparam/sender/parser,
BLregister/parser) совпали по коду и разрешённым relocations; набор118defined
`dsi_panel_*` functions равен. Все3`pwm_apply_might_sleep` sites остаются в
альтернативномtype0, выбранныйDCStype2 их не использует; DCmap по-прежнемуOFF/ON.
Таким образом, новыйCN48 runtime emission branch в проверенномpath не обнаружен.
Parent повторил сравнительныйscript точно и независимо расширил проверку до
всехsection attributes/RELA targets; nativeCPIO и CRCchecks также прошли.
Reproducer: privatecache `module-analysis/compare_scoped.py`.

Никаких device calls в этой firmware-ветке, DSI/reboot/flash не было. A9-only
сохраняется как промежуточный baseline. Отрицательный результат этой гипотезы
не закрывает R3 и не доказывает невозможность высокочастотного режима; недостаёт
target-specific emission mapping/оптического ответа, а не ещё одной копии этих
же command tables. Подготовленная A0D1C1 серия не запущена и требует точного
отдельного подтверждения, как и любая новая составленная DSI-программа.

## Продолжение 2026-11-08: bootloader новой CN48 прошивки

**Гипотеза:** несмотря на равенство DT и `msm_drm.ko`, новая CN48 загрузочная
прошивка могла содержать другую BOE-программу или карту выбора версии. Из того же
публичного ZIP через проверенные Range/If-Match извлечён **только**
`bootloader.img`:83563776bytes,11534057compressed,ZIP CRC32`be4d5cd3` проверен;
[provenance](bootloader_acquisition.json). Это офлайн-источник, не образ для flash.
`SINGLE_N_LONELY` контейнер имеет36 корректных записей,32 flash-файла совпадают
с `default.xml`; оба FV из `uefi.elf`/`abl.elf` сверены с контейнером и прошли
`7z t` (214/3 files). Для сравнения извлечены только9 BOE XML,
`DisplayDxe.efi`, `BacklightDxe.efi` и `MotoBootModule.efi` в approved cache.

[Воспроизводитель](bootloader_compare.py) и [компактный результат](bootloader_comparison.json):

- **Все9 CN48 BOE XML побайтно равны GLOBAL64 reference**, включая ILI97701A
  v2/v3/v4(95/136/95 packets). По сравнению с ранним CN11 только эти три
  варианта отличаются; совпадение с GLOBAL включает уже описанный page2D block.
  CN48 v4 тем самым совпадает с ранее независимо сверенным selected DT timing@0
  по init-пакетам, **не** по всей firmware или её live execution.
- `DisplayDxe.efi` и `BacklightDxe.efi` имеют ту же длину, code/data и остальные
  bytes, что GLOBAL64, за исключением **11 bytes Jenkins CodeView path** у каждого.
  Reference BOE group0 пороги выбора из более раннего отчёта не изменились в
  этих модулях. Но `MotoBootModule.efi` **не равен** GLOBAL64: при одинаковой
  PE layout изменены bytes `.text` и `.data`; нельзя распространять равенство
  display-драйверов на весь bootloader.
- Узкий code-level контроль именно новой CN48 `MotoBootModule` через Ghidra12.1.4:
  `mmi,panel_ver` RVA`0x12deff` имеет xref`0xdaf28` в функции`0xd7d74`;
  `decompile --lines 1501:1618` и GLOBAL64 counterpart source53..170 **совпали
  текстом во всех118 строках panel-writer fragment**. В обоих версиях он читает
  EFI `DisplayPanelVer` (`GetVariable`+0x48, GUID
  `2b8c2f8846965f438de5f208ff80c1bd`) и передаёт результат в
  `/chosen/mmi,panel_ver`. Это не доказательство идентичности всей функции
  (18,448bytes, в целом отличается), успешного variable read или фактического
  значения на аппарате. Только Ghidra `brief`/`--lines` excerpts читались, не
  полный raw decompiler export. Кодовые доказательства — во внешнем cache
  `.../ghidra-toolkit-20261107/cn48-boot-version-20261108/`.

Проверки: повторный `analyze()` воспроизвёл JSON byte-exact; syntax/JSON parse
прошли; `7z t` обоих FV exit0; при приобретении член ZIP прочитан полностью с
CRC и ограничением расширения. CN48 является другим региональным reference,
не доказанной версией bootloader текущего XT2611-1; физические `DC`/silicon
revision/PWM Hz и `DisplayPanelVer` producer остаются unknown. Гипотеза о новом
готовом CN48 BOE high-PWM init **не подтверждена**, R3 остаётся active, A9-only
остаётся лучшим промежуточным panel baseline. `A0D1C1` не авторизован и не
запущен; на телефонах, камере и DSI эта проверка ничего не меняла.

Независимое review в offline-scope **PASS**: второй parser контейнера, ELF/FV
headers, `7z t`, повторная экстракция12 members трёх references,95 пакетов
CN48 v4 против selected DT, CodeView spans и два118-line Ghidra excerpts
подтверждены; `analyze()` воспроизвёл JSON побайтно. Reviewer сверил CRC32
извлечённого образа, но **не повторял HTTP** и не подтверждал самостоятельно
ETag/54 ranges; эти сведения остаются acquisition provenance исполнителя.
