# Prospective v2: native10s, unchanged stock

Это новый заранее заданный протокол, не подмена v1 и не reanalysis старого source03.
`protocol.py`/первоначальный PLAN описывают исторический v1 с окнами до12s.
`protocol_v2.py` и `coordinator.py` относятся ТОЛЬКО к nominal10s route:
[30,90),[90,150),[150,210),[210,270), то есть1–9s encoded timeline при30fps.
Окна смежные, не независимые. ROI/q/Hann/degree2/FFT8192/all-ROI5% НЕ меняются.
Ни новый receipt, ни short stable observation не допускают AA10/14/physicalHz.

## Что реализовано offline

Отдельный coordinator, без Trial/Sweep inheritance и без CLI. Зависимости передаются
из будущего verified source closure: OfflineBaselineADB, camera parser,
readonly probe constants, a9 lock_commands, new_camera_video и pure native_state.
Fresh originals включают before.boot_id. Target setup только native DBV3600,
если fresh DBV иной; framework keys/logger/DC/refresh не пишутся. Native mode
проверяется по latest retained kernel mode120/group3 и software120; список mode
records должен оставаться точно неизменным (truncation тоже fail).

Source1.56.2/version96 UI labels: Settings → Video settings… → Maximum duration
of video →10 seconds; Restart video after max duration → Don't restart.
Текущее checked selection сохраняется ДО mutation, затем re-open/readback.
Restart on maximum file size тоже явно отключается при current true, с fresh
original rollback. Не читаются private preferences/configs. Exact-match UI,
checked/enabled/package/bounds и fresh exclusive XML fail closed. Если строки
не видны/другой язык/другая layout, никакого guessed tap/scroll.

Native MediaRecorder cap — локальная preventive мера, НЕ абсолютная wall-time
гарантия при всех сбоях OS/encoder. Один start, включая startup в15s overall.
Никаких Stop tap: гонка native auto-stop могла бы превратить tap в новый start.
Только recording metadata и PREVIEW observation. Initial PREVIEW после dispatch
НЕ stop: требуется ранее наблюдавшаяся advancing recording pair. То же правило
для позднего bounded cleanup probe. Неустановленный start/stop оставляет mutex и
cleanup pending. Никаких retry start, force-stop, reboot, продления37s guard.

Late stop/read>15s сохраняет failure. Early controls должны быть подтверждены
двумя recording snapshots в первую секунду от start dispatch, иначе inconclusive;
окна не сдвигаются. Этот conservative bound может быть практически трудным.
Snapshot timing не является per-frame sensor/PTS калибровкой; это отдельный
remaining validity вопрос, а не заявленная гарантия первыхencodedframes.

При verified stop: restore только mutated preferences и fresh original DBV,
boot checks и exact unchanged framework keys, потом собственный mutex release.
При UI/navigation failure cleanup может остаться pending: код не делает слепые
Back loops из неизвестного dialog/page. Поздний cleanup явно отдельный failed-run
путь, не исправление первоначального time cap.

Private transfer: ровно один новый mp4 без удаления прежних; source size/hash
до/после, OfflineBaselineADB bounded sync, explicit byte cap, created-inode
binding, sink lifecycle, private inode/time/hash checks. Исходный media сохраняется.

## Что НЕ готово к live

1. Нет reviewed launcher с точным byte-bound source closure для coordinator и всех
   зависимостей, transport construction + fresh private directory + private sink.
   Constructor injection/tests не являются этим launcher или live admission.
2. `admission()` — строгий receipt shape, но не authentic producer. Нужен реально
   связанный fresh native-mode/scene/visual geometry receipt и revalidation у
   actual start после camera preferences UI. Synthetic booleans/hashes не замена.
3. Current camera launch/Intent override, output location и exact UI/dialog/switch
   hierarchy не проверены на устройстве; XML labels из source не доказывают shape.
4. Нет live recorder cap/early metadata/stop/rollback/transfer execution. В тестах
   только synthetic transport and snapshots. Validating encoded media/PTS и
   geometry — отдельный offline stage; `timeline()` reject-only не декодирует MP4.
5. No per-frame control/timebase calibration. Source03 acquisition остаётся
   rejected, physicalPWM≥2000Hz не достигнут.

## Проверки

30 focused tests PASS normal Python и -O (8v1 +22v2/coordinator).
Включают native10s stop, neverstop, delayed start/initialPREVIEW, unknown transport,
прямой повтор record после success/uncertainstart, latepreview, no-target-write
при recording, fresh original restoration, framework/boot change, pending
preference/switch rollback, late-read rejection, receipt rejection и exact windows.
Реальные UI, constructor/source closure, transport, sink и end-to-end run не
подменяются этими isolated synthetic tests. Требуется independent review.
