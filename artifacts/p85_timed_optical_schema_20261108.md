# Оптическая схема timed factory-15 surrogate

Статус: офлайн-реализация и тесты. Это не результат нового опыта,
не доказательство времени будущего возврата и не допуск candidate14.

Итог проверки: 50 объединённых оптических тестов проходят обычно и с
python -O; py_compile и проверка форматирования проходят. Независимый
review — PASS. Оба найденных синтетических контрпримера теперь отклоняются;
старые timing plans совпадают, AST прежних validate_run и Fourier analyze
не изменён. Новый live-прогон этой проверкой не выполнялся.

## Изолированные файлы

- [analyze_p85_timed_surrogate.py](../06-tools/analyze_p85_timed_surrogate.py).
- [test_analyze_p85_timed_surrogate.py](../06-tools/test_analyze_p85_timed_surrogate.py).
- В [старом анализаторе](../06-tools/analyze_p85_optical.py) только чистый
  расчёт окон вынесен в select_windows_from_stages(stages, recording_preflight,
  pts, ...). Старый select_windows сначала вызывает неизменённый validate_run.
  Старые правила не разрешают пропуск C1 и не принимают новый scope.
- Аппаратные исполняемые файлы в этой работе не изменялись.

## Точная новая схема

scope: p85-timed-stock-surrogate-v1. Порядок стадий строго
baseline → sham15 → return15. candidate_enabled=false, candidate_attempts=0,
unknown_value_write_attempted=false, unknown_register_writes=false.
Попытки записи только sham15 и return15; обе записи имеют ровно три
standalone callbacks и проверенные native/wire gates.

Во всех стадиях обязательны qualified P85 data=[21,0,0], native_dbv=3600,
framing/cleanup evidence и минимум 120 продвинувшихся sensor frames.
Baseline и return обязаны иметь реальное qualified C1 data=[0,0,96] с
положительным phase_seconds.c1.

**Только sham15** содержит точно:

~~~json
{
  "c1": {
    "status": "not_measured",
    "reason": "diagnostic omitted by timed-stock protocol"
  }
}
~~~

В sham15 отсутствуют c1.data и phase_seconds.c1. Нулевой duration,
подстановка baseline/return C1, отсутствие самого поля c1 или произвольная
другая причина не принимаются. Результат анализа также явно сохраняет
status=not_measured без data. Это диагностическое отсутствие измерения,
а не измеренное нулевое значение.

## Время и возврат

Сохраняются camera_start/end с настоящими host_call_start/end_utc,
host_call_elapsed_seconds и host_capture_bounds.begin/end_monotonic;
hold_start/end_utc и hold_start/end_monotonic.

- Во всех стадиях hold_seconds=4.5.
- camera_end.begin_monotonic − camera_start.end_monotonic ≥4.5.
- Все camera endpoints находятся внутри hold.
- UTC−monotonic offset по шести границам hold/camera одной стадии
  согласован в пределах 50 мс. Равенства длительности отдельных вызовов
  недостаточно: оно не обнаруживает скачок часов между вызовами.
- Монотонное время определяет фактически выдержанный интервал; UTC
  используется для проверенной в указанных пределах привязки видеокадров.

У sham15 обязателен return_prequiet:

- started_monotonic и ended_monotonic после camera_start.end, до
  camera_end.begin; полный host elapsed не меньше 2 с.
- quiet_evidence содержит штатную двухсекундную quiet-проверку,
  актуальные native120/group3 и реальные kernel_marker_bounds.
- Разность target kernel end_seconds − begin_seconds ≥2 с.
  clock точно обозначен как «target kernel printk monotonic; not host/camera clock».
  Значения kernel clock никогда не вычитаются из host/camera timestamps.

Пусть t0=camera_start.end_monotonic, deadline=t0+4.5, a/b — начало/конец prequiet.
Тогда поля фиксируют:

