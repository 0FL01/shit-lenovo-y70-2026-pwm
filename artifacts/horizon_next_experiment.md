# HORIZON R3 — один следующий опыт: stock → A0D1C1 → stock

**TL;DR. Предлагается одна кандидатная стадия A0D1C1 между двумя stock-контролями, с уже подготовленными target-origin байтами, проверкой передачи/коротких readbacks и полным возвратом. Это проверка неизвестного совместного профиля D+C при A9=OFF; точные физические Hz камерная серия сама по себе не устанавливает.**

**Статус: PROPOSAL ONLY / NOT AUTHORIZED / NOT RUN.** Дата2026-11-08. В текущем исследовании никаких действий с target или камерой не выполнялось. Этот документ конкретизирует интерпретацию и gates прежнего [A0D1C1 proposal](dsi_coupled_9d_20261107/proposal.md), не расширяет его bytes/sequence и не заменяет отдельное подтверждение владельца по [AGENTS.md](../AGENTS.md), строки9–15,51.

## 1. Один вопрос и конкурирующие объяснения

Проверяем: способен ли native D=ON вместе с C=ON создать другой воспроизводимый optical state при A9=OFF?

- H₀: качественное подавление fine в прежних опытах обусловлено A9; профиль011 близок к stock000.
- H₁: D действует условно на фоне C;011 отличается от000, хотя010 и001 ранее не дали нужного результата.
- Возможное H₂: меняется только duty/amplitude или переходное состояние, а физический carrier остаётся прежним.

Новая серия различит H₀/H₁ на уровне **составного profile effect**. Сама по себе она не выделяет9D из33 изменённых пакетов. Вычисление D×C contrast с историческими010/001/000 потребует предположения сопоставимости состояния. H₁/H₂ по одним полосам могут остаться неразличимы; для carrier нужен независимый временной канал. Основание: [факторизация](horizon_r3_20261108/agent_a_ddic.md), §1; [независимое ревью](horizon_r3_20261108/agent_d_review.md), §§1,4.

## 2. Точная программа и границы разрешения

**Единственная серия:** `baseline(stock) → a0d1c1 → return_a0d1c1(stock)`.

Candidate — существующий `artifacts/dsi_coupled_9d_20261107/on_keep_a9_off.bin`: полный native ON, толькоoffset68/`23:A9` возвращён в0E. Offset97/`24:9D` остаётся8E. Длина875bytes,75packets; порядок/headers,74batch packets иfinal flush/page0 сохранены. От OFF —84bytes/33packets; от прежнегоS0C1 — толькоoffset97. Новых значений регистров нет, однако сочетание ещё не квалифицировано аппаратно.

Контроль целостности именно proposed/recovery payloads:

```text
candidate SHA256 8604d62cb74646105413c94105a5d66273e865bda2be0e0225f5dc3f69eac62e
stock SHA256     b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193
chunk byte ranges [0,253) [253,500) [500,754) [754,864) [864,875)
```

Stock bytes берутся из `artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command`. Не заменять их только двумя selector writes. В серию входят DBV replay, прежний bounded Settings redraw, короткие readbacks,7s camera holds, native trace, cleanup и emergency ordinary reboot при неопределённой очереди. Повтор S0C1, A9-only, новые registers/режимы/выдержки, firmware/slot/kernel changes и persistence в неё не входят.

Будущий approval record должен содержать **фактическое**, ещё не полученное подтверждение владельца и timestamp. Existing runner требует:

- `proposal = artifacts/dsi_coupled_9d_20261107/proposal.md` — эта точная привязка остаётся прежней;
- `candidates = ["a0d1c1"]`;
- `sequence = ["stock", "a0d1c1", "stock"]`;
- `program_sha256.stock` и `.a0d1c1` точно как выше;
- непустой `owner_confirmation`, timezone-aware `approved_at_utc`;
- `emergency_reboot_approved = true`.

Файл `artifacts/dsi_coupled_9d_20261107/authorization.json` сейчас отсутствует; не создавать его из этого proposal или старого согласия S0C1. `run.json` также отсутствует. [Runner](../06-tools/run_dsi_mode_trial.py), строки43–81,91–105,115–146; [offline audit](horizon_r3_20261108/root_offline_audit.json), `/candidate_identity`.

## 3. Предварительные условия будущего запуска

Все пункты этого раздела относятся только к сеансу **после отдельного подтверждения**. Сейчас даже read-only ADB не выполнялся.

