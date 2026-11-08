# Current kernel / KernelSU-Next: source inventory

## Addendum2026-11-07 — runtime module identity beyond Build ID

[CN48 binary comparison](cn_48_7_recon_20261107/result.md): CRC-verified
W3WWL36.65-48-7 vendor_boot module SHA`d3519a51bf9a74e02448c455349f8e69fccca1aa316a7be4951ada76c6b8b52d`
is byte-equal to savedGLOBALreferenceW3WW36.65-64-4 module. CurrentOTA
SHA`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804` differs only in
BuildID and local`__UNIQUE_ID_*` names in symtab/strtab: allothersectioncontents,
attributes and103589resolvedentries across21RELAsections match. This confirms
the checked compiledcode/data path is notnewregionalPWMlogic. **It does not
establish a whole source rebuild match**, bootcompatibility or physicalPWMHz.
Currenttargethashguards/recovery images remain unchanged; no module installed.

Текущий checkpoint: **2026-11-06 12:19 UTC, R2 verified**. Постоянный built-in
KernelSU-Next33355/v3.4.2 установлен только в boot_b, UID0 повторно проверен после
обычного reboot, Enforcing и loaded msm_drm сохранены:
[install.json](kernel/gki_r59/kernelsu_next/persistent/install.json).
Оригинал текущего96MiB boot_b получен до записи:
[provenance](originals/W3WWS36.65-64-4-1/boot_b_acquisition.json),
[точный откат](flash_proposal.md). Его kernel body **побайтно равен Google r59**;
это больше не только source/version candidate. Known-good root-only boot служит
baseline для будущего PWM kernel rollback, не заменяет originals других разделов.

Текущий `msm_drm.ko` сохранён в `kernel/gki_r59/target_vendor/`; фактическая загрузка
проверена, но полный source-to-module match остаётся `unknown`. Live BOE v4 DT получен;
следующий R3 checkpoint — [DC/EM transition analysis](dc_transition_recon_2026-11-06.md),
где stock transport A/B уже verified13:49: full DC sets/native returns/actual DBV
сняты, cleanup выполнен; далее camera/owner evidence, не firmware catalogue/IMEI.
Ниже — датированная история подготовки; прежние pending
утверждения описывают соответствующий момент, не отменяют текущий результат.

## Совпадение идентификаторов — найдено

- `confirmed-on-target`, ранее сохранённый `uname` и повторный ADB 06:53 UTC:
  `6.12.58-android16-6-g09eda8c8505a-ab15950084-4k`, Clang 19.0.1/r536225
  ([device_inventory.json](device_inventory.json), build; [RECON](unlock_pwm_recon_2026-11-06.md)).