- wait_seconds=max(0, deadline−b);
- overlap_seconds=max(0, min(b,deadline)−max(a,t0));
- overshoot_seconds=max(0,b−deadline).

Эти значения сверяются с timestamps с допуском 5 мс. Overshoot может
удлинить hold, но не сократить его. После camera_end обязательна полная
hold-проверка. sham15.hold_verified_monotonic не раньше hold_end.
Return writes[].started_monotonic не раньше hold_verified; dispatch и
validated timestamps упорядочены. Ни одна return DSI-команда не переносится
в оптическое окно.

## Timed lifecycle

Новая схема обязана иметь явные timed_stock_exploratory=true,
active_limit_seconds=37, host_limit_seconds=45, recovery_reserve_seconds=8,
timed_watchdog_seconds=60 и timed_watchdog_renewals=0.

Проверяются active_start_monotonic, arm_seconds, return_qualified_monotonic,
disarm_seconds и active_G_seconds. Arm предшествует обеим записям; return
qualified следует после validated return write. G согласуется с временем
квалификации и disarm и меньше 37 с. Final candidate_watchdog должен быть
disarmed_after_verified_return_or_boot, но любой recovery/reboot всё равно
отклоняет обычную успешную квалификацию. host_alarm_restored_before_cleanup
и explicit15_readback_and_stock_c1_verified обязательны.

Baseline hold завершён до active interval, middle находится внутри него,
полный return optical hold начинается после проверенного disarm. Overall
watchdog и обычные cleanup/return gates остаются обязательными отдельно.

Эти поля описывают наблюдённый factory15 прогон. Они не превращают частичные
замеры в доказанную верхнюю границу будущего возврата и не допускают unknown14.

## Неизменные оптические ограничения

До любого stat/ffprobe/decode видео проверяются точный новый scope,
finished_at_utc, успешный статус и все cleanup gates. Затем используются
те же оригинальные PTS, согласованные sensor/encoder offsets, минимум
60 центральных encoded frames, host-call envelopes и условные бюджеты
давности metadata/привязки MP4. 120 sensor frames не заменяют 60 пригодных
encoded frames.

Каждый опыт требует нового native-Y/noautorotate просмотра первого,
среднего и последнего кадра каждой стадии и связанного с данным run.json
ROI review. Fixed fine q выбирается только по baseline. Сохраняются полный
спектр 0–0,5, total/coherent/incoherent, detrend sensitivity, соседние ROI
и временные блоки. Среднее по времени не вычитается.

physical_pwm_hz=null, stock_optics_restored=null, sham_optics_unchanged=null,
lead_approved=false и candidate_enabled=false. Нет автоматического
p85-stock-review-v1 или утверждения полной оптической эквивалентности.

## Проверки

~~~sh
.venv/bin/python -m unittest discover -s 06-tools -p 'test_analyze_p85*.py'
.venv/bin/python -O -m unittest discover -s 06-tools -p 'test_analyze_p85*.py'

.venv/bin/python 06-tools/analyze_p85_timed_surrogate.py "$RUN" "$VIDEO" \
  --plan --output "$NEW_PLAN" --preview-dir "$NEW_PRIVATE_REVIEW_DIR"

# Только после свежего просмотра и заполнения ROI review:
.venv/bin/python 06-tools/analyze_p85_timed_surrogate.py "$RUN" "$VIDEO" \
  --review "$ROI_REVIEW" --output "$NEW_RESULT" --profiles "$NEW_PROFILES"
~~~

Регрессии включают побитовое равенство старых primary/stronger timing plans
для завершённых stock04 и batch01; отказ старого пути при missing/not_measured
C1; новый протокол и его ошибки; отсутствие выдуманных C1/approval;
временные/clock/quiet/return/watchdog ограничения; отказ до доступа к
незавершённому видео; exclusive-create и python -O.

Тесты не касаются устройств и не читают новое живое видео. Сохранённые
численные NPZ/JSON старых опытов используются только как read-only fixtures.