1. Выполняющий агент на настроенном исследовательском host выбирает свежие transport IDs target и PacmanPro. Они различны, не наследуются из старых запусков. Existing runner использует private path `/home/stfu/.cache/opencode-tmp/opencode/dsi-coupled-9d-20261107`; должен быть доступен новый output location без чужих/старых результатов. Нет устройств на текущем offline workspace — здесь аппаратную команду не запускать.
2. Exact identity gate: SKU`XT2611-1`, build`W3WWS36.65-64-4-1`, slot`_b`, kernel`6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k`, SELinux`Enforcing`, `uid=0`, panelName`boe_ili97701A_682_1440x3168_dsc_cmd_v4`. Module SHA256`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`. Несовпадение означает stop/review, а не правку assert для продолжения.
3. Target awake/manual, `panelDC=0`, `bl_power=0`, native ESD mode`reg_read`, command logger0; отсутствие существующих `pwm_mode` probes/trace instance и собственного temporary dir. Не читать `panelCellId` как пассивный identifier: прежний анализ показывает отдельные panel transactions.
4. Сохранить исходные Android brightness mode/value, min/peak refresh, screen timeout, power state и native DBV. Runner установит DBV3600, requested120, providerDC0, одинаковый redraw. Requested120 — условие воспроизводимости, не measured emission/scan rate.
5. Camera PacmanPro/OpenCamera:100µs, ISO6400, AE/AF OFF, manual focus9.11752701±0.001, OIS/EIS OFF; неизменные geometry/crop/zoom между recording-стадиями. Камера закреплена; владелец не должен терпеть дискомфорт ради7s hold. Runner сверяет metadata, но sensor-row/ISP/timebase этим не квалифицируются.

Первичный код gates: [runner](../06-tools/run_dsi_mode_trial.py), строки286–327,525–590. Ранее проверенный module/hash не означает, что он по-прежнему установлен; future identity gate обязателен.

## 4. Команды и ожидаемая последовательность

Команды ниже — **для будущего отдельно согласованного сеанса**, не инструкции к выполнению в этом offline-запуске. `TARGET_TRANSPORT` и `CAMERA_TRANSPORT` заполняет агент по свежей идентификации; значений сейчас нет.

```sh
python3 06-tools/run_dsi_mode_trial.py "$TARGET_TRANSPORT" "$CAMERA_TRANSPORT" --coupled-9d
```

Запуск без `-O`, без подмены guard/authorization, строго один раз. Не использовать `--coupled-on`, owner-view, старый40-byte reader или вручную собранные shell DSI writes.

На каждой стадии runner должен подтвердить:

1. Пять batch chunks с ожидаемыми pending offsets/lengths и последним flush; ровно75 native table packets, payload/header/mode byte-exact с выбранной программой; no LOST, negative rc, DMA completion failure, probe missed events.
2. Один DBV replay`51 0e 10` и readback3600. Затем тот же Settings redraw. Это reproducer context, не чистый эксперимент latch-vs-delay.
3. Только ранее квалифицированные запросы `23:A9` length1, `24:9D` length1, `00:52` length2. Expected responses:
   - baseline: `0E / 0E / 0E10`;
   - a0d1c1: `0E / 8E / 0E10`;
   - return: `0E / 0E / 0E10`.
4. Для readback —7 standalone page callbacks с `(pending=0,length=11,flags=0)`, restore page0 иESD`reg_read`.7s hold, повторная проверка DBV/DC/power/camera, журнал completion errors. Всего в штатной серии225 table packets,3 DBV replay,9 requested register reads; page-management callbacks считаются отдельно.

**Transport limit:** requested length≤2 не гарантирует безопасный отказ на произвольный response type. В старом short-read review неожиданный long response в4-byte buffer способен вызвать `__fortify_panic`. Такого ответа у этих A9/9D/52 в проверенных данных не было; универсальная безопасность reader не заявляется. [State-marker result](ddic_state_marker_20261107/result.md); [прежний proposal](dsi_coupled_9d_20261107/proposal.md), строки75–80.

После подтверждённого stock-return и acquisition выполняется только offline analyzer:

```sh
python3 06-tools/analyze_dsi_redraw.py --coupled-9d
```

Он создаст `analysis_spatial_v2.json` в отдельном candidate-dir и откажется перезаписывать существующий v2 evidence. Сохранить original MP4, run.json, camera metadata, kernel/control traces и profile NPZ с provenance; публичные отчёты не должны раскрывать serial/IMEI/token. Исходные historical evidence не заменять.

## 5. Заранее заданные критерии результата

**Validity gate:** только complete series с exact packet/readback match, стабильными камерными условиями, соседними stock controls и успешно проверенным возвратом. Ошибочная передача, missing trace или drift камеры делают исход неинтерпретируемым; нельзя записывать его как отрицательный результат физиологической/частотной гипотезы.

**Первичный camera endpoint:** нормированная total q93-компонента candidate относительно среднего двух соседних stock, тем же corrected spatial-v2 способом. Дополнительно сохранить полный spatial spectrum и phase, broad-компоненту и средний сигнал: перенос мощности из q93 в другой peak нельзя перепутать с исчезновением модуляции. Не ограничивать поиск только предполагаемыми2q/3q, не присваивать peaks физические Hz.

