# Независимый review scientific v2 adapter — 2026-11-10

**Verdict: PASS для offline numeric adapter; production entry пока fail-closed.**
Новые записи/устройства/private deployment evidence не читались. Это не допуск capture или qualification фактического MP4.

## Проверенный scope

- `06-tools/stock_observation_analysis_20261110/analyze.py`: SHA256 `3c23c9acc9e56e149494146b9ed3345277492d1ce5661c77e6c705133c00661a`.
- `test_analyze.py`: `cef95e3f2e8b072bb0e974c062ef94f6db422b6b260baab67f3a7f0268011e39`.
- Numeric constants/timeline из `stock_observation_20261110/protocol_v2.py`, просмотренный hash `1d1526b73316c145f9f943ec820e141c1797560a02775d1656619152e066c659`; source-integration/admission изменения отдельно от этого review.

## Что подтверждено

1. `validate_probe` вызывает существующий `analyze_p85_optical.validate_pts`: один H264 video stream,1280x720/yuv420p/tv, без audio, исходные decoded PTS/count. Дополнительные finite stream/container duration9..15s, cadence, origin/endpoints и rate checks не расширяют frozen duration.10s nominal cap отдельно не выдаётся за доказанный по длине файла.
2. `extract_profiles` вызывает существующий `decode_y` для original indices30..269. Этот decoder использует `-noautorotate`, `extractplanes=y`, native crop и passthrough. Crop[225,245,80,330] правильно даёт полосы left/main/right с x225/255/285, width20. Нет rescale, нового ROI или обработки изображения.
3. `measure_profiles` непосредственно вызывает существующий `fixed_metrics(window,[Q],degree=2)` для4×60×330 каждой ROI. Через `optical_spectrum.analyze_profiles` сохраняются Hann, degree2, total RMS Fourier coefficient и нормировка `(mean Y−16)`. q=.019775390625 фиксирован, нового peak search нет.8192 означает происхождение q из ранее замороженной grid; фактический estimator использует explicit singleton Fourier frequency, не новый FFT peak selection.
4. Окна [30,90),[90,150),[150,210),[210,270) соответствуют1–9s; каждое окно2–4 сравнивается с window1. All-ROI absolute5% применяется ко всем9 отношениям, без усреднения ROI. `windows_independent=False` и описание adjacent/non-independent присутствуют. Это не четыре независимых trial и не physical Hz/candidate admission.
5. Structural record intake не аутентифицирует JSON booleans: возвращает inconclusive, acquisition_admitted=False, qualification_eligible=False. `analyze_actual` закрыт конкретно из-за отсутствия reviewed source/recording producer и acquisition-time created-inode custody verifier. Нет нового требования абсолютной per-frame controls calibration. Условные advancing snapshots/PTS остаются с явно указанными ограничениями.

## Независимые проверки

- 14/14 focused tests PASS normal;14/14 PASS `python3 -O`.
- 10/10 existing `test_optical_spectrum.py` PASS.
- Дополнительно synthetic270-frame9s и450-frame15s endpoints PASS.
- Дополнительно distinct-column decoder stub подтвердил точные ROI offsets: means9.5/39.5/69.5 для left/main/right. Реальные media не открывались.
- `git diff` для reused `analyze_p85_optical.py` и `optical_spectrum.py` пустой на момент review.

## Оставшиеся blockers

Нужна конкретная reviewed capsule producer/verifier, связывающая exact source closure, writer records, финальные boots, acquisition-time sink/created inode и media identity. Затем actual entry должен выполнить intake → probe → genuine byte-bound12-frame ROI review → decode/metrics и private retention, без обхода через отдельные pure helpers. Текущие структурные формы и synthetic tests эту связь не создают. После интеграции требуется отдельный review producer/actual entry; текущий verdict не распространяется на будущие изменения.

На проверенной numeric версии новых scientific defects не найдено. Не выполнены и не требовались реальные capture, hardware calibration или переоценка rejected source03.

## Повторный review concrete capsule route — supersedes initial gate assessment

Просмотренный adapter SHA256 `57c7666bb0f565c02f532504eaea0cbf7d4c1fd501b63453b3186a7a4b702512`; capsule tests `8227ba4a79fc5cfbf099f563955417ea1c7f9b08b6ba8079ad5faefd66f0c6d4`. Producer coordinator `d6b08c9ec08446c8ef723970ec45cede2fef1b664a0326c826664538bbdb9e6b`, construction `4607a49f7ae511c7d9e4a30e8e3b53cd0384f5383dfba3615c0a40c8d51acbbe`.

Concrete `analyze_actual` теперь реализован, поэтому прежнее описание always-closed entry историческое. Capsule schema согласована с producer: source closure canonical map, exact record bytes/hashes, final boots equality, sink facts и created dev/inode/uid/mode. Expected source поступает отдельно, не извлекается автоматически из capsule. Late first advancing pair допускает только conditional diagnostic с unknown first-window coverage, strict acquisition inconclusive и qualification/candidate flags false. Numeric q/ROI/5% machinery не изменена.

**BLOCKING correctness finding:** `private_bytes` сравнивает полный `os.stat_result` до/после чтения; это включает atime, который может измениться от самого чтения. `analyze_actual` также сравнивает полный stat между reads. Поэтому неизменённые файлы ошибочно отвергаются. Независимый29-test normal run:28 PASS,1 ERROR (`test_late_pair_remains_inconclusive`, private input changed). Дополнительный deterministic aged-atime synthetic file воспроизвёл тот же отказ. Optimized run в этой команде не запускался из-за предыдущего failure.

Требуемое исправление: сравнивать identity/permissions/owner/nlink/size/mtime_ns/ctime_ns, исключив atime; сохранить byte digests и post-analysis reread. Добавить aged-atime regression и rerun normal/-O. До исправления production diagnostic route не получает PASS. Devices, actual media и publication не выполнялись.

## Финальная перепроверка atime fix — текущий verdict

**PASS concrete conditional offline diagnostic route; предыдущий atime blocker устранён.**

Hash-bound recheck до/после тестов:
- analyze.py: `c589c3560660d01dc3252e306d7aeb5921ae25723df9c5c7e5c0e4c436a04753`.
- test_analyze.py: `cef95e3f2e8b072bb0e974c062ef94f6db422b6b260baab67f3a7f0268011e39`.
- test_capsule.py: `ce0b94a593a358d6c997fbda993f9e7cb088e4093a2c0161dd95f3cfa9bf2ff4`.

`stable_identity` теперь сравнивает dev/ino/mode/uid/nlink/size/mtime_ns/ctime_ns, исключая только read-induced atime; применяется и внутри private_bytes, и между media reads. Byte SHA256, inode custody и повторная проверка records/review сохранены. Новые aged-atime и identity-mutation regressions включены.

Независимо повторено: **31/31 normal PASS,31/31 -O PASS,10/10 existing spectrum PASS**. Проверяемые hashes стабильны. Source/custody capsule и final-boots checks соответствуют описанному выше producer; independently pinned expected_source остаётся обязательным. Late first pair допускает только unknown first-window coverage и conditional_diagnostic_only, не acquisition/qualification/candidate PASS. Numeric q/ROI/windows/all-ROI5% неизменны.

Ограничения остаются честными: actual media отсутствует, genuine byte-bound ROI review не выполнен, текущие device/profile/cap не проверены этим review. Это проверка offline software route, не разрешение или свидетельство нового capture. Ни devices, ни publication не выполнялись.
