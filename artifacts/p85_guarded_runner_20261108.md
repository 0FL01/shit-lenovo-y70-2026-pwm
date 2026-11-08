# Изолированный P85 runner: offline-проверка, live ещё не выполнен

## Состояние

Новые файлы: `06-tools/p85_guarded_trial.py`, `run_p85_guarded_trial.py`,
`test_p85_guarded_trial.py`, `test_run_p85_guarded_trial.py`, `test_p85_integration.py`. Существующие shared
runner/readers не изменены. В этой работе не выполнялись device/ADB операции,
commit/push. Независимый reviewer завершил проверку: stock-only код READY после исправлений.
Это разрешает координатору перейти к физической квалификации, но не доказывает
её успешность. Candidate остаётся неквалифицированным до stock video review
и измерения latency.

CLI по умолчанию только строит/проверяет scripts и выводит offline manifest.
Физическое выполнение требует явного `--execute`. Импорт не запускает transport.
`--stock-only` содержит baseline → sham85=15 → explicit85=15 return.
`--candidate` добавляет только ОДИН85=14 между sham и return; требует сохранённую
успешную stock-only квалификацию с оптическим review и новый review текущего ROI.
Никаких85=11, C1 writes, DC75/init replay, unlock/latch/sleep/reset-trigger,
boot/flash/AVB/persistent module/security изменений.

## Что проверяется

- Root owner-token mutex, неизменная serial binding обоих устройств,
  SKU/build/kernel/module SHA/panel/Enforcing, свежие output/private каталоги.
- Обычный90→120 anchor; только actual120/group3,1440×3168,clock1234000000,
  DC0/DBV3600. Quiet checks не являются атомарным compositor lock.
- Общий independent600s watchdog до mutable target setup. Для candidate отдельный
  fixed60s watchdog, arm ровно один раз после проверки identity/quiet/ROI/readback;
  продления нет. Host45s budget с резервом8s ограничивает каждую команду.
- Exactly3 standalone callbacks: page23,85=value,page0. После каждой проверяются
  native controller/TX returns, pending0,flags0,length11/9/11, PID и порядок,
  неизменный prefix trace, точные kprobe hits/misses и wire bytes. Shell return0
  сам по себе недостаточен. Host ещё проверяет итоговый trace/profile и весь
  помеченный wire/native interval после cleanup.
- P85-only explicit long3 adapter использует failure-safe lifecycle stock C1,
  а не старый standalone85 cleanup. MRPS3/scratch16/count9/header1c030016,
  raw9/13, точный return3, single receive, exact counts; старый short1 parser
  неизменён. CRC payload не наблюдается. Long0 всё ещё может panic до validator.
- На каждом этапе одинаковый порядок P85 затем C1, после них optical hold.
  Стоковые ожидания15 00 00 и00 00 60; candidate ожидает14 00 00 без предположения
  о физическом эффекте. Никаких повторов при несовпадении.
- Одна непрерывная OpenCamera1.56.2 запись Nothing A001/Galaga rear1280×720,
 100000ns/ISO6400/focus2.0387485/crop4080×3072/zoom1,AE/AF/OIS/EIS OFF,
  recording skew15047630ns. Настройки камеры не меняются.
- Hold4.5s, ≥120 advancing sensor frames между active request/result snapshots.
  Это НЕ доказательство120 стабильных encoded кадров. Lead должен выбрать
  центральные≥60 encoded кадров с временными margins и одним ROI. PTS нельзя
  автоматически считать sensor timestamps. `stable_encoded_frames` остаётся null.
- После exact15 write, qualified15 readback и stock C1=60 candidate-watchdog разрешено снять;
  post-return hold, камера, original settings/logger/ESD и optical review всё
  равно обязательны. Readback не гарантирует физическое восстановление DDIC.

## Практический запуск координатором после review

Сначала заново определить transport IDs по private ADB инструкции. Не копировать
исторические5/1 как identity. Пример намеренно без IDs и без live-флага:

    python3 06-tools/run_p85_guarded_trial.py TARGET CAMERA --stock-only \
      --experiment-id p85_stock_UNIQUE --output artifacts/p85_stock_UNIQUE