- `reported`, проверенные первичные Google sources: в
  [GKI release catalogue](https://source.android.com/docs/core/architecture/kernel/gki-android16-6_12-release-builds.json)
  branch `android16-6.12-2025-12`/kernel `6.12.58` содержит запись:

```json
{
  "tag": "android16-6.12-2025-12_r59",
  "date": "2026-07-28",
  "sha1": "09eda8c8505ac19be9c4e063afa1d351c1ca9fe2",
  "kernel_bid": "15950084"
}
```

- `reported`, независимая проверка Gitiles tag:
  [kernel/common r59](https://android.googlesource.com/kernel/common/+/refs/tags/android16-6.12-2025-12_r59?format=JSON)
  разрешён в тот же полный commit `09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`.
  SHA-prefix **и** build ID совпадают с target-наблюдением, не только версия 6.12.
- Baseline воспроизведён: config byte-equal, 10 210 symbol/CRC совпали с reference.
  Последующий RAM trial дал оригинальный boot: его kernel равен Google binary.
  Упаковка и persistent boot проверены на цели после отдельного owner approval.
  Это подтверждает observed loaded vendor set, не все возможные модули/приложения.

## Реальные source/build paths

`reported`, pinned Google r59, не Motorola build manifest:

- [`BUILD.bazel:250–260`](https://android.googlesource.com/kernel/common/+/refs/tags/android16-6.12-2025-12_r59/BUILD.bazel#250):
  `common_kernel(name="kernel_aarch64")`, `abi_definition_stg="gki/aarch64/abi.stg"`,
  AutoFDO profile `gki/aarch64/afdo/kernel.afdo`,
  `defconfig="arch/arm64/configs/gki_defconfig"`.
- [`gki_defconfig`](https://android.googlesource.com/kernel/common/+/refs/tags/android16-6.12-2025-12_r59/arch/arm64/configs/gki_defconfig):
  `CONFIG_LOCALVERSION="-4k"`, `CONFIG_MODVERSIONS=y`, `CONFIG_MODULE_SIG=y`.
  Равенство полученного baseline config фактическому target теперь доказано ниже.
- [CI build 15950084](https://ci.android.com/builds/submitted/15950084/kernel_aarch64/latest)
  — ссылка на исходный build, не скачанный и проверенный recovery-образ телефона.
- На начальном source audit одноимённый r59 tag в `kernel/manifest` не разрешился;
  это не исключило manifest в CI artifacts. **Точный CI manifest теперь получен**
  (см. следующий checkpoint), подвижная ветка не используется как его замена.

## Фактический target config — получен 07:46 UTC

- `confirmed-on-target`: обычный shell смог прочитать `adb exec-out cat /proc/config.gz`;
  exit 0, gzip signature и распаковка успешны. Сохранены все **8085 строк**:
  [target_config_20261106.config](kernel/target_config_20261106.config).
- Проверены `CONFIG_KPROBES=y`, `CONFIG_EXT4_FS=y`, `CONFIG_MODVERSIONS=y`,
  `CONFIG_MODULE_SIG=y`, `CONFIG_CFI_CLANG=y`,
  `CONFIG_CFI_ICALL_NORMALIZE_INTEGERS=y`, `CONFIG_LOCALVERSION="-4k"`.
  Базовые Kconfig dependencies KSU присутствуют, но это ещё не сборка/boot test.
- Машиночитаемое подтверждение boot/config:
  [post_unlock_observation_2026-11-06.json](post_unlock_observation_2026-11-06.json).
  Актуальный GLOBAL mirror index по-прежнему содержит только два pre-OTA архива;
  текущий `W3WWS36.65-64-4-1` там не найден при проверке 2026-11-06.

## 07:55–08:03 UTC — readback, официальный GKI и pinned build manifest

- `confirmed-on-target`: Motorola bootloader не поддерживает стандартный host fetch:
  `max-fetch-size` отсутствует, один `fetch boot_b` завершился exit 1 с сообщением
  `Device does not support fetch command`. 0 bytes; пустой файл удалён. Boot/vendor_boot
  по 96 MiB, recovery 128 MiB в текущем слоте. Устройство штатно возвращено в Android;
  [boot_readback_2026-11-06.json](boot_readback_2026-11-06.json). Это не вывод о всех
  возможных OEM/readback протоколах; они не перебирались.
- `reported`, Google-certified GKI r59 ZIP из официальной
  [release table](https://source.android.com/docs/core/architecture/kernel/gki-android16-6_12-release-builds):
  [URL](https://dl.google.com/android/gki/gki-certified-boot-android16-6.12-2025-12_r59.zip),
  16 829 063 bytes, сохранён в `downloads/gki-certified-boot-android16-6.12-2025-12_r59.zip`.
  ZIP member CRC passed; `boot-6.12.img`, 64 MiB, header v4, ramdisk 0, kernel 41 306 624 bytes.
- Встроенный IKCONFIG распакован; **все 8085 строк побайтово равны target config**.
  Полная Google kernel release string содержит текущие SHA/build ID и Clang r536225.
  Результат, source URL и размеры: [acquisition.json](kernel/gki_r59/acquisition.json).
  Это усиливает GKI/config match, **не доказывает равенство Motorola boot partition**
  или vendor-module CRC; Google boot image не объявляется handset original/flash candidate.
- `reported`, официальный CI artifact
  [manifest_15950084.xml](https://ci.android.com/builds/submitted/15950084/kernel_aarch64/latest/manifest_15950084.xml)
  получен по опубликованному artifactUrl без аккаунта; временный signed URL не сохранён.
  Сохранён [pinned manifest](kernel/gki_r59/manifest_15950084.xml), 8185 bytes,
  **50 проектов, все revisions — полные SHA**. `common=09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`,
  `build/kernel=a71b075c1d43d226779d2e834433e7a1d1885beb`,
  Clang prebuilts `77c95e8253c2c82ffd4fee92c0ad9f5ac1e8ca04`.
- Core source checkout завершён 08:06:31 UTC: оба HEAD совпали с pins. Историческая
  запись исходных путей/команд: [source_checkout.log](kernel/gki_r59/source_checkout.log).
  Затем source trees перенесены в правильную Kleaf-структуру workspace:
  `sources/gki-15950084/common` и `sources/gki-15950084/build/kernel`.

## 08:06–08:16 UTC — baseline workspace и официальный CRC reference

- `reported`, проверенный local source:
  `sources/gki-15950084/common/build.config.constants:1–4` задаёт Android16/6.12,
  KMI generation 6, **Clang r536225**, **Rust 1.82.0.p1**. Legacy
  `build.config.gki.aarch64:1–6` прямо предупреждает, что GKI больше через него не
  собирается; baseline будет через pinned Kleaf/Bzlmod, не старый build.sh flow.
- Native Git workspace preparation запущена в фоне: manifest `ddk`/`ddk-external`
  projects плюс прямо используемые GKI local repositories и boot tools; не скачиваются
  COS/recovery/device ports, GBL/Fuchsia/tests/виртуальные device-module trees.
  Два concurrent fetch job; устаревшая/ненужная Clang r547379 исключена sparse checkout,
  r536225 и используемые Kleaf/toolchain support directories оставлены. Все revisions
  из CI manifest. До завершения job успешность зависимостей/готовность сборки неизвестна;
  результат появится в `artifacts/kernel/gki_r59/workspace_prepare.json`.
- Для будущей ABI-проверки получен официальный
  [kernel_aarch64_Module.symvers](https://ci.android.com/builds/submitted/15950084/kernel_aarch64/latest/kernel_aarch64_Module.symvers):
  633 144 bytes, 10 210 формально разобранных symbol/CRC rows.
  [Local reference](kernel/gki_r59/kernel_aarch64_Module.symvers),
  [provenance](kernel/gki_r59/module_symvers_acquisition.json).
  Это **reference**, не уже пройденная проверка baseline/root/vendor-module ABI.
- На этом checkpoint compile/KSU ещё не запускались; последующее состояние — ниже.

## 08:26–08:37 UTC — workspace verified, первый baseline build, KSU source audit

- [workspace_prepare.json](kernel/gki_r59/workspace_prepare.json): **29 selected
  project HEADs verified**, без ошибок, 08:26:32 UTC. Проверены реальные инструменты:
  Clang 19.0.1/r536225 (build14043575), Rust 1.82.0-dev (linux-15123656), Bazel 8.0.0.
  У wrapper нет рабочего `--version`; штатный `tools/bazel version` успешен.
- Создан [build_gki_baseline.sh](../06-tools/build_gki_baseline.sh), только немодифицированный
  `//common:kernel_aarch64`, release/KMI config, шесть Kbuild jobs, source-HEAD/dirty guards.
  BUILD_NUMBER=15950084 воспроизводит reference label; это local reproduction, не OEM image.
- Первый запуск остановился **до компиляции** при workspace stamping: полный CI manifest
  содержал намеренно не скачанный external/dtc. Записи сохранены:
  [baseline_build.json](kernel/gki_r59/baseline_build.json),
  [baseline_build.log](kernel/gki_r59/baseline_build.log).
- Вместо скачивания неиспользуемых проектов/отключения KMI выбран документированный
  native-Git mode `--extra_git_project=common --extra_git_project=build/kernel`
  (`kleaf/bazel.py:325–357`, `docs/scmversion.md:34–59`). Full pinned manifest остаётся
  provenance всех зависимостей. На 08:37 результат следующего запуска ещё ожидался;
  он завершился успешно в 08:40:22 (см. следующий checkpoint).

### Pinned KernelSU-Next для последующей built-in интеграции

- Получен `sources/KernelSU-Next-v3.4.2`, commit
  `4c706b5938665866ebe16944a481a7b91e3396af`:
  [source provenance](kernel/kernelsu_next_source.json). Setup/install scripts не запускались.
- `kernel/Kconfig:3–13`: CONFIG_KSU=y поддерживается при KPROBES/EXT4_FS (на target есть).
  KSU_DEBUG/KSU_DISABLE_MANAGER/KSU_DISABLE_POLICY default n; сохранять эти defaults.
  `kernel/supercall/perm.c:27–29` ограничивает su Manager/allowlist, debug allow_shell
  выключен в `kernel/core/init.c:79–84`. Не заменять это unrestricted shell root.
- Upstream `kernel/setup.sh:60–64` показывает native driver/Kconfig integration points,
  но также делает git pull/stash; скрипт не выполнялся. Минимальный root diff готовится
  только после успешного baseline, без display-команд/нового recovery.
- `kernel/Kbuild:98–135` вычисляет version из Git и при отсутствии отдельной .git
  metadata падает обратно на code1/tagv0.0.1; `manager/.../Natives.kt:24` требует >=33188.
  Для воспроизводимой hermetic integration нельзя терять metadata или разрешать
  unshallow network fetch внутри компиляции. Получена полная история **до закреплённого
  tag**, HEAD не изменён: 3355 ancestors → upstream code **33355**, tag **v3.4.2**.
  [Version provenance](kernel/kernelsu_next_version_metadata.json).
  Kbuild уже имеет fallback variables для этих значений; передача через make_goals
  впоследствии проверена реальной root-сборкой. Сам upstream KSU source не изменялся.

## 08:40–09:38 UTC — baseline pass, root-only build/validation pass

`reported`, проверено офлайн; это не `confirmed-on-target` root.

- [Baseline build](kernel/gki_r59/baseline_build_native_git.json) завершился exit0
  в 08:40:22; [validation](kernel/gki_r59/baseline_validation.json): все **8085 config
  lines byte-equal target**, все **10 210 exports/CRC совпали**, пропусков/добавлений нет.
- Image имеет тот же размер/полную Linux version string, но не byte-equal Google:
  **1116 отличающихся bytes целиком внутри built-in certificate и ELF notes**.
  [Diagnosis](kernel/gki_r59/baseline_certificate_diagnosis.json) локализует обе области;
  остальные bytes совпали. Причина существенна: target включает MODULE_SIG_PROTECT и
  TRIM_UNUSED_KSYMS, поэтому новый локальный certificate может нарушить приём GKI modules.
- Из официального Google Image извлечён **публичный**, не private, certificate:
  [PEM](kernel/gki_r59/google_module_signing_cert.pem), SHA256
  `dd1224298b6239681fb1eb2e06e65b4d6c5d7181b75044f44cf30f38dafa88e8`.
  Это Google reference trust; live Motorola certificate пока не прочитан.
- [Root patch](kernelsu_next_patch.diff): только driver Makefile/Kconfig entry и symlink
  на pinned KSU, leaf-target make variables для code33355/tagv3.4.2, один native
  CONFIG_SYSTEM_TRUSTED_KEYS path и public certificate. **Display/DTS не менялись**.
  Google trust добавлен стандартным механизмом; обычный локальный build key также остаётся.
  MODULE_SIG/PROTECT/ALL, MODVERSIONS, CFI и SELinux config не ослаблялись.
- [Root build script](../06-tools/build_gki_kernelsu_next.sh) проверяет pinned HEADs,
  clean KSU/Kleaf, exact saved patch и certificate input. `bash 06-tools/build_gki_kernelsu_next.sh`
  завершился exit0 в 09:08:30; [build record](kernel/gki_r59/kernelsu_next_build.json).
  Baseline script намеренно откажется работать на текущем patched common tree;
  его outputs сохранены в `artifacts/kernel/gki_r59/baseline/`. Нужен clean pinned tree
  для повторного baseline, а не уничтожение текущего root diff.
- [Root validation](kernel/gki_r59/kernelsu_next_validation.json): CONFIG_KSU=y,
  DEBUG/DISABLE_MANAGER/DISABLE_POLICY=n; иных config deltas, кроме trusted-key path,
  нет. Все **10 210 exports/CRC равны reference**, Google certificate реально включён
  в Image, builtin init/hook symbols и compiled **33355/v3.4.2** найдены.
- Root raw Image: `artifacts/kernel/gki_r59/kernelsu_next/Image`, **41 638 400 bytes**,
  SHA256 `a6edb2ae26b273eb7b4ac510875efc8b9ac0c7963c084072896bfb0184a6723d`.
  Release содержит `g09eda8c8505a-dirty-ab15950084-4k`: dirty — сохранённый root patch,
  не OEM binary. Actual vendor vermagic/module loading ещё не проверены. Scripts
  воспроизводят build/config/CRC, но не обещают byte-identical Image с новым local key.
- [Обычный Manager](kernel/kernelsu_next_manager.json), **не spoofed**:
  `downloads/KernelSU_Next_v3.4.2_33355-release.apk`, официальный release digest совпал;
  v2 signer certificate 998 bytes/SHA256 `79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7`
  совпал с Kbuild pin. Host apksigner отсутствует; полная APK signature verification
  не запускалась, native PackageManager verification при установке обязательна.
  APK **не установлен**, UID0/Enforcing после root reboot не проверены.

## Исторический blocker R2 до RAM bootstrap: firmware catalogue access

- Public mirror текущего Motorola build не дал, стандартный fetch не получил boot_b.
  Нельзя упаковывать raw root Image в старый XT2611-3 boot и объявлять recovery готовым.
- `reported`, [MFD auth documentation](https://github.com/JoshRob297/moto-firmware-downloader/blob/main/docs/AUTHENTICATION.md)
  описывает authenticated `search`/catalogue, официальный Lenovo browser login и
  short-lived token. [Другой LMSA client](https://github.com/enigma550/LenovoMotoFirmwareDownloader)
  также требует login. Никакой client/installer/Rescue не запускался и токен не запрашивался.
- [OTA community documentation](https://github.com/FixeQD/motorola-update) описывает
  запрос с serial/IMEI; **не выполнялся**, идентификаторы вовне не передавались.
- Следующий минимальный шаг требует owner consent/login: только read-only catalogue
  и download точного build, **без Rescue/flash и пока без unique IDs**. Даже после
  login доступность нужного post-OTA GLOBAL package не гарантирована; полученное
  CN/старое/другое SKU нельзя автоматически применять. Пароль/токен не публиковать.

### После owner consent — официальный login URL подготовлен

- Владелец согласовал catalogue/download, **без Rescue/flash и IMEI/serial**.
  Pinned MFD **v1.3.4**, commit `b5ea93abf5bc02ee56f5f7a9601320b9d80e3396`,
  исходник в approved private cache; installer/CLI wizard не запускались.
- Проверены TLS base/state и token-file path, model-only body в `mfd-cli.mjs:1661–1705`;
  browser opener — единственные child_process calls. Запрос login URL воспроизведён
  native HTTPS по `344–437,1067–1071`: HTTP200/code0000, issuer **passport-glb.lenovo.com**,
  redirect **lsa.lenovo.com**. Переданы random session UUID, не phone identifiers.
- [Catalogue checkpoint](lmsa_catalog_2026-11-06.json) не содержит URL nonce/token.
  URL/пустой token input сохранены вне репозитория в private0700 directory/files0600.
  На этом checkpoint ещё требовался owner login; следующий результат — ниже.

### Authenticated catalogue / FSG blocker

- Owner callback оказался JSON, не голым URI; code0000/content URI обработаны
  структурно, без вывода token. Native CLI validation exit0, session0600 в private HOME.
- Каталог содержит **1117 моделей**, в том числе XT2611-1/Legion Phone Y70 New Generation
  и XT2611-3/motorola edge 70 max. `readSupport=true` означает matching по программным
  свойствам, **не поддержку дампа разделов**. Model-only params: fingerPrint,
  fsgVersion.qcom, roCarrier. Generic legacy getResource для -1 вернул null code/content;
  он не принят за корректный match.
- Pinned LMFD `061a16cb0121870d09c48db9eaf95ffba9fae5d2`,
  `core/features/firmware/read-support-lookup.ts`, задаёт getNewResource body:
  modelName/marketName/category/params/matchType=1; IMEI/IMEI2/SN/channelId optional.
  Выполнен именно property-based lookup, optional unit IDs не отправлялись.
- `confirmed-on-target`, [software properties](lmsa_match_properties_2026-11-06.json),
  10:29 UTC: тот же XT2611-1/W3WWS36.65-64-4-1, fingerprint/teleu; ro.boot.fsg-id пуст,
  radio software version M8845_DE90_31.179.01.104.17R. Это не FSG label, подмены не было.
- Оба auto matches с неизвестным/empty FSG: HTTP200/**0001, Parameters lack**/null content.
  Пакет не получен; **это не доказывает отсутствие firmware**. Known missing required
  value — fsgVersion.qcom; заполнение ещё не гарантирует успешный match.
- Следующий scoped diagnostic требует согласованного mode change: reboot bootloader,
  identity/slot guards, только getvar version-baseband/fsg-id, normal stock return.
  [Motorola LMSA logs для другой Qualcomm модели](https://gist.github.com/cheater/f87273684c350c5e3719026d19bd7693)
  используют version-baseband для FSG;
  поддержка/полезное значение на XT2611-1 ещё unknown. Никаких новых OEM/image/AVB writes.

## Ограниченные Motorola queries

`reported`, независимый read-only аудит: GitHub API
`git/matching-refs/tags/MMI-W3WWS36.65-64-4-1` → `[]` в
`MotorolaMobilityLLC/{kernel-msm,kernel-display-devicetree,kernel-msm-5.4-techpack-display,kernel-devicetree}`.
Прямое разрешение `09eda8c8505a` через kernel-msm commits API не установлено (422).
Это не exhaustive отсутствие исходников под другими refs; GKI r59 найден отдельно.

`reported`, каталог Google также связывает архивный CN `g18b507169406/14630870`
с r6, GLOBAL pre-OTA `gb0a9599c6c01/14987696` — с r25/r26. Они не заменяют r59;
имеющиеся ROM остаются offline references, не текущими recovery originals.

## Текущий следующий checkpoint

R2 **verified**: отдельный RAM trial/original readback и owner-approved boot_b flash
завершены, ordinary reboot сохранил UID0/Enforcing. R3 **in_progress**: live v4
идентифицирован, DC/EM-кандидаты описаны в новом анализе выше; частота >=2000 Hz
не подтверждена. Старые FSG/catalogue blockers ниже исторические, не prerequisite.

### FSG metadata diagnostic: completed, no usable value

- [Bootloader evidence](fsg_bootloader_read_2026-11-06.json), `confirmed-on-target`,
  10:54:45–10:55:28: owner approved metadata-only roundtrip, guards avr/XT2611-1/b/
  non-userspace passed. version-baseband **Done** is not a usable firmware/FSG label;
  fsg-id remote not-found/FAILED despite host exit0. No further OEM probing or value guessing.
- Normal fastboot reboot accepted; Android boot_completed1/current build/SKU/_b verified.
  No image download-to-device/flash/erase/AVB/slot change. This does not establish fastboot boot.
- Read-only property-name filter found only dev.mnt.{blk,dev,rootdisk}.vendor.fsg storage
  metadata. Actual /vendor/fsg exists,0755, but listing Permission denied. No modem/NV file
  contents or raw FSG block reads; SELinux cause remains a hypothesis, no policy changes.
- GLOBAL -3 legacy manual getResource also HTTP200/null code/null content. Both manual
  branches yielded no selector/ROM; neither is accepted as a valid match or no-firmware proof.
- **Scoped blocker:** documented identifier-free auto match needs a verified FSG value,
  unavailable through the tested getters; exact current originals still absent.
  MFD `mfd-cli.mjs:1214–1265` and LMFD read-support-lookup.ts also document
  `/rescueDevice/getNewResourceByImei.jhtml`. Sending IMEI to this verified Lenovo host
  requires a separate owner decision/private input; no identifier submitted so far.
  It may return origin-CN rather than current GLOBAL, so success/applicability is not promised.
G0R/G1/G3 не объявлены пройденными; ни temporary boot, ни flash не разрешены этим checkpoint.
