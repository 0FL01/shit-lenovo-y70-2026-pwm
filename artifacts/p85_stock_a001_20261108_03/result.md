# P85 stock-only 03: camera metadata ещё не согласована

Committed/clean source `47a7782490f940560525865fefffdf38d8e4f728` прошёл target
setup и начал запись камеры. Первый recording dump не прошёл строгий guard:
`Request/result not settled to same request`. Это переходное состояние camera
pipeline, а не разрешение использовать несовпадающие request/result.

[run.json](run.json) содержит zero qualified stages, пустой список register85
writes, zero candidate attempts и unknown-value-write=false. Baseline register
reads и P85 writer не запускались. Неизвестное14 не отправлялось.

Завершение в 2026-11-08 17:21:42 UTC: исходные Android settings/native DBV6438/
logger и ESD восстановлены, камера остановлена, watchdog снят, собственный mutex
освобождён. Reboot не понадобился; ошибок cleanup нет. Частичная запись приватна
и не является успешной stock/sham/return optical qualification.

Следующее исправление ограничено read-only ожиданием startup metadata: без
повторного tap записи, camera settings или DSI. Допустим только известный
переходный mismatch request/result ID, с коротким deadline и лимитом попыток;
два успешных снимка всё равно должны пройти весь profile/session/progress guard.
Иные ошибки нельзя скрывать retry. Исходный failed run остаётся неизменным.

Same-value85 runtime write и candidate14 остаются неквалифицированными.
Физические >=2000Hz не установлены; timing budget не увеличивается.

Поправка к первоначальному тексту: saved original этой попытки равен6438,
не прежним828 из01–02. Код восстановил именно сохранённые6438. Android
brightness98/manual не изменились; причина изменения native DBV между02 и03
не установлена. Исправлено описание, а не состояние устройства или run.json.
