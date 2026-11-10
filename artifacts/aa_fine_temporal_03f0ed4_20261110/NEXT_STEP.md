# Prospective observation: stock without table writes

**Только offline предложение. Ни capture, ни изменения устройства этим файлом не разрешены.** Перед запуском нужна отдельная scoped execution assignment, проверка применимой авторизации/guards и проверенная no-write capture возможность; это не новая blanket policy об обязательном approval для любых camera-only действий. Гипотеза: сходная пространственная/внутриоконная amplitude variation повторяется на неподвижной stock scene без custom/raw DSI table/selector writes. Один опыт проверяет recurrence, а не достигает physical PWM ≥2000 Hz.

## Предусловия

- Для этой no-mutation ветки требовать УЖЕ совпадающие stock brightness, native display mode, Settings scene, geometry и camera controls по исходному manifest; при mismatch остановиться. Saved run подтверждает acquisition native DBV3600 / software120Hz, но before/original native DBV6438 (screen_brightness98) и original_settings_dbv_logger_restored=true. Текущее устройство не проверялось. Нельзя молча восстановить DBV3600 как часть «без настроек». Если нужен setup, отдельно перечислить конкретные ordinary settings mutations и rollback в execution assignment; обычный driver при setup может отправлять стандартные panel commands. Эта ветка их не выполняет. Не угадывать отсутствующие values. Состояние должно стабилизироваться ДО записи; геометрия/содержание старых полос заново просматриваются для нового media.
- Controls из camera audit: 100000 ns, ISO6400, focus2.0387485, zoom1, AE/AF/EIS/OIS OFF, исходный crop/native1280×720. При mismatch остановиться; изменения принадлежат отдельному явно перечисленному setup plan с rollback, не этому no-mutation наблюдению.
- Только проверенный отдельный capture path, который НЕ делает custom/raw DSI table/selector writes или settings mutations и НЕ входит в isolation/active table transaction. Если доступный harness умеет capture лишь внутри write transaction, остановиться на offline design. Не продлевать действующий37s active guard и не считать это разрешением обходить его.
- Новая observation evidence должна иметь обязательный before.boot_id, source-bound version и собственные действительные evidence/custody. Исправление старого source03 projection не переносится в новую acquisition. No-write observation имеет собственный тип evidence, а не фиктивные sham/return transaction records.

## Заранее фиксированное наблюдение

Одна запись не более15s в непрерывном unchanged stock. Нет custom/raw DSI replay, переключения settings, candidate, deliberate redraw или движения в ходе записи. Не утверждается отсутствие всех обычных driver-generated DSI packets. Номинально30fps. Четыре60-frame окна [30,90), [120,180), [210,270), [300,360) относительно первого сохранённого кадра; центры около2,5,8,11s. Фактические PTS/сохранённые anchor counts проверяются после capture, temporal gaps не исправляются выбором удобных кадров. При отсутствии полного окна или сомнительной привязке результат inconclusive. При отклонении фактического frame rate от исходного план пересматривается ДО нового опыта, не post hoc.

Почему15s: это конечный минимальный тест recurrence, содержащий четыре полных2s окна с паузами и около3s конечного запаса, против исходных2s отдельных наблюдений. Он покрывает несколько наблюдавшихся циклов camera-row phase, но не доказывает долговременную стационарность. Достаточность только операционная: четыре полных source-bound окна с валидной геометрией/controls/PTS. Отсутствие drift не является основанием автоматически удлинять запись или объявлять стабильность.

Первое окно является reference. Три старых ROI, исходный q=0.019775390625 cycles/camera-row (ранее выбранный baseline-only), FFT8192, Hann, degree2, total per-frame RMS/(mean Y−16) и существующий all-ROI5% criterion не изменяются. q заранее заморожен для всех новых окон, без нового выбора на их сравнении. Прежний search-band0.012–0.03 остаётся только secondary peak-stability diagnostic; его maxima не заменяют fixed-q metric. Это новый prospective control diagnostic; старый source03 right+5.3904% остаётся failure. Соседние strips и окна одного capture не являются независимыми экспериментами.

Заранее объявленные secondary summaries, без отбора выигрышных:
- все per-frame fine amplitude/phase/mean-Y curves и все20-frame blocks;
- common ROI correlation, peak-q stability и constant-amplitude phase/q null;
- full/inset30/upper220/lower220 со всеми прежними sensitivity variants;
- PTS/GOP/I/P counts и packet-size associations, без causal interpretation;
- full fixed primary ratios отдельно от secondary summaries. Более длинная запись не превращается в усреднение всех кадров для получения pass.

## Falsifiable outcomes и пределы

- Если на unchanged stock нарушается прежний5% all-ROI control criterion и/или вторичная заранее определённая recurrence: хотя бы в одном ROI любого окна abs(100×(metric(last20)/metric(first20)−1))≥10%, drift может происходить без custom/raw DSI write. Предположение «custom/raw table write необходим для такого drift» опровергнуто в этой обстановке; stock-control repeatability остаётся unresolved. Вторичный10% recurrence marker не меняет первичный5% criterion и не является новым pass/fail для candidate admission. Это не определяет panel vs camera/ISP/codec vs scene.
- Если criterion сохраняется, это лишь стабильный контроль в одном коротком наблюдении. Это не доказывает, что прежний drift вызван write, не исключает редкую/долгую вариацию и не допускает AA10 автоматически. Отсутствие явления в этой записи не устанавливает физические Hz.
- Sham-write causality потребовала бы отдельного заранее спланированного matched-control опыта с independent повторениями и разрешением. Compression causality лучше проверять синхронными precodec Y и encoded Y из реально доступного API; такая capture extension сейчас не обещается и не разрешена. Даже precodec Y не отделяет panel от camera exposure/ISP; для этого нужен независимый optical channel/калибровка.

Прервать при дискомфорте, неожиданном state/control/geometry drift, thermal warning, capture/timing failure. Не провоцировать симптомы и не продолжать ради полного окна. После отдельной scoped execution assignment и applicable authorization review сначала проверить prerequisites, затем выполнить только этот observation, сохранить private media и sanitized report. В текущем offline task никакого устройства не касаться.
