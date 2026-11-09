# Minimal runtime input closure: timed stock only

Read-only source audit 2026-11-09. Это deployment design, не transfer/run authorization.

## Что действительно читает timed stock

У фактической цепочки TimedStockTrial.execute -> setup/prepare_writer/write_stage
нет чтения host stock command table или firmware artifact перед DSI.
Пакеты sham15/return15 построены из source constant p85_single_bit_plan.proposal:
page23,85=15,page0; p85_guarded_trial.write_script:96 и validate_write_wire:203.
p85_batched_envelope.child_envelope:87+ допускает только p85/c1/sham15/return15.
Timed guard добавляет fixed factory-only label, exact stock DBV/mode/boot/owner
и отсутствие чужого transfer. Existing source hashes и exact packet/trace checks
связывают command bytes, не внешний файл. Не копировать всю artifacts tree.

validate_init(init) в p85_single_bit_plan существует как offline provenance check,
но timed live call graph его НЕ вызывает. Нельзя утверждать, что runner заново
читает/хэширует original device-tree init или привязывает его к current vendor
hardware сверх существующих identity/module/panel guards.

Imported run_dsi_mode_trial нужен только для pure new_camera_video(before,after)
на строках104+. Его main (не вызываемый timed runner) использует:
- 06-tools/inspect_cn_dtbo.py через runpy.run_path:213;
- artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command
  и qcom,mdss-dsi-dc-on-command около228–230;
- authorization.json, run.json и другие candidate artifacts.
Это НЕ runtime input timed-stock route. Не включать main/other experiments в launch;
если будущая wiring вызовет эти helpers, closure уже другая и admission прекращается.

a9_reproduction импортируется для pure lock_commands; его fresh_programs/main
читают command tables/authorization вне exercised path. Не запускать их.
run_p85_guarded_trial.qualification/review-file reads принадлежат candidate14,
отключены в timed stock. Не переносить candidate review JSON как скрытый admission.

## Необходимые private/host inputs

1. Clean Git tree/object database HEAD с exact expanded executed source set.
   Простого копирования13 .py без Git provenance недостаточно.
   Bootstrap launcher identity проверяется отдельно до исполнения; не self-trust
   по самостоятельно сгенерированному manifest.
2. Independently approved PRIVATE pin manifest: existing process/executable digest,
   namespace/listener/process identity, exact two serials, explicit ProcLimits.
   Current Linux dependency сверяет actual bytes/metadata against pins.
   Expected pins нельзя создавать из того же acquisition как proof.
3. PRIVATE exact fresh parent/capture path, expected host UID и parent device/inode;
   explicit CapacityPolicy(max_video_bytes,reserve_bytes), no magic default.
   observed_size из camera stat до pull; factory/API delta связывает этот размер.
4. Interpreter/stdlib/Git на host, required signals/thread/main-thread behavior,
   monotonic clock, local filesystem/syscall assumptions. Existing Linux/kernel/
   server trust остается предпосылкой, fixture не доказывает hard OS deadlines.
5. ffprobe на host при legacy path ИЛИ reviewed deferred-video path + authorized
   ordinary private transfer на nc-lab с доступным ffprobe. Не пропускать validation.
6. Fresh output/private directory, fresh experiment-id; owner token создаётся
   existing caller. Не переносить или усыновлять spent capture/owner directory.

## Existing on-device inputs: НЕ файлы для host-copy

Sweep.identity:243–250 проверяет SKU/build/slot/kernel/Enforcing/device, UID0,
panelName и SHA256 /vendor/lib/modules/msm_drm.ko против embedded MODULE_SHA
1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804.
capture_ddic_c1.reader_script также сверяет module SHA перед child operations.
Не требуется копировать msm_drm.ko на host для этой проверки.

Caller читает current native brightness/mode, panelDC, boot_id, ESD, retained logs,
camera package/profile/metadata/UI и capture inventory; это fresh runtime facts,
не сохранённые deployment inputs. /sdcard/DCIM/OpenCamera unique mp4 избирается
actual before/after set, camera stat -> expected_size/cap -> size-check.
Existing parser и settings/ownership guards остаются обязательны.

## Fail before physical trial

Future preflight должен до devices/actions отвергать missing/untracked source,
неполный private config, отсутствующую source/data closure, wrong module origin,
неподдержанный environment/capacity и недоступный выбранный validation route.
Для fresh directory identity нельзя обещать проверку inode до её создания;
разделить admitted host-only setup и проверку до phone I/O.
On-device identity/read checks выполняются существующим caller до mutation;
это не повод выносить DSI или cleanup вне lifecycle.
Нет утверждения, что все эти host preflight checks уже реализованы.

Для ordinary host receipt после lifecycle достаточно минимального in-caller факта:
closed/no uncertainty, byte count/hash, capture/report/source association.
Это не protected phone producer, sealing, root fallback или новая security boundary.
Отдельный finalizer module не обязателен; если появится, включить в executed set.