Experiment ID должен быть lowercase `[a-z][a-z0-9_]{7,63}`; `UNIQUE` в примере
заменить lowercase suffix. Только координатор добавляет `--execute` после review.
Нельзя использовать уже существующий output/private path или очищать dmesg для
прохождения markers. Нельзя запускать параллельно другой physical runner.

Stock-only сохраняет публичный `run.json`. `capture.mp4` и
`baseline-camera-review.png` находятся только в private run cache вместе с
raw transport/boot/serial-bearing output;
не публиковать private файлы. Скриншот нужен для ROI/геометрии, не измеряет PWM.
Итог runner только `awaiting_optical_review`, не «панель восстановлена».

После полного video review создать отдельный JSON:

    {
      "schema": "p85-stock-review-v1",
      "run_report": "absolute path to that run.json",
      "run_sha256": "SHA256 of the unchanged run.json",
      "stock_optics_restored": true,
      "sham_optics_unchanged": true,
      "central_stable_encoded_frames": 60,
      "timestamp_margins_reviewed": true,
      "lead_approved": true
    }

Здесь SHA связывает конкретную разрешённую квалификацию, не рутинное хеширование
отчётов. Candidate CLI требует `--candidate --qualification REVIEW.json
--baseline-review FRESH_PATH.json`. Этот свежий review path не должен существовать
до старта. После baseline/sham runner сохраняет pending status и ждёт максимум90s.
Lead проверяет новый private `baseline-camera-review.png` и пишет JSON с schema
`p85-baseline-review-v1`, текущими `experiment_id`, `camera_session` и `frame_count`
из baseline.camera_end, `review_image_sha256` из report, `roi_acceptable:true`,
`lead_approved:true`. Нельзя заранее заполнить или повторно использовать review.

## Timing и границы

Записываются фактические durations P85/C1/hold-and-metadata и write phases.
Первый conservative gate: `2×max(stage duration)+10 <45s` на сохранённом stock-only
и текущих baseline/sham. Он может отказать при медленном ADB. В этом случае не
увеличивать60s watchdog автоматически. По эмпирическим phases можно отдельно
review-нуть более точный upper budget: candidate write → P85/C1 → hold →15 write
→qualified15 read + stock C1. Post-return hold не обязан входить в candidate exposure.
Сейчас завышенный conservative preflight оставлен намеренно до первых измерений.

Unknown transport/queue, lost evidence, timeout, failed callback или несовпавший
readback прекращают серию. Никакого page0/15/stock append в uncertainty. Только
однократный same-bound-target ordinary reboot или независимый watchdog; изменённый
boot и identity проверяются. При failed recovery lock/watchdog сохраняются.
HUP/TERM/INT проходят exception/recovery path. Hard kill/host loss оставляет
watchdog на устройстве; камера может продолжить запись до coordinator cleanup.
Автоматического live анализа gross optical abnormality нет: lead может прервать
процесс при видимой аномалии. Snapshots не обнаруживают все дефекты изображения.
Повреждение может произойти до watchdog. Обычный reboot не гарантирует DDIC repair.

85 не установлен как PWM divider, writable/volatile register или runtime-latched
control.15→14 и15→11 оба one-bit; численная близость14 не делает его безопасным.
Ни readback, ни C1, ни полосы rolling shutter не превращаются в Hz. Цель≥2000Hz
остаётся недоказанной. При отсутствии эффекта не применять другие values/triggers.

## Offline verification

90 focused tests PASS, включая существующие P85 plan/C1/85/stock sweep/metadata/
transaction tests; 23 новых tests PASS также с `python3 -O`. Generated-shell
fixtures действительно выполняют shell в fake temporary files и проверяют
native failure при успешном printf, shell errors, wrong wire, foreign wire,
pending/flags, misses, prefix corruption, HUP/TERM: никаких последующих DSI или
ESD re-enable. Mock orchestration покрывает ошибки candidate/return, recovery
failure, camera stop failure, stale qualification, deadline и no-device CLI.
Это focused regression, не весь repo и не physical qualification.

