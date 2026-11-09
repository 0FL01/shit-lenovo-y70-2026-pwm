# Реализованный offline recovery qualification harness

Этот каталог содержит работающие pure-Python state machines и fake dispatch/results, не план будущего кода. Никакого реального reader, ADB, proc, SSH-host/phone endpoint, executable command string, DSI, return15, shutter toggle или runtime import нет. Только literal FakeBackend; подстановка другого backend отвергается. Выход всегда physical_admission=false и stock_admission=HOLD. Даже fake_components_verified не означает физическое recovery или разрешение stock опыта.

## Реализованный интерфейс custody

custody_bridge.py импортирует только новый pure model `06-tools/recovery_hop_custody_20261109/custody_model.py`: перед compile сравнивает SHA256 и исполняет те же прочитанные bytes, без повторного чтения через loader. Пин bd15667991aa29e516ed14e4186215025b123a18bc79ebb49e8776cc04a8d953 согласован с владельцем модели. Это offline dependency, не production runtime. Если модель меняется, импорт отказывает до любых fake calls; нужен отдельный review/refreeze.

Каждый READ_STATUS или recovery action проходит actual assess_route→admit с exact request/authority, incident, route, component, physical target, source digest, одноразовыми operation/evidence nonces и dispatch clocks в собственных доменах. Bridge хранит latest reducer state и вызывает complete после результата; timeout/unknown и denial терминальны. Неподтверждённая/denied причина исходного incident также блокируется. Старый route/adapter не оживляется. В положительных fixtures причина VERIFIED_NONSERVER_EXIT и external approval/reader capabilities намеренно вымышленные: это тест reducer, а не диагноз реального incident или newly qualified route.

RouteFixture строит четыре синтетических ordered hops client_forward/ssh_session/remote_adb/transport_device с явно совпадающими bindings и reader provenance. Использованы interval observations и отдельно physical ID/boot. Нет утверждения, что pidfd, proc snapshots или boolean-флаги сами обеспечивают custody. Dataclass signatures/receipt objects не создают реальной аутентификации: externally qualified collector и authority остаются отсутствующими предпосылками. Gate принимает только actual CustodyAdmission bridge, не произвольный callback с admitted=true.

QualifiedReceipt выдаётся только после допуска read и successful fake result с совпадающими route physical ID/boot. Проверяются локальное происхождение объекта, неизменность payload, stage, свежесть и single-use. Копия/подмена/повтор/stale/future receipt терминально отклоняются. Семантические pre-action наблюдения также должны оставаться свежими. Fake mutation включает receiver-side guard ожидаемого boot/session/owner; STOP_CAMERA требует active owned session, RESTORE_CAMERA требует inactive. Это **вымышленный conditional-stop capability**, не найденный или реализованный stop API OpenCamera. Реальная атомарная session-selective операция остаётся квалификационным blocker; её нельзя заменить tap/force-stop.

## Target transitions

NEED_PRECHECK → READY_REBOOT → NEED_CHANGED_BOOT → READY_RESTORE → NEED_RESTORED_READBACK → VERIFIED_FAKE_COMPONENT.

Precheck требует exact identity/module/panel, UID0, Enforcing, исходный boot и полный сохранённый settings/native DBV/logger snapshot. Reboot допускается один раз, с expected boot; attempted отмечается до dispatch. Ack не означает changed boot. Следующий read требует **отдельно подготовленный route contract нового boot**, а не переиспользование старого physical binding. После exact changed UUID, boot_completed, identity/root/Enforcing/module/panel/DC/ESD проверок controller передаёт RebootProof с identity того admitted read в reducer; только затем разрешается RESTORE_TARGET. Restore использует исключительно захваченные originals; отдельный readback проверяет их и DC/ESD/power. Нет слепого stock15/DSI fallback. Ownership/watchdog cleanup и физическая DDIC безопасность не симулируются как доказанный успех этим component contract.

## Camera transitions

NEED_PRECHECK → READY_STOP → NEED_STOP_OBSERVATION → NEED_MEDIA_FINALIZATION → READY_PROFILE_RESTORE → NEED_PROFILE_READBACK → VERIFIED_FAKE_COMPONENT.

Stop возможен только для exact observed session+owner+camera boot с independently qualified stop-only capability. Idle/foreign/replaced/unknown session не вызывает повторного нажатия или остановки другого приложения. Source-derived callback ordering/installed APK equivalence не используются. Cap callback/ack/elapsed time не завершает stop. Затем независимо требуются остановка, тот же original media ID, finalized/retained/decode-valid/metadata-retained evidence, и только после этого восстановление exact original A/task/full profile (focus, exposure, ISO, locks, zoom, geometry/FPS/audio) и исходных preferences. Новая запись не является recovery action. Отсутствующий original snapshot не заполняется defaults.

Любое неверное состояние, denial, timeout, stale/replayed evidence или unknown completion переводит соответствующий controller в RECOVERY_FAILED и запрещает следующие действия этого epoch. Запись исходного failed incident копируется неизменной; успешный другой component не снимает failure. Target watchdog60/600 явно не доказывает camera stop. Новый independent recovery epoch для разрешения неизвестного состояния не реализован и не открывается автоматически.

## Проверки и результат

test_harness.py реально вызывает обе state machines через actual custody reducer и fake backend. Проверяются happy fake sequence, wrong incident cause/old route, unqualified reader/custody gap/foreign bindings, exact authority, stale route/receipt/pre-action state, one reboot, timeout/unknown no retry, unchanged boot, root/Enforcing/DC/ESD mismatch, original settings mismatch, foreign/replaced camera session, callback-before-stop, missing finalization/retention/metadata/decode, wrong original A/task/profile/preferences, receipt copy/mutation/replay, prohibited action vocabulary, nonfake backend и одна успешная компонента при failure другой.

tests_initial.txt сохраняет первую интеграционную ошибку: sibling API добавил required evidence_nonce до freeze;14 ошибок были до fake dispatch. После адаптации и пина final API tests_normal.txt/tests_optimized.txt являются актуальными проверками. Fixture values/identities/approval IDs/media IDs синтетические и не назначают реальных caps/действий. Отдельный result.json сохраняет несколько реально выполненных fake сценариев и их dispatch journals.

Нет текущего физически допущенного backend/route/reader, session-only stop, установленного APK/source match или A001 behavior qualification. Следующий физический шаг требует независимой admission работы и явной lead assignment. Этот harness не обходит protected Lenovo producer/receipt и не меняет source/runtime/Git. Ранее замороженные camera-contract артефакты не редактировались.