- Обратимое крупное отличие candidate от обоих stock — новый intermediate optical state. Ratio≤0.5 служит заранее указанным ориентиром крупного подавления именно q93, **не** p-value, минимальной чувствительностью опыта или доказательством frequency gain. Отдельный устойчивый спектральный рисунок тоже сохраняется, даже если q93 не уменьшилась.
- Нет существенного эффекта за пределами различия самих stock controls, нет нового устойчивого рисунка — закрыть A0D1C1 в данном context. Не повторять автоматически и не открывать S0C1 заново.
- Улучшилась только амплитуда/комфорт — сохранить отдельный результат с точными условиями; A9-only historical0.2264067 не заменять без сопоставимого подтверждения. Сравнение с исторической A9 не объявлять одновременным head-to-head.
- Изменённый q93/31-pixel peak, readback или requested refresh **не** подтверждают≥2000Hz. Владельческая оценка пригодности важна, но тоже не заменяет timebase.

**Строгий endpoint цели R3:** независимая локальная optical waveform с квалифицированной временной базой показывает воспроизводимо управляемый carrier/pulse recurrence≥2000Hz; нижняя граница с учётом установленной погрешности также≥2000Hz (оценки2000±20Hz недостаточно). Проверены fundamental versus harmonic, pulse intervals, duty и возможная низкочастотная огибающая. Пик2160Hz при основном цикле720Hz не считается таким результатом. Наличие высокочастотного carrier отдельно не означает исчезновения огибающей.

Если квалифицированного optical recorder нет, серия остаётся полезной сравнительной пробой согласно `AGENTS.md:15`; её endpoint ограничен камерным effect. Минимальный независимый qualifier и требования к фотодиоду/ADC описаны в [C](horizon_r3_20261108/agent_c_optics.md), §4. Новая аппаратура/новые измерительные действия не добавляются в старое согласие автоматически; конкретный recorder сейчас не выбран и новые съёмки не выполнены.

## 6. Stop conditions и возврат

**Немедленно остановить candidate progression**, если: mismatch identity/hash/readback; missing/unexpected packet; lost/missed trace; отрицательный rc/DMA error; uncertain pending batch; изменение DBV/DC/geometry/exposure; black screen, артефакты, зависание, необычное поведение панели; дискомфорт владельца. Не «добирать» ещё один прогон для красивого графика.

**Штатный возврат** уже является третьей стадией: full native OFF875bytes/75packets → same DBV replay → redraw → `0E/0E/0E10` → hold/error check. Затем restore page0/ESD`reg_read`, logger0, убрать только собственные probes/trace/temp files, остановить и сохранить camera capture. Восстановить captured Android policy и исходный manual native DBV/power; подтвердить `panelDC=0`, logger0, Enforcing. `target_restored=true` допустим только после фактических checks; это возврат к captured preflight policy, а не произвольной «заводской» политике.

**При неопределённой очереди или неизвестном состоянии candidate** не дописывать новый stock batch. Existing runner запускает отдельно включённый в scope ordinary reboot через `recover_reboot()` (`run_dsi_mode_trial.py:502–523`), затем заново выбирает transport и проверяет exact identity/root/Enforcing/`panelDC=0`. Это возврат через неизменённую stock initialization, без flash. Если recovery не подтверждён — прекратить новые writes, сохранить журнал и явно сообщить отсутствие доказанного возврата. Обычный reboot не гарантирует устранение необратимого повреждения панели.

Наличие approval на hardware profile обязательно отдельно от выполненных offline-тестов. Один scoped consent покрывает именно эту полную серию с проверками/возвратом; дополнительных per-command вопросов не требуется.

## 7. Уже выполнено offline и одно следующее действие

Проверены candidate identity, все75packet headers, отсутствие authorization/run; A/D/C факторизация и rank6/8 независимо воспроизведены; семь исторических ratios пересчитаны из summaries; runner exact-scope unit test прошёл, no-authorization и `-O` пути отказали до subprocess. Физическая квалификация профиля отсутствует. [Root audit](horizon_r3_20261108/root_offline_audit.json), [runner checks](horizon_r3_20261108/runner_offline_checks.json), [независимое D review](horizon_r3_20261108/agent_d_review.md).

**Следующее действие: отдельное подтверждение владельцем этой одной stock→A0D1C1→stock серии и только затем её полное выполнение агентом.** При валидном отрицательном результате следующий новый вопрос — matched frame-event/no-event при одинаковой задержке; его harness и scope должны быть подготовлены отдельно. Текущий документ такого второго опыта не разрешает.
