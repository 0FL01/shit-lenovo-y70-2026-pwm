# XT2611-1 RETCN W3WWL36.65-11-18: дисплейный разбор

Дата: 2026-10-28. Статус фактов об архиве/source — **`reported`**: байты проверены
офлайн, но это не наблюдение live-панели владельца. Телефон в этой задаче не использовался.

## Пакет и извлечение

Вход: `downloads/XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip`.
Размер **14 918 250 042 байта**, 57 записей; Motorola XML service package с
**36 sparsechunks**, не OTA `payload.bin`. Корень извлечения (далее **R**):
`extracted/XT2611-1/W3WWL36.65-11-18/`.

`R/images/AVR_CN_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.info.txt`
заявляет XT2611-1, Android 16, build date `Tue Jun 2 05:19:57 CDT 2026`, fingerprint
`Lenovo/avr_cn/avr:16/W3WWL36.65-11-18/12710e-0d97a:user/release-keys`.
`R/filesystems/vendor_a/build.prop:23` содержит
`motorola/avr_cn/avr:16/WWW36V.65-11-ST9.1/12710e:user/release-keys`.
`signing-info.txt` заявляет HAB product avr, CID **11**, регион ChnIndJpnUnlk;
это метаданные пакета, не проверка подписи или совместимости с телефоном.
Flash/service XML **только прочитаны**; flashfile включает erase userdata/metadata.

`simg2img` применён ко всем chunks в **числовом порядке**, без raw-конкатенации.
`R/super.raw.img`: **27 917 287 424 байта**; `lpdump`: metadata v10.2, три metadata
slots, `virtual_ab_device`. Поэтому `AB Update Enabled: False` из info-файла нельзя
использовать вместо реальной partition layout. Через `lpunpack` и `fsck.erofs`
без root/mount извлечены vendor_a, vendor_dlkm_a, odm_a, system_ext_a в
`R/filesystems/<partition>/`. Product/system не распаковывались.
Размеры, lineage, архивный listing и инструменты: [firmware_manifest.json](firmware_manifest.json).
ZIP CRC проверен для 46 извлечённых members, не всего архива; подписи не верифицировались.

## Boot и модуль

- Boot header v4, kernel **41 232 896 байт**, ramdisk 0, несжатый ARM64 Image/PE.
  В payload: **`6.12.58-android16-6-g18b507169406-ab14630870-4k`**,
  `Mon Dec 22 22:41:20 UTC 2025`, Clang 19.0.1/r536225,
  LLVM `b3a530ec6537146650e42be89f1089e9a3588460`.
  Это CN kernel из source issue, **не** установленный GLOBAL `gb0a9599c6c01-ab14987696`.
- Vendor boot v4, page 4096, DTB 531 055 байт; один platform ramdisk fragment,
  8 918 200 байт legacy LZ4 → 32 095 744 байта CPIO.
- `R/vendor_boot_ramdisk/lib/modules/msm_drm.ko` и
  `R/filesystems/vendor_dlkm_a/lib/modules/msm_drm.ko` **побайтово идентичны**,
  размер **6 075 488 байт**, ELF build ID `13232a6fe74b761626ed9c14ee2f59b68ca46504`.
  В ramdisk modules.load нет msm_drm; в modules.load.recovery он присутствует.
- Vermagic: `6.12.58-android16-6-maybe-dirty-4k SMP preempt mod_unload modversions aarch64`.
  Наличие modversions и той же базовой версии не доказывает ABI/KMI-совместимость.

В stock ELF есть `panelDC_show`, `dsi_panel_send_param_cmd`, `dsi_display_set_param`,
`dsi_panel_set_param`, `sde_kms_set_panel_feature`, `msm_ioctl_set_panel_feature`.
Дизассемблирование panelDC_show подтверждает чтение поля структуры + scnprintf,
не panel-register read. Источник загруженного GLOBAL модуля не установлен.

## DTBO и DC commands

dtbo.img: 75 497 472 байта с padding; table total size 615 009; одна entry,
DTB offset **64**, size **614 945**, id/rev/custom нулевые. Root model avr,
compatible qcom,alor-qrd / qcom,alor / qcom,qrd;
msm-id `<685 0x10000>`, board-id `<0x46 0x9000>` — это CN overlay, не IDs телефона.

