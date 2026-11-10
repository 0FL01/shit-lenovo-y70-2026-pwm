# Отдельное stock observation: offline preparation

Проверен HEAD964cf0e68ebb878145ff665d70b9a2cd5eb1f758. Никаких устройств,
ADB/research-usb, capture/deployment, DSI, commits/push или WORKSTATE edits.
`05-safety/optical_measurement.md` отсутствует. Capability camera-local stop
исследуется отдельно; готового проверенного ≤15s capture route пока нет.

## Точный reusable route

Отдельный caller: reviewed `OfflineBaselineADB` + `LinuxAssociation` +
`host_source_integration_20261109/fresh_private_directory.py` +
`host_private_sink_20261109/private_video_sink.py`. Сохранить immutable role
binding, fixed existing server/process association, absolute deadlines,
camera-only pull, byte caps, fresh0600 created-inode custody и last_facts
uncertainty. Не заменять это bare adb или legacy transport для удобства.
`a9_reproduction.lock_commands(token)` даёт общий mutex acquire/verify/release;
не вводить альтернативный lock и не забирать stale lock.

Pure `camera_capture_metadata.validate_capture` проверяет request/result,
profile/session/progress, но не все encoded frames. `run_aa_timed_stock_trial`
settings_scene parser полезен без target_scene/redraw wrappers. Новый отдельный
`06-tools/stock_observation_readonly_20261110/` прошёл независимый offline review
и 18 тестов в normal/-O. Он использует публичные transport/parser dependencies,
фиксированные команды чтения и санитизированный вывод. Это ещё не фактическая
проверка устройств, actual native120 или duration/restart preferences.

**Не запускать** Trial.setup/restore/execute, Sweep.anchor/restore или full AA
main. Они включают logger, timeout, HOME/Settings,90→120Hz/native DBV, ESD/mount,
watchdogs либо table/selector transactions. Legacy capture_ui_dc_reference.py
имеет старый path/focus и bare adb/assert guards. Узкие camera UI/identity/metadata
helpers требуют адаптации: fresh owned XML на каждый dump, deadline и custody.

Trial.settle_recording может занять8s после start. stop_camera делает несколько
UI calls до stop, каждый с timeout15s. Host sleep+stop не гарантирует≤15s при
network loss. Target600s watchdog не останавливает отдельную камеру. Нужна
проверенная native camera finite-duration semantics; не выдумывать intent extra,
keyevent или broadcast, не применять force-stop/reboot. Recorded-duration rejection
не является preventive guarantee. Camera-local stop capability пока unresolved,
а не окончательно отвергнута.

## Отдельный explicit setup и rollback

До mutations сохранить свежие target и camera boot IDs, target пять system keys:
screen_brightness, screen_brightness_mode, min_refresh_rate, peak_refresh_rate,
screen_off_timeout; native DBV, logger, power/DC, Enforcing, actual mode evidence,
focused activity/scene. Исторические6438/98/0/120.0/1800000/logger0 не restore defaults.

Минимальный setup при подтверждённых manual mode0, native120, DC0/power0/logger0,
unlocked Settings и верных camera controls: один normal driver write3600 в
`/sys/class/backlight/panel0-backlight/brightness`, только если DBV отличается.
Проверить stable state ДО start. Это ordinary native brightness mutation со
штатными driver-generated panel commands, НЕ «никаких writes» и не custom/raw DSI.
Logger не включать, selector/table/ESD/isolation/trace не применять. Если native120
не доказан текущим read-only evidence, не подменять проверку автоматическим90Hz anchor.

При несовпадающей scene отдельный будущий explicit UI setup может открыть
`com.android.settings/.Settings$DisplaySettingsActivity`, но только после
определения исходного activity/scroll/focus и реального rollback. Одного имени
activity недостаточно для exact UI restore. Не менять DC, mode/rates/timeout или
camera controls автоматически. Для каждого нового mismatch нужен конкретный
setup delta; при неопределённом rollback fail closed, не молчаливый navigation.

Camera controls проверить, не менять:100000ns, ISO6400, focus2.0387485, zoom1,
crop[0,0,4080,3072], AE/AF/EIS/OIS OFF; recording1280×720 nominal30fps,
skew15047630ns. PREVIEW previous не переносится в recording session.

После verified stop и того же boot восстановить только изменённые keys из fresh
originals (null→delete; refresh_restore_order), native original DBV последним,
проверить сразу и после1s. Сверить все пять keys/DBV/logger/DC/power/Enforcing/UI.
Не писать неизменённые значения ради фиктивного restore. Uncertain write сначала
проверить; не повторять автоматически. Release только собственного mutex после
проверенного cleanup. Сохранять uncertainty, если связь не позволяет проверить.

## Предопределённый finite protocol

Source freeze + private directory → roles/server/identity → общий mutex → fresh
originals/setup → fresh visual geometry review → verified camera-local finite stop
и PREVIEW → latch start attempt ДО tap → unchanged recording → verified stop,
private transfer/custody → originals restore → release. Already recording: abort.
Uncertain start: не tap снова. Stop только по fresh Stop control, already PREVIEW
не toggle. Pre-existing media не удалять. Один новый MP4 по before/after inventory,
source size/hash до/после transfer, created inode и explicit cap. Никаких claims
о cancellation только из socket timeout.

15s budget включает startup, не начинается после8s settle. Окна [30,90),
[120,180),[210,270),[300,360) привязаны к первому сохранённому кадру. Если early
controls неизвестны, late settle не оправдывает post-hoc shift; inconclusive.
Нет полного окна/PTS gap/recording>15s: inconclusive, не обрезать до «pass».

Отдельный evidence type stock-observation-v1 с обязательным private before.boot_id,
source closure, state/role identity, timing, controls, cleanup и private custody.
Не fake sham/return receipts и не AA acquisition acceptance. Public allowlist без
serial/boot IDs/session tokens/raw media. Exact ROIs после fresh visual review:
left[225,245,20,330], main[255,245,20,330], right[285,245,20,330]. q=.019775390625,
FFT8192/Hann/degree2 и all-ROI5% unchanged. Все secondary summaries и10% recurrence
marker из aa_fine_temporal_03f0ed4_20261110/NEXT_STEP.md сохранены; не candidate gate.
Нет физических Hz, допуска AA10/14 или исправления старого rejected source03.

## Минимальный code delta

`06-tools/stock_observation_20261110/protocol.py` — только inert state/budget model
и reject-only timeline validator, без transport/commands/coordinator/live entrypoint.
Bool local_stop_verified в модели — условие теста, НЕ hardware verification receipt.
`test_protocol.py` — fault skeleton: missing local stop, startup counted in budget,
uncertain start/no retry, already PREVIEW/no toggle, uncertain stop/no retry,
backwards/nonfinite clock, fixed windows/duration/PTS/early-controls failures.
Это не тест реальных identity, rollback, mutex, UI, device stop или custody;
они обязательны для будущей отдельной implementation review.