Whole-stage uncertainty сохраняется до expected P85/C1 + native/DBV + hold validation;
ошибка даже после успешного child transfer допускает только reboot recovery до
settings restoration. Concrete setup regression проверяет828→native90→120→3600
с ровно одним guarded brightness dispatch. Concrete observation fault tests для
baseline/sham/return проверяют wrong P85/C1, lost/extra native events, metadata,
frame progress и final state: ровно recovery перед settings, без следующей записи.
Видео после private pull дополнительно проверяется ffprobe: H2641280×720,~30fps,
ровно один stream, audio отсутствует. Это encoded FPS, не PWM. Exact owned camera
XML удаляется после verified stop; при uncertain stop cleanup остаётся pending.

Для exact profile accounting P85 adapters сначала сохраняют trace/profile,
отключают и удаляют только свои probes, затем возвращают native ESD. Test с
ESD-time profile increment подтверждает отсутствие гонки; shared helpers не
изменены. Каждый camera snapshot содержит host_call_start_utc/end_utc/elapsed_seconds;
recording_preflight и stage hold_start_utc/hold_end_utc поддерживают консервативную
оценку временного окна отдельным optical analyzer, не синхронизацию PTS/sensor.

## Stock-only01: gate0 E2BIG и отдельное offline исправление

Координатор выполнил `p85_stock_a001_20261108_01`. Baseline квалифицирован:
P85=15 00 00, C1=00 00 60, duration34.389s (P857.404s, C16.977s,
hold+metadata10.459s). Первая sham запись остановилась ДО первого writer packet:
Android `/system/bin/printf: Argument list too long`, empty trace, все5 probe
counts0, RECOVERY_REQUIRED43. Причина: полный retained dmesg передавался одним
argv внешнему printf. Координатор отдельно подтвердил reboot/settings/native828/
logger/camera/watchdog/mutex recovery. Failed01 и его run.json не изменялись.
Никакого14, автоматического retry или нового live запуска в этой правке не было.

Исправление только в P85 файлах:
- Writer сохраняет полный dmesg, trace и profiles в шесть фиксированных файлов
  собственного fresh root workdir и читает их напрямую через awk/cmp. Префикс
  trace, exact PID/return/pending/flags/wire и unique markers сохранены.
- Размеры fail-closed: trace≤256KiB, profiles≤1MiB, retained dmesg≤16MiB.
  Логи не обрезаются и не очищаются; ошибка чтения или превышение прекращает
  операцию до следующего DSI. Нет pipeline, маскирующего ошибку dmesg.
- Normal trap удаляет ровно известные gate-* файлы. После verified recovery
  coordinator удаляет/проверяет те же точные writer remnants перед inherited rmdir;
  никакого wildcard или удаления неизвестных файлов.
- Изолированные P85/C1 reader wrappers отвергают snapshot/events/profiles длиннее
  16Ki shell characters до external printf (не более64KiB для UTF-8), сохраняя
  исходный uncertainty cleanup. Общие stock/C1 helpers не изменены.
- Regression принудительно использует настоящий `/usr/bin/printf`: прежний
  variable→argv путь воспроизводит E2BIG на2MiB retained native log до первого
  packet, исправленные sham/candidate/return scripts проходят с тем же логом.
  Проверены read failure,17MiB rejection, oversized reader profile, normal/failure
  cleanup и реальные reboot-remnant удаления только разрешённых файлов.

Текущий candidate budget не менялся. Даже чистая stock-only02 ещё не сделает
candidate готовым: измеренная baseline latency сейчас не проходит conservative
`2×stage+10 <45s` gate. Нужны отдельные timing/optical review и решение координатора.

### Source provenance до следующего физического опыта

Runner записывает `source_commit`, `source_blob_ids` и
`source_worktree_clean_for_runner` для фиксированных10 исполняемых файлов.
Сравниваются committed Git blobs с фактическим содержимым и diff относительно
записанного commit. Live CLI отказывает ДО создания output/private каталогов и
device I/O, если relevant runner/helpers untracked/изменены. Координатор должен
сначала commit reviewed sources; эта работа ничего не commit/push.
Нерелевантные untracked артефакты не влияют. Docs-only commit может изменить HEAD,
но не blob map; candidate qualification сравнивает именно map исполняемых файлов.
Offline CLI остаётся без device I/O и создания output каталогов.