Одновременно присутствуют BOE ILI97680A 1264×2780 v1–v4 и ILI97701A 1440×3168 v0–v4.
Для ILI97701A:

| Вариант | DC ON / OFF байт | Пакетов в каждом | Различающихся пар | ON / OFF offset в dtbo.img |
|---|---:|---:|---:|---:|
| v0 | 426 / 426 | 41 | 11 | 508824 / 509288 |
| v1 | 426 / 426 | 41 | 11 | 512928 / 513392 |
| v2 | 578 / 578 | 48 | 11 | 516640 / 517256 |
| v3 | 578 / 578 | 48 | 11 | 535796 / 536412 |
| v4 | 875 / 875 | 75 | 34 | 559792 / 560704 |

Каждый вариант имеет имя mipi_mot_cmd_boe_1440p_dsc_682, supplier boe,
DC transfer state dsi_hs_mode. Полные node paths, stock hex, offsets и packet differences:
[cn_panel_commands.json](cn_panel_commands.json). **Это данные для анализа, не DSI-рецепт.**
В v4 меняются несколько страниц, включая 0x23/0x24/0x53 и 0x5a–0x5c;
DC не сводится к одному доказанному регистру-множителю частоты.

**Все десять DC ON/OFF массивов v0–v4 побайтово равны** файлам
`display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_vN.dtsi`
Motorola kernel-display-devicetree, tag MMI-W3WWL36.65-11-18, commit
**`f088523dfba85c95c15f43726fcf972c0c7a957a`**.
Для v4: [OFF L74–152, ON L153–230](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi#L74-L230).
Это ограниченный source-to-CN-data match, не воспроизведение всего DTBO/модуля
и не source-to-installed-GLOBAL proof.

Default-panel `<0x1ce>` в `/fragment@199/__overlay__/qcom,dsi-display-primary`
разрешается в `/fragment@207/__overlay__/qcom,mdss_dsi_mot_dummy_qhd_video`.
Default reference **не выбирает live BOE revision**. Panel selection args/IDs телефона
недоступны shell; совпадение calibration name не выбирает v4.

У v4 brightness max 16180, backlight type **bl_ctrl_dcs**, timing@0–5:
120/144/90/60/30/24 Гц; timing@6–7 имеют special idle-10/1 groups с nominal framerate 120.
Это refresh, **не PWM Hz**. Generic PMIC PWM period автоматически не применим к bl_ctrl_dcs.

## Native HAL и диагностические false leads

`R/filesystems/vendor_a/lib64/hw/displaypanel.default.so`: 52 080 байт,
ELF build ID `37539c0f74fbff02b72d6eacd0397747`:

- setDcMode VA **0x4760**: в 0x47c8 задаёт param index **3**, в 0x47d0 вызывает setParam;
- setParam VA **0x428c** проверяет support flag; 0x4314–0x4328 формирует пару
  `{param_idx, value}` и вызывает ioctl **0xc008649f** для `/dev/dri/card0`;
- отдельный setPanelFeature VA 0x43f0 использует тот же ioctl.

Binding проверен по GOT/relocations: PLT stub 0x5370 → GOT 0x84c0 → ioctl,
stub 0x5220 → GOT 0x8450 → setParam. Автоматические @plt-подписи objdump здесь
смещены; без relocation check они вводят в заблуждение.
Kernel route и pinned code lines: [driver_callgraph.md](driver_callgraph.md).
UI → этот конкретный метод и равенство GLOBAL implementation остаются unknown.

`vendor/etc/sensors/als_comp_config.xml:21–24` использует panelDC как dcNodePath;
`:43–44` содержит pwmToDcDbv=3601; `:91–102` — разные ALS models для DC off/on.
**3601 — значение sensor-compensation config, не частота и не доказанный setter дисплея.**

Воспроизведение DC-разбора (без ADB/DSI/write):

```sh
python3 06-tools/inspect_cn_dtbo.py downloads/XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip
```

Парсер читает ZIP/FDT/семибайтные заголовки пакетов, проверяет границы и печатает JSON.
Смысл BOE-регистров в оптических герцах, exact live revision и безопасный PWM override — **unknown**.
