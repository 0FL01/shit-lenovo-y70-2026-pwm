# Long-lived agent progress journal

Checkpoint 2026-11-08, **P85 factory15 runtime transport проверен; fine-контроль воспроизведён, R3 не решена.**

- [Stock-only04 hardware](artifacts/p85_stock_a001_20261108_04/hardware_result.md): baseline → sham15 → return15 прошли при DBV3600/native actual120/group3. Две трёхпакетные записи85=15 и все шесть framed reads независимо replay-validated; P85 `15 00 00`, C1 `00 00 60` во всех фазах. Никакого14. Same-value write не доказывает read/write-plane identity, volatile semantics или частотный setter.
- [Оптика04](artifacts/p85_stock_a001_20261108_04/optical_result.md): fresh ROI/PTS и60 кадров на фазу прошли независимый review. Main fine sham/baseline1.0000529, return1.0149156; среднийY меняется менее0.25%. Broad/full-spectrum equivalence не установлена (return L2 около9.6–10%), поэтому blanket optical approval не создан. Два полных decode совпали точно. Hz/комфорт не измерены.
- На завершении04 восстановлен saved original native DBV **6438**, Android98/manual/min-peak120/timeout1800000/logger0; камера остановлена, ESD reg_read/Enforcing/DC0 подтверждены, watchdog/mutex сняты без reboot/errors. Указанные ранее828 для03–04 были ошибкой описания: обе попытки корректно сохранили/восстановили6438. Причина native изменения между02 и03 не установлена; устройство ради исправления текста не менялось.
- [Latency plan](artifacts/p85_latency_plan_20261108.md): stage32.64/32.74/30.71с, writer17.21/16.69с всё ещё не проходят45с/60с ограничения. Изолированный stock-only batching adapter разрабатывается офлайн, не меняет child DSI scripts и должен пройти свою квалификацию. Candidate14 остаётся выключенным. Предыдущий опубликованный source checkpoint: `86ffbfd76aed81b95ca0e990362dd55aacca99a8`.

Checkpoint 2026-11-08, **P85 stock-only 01–03 остановлены до parameter write; восстановление проверено.**

- [Failed qualification 01](artifacts/p85_stock_a001_20261108_01/result.md): baseline при DBV 3600/native actual 120 дал qualified P85 `15 00 00` и C1 `00 00 60`. Writer gate0 затем упёрся в Android external printf argv limit на retained dmesg; его trace/profile пусты. Параметр 85 не записан, 14 не использовался. Один штатный reboot и полный original settings/native 828/logger/ESD/camera/watchdog/mutex cleanup проверены.
- [02](artifacts/p85_stock_a001_20261108_02/result.md) остановилась на post-reboot keyguard до native anchor; обычный OS dismiss затем дважды проверен без credentials/security-setting changes. [03](artifacts/p85_stock_a001_20261108_03/result.md) остановилась на первом recording dump: ещё PREVIEW, старый skew и нулевые encoder frames. Обе попытки полностью восстановлены без reboot, zero85 writes. Startup исправлен узко: initial2s wait, максимум5 read-only dumps/8s, только otherwise-valid ID mismatch retry, две строгие последовательные recording snapshots. PREVIEW/old skew/zero frames остаются fatal; startup-only alarm ограничивает зависший transport и снимается до cleanup.
- [Новый P85 runner](artifacts/p85_guarded_runner_20261108.md) теперь использует exact owned files для dmesg/trace/profile/prefix, без очистки логов и ослабления guards. Ошибка воспроизведена external printf с 2 MiB журнала, исправление и отказ на oversized/read-error проверены независимо. Перед следующим live run обязателен committed/clean набор десяти executable Git blobs, записываемый в отчёт.
- [Отдельный optical analyzer](artifacts/p85_optical_qualification_20261108.md) требует завершённого cleanup, нового ROI review и временных границ по metadata/PTS; failed01 не выдаётся за пригодную stock/sham/return серию. Raw video/screenshots остаются приватными. Абсолютные Hz не выводятся из image rows или C1.
- Candidate по-прежнему не квалифицирован: measured baseline 34.389 с не проходит текущий conservative 45 с budget при отдельном 60 с watchdog. Следующий опыт — снова только заводской 15, после commit исправленного кода и fresh preflight. Прежний опубликованный checkpoint: `47a7782490f940560525865fefffdf38d8e4f728`. R3 >=2000 Гц не решена.

Checkpoint 2026-11-08, **stock brightness map завершена; C1 не является установленным счётчиком частоты.**

- [Квалифицированная stock-карта](artifacts/stock_c1_20261108_01/run.json): при одном native actual 120/group 3 DBV 828/460/2048/3000/3600/828 даёт C1 `00 02 B3 / 00 02 C0 / 00 02 26 / 00 01 30 / 00 00 60 / 00 02 B3`. Возврат точно воспроизведён; исходные настройки/native 828/logger восстановлены до снятия watchdog и mutex. Камера и неизвестные значения регистров не затрагивались. Новый gated reader проверяет фактические driver returns до следующего DSI, поскольку debugfs TX bytecount не доказывает успех передачи.
- Важное уточнение прежней гипотезы: C1 зависит от DBV, включая ненулевой младший полубайт. Общая модель «raw C1 или C1 >> 4 равен частоте/числу импульсов» не подтверждена. Семантика duty/off-time/width/status тоже пока неизвестна. Факт A9 `60 → 10 → 60` и подавление fine image-компоненты сохраняются, но не превращаются в доказанные one-count или Hz.
- [Сохранённая оптика DBV 828](artifacts/qualification_dbv828_20261108/result.md) показывает различимый период около 50.6 camera rows, как stock DBV 3600; это cross-session сравнение без синхронного C1. [Архивная серия 120/144/90](artifacts/stock_base_rates_20261107/reuse_index_20261108.md) уже покрывает простой six-pulse alias test, поэтому повтор тех же настроек ради того же вопроса не планируется. Ни один результат не доказывает >=2000 Гц.
- Завершённый offline suite после stock sweep: 115 tests, 2 skips. Следующая отдельная разработка — ограниченный 23:85 `15 → 14 → 15` runner с sham 15, same-video наблюдением, коротким независимым watchdog и обязательной stock-only квалификацией. Пока это offline; unknown-value 85 write не выполнялся.
- Предыдущий содержательный checkpoint опубликован, remote main проверен на `9f50b79f4c0e7cf671546ed355b6e6fcfeeaccf6`. Новый stock-map checkpoint готовится отдельно от незавершённого P85 runner. [Сводка цикла](artifacts/pwm_resume_20261108.md).

Checkpoint 2026-11-08, **A9+C1 причинная серия завершена; R3 >=2000 Гц не решена.**

- [Серия 06](artifacts/a9_c1_a001_20261108_06/c1_result.md): stock → A9-only → stock при DBV 3600 и native actual 120/group 3 даёт квалифицированный C1 00 00 60 → 00 00 10 → 00 00 60. Все три программы по 75 пакетов и полный stock/settings/native 828/ESD/camera/watchdog/mutex cleanup прошли без ошибок. Это поддерживает DC-like/one-count гипотезу, не high-PWM. [Same-video optical analysis](artifacts/a9_c1_a001_20261108_06/optical_result.md) воспроизводит 74.95% подавления тонкой image-code компоненты; возврат stock отличается на −0.51%, broad остаётся. Полный spectrum review и повторное декодирование пройдены. Physical Hz остаются unknown.
- [Новый ответ 23:85](artifacts/p85_live_20261108/stock828_long3_reanalysis.json): framed long3 15 00 00 при исходном DBV 828, WC/ECC/count квалифицированы offline из сохранённой пробы; строгий short1 reader корректно отверг неожиданный format. Повтора и записи в 85 не было. Width/semantics/volatility/read-write-plane identity неизвестны; postcheck stock/Enforcing/cleanup пройден.
- Native-mode preflight теперь использует проверенный stock-only 90 → 120 anchor, explicit actual-state evidence, quiet gates, локальную отправку пяти блоков и уникальные per-run markers. Серии 02–05 сохранены как failures до A9 candidate, а не объявлены успехом; guards не ослаблялись. Последний завершённый общий offline suite: 103 tests, 2 skips.
- Следующий безопаснее шаг: qualified stock C1 map в пределах native minimum DBV 460–3600. Unknown-value single-bit 85 proposal остаётся offline; live implementation ещё не квалифицирована.
- Второй checkpoint опубликован и remote main проверен на 610102c7abb0ef56a7106dc3ffbdd4040ac216f7. Новые результаты серии 06 и helpers готовятся к следующему содержательному commit/push. [Сводка цикла](artifacts/pwm_resume_20261108.md).


Checkpoint 2026-11-08, **R3 возобновлена новым автономным заданием владельца.**

- Новая миссия разрешает конечные ADB/root/DSI/settings/camera/reboot эксперименты на обоих устройствах без отдельного вопроса на каждый тест. Историческая пауза снята; safeguards и bootchain/flash проверки остаются. [Краткий текущий checkpoint](artifacts/pwm_resume_20261108.md).
- Текущие target/camera и приватный ADB tunnel проверены; обычная перезагрузка восстановила прежний root/Enforcing/build/slot/stock DC. Новый existing-server-only транспорт исключает запуск случайного ADB daemon; active-session camera parser различает preview и recording.
- Подготовлены новый same-video A9-only runner с проверенным redraw, stock-return и независимым reboot-watchdog, а также bounded C1 framing reader. 67 offline tests, 2 skips. Это ещё не новый PWM результат; ни частота>=2000Гц, ни C1 semantics не доказаны.


Checkpoint 2026-11-08, **remote ADB tunnel installed; two devices verified.**

- `03-investigation/adb-remote.md`: private user-service SSH tunnel to the USB host is enabled; directory/socket permissions 0700/0600. Read-only tests identified the target and separate optical camera, exercised shell, binary `exec-out` and `pull`, and confirmed recovery after a controlled service restart and simulated SSH exit. Fastboot binary is present on the USB host, but no device was in bootloader mode. No phone settings, DSI, camera recording, reboot or flash were changed.
- Isolated test confirmed that ADB may start a local daemon if the Unix socket is missing; matching client/server versions and the documented preflight are mandatory. AWG disruption, USB-host reboot, bootloader recovery and sustained 24/7 availability remain unverified. Host addresses, credentials and device serials stay private.

Checkpoint 2026-11-08, **рабочая папка скопирована на nc-lab; среда для офлайн-R&D восстановлена.**

- `/home/opencode/ai/legion-Y70-madness`: полное rsync-сравнение по содержимому и метаданным без различий на момент переноса, SHA256 двух boot-образов совпадают с исходником; исходник сохранён. На сервере пересоздана `.venv`, установлены Git LFS, ADB/fastboot, simg2img и erofs-utils; Ghidra 12.1.4 с отдельными PyGhidra и Temurin 21 перенесена и проверена. Системная Java осталась Temurin 8. Портированы пути домашнего каталога Ghidra и временных файлов теста. Удалённый offline unittest: 32 теста, 2 skip; Ghidra known-answer: 12 PASS. Существующий ключ пользователя настроен для GitHub в локальном конфиге копии репозитория; dry-run push успешен.
- Проектный MCP `4pda` восстановлен из исходного pinned commit `7ee79e7fa5712b05556cb653604c41f2cb8085fb`; конфиг запускает его через PATH, удалённый OpenCode подтвердил `mcp connected`, 3 инструмента. Существующая конфигурация OpenCode Console при проверке периодически отвечала HTTP 401; это не доказательство отказа других провайдеров.
- OpenCode `nc-lab` v2.2.5 под `opencode`: фактический `opencode run -m zai-coding-plan/glm-5.3-flash` из проекта с закрытым stdin вернул `READY`; предыдущие тайм-ауты неинтерактивной SSH-проверки были устранены перенаправлением stdin из `/dev/null`. Локальный OpenCode/backend, его база, сессии и учётные данные не переносились.
- Вне папки проекта остались прежние приватные кеши и несколько исторических скриптов с `/home/stfu/...`; перед их использованием или любым опытом на телефоне нужен отдельный аудит путей/данных и повторная идентификация устройства. ADB-доступ к физическим телефонам с сервера не подтверждён. Последняя зафиксированная цель — stock после подтверждённого возврата в08:12, не предположение о текущем состоянии; DSI/flash/reboot при переносе не выполнялись.

Checkpoint 2026-11-08 08:12 UTC, **HORIZON/R3 active; A0D1C1 ВОЗВРАЩЁН В STOCK по команде владельца.**

- После ручного опыта владелец попросил stock для live-проверки. [Отдельный отчёт возврата](artifacts/dsi_coupled_9d_20261107/owner_view/return/run.json): один stock batch75 пакетов, readback A9/9D `0E/0E`, DBV `0E10`, `stock_return_verified=true`, `target_restored=true`, `owner_view_active=false`, `pending_bytes_may_exist=false`, ESD `reg_read`, ошибок cleanup нет; Android manual52/min-max120/timeout1800000 и native DBV3584 подтверждены **при завершении runner в08:12:31 UTC**. Более позднее read-only значение native DBV **3356** при тех же Android52/power0/DC0: причина неизвестна, не фиксировать его новой записью во время проверки владельца и не выдавать3584 за постоянное live значение. Ни reboot/flash, ни повторного A0D1C1.
- По требованию владельца выполнена [офлайн-сверка сохранённых A001 видео](artifacts/dsi_coupled_9d_20261107/owner_view/optical_compare.md): stock DBV3584 против A0D1C1 DBV3600 при camera100µs/ISO6400. Fine image peak сохраняется примерно на95–98 строках, нормированные fixed-q93 амплитуды stock0.2804–0.3031, candidate0.2606–0.2926 **перекрываются**; крупного подавления в этих несопоставимых по DBV/времени видео не видно. Это не same-DBV причинный опыт, не измерение PWM Hz/огибающей; A9-only q93ratio0.2264067 остаётся лучшим доказанным промежуточным panel baseline. [Актуальный handoff](artifacts/dsi_coupled_9d_20261107/owner_view/plan.md); R3≥2000Гц не решена. Владелец просил затем зафиксировать документы и **остановить работы**; никаких новых DSI/ADB-настроек без новой команды.

Checkpoint 2026-11-08 07:57 UTC, **HORIZON/R3 active; A0D1C1 включён для ручного просмотра, НЕ stock.**

- По отдельному [ручному разрешению](artifacts/dsi_coupled_9d_20261107/owner_view/authorization.json) выполнена **одна** серия stock→A0D1C1 без автоматического возврата: [фактический run](artifacts/dsi_coupled_9d_20261107/owner_view/run.json) — 75+75 точных пакетов, readback stock `A9/9D=0E/0E`, candidate `0E/8E`, DBV `0E10`, `owner_view_active=true`, `pending_bytes_may_exist=false`, ESD `reg_read`, cleanup без ошибок. Кандидат оставлен активным намеренно; `stock_return_verified=false`, `target_restored=false`, return/run отсутствует. До опыта native DBV3584/Android manual52/timeout1800000/min/max120; при handoff nativeDBV3600 и временный timeout600000. Ни flash, ни persistence, ни повторов. **PWM Hz/комфорт неизвестны; A9-only q93ratio0.2264067 остаётся лучшим измеренным промежуточным panel baseline**, не частотой.
- Замена камеры — Nothing A001/Galaga, не исторические Pacman/G54: Open Camera1.56.2 настроена rear H264 1280×720 без audio, 100µs/ISO6400, AE/AF/OIS/EIS OFF, manual focus2.03874850, crop4080×3072. [Кандидатный ролик](artifacts/optical/a001_a0d1c1_manual_20261108.mp4) снят уже после ручной активации, экран в ROI `[540,190,60,500]` виден без насыщения, но нет одновременного stock-контроля A001 при DBV3600 (прежний stock A001 был3584): **физические ≥2000Гц и отсутствие огибающей не доказаны**. Владелец запросил паузу/перенос среды: не посылать больше DSI автоматически; безопасный [план handoff/возврата](artifacts/dsi_coupled_9d_20261107/owner_view/plan.md), return только по отдельной команде владельца или штатный аварийный reboot при неопределённой очереди. После sleep/reboot или переноса нельзя предполагать, что A0D1C1 сохранился.

Checkpoint 2026-11-08, **Charge-bypass RECON: `direct_power_supply` подтверждён на цели.**

- [Отчёт](artifacts/charge_bypass_recon_20261108/recon.md): на Lenovo Y70 (avr, глобальная Edge 70 Max, kernel 6.12.58) `direct_power_supply=1` даёт `CDIS=1`, голос `MMI_DIRECT`, батарея idle (`current_now=0`, `charge_counter` стабилен 60 с), USB/ADB живы; `force_charger_suspend=1` даёт `CSUS=1` и разряд ~200 мА при сохранённом ADB. Штатный GameMode имеет «Bypass charging» (только на время игры). План: парковка 60 % → bypass → `service.d` watchdog. Всё обратимо; `upper_limit` побочно стал 100 (reboot вернёт -1), разделы/boot не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; A0D1C1 однократно разрешён, НЕ запускался — камера G54 ещё не квалифицирована.**

- Владелец отдельно разрешил ровно одну `stock → A0D1C1 → stock` серию по [proposal](artifacts/dsi_coupled_9d_20261107/proposal.md), включая штатный аварийный reboot при неопределённой очереди; [точная запись согласия](artifacts/dsi_coupled_9d_20261107/authorization.json) создана, `run.json` отсутствует. Никакого flash/persistence или дополнительной DSI-серии. Для замены Pacman владелец разрешил установить Open Camera на Moto G54: установлен проверенный APK v1.56.2, фронтальная камера дала 720p H264 без аудио и два metadata100us/ISO6400/AE-AF-OIS-EIS OFF/focus0, но тестовый кадр был тёмным, Lenovo вне кадра. После сообщения владельца «развернул» приложение оказалось в photo mode, затем G54 исчезла из ADB; переключение в video mode и проверка нового кадра **не выполнены**. До повторной идентификации G54, кадра с Lenovo и ROI на экране панельный опыт не начинать. Исполнитель адаптирован для G54 и target-bound recovery, ближайшие5 тестов и независимое review PASS; исходный Lenovo UID0/Enforcing/DC0, последнее native DBV3584/power0, Android manual52/timeout1800000/min-max120/stay-on7. Панельные команды не отправлялись, R3≥2000 Гц неизвестна; A9-only q93ratio0.2264067 — промежуточный baseline, не Hz.

Checkpoint 2026-11-08, **HORIZON/R3 active; UEFI detection copy thunk checked offline.**

- [Bounded reference Ghidra check](artifacts/uefi_panel_recon_20261107/selection_followup.md): saved GLOBAL64 `DisplayDxe` detection thunk `0x1f8c4→FUN_00005668→FUN_00005a4c` guards length then copies memory; allowed briefs/excerpts have no direct EFI `DisplayPanelVer` SetVariable call. Independent scoped review PASS. This closes only the direct-writer hypothesis for this path, not other UEFI producers, current owner boot or physical PWM Hz. A9-only q93ratio0.2264067 remains intermediate; A0D1C1 exact approval/run absent; no device/DSI/camera action.

Checkpoint 2026-11-08, **HORIZON/R3 active; UEFI version-log wrapper checked offline.**

- [Bounded Ghidra brief/excerpts](artifacts/uefi_panel_recon_20261107/selection_followup.md) of saved GLOBAL64 `DisplayDxe` `FUN_0001f66c` show formatter→logger→canary handling, with no **direct** EFI `DisplayPanelVer` SetVariable call in this function; independent scoped review PASS. Other producers/indirect effects and the owner's executed UEFI/physical PWM Hz remain unknown. A9-only q93ratio0.2264067 is intermediate; A0D1C1 authorization/run absent; no device/DSI/camera activity.

Checkpoint 2026-11-08, **HORIZON/R3 active; conditional h1–h4 ranking checked after inverse Y'.**

- [Новая офлайн-проверка](artifacts/pacman_gn9_readout_20261108.md): на тех же6×75 stock кадрах pixelwise inverse BT.709 Y' распространена с `h1` на все4 пространственные гармоники. Условный MAE16 против ideal sinc изменился: GN9/full-window512.127Hz0.126349→0.131789, иллюстративные720Hz0.025371→0.038611,1440Hz0.088481→0.115448,2160Hz0.146042→0.170402; порядок четырёх ошибок сохраняется, но **не** измеряет физические720/≥2000Hz или отсутствие огибающей: Y'-обращение не радиометрия, сенсорный mapping и temporal-harmonic гипотеза не установлены. Независимое ревью пересчитало13,5 млн Y-пикселей, ratios и MAE16 без замечаний. A9-only q93ratio0.2264067 — intermediate; A0D1C1 exact approval/run отсутствуют, devices/DSI/camera не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; гармоники stock exposure sweep проверены совместно.**

- [Дополнительная офлайн-проверка](artifacts/pacman_gn9_readout_20261108.md): архивные camera-Y ratios `h=1…4` при четырёх выдержках сравнены с условной линейной sinc-моделью `h×f`. MAE16 для прежней совместной GN9/full-window512.127Hz —0.126349, иллюстративной720Hz —0.025371; отдельные 720Hz гармоники тоже расходятся, например `h3` при2000 мкс0.026518 против0.067257. Независимое ревью пересчитало все16 архивных отношений и четыре MAE16 без замечаний. Физические720/≥2000Hz **не доказаны**: временной порядок пространственных гармоник, installed camera mapping, ISP и линейность Y-кодов неизвестны. A9-only q93ratio0.2264067 остаётся промежуточным baseline, A0D1C1 exact approval/run отсутствуют; устройства/DSI/камера не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; BT.709 Y'-sensitivity на stock exposure sweep проверена офлайн.**

- [Новый pixelwise transfer-контроль](artifacts/exposure_notch_20261107/supported/envelope_check.md): для тех же6×75 stock кадров native limited-range HEVC Y и encoded transfer metadata `bt709` обращена Y'-функция до усреднения ROI. Fine q93.43 notch/control1428.571µs изменился0.032795→0.049325, rebound2000µs0.172537→0.294819; минимум остаётся, и условная GN9/full-window/одна синусоида512.127Hz (0.326305/0.023760) не согласуется с обеими точками. Это **чувствительность camera-code метрики**, не калиброванная радиометрия или физические OLED Hz/безопасность: Y' образован после нелинейного RGB/ISP, реальный сенсор/отображение строк и экспозиция неизвестны. Inline reproducer и независимый native-Y/QR/Fourier review PASS. A9-only q93ratio0.2264067 остаётся intermediate; A0D1C1 exact approval/run нет, устройств/DSI/камеры не трогали.

Checkpoint 2026-11-08, **HORIZON/R3 active; сохранённый stock exposure sweep проверен поперёк экрана.**

- [Новый bounded offline x-strip контроль](artifacts/exposure_notch_20261107/supported/x_strip_exposure.md): шесть исходных75-кадровых окон100→500→1000→1428.571→2000→100µs, пять экранных/заэкранных полос, два broad-q, detrend1–3, raw отдельно от moving-only. На1428.571µs moving-only broad camera-image амплитуда1.589 Y-кода, нормированная camera-code величина0.4352 от среднего двух100µs controls, x-когерентность трёх полос0.998–0.999, центр/заэкранная амплитуда33.53; это не физическая огибающая или PWM Hz. Fine total-RMS notch~0.0328 — **другая** метрика. Смешение двух q в первоначальной сводке найдено и исправлено до отчёта; source→JSON byte-exact, normal/`-O` no-overwrite, независимый пересчёт720 метрик PASS; неточность описания JSON исправлена. A9-only q93ratio0.2264067 остаётся промежуточным baseline; A0D1C1 exact approval/run нет, phones/ADB/DSI/camera не использовались.

Checkpoint 2026-11-08, **HORIZON/R3 active; broad-рисунок в архивной stock 720p→4K→720p проверен офлайн.**

- [Новый ограниченный контроль](artifacts/readout_resolution_scaling_20261108/result.md) на трёх сохранённых stock-видео: период moving broad в центральном окне после приведения к720p (detrend2) A1/B/A2=227.56/237.45/248.24 строк; raw=227.56/237.45/256.00. Напротив, fine~93–94. На трёх окнах, raw/moving и detrend1–3 широкий peak неустойчив (~195–431 строк, два поздних A2 на границе); same720p возврат дрейфует. Это не доказывает физический источник low envelope и не даёт PWM Hz: ROI500 строк вмещает лишь~1.15–2.65 широких цикла, camera-row mapping неизвестен. Независимое ревью декодировало41.25млн Y-пикселей и пересчитало54 пика (max RMS5.44e−15), PASS. Лучший panel baseline A9-only q93ratio0.2264067 не менялся; A0D1C1 exact approval/run нет, device/DSI/camera не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; сохранённые kernel traces проверены офлайн.**

- [Узкая проверка boot-version следа](artifacts/uefi_panel_recon_20261107/selection_followup.md): во всех99 частных `*kernel.txt` (52,144,946bytes) нет буквальных `DisplayPanelVer`/`readback_ver`/`mmi,panel_ver`/`panelVer`/`detected panel name`; три совпадения `ili97701a` содержат только software name, не версию. Архивные трассы не дали фактический UEFI readback, но отсутствие строк не доказывает отсутствие события или иной лог-формы. Не считывал телефон, DSI, камеру или новые identifiers. A9-only — промежуточный baseline, физические Hz неизвестны; A0D1C1 authorization/run по-прежнему нет.

Checkpoint 2026-11-08, **HORIZON/R3 active; проверен офлайн boot-variant fingerprint.**

- [Новая ограниченная сверка](artifacts/uefi_panel_recon_20261107/boot_fingerprint.md) эталонных UEFI v0–v4, трёх выбранных Android v4 массивов и четырёх прежних 4864-адресных DDIC архивов: из96 variant-dependent write-адресов 53 затрагиваются Android-массивами; ещё25 лежат на неархивированной page2F. Среди18 оставшихся архивных адресов 15 — v0-only page51 с4 совпадениями префикса и11 несовпадениями, 3 — v3-only нулевые page63:F8–FA. **Дополнительный полный отбор всех52 выбранных DT packet arrays/1101 пакетов** не нашёл иных записей по43 оставшимся адресам; это расширение только условного множества возможных writers, не live trace. Старый long-reader не квалифицирует длину ответа; отсутствие записи не задаёт DDIC default. **Live UEFI-вариант/PWM Hz не установлены**. Независимое parser-review PASS для первоначальных трёх массивов; полный отбор воспроизведён отдельно. A9-only q93 ratio0.2264067 — intermediate; A0D1C1 exact approval/run отсутствуют; device/DSI/camera не использовались.

Checkpoint 2026-11-08, **HORIZON/R3 active; экспозиционная фаза у notch проверена офлайн.**

- [Новый ограниченный фазовый контроль](artifacts/exposure_notch_20261107/supported/envelope_check.md) на сохранённом stock-видео: около изображения-перехода `1000→1428.571µs` fine-модуль q93.43 падает с4.547 до0.259–0.604 Y-кода. Оценённый фазовый сдвиг зависит от post-hoc окна минимум на1.37 рад, coherence может падать до0.42; индекс3297 — порог среднего Y, не sensor timestamp. Фазовый знак не квалифицирует фундаментал/≥2000Hz и не исключает envelope. Независимый численный review PASS; неточность «60 кадров» исправлена на50–60. A9-only q93 ratio0.2264067 остаётся intermediate; A0D1C1 exact approval/run отсутствуют. Телефоны/DSI/камера не использовались.

Checkpoint 2026-11-08, **HORIZON/R3 active; публичный GN9 readout-путь проверен офлайн.**

- [Продолжение source→archive анализа](artifacts/pacman_gn9_readout_20261108.md): pinned NothingOSS adaptor запрашивает readout line отдельно, но все три GN9 source variants в `GET_PERIOD_BY_SCENARIO` игнорируют readout-флаг и возвращают ту же6816-линию; adaptor округляет время строки вверх до6554ns. Его rounded-field×2296=15 047 984ns, что на354ns больше архивного Camera2 skew15 047 630ns; последнее совпадает с усечением *точного* GN9 span. Прямое копирование rounded-field отвергнуто **условно** для публичного режима, но installed HAL и физические OLED PWM Hz неизвестны. Независимый source/math review PASS, ссылки на смещённые строки `_16b` уточнены. A9-only intermediate0.2264067; A0D1C1 exact consent/run отсутствуют, устройств/DSI не трогали.

Checkpoint 2026-11-08, **HORIZON/R3 active; GN9 single-sine/exposure consistency checked offline.**

- [Офлайн-проверка совместной GN9/камерной модели](artifacts/pacman_gn9_readout_20261108.md): условные2296 строк/6816 clocks/1.04GHz и q93.43 дают512.127 Hz **только при равномерном полном sensor→720p mapping и одном синусоидальном компоненте**. Идеальная sinc-модель предсказывает для1428.571/2000 мкс ratios0.3263/0.0238, архивная Y-code метрика0.0328/0.1725; совместная модель не объясняет notch+rebound. Нельзя выбрать виновное допущение или объявить720/≥2000 Hz: installed driver/ISP/alias/линейность/огибающая неизвестны. A9-only остаётся промежуточным baseline, A0D1C1 authorization/run нет, телефоны/DSI не трогались.
- Follow-up к той же модели: публичный GN9 `write_shutter` пишет целое число строк в `0x0202`; если фактическая выдержка отличается от requested не более чем на одну GN9 video-строку (включая100-мкс controls), ideal512.127Hz sinc ratios остаются0.32157…0.33106 /0.02053…0.02697 для1428.571/2000 мкс против архивных0.032795/0.172537. **Только однострочное округление** не спасает совместную модель; фактические exposure/HAL/mapping и физические PWM Hz не установлены. [Условия и воспроизведение](artifacts/pacman_gn9_readout_20261108.md). R3 active, A0D1C1 approval/run отсутствуют; device I/O нет.
- Ещё один bounded source→model check: публичный NothingOSS `adaptor-ctrls.c` имеет `V4L2_CID_EXPOSURE` в целых строках **и** `V4L2_CID_EXPOSURE_ABSOLUTE` с шагом100 мкс, installed HAL-path unknown. При условной ошибке каждого exposure/control≤100 мкс ideal512.127Hz sinc ratios1428.571/2000 мкс ограничены0.25640…0.40158/0…0.07073, архив0.032795/0.172537 вне обоих. Это отсекает *только* указанную квантовку как единственную причину несовместимости всей простой модели, не измеряет PWM/Hz. [Контракт и границы](artifacts/pacman_gn9_readout_20261108.md); A0D1C1 без согласия/run, устройств не трогали.

Checkpoint 2026-11-08, **HORIZON/R3 active; public Pacman GN9 mode/skew comparison, offline.**

- [Новая source→archive сверка](artifacts/pacman_gn9_readout_20261108.md): pinned NothingOSS Pacman GN9/stech `normal_video` clock1040MHz × line6816 × height2296 даёт nominal span **15,047,630.769 ns**; сохранённые шесть PacmanPro Camera2 skew равны15,047,630ns. Source register table независимо задаёт те же6816/2296; JN1 и остальные GN9 modes не дают точного совпадения. Это сильная *гипотеза режима*, но public Pacman source не идентичен доказанному installed PacmanPro HAL, Camera2 activeArray3072→video mapping и фактическое sensor readout не квалифицированы; никакого физического PWM Hz/≥2000 вывода. A9-only intermediate q93ratio0.2264067, A0D1C1 отдельное разрешение/run отсутствуют; устройства/камера/DSI не трогались.
- Follow-up той же GN9-гипотезы, offline: три pinned source versions имеют одинаковые active `winsize_info[2]` и video registers: `8160×6144→4080×3072`, затем внутренний crop `(0,388,4080,2296)`; raw bounds `0x0318..0x1507` охватывают4592 строки, старт согласуется с `(0x0318−0x0010)/2=388`. Полный Camera2 `cropRegion=4080×3072` поэтому совместим с внутренним video crop, но не доказывает выбор режима на PacmanPro, ISP mapping или реальные PWM Hz. [Источник и ограничения](artifacts/pacman_gn9_readout_20261108.md); устройств не касались.

Checkpoint 2026-11-08, **HORIZON/R3 active; saved 4K simple-upscale control inconclusive.**

- [Offline test](artifacts/readout_resolution_scaling_20261108/result.md): по кадрам125/150/175 4K stock проверена реконструкция Y из каждой третьей строки/колонки билинейно (9 фаз): остаток0.785/0.797/0.785 Y RMS и2.13/2.33/2.15% пикселей>|2|. Синтетический 3× nearest A1 даёт0.469/0.434/0.451 Y, но не прошёл4K HEVC кодирование. Не исключены codec/ISP/другой scaler; sensor `N_eff` и PWM Hz не получены. R3 active, A9-only intermediate0.2264067, A0D1C1 без exact approval/run; новых device I/O нет.

Checkpoint 2026-11-08, **HORIZON/R3 active; offline BOE UEFI group discriminator.**

- [Шестигрупповой эталонный каталог](artifacts/uefi_panel_recon_20261107/selection_followup.md) побайтно равен GLOBAL64 и CN48 DisplayDxe: BOE group0 ожидает ID bytes `D2 00` и выбирает v1…v4 по second-read, отдельно названный BOE v0 group3 ожидает **`BF 00`** и не имеет version thresholds. Значит v0 не fallback при second-read0 **после D2 ID match в этом reference**. Сохранённые Android `panelId=d2/panelVer=0` не являются подтверждёнными UEFI-readbacks; current boot selection/физическая revision/частота неизвестны. A9-only baseline прежний, R3≥2000Hz active, A0D1C1 exact approval/run отсутствуют; телефоны/DSI не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; MP4 sensor-timebase metadata check (offline).**

- [Узкий follow-up](artifacts/readout_resolution_scaling_20261108/result.md): `ffprobe` трёх сохранённых stock A1/B/A2 MP4 не содержит frame side data либо названного sensor mode/row-time в format/stream tags; bitstream-copy и подсчёт HEVC NAL выявили только video frames/VPS/SPS/PPS, **SEI39/40=0/0** во всех трёх (349/350/349 кадров). Текстовые ключи rollingShutterSkew/sensorMode/sensorReadout/lineDuration отсутствуют. Это не исключает непрочитанные бинарные поля, vendor HAL или иной источник row-time и не измеряет PWM Hz. A9-only baseline0.2264067 прежний, A0D1C1 authorization/run отсутствуют; телефоны/DSI/камера не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; проверена геометрия сохранённого 720p→4K→720p (offline).**

- [Дополнение к readout resolution control](artifacts/readout_resolution_scaling_20261108/result.md): девять кадров125/150/175 A1/B/A2 независимо декодированы как native Y, B приведён ровно3×3 к720p. Экранные x-границы136–139/744–747, верхний переход51–58 нормализованных строк; x-профиль B↔A1 corr0.99878–0.99907. Независимое review подтвердило native bytes, downsample и численные ориентиры (max corr error5.6×10⁻¹⁶); [воспроизводитель/JSON](artifacts/readout_resolution_scaling_20261108/geometry_check.py) byte-exact, normal/-O существующий output сохраняется. Это подтверждает совпадение *геометрии изображения* в выбранных кадрах, но не sensor mode, `N_eff`, абсолютный PWM Hz или исчезновение низкочастотной огибающей. A9-only q93ratio0.2264067 остаётся intermediate; A0D1C1 authorization/run отсутствуют; устройства/DSI/камера не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; saved stock resolution/phase alias checked offline.**

- [Новый временной контроль](artifacts/readout_resolution_scaling_20261108/phase_alias_result.md) тех же stock720p→4K→720p Y-кадров: при fixed equivalent q93.43 центральные75 кадров дают sampled fine-phase drift1.124/1.204/1.394 цикла за номинальную секунду камеры; второй720p этап сдвинут даже сильнее, чем4K относительно первого. Значит разницу alias нельзя изолированно приписать изменению разрешения съёмки. Encoded PTS строго идут шагом3000ticks/1:90000 (видимые≤0.67µs — округление ffprobe), но это не сенсорные timestamps; окна перекрываются, физические Hz/огибающая неизвестны. Source→JSON byte-exact, normal/-O no-overwrite, 10 optical unit tests и независимый пересчёт27 компонентов (max slope diff6.22e−15) PASS. A9-only0.2264067 остаётся intermediate, A0D1C1 требует отдельного согласия; device/DSI/camera не использовались.

Checkpoint 2026-11-08, **HORIZON/R3 active; архивный 720p→4K→720p stock контроль геометрии.**

- [Новый офлайн-расчёт](artifacts/readout_resolution_scaling_20261108/result.md) использовал три сохранённых stock-видео и исходную HEVC Y-плоскость при DBV3600/DC0/requested120,100µs/ISO6400: fine period в выходных строках A1~93–94, 4K~278–282, A2~93; после деления 4K на3 все три окна и две image-гармоники дают тот же класс spatial period. Это проверяет нормировку камеры, **не** независимую sensor-row timebase: неизвестный `N_eff`, физический PWM Hz и безопасность остаются unknown. Independent review подтвердило41 250 000 raw-Y ROI bytes и27 peaks (max numeric difference8.88e−16); source→JSON/normal/-O checks PASS. A9-only q93 ratio0.2264067 — прежний intermediate, A0D1C1 exact consent/run отсутствуют, новых phone/DSI/camera действий нет.

Checkpoint 2026-11-08, **HORIZON/R3 active; ELVSS/HBM DIM OFF gate checked offline.**

- [Узкая target-module/DT проверка](artifacts/elvss_hbm_gate_20261108.md): `dsi_panel_get` в сохранённом current `msm_drm.ko` связывает `qcom,mdss-dsi-hbm-dim-off` с `panel+0xbea`; `dsi_panel_post_enable` допускает отдельный ELVSS descriptor только при этом flag и `read_elvss`. У selected BOE v4 в425 DT files нет gate/command set; в52 command arrays/1101 packets нет `B7`. Это закрывает только гипотезу о **готовом selected-DT ELVSS/HBM-DIM-OFF профиле**, не DDIC/Hz или других writers. Независимое scoped review target ELF/Ghidra/DT PASS без замечаний. A9-only intermediate0.2264067, R3≥2000Hz неизвестна; A0D1C1 separate approval/run отсутствуют, devices/DSI/camera не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; saved selector-video HEVC GOP diagnostic (offline).**

- [Новый bounded optical-method check](artifacts/selector_codec_gop_20261108/result.md): архивный HEVC содержит I-кадр каждые24 кадра (112 I/2567 P); ffprobe↔NPZ PTS различаются постоянными0.1025s. На пяти точных75-frame stock/A9/stock/9D/stock окнах broad phasor error у I кадров имеет ранг1/20/16/23/19 из24 фаз GOP. Воспроизводимого broad-скачка строго на I-кадре нет, однако P-frame codec/ISP артефакт, близость sampled alias~1.3Hz к GOP1.25Hz и физический источник полос **не исключены**. Независимое review пересчитало все2679×500 Y профилей,20 I/P и240 phase-медиан (max difference3.86e−15), PASS. A9 q93 ratio0.2264067 остаётся intermediate, PWM≥2000Hz unknown; A0D1C1 approval/run отсутствуют, device I/O не выполнялось.

Checkpoint 2026-11-08, **HORIZON/R3 active; moving broad pattern tested across saved screen image.**

- [Новое офлайн x-strip сравнение](artifacts/selector_broad_x_20261108/result.md) декодировало ровно архивные5×75 кадров и сверило центр Y с прежним NPZ побайтно по значениям. При удалении только стационарного UI-фона moving broad band около q=1/(3×93.43) когерентен между тремя разнесёнными экранными полосами (degree2 across five stages0.779–0.998), за экраном амплитуда слабее в20.3–26.6 раза. Under A9-only broad остаётся движущимся при подавленном fine. Это экранно-локализованный **камерный рисунок**, не доказанный физический low-frequency OLED emission, не измерение PWM Hz/безопасности. Raw с сохранённым фоном и degree1/3 sensitivity сохранены отдельно; A9-only baseline q93 ratio0.2264067, A0D1C1 exact approval/run отсутствуют, devices/DSI/camera unchanged.

Checkpoint 2026-11-08, **HORIZON/R3 active; broad/fine phase tested on saved selector video.**

- [Новая офлайн-проверка](artifacts/selector_broad_phase_20261108/result.md): пять сохранённых75-frame окон stock→A9→stock→9D→stock, fixed fine q1/93.43 и preselected broad q=fine/3±0.001. На degree2 фазовая связь при точном3:1 даёт0.743/0.366/0.462/0.547/0.558; соседние broad-q часто не хуже, а detrend1/3 меняет результат. Поэтому строгая модель «wide — устойчивый3:1 фундаментал fine» не подтверждена; физическую low-frequency envelope это не исключает, абсолютных Hz нет. [Script/JSON](artifacts/selector_broad_phase_20261108/analyze.py) воспроизводятся byte-exact; normal/-O существующий output не перезаписывают. A9-only baseline q93 ratio0.2264067 сохранён, A0D1C1 exact consent/run нет, устройства/DSI/камера не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; Ghidra page-base xref negative control.**

- [Офлайн-контроль метода](artifacts/uefi_panel_recon_20261107/selection_followup.md): четыре page-base адреса `DisplayPanelVer` в трёх сохранённых CN48 PE не имеют Ghidra xrefs, **но** две прямые ссылки на соседнюю `DisplayPanelName` обнаруживаются только по адресу строки, не её страницы. Поэтому пустая page-base ссылка не закрывает гипотезу PC-relative producer; дальнейшие одинаковые page-запросы не обоснованы. Целевой EFI variable/current boot/частота остаются unknown. A9-only — промежуточный baseline; A0D1C1 exact approval/run отсутствуют; телефоны/DSI/камера не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; saved Pacman camera mode metadata checked offline.**

- [Узкий повторный контроль timebase](artifacts/optical_readout_ambiguity_20261108.md): в сохранённом camera-service тексте (394719 bytes) нет прямо именованных `sensor mode`/`binning`/`line time`/`pclk`; stream/crop/readout не задают эффективный span активных строк для720-row видео. Это не исключает vendor HAL/неименованные поля и не превращает модельные512/686/2185 Гц в физический PWM. A9-only промежуточный baseline, A0D1C1 approval/run отсутствуют, телефоны/DSI/камера не затронуты.

Checkpoint 2026-11-08, **HORIZON/R3 active; v3-only page2F table checked against full saved UEFI XML corpus.**

- [Расширенный офлайн-контроль](artifacts/uefi_panel_recon_20261107/result.md): структурный проход всех82 XML сохранённого GLOBAL64 FV нашёл записи page2F только в ILI97701A v3 (24×3 монотонных16-bit значения, равных pinned Motorola DT v3); у выбранного target v4 в52 DT arrays page2F ранее не было. Никакого decoder-а частоты или готового v4-профиля результат не даёт, назначение таблицы unknown. Телефоны/DSI/камера не трогались, A9-only baseline и A0D1C1 exact-approval gate прежние.
- Дополнительный bounded XML-name check тех же82 профилей: из84 имён элементов только `DSIBitClockFrequency` (17 профилей) соответствует поиску `PWM/flicker/dimm/frequency`; у BOE v4 это 1.234 Gbit/s DSI, **не** OLED PWM. Именованного PWM-frequency поля нет в этом корпусе, но бинарная семантика DDIC остаётся unknown. [Границы](artifacts/uefi_panel_recon_20261107/result.md); новых device actions нет.

Checkpoint 2026-11-08, **HORIZON/R3 active; rate-switch interval multiplier checked offline.**

- [New bounded target-code/DT check](artifacts/rate_switch_interval_recon_20261108.md): `dsi_panel_parse_rate_switch_config` defaults multiplier to2 but separately reads an enable boolean that is absent from selected BOE v4 root+8 timings. Target `dsi_panel_switch` applies this multiplier to a minimum **millisecond interval between UI refresh switches**; conditional extra transmission is the same ordinary timing-switch set, not a ×2 OLED emission mode. Motorola source formula and target Ghidra excerpt agree; source comment at line8606 is not the executed formula. No physical Hz inference, A9-only intermediate baseline and exact A0D1C1 approval boundary unchanged. Offline only, no device actions.

Checkpoint 2026-11-08, **HORIZON/R3 active; EFI version static-pointer hypothesis checked offline.**

- [CN48 `DisplayPanelVer` pointer check](artifacts/uefi_panel_recon_20261107/selection_followup.md): в трёх сохранённых UEFI PE, ранее содержащих строки версии, нет exact32/64-bit указателей на эти строки и нет 32-bit aligned `.data`/DIR64 targets в пределах512B. PE `.reloc` разбор имеет позитивный контроль: уже известный callback `0x56150→0xbd74` присутствует как DIR64. Это исключает только *статическую таблицу указателей рядом со строкой*, не PC-relative/computed writer, текущую boot-переменную или другие firmware stages. Stock base-rate temporal alias уже рассчитывался раньше и не выдан за новый эксперимент; физических Hz нет. A9-only промежуточный baseline, A0D1C1 authorization/run отсутствуют; телефоны/DSI/камера не тронуты.

Checkpoint 2026-11-08, **HORIZON/R3 active; target PRR ioctl path bounded offline.**

- [Текущий модуль + выбранный BOE v4 DT](artifacts/partition_refreshrate_recon_20261108.md): Ghidra excerpts подтвердили, что `dsi_panel_parse_prr_config` сохраняет `qcom,partition-refreshrate-enabled` в `panel+0x898`, а `dsi_panel_set_partition_refreshrate` может отправить PRR-команды только при enable==1 и отдельном mode guard. В выбранном DT нет enable/PRR commandsets во всех root+8 timing nodes; одна запись DRM ioctl сама по себе может вернуть0 без DSI. Это закрывает только гипотезу о готовом *selected-DT* PRR high-PWM обходе, не исключает другое ПО/overlay и не измеряет Hz. A9-only baseline и A0D1C1 exact-consent gate прежние; аппаратных действий не было.

Checkpoint 2026-11-08, **HORIZON/R3 active; bounded offline temporal-alias test.**

- [Новый контроль сохранённого stock Pacman video](artifacts/temporal_alias_20261108/result.md): из двух100-мкс окон по75 кадров q93.43 fine-полосы имеют межкадровый наклон1.336/1.303 цикла/с, а q×2/×3 примерно удваивают/утраивают его. В первом окне encoded PTS почти равномерны (≤0.67 мкс): фазовая согласованность при условных alias1.336/721.336/2161.336 неотличима (~0.998). Во втором есть до134 мкс PTS-jitter, но **PTS не квалифицированы как sensor exposure timestamps**, и различие согласованности не выбирает физические Hz. MP4 содержит лишь HEVC/AAC, отдельного sensor-metadata track нет. [Reproducer/JSON](artifacts/temporal_alias_20261108/analysis.json) воспроизведён побайтно, normal/-O не перезаписывает output; independent numeric review PASS (до4.53e−14 расхождение). Только offline profiles; A9-only остаётся panel baseline (q93 ratio0.2264067, не Hz), A0D1C1 exact consent/run отсутствуют, ни телефон, ни камера, ни DSI не трогались.
- [Причинный контроль на прежнем panel-trial, без его повтора](artifacts/temporal_alias_20261108/selector_followup.md): все пять75-frame окон stock→A9→stock→9D→stock анализированы при **исходном фиксированном q=1/93.43**, нормированная амплитуда сверена с историческим q93 RMS (не путать RMS и mean). Stock/returns/9D дают согласованность одного фазового наклона0.994–0.997, A9-only0.408 при сильно ослабленном q (минимум амплитуды0.0524 против≥3.86 Y-кодов у остальных). Поэтому A9-only фазовый наклон полного окна не квалифицирует новое значение PWM; у 9D-only наклон1.464 сохраняется в следующем stock, что не изолирует causal frequency shift. Независимое численное review PASS (max8.88e−16), JSON побайтно повторён, normal/-O отказ от overwrite; это не отменяет сохранённое амплитудное улучшение A9 и не добавляет Hz; новые операции с устройством отсутствуют.

Checkpoint 2026-11-08, **HORIZON/R3 active; stock camera readout timebase bounded offline.**

- [Новая проверка Pacman rolling-skew](artifacts/optical_readout_ambiguity_20261108.md): сохранённое видео1280×720/q93.43 и metadata skew15.047630ms/active4080×3072 при простой равномерной модели дают *разные условные* f:512Hz (полный height),686Hz (16:9 crop2295),2185Hz (гипотетические720 эффективных строк). Фактический mapping и применимость preview skew к encoded mode не проверены; даже компонент q93 не определяет fundamental PWM. Это не опровергает старый exposure-notch аргумент за~720 fine component и не доказывает≥2000. Без новых device actions, A9-only intermediate baseline и A0D1C1 exact-consent gate сохранены.

Checkpoint 2026-11-08, **HORIZON/R3 active; cell-ID page serialization bounded offline.**

- [Current target-module Ghidra/selected DT check](artifacts/cellid_serialization_20261108.md): enabled `panelCellId_show` path sends `FF 5A A5 1D`, reads register80/23 bytes, then sends page00. In `dsi_panel_tx_cellid_cmd` prefix is **before** and suffix **after** the same panel mutex that encloses the stock DC sender's full descriptor loop; the page-send helper has no own mutex. Thus that narrower sequence is not atomic under `panel_lock`; actual concurrent invocation, transport-wide serialization and PWM effect unknown. Historical S0C1 logs had no page1D write. Cell ID content/privacy untouched; A0D1C1 remains not authorized or run, no new device actions. A9-only remains best intermediate optical baseline, not ≥2000Hz.

Checkpoint 2026-11-08, **HORIZON/R3 active; CN48 boot backlight path bounded offline.**

- [Новая Ghidra/PE-проверка](artifacts/uefi_panel_recon_20261107/backlight_followup.md): в сохранённом reference CN48 `BacklightDxe` передаёт brightness через протокол `+0x18` (indices0/3, не множитель); его GUID и registered method pointer в `DisplayDxe` совпадают. Метод обрабатывает index0 и property0 → config5 → indirect callback. **Binding исправил соседнюю гипотезу**: BOE v4 descriptor row#77 `0x558b8`→table`0x56128`→callback`0xbd74`→state+`0x3448`; `0xbbbc` находится в другом table. Реально привязанный к reference v4 `0xbd74` при type3 отправляет DCS `0x51` brightness. BOE v4 XML задаёт type3/14bit без PMIC PWM-frequency; generic WLED/PMIC-ветка соседнего callback не стала OLED frequency setter. Runtime *исполнение* reference пути/текущий target bootloader/физические Hz **unknown**. A9-only baseline не Hz; A0D1C1 authorization/run нет; ADB/камера/DSI/settings/flash/reboot не выполнялись.
- [Узкая офлайн-проверка готовности A0D1C1](artifacts/dsi_coupled_9d_20261107/proposal.md): все 52 выбранных DT packet arrays (1101 packets) разобраны. Все 33 изменённые пары (page,opcode) встречаются только в заводских DC ON/OFF arrays, ни разу в остальных50, включая 8 timing-switch/on/off. В уже сохранённой исторической S0C1 серии по трём наборам маркированных kernel logs: 75 table writes+один DBV replay на стадию, 0 DSI writes при redraw и post-read hold, без `LOST` в readback traces; это не прогноз для A0D1C1. Закрыта только гипотеза статической timing-перезаписи части C1; другие runtime writers/переключение DC и физические PWM Hz unknown. Candidate/stock SHA256 и 4 ближайших unit tests повторно проверены; exact approval/run отсутствуют, устройства не трогались.

Checkpoint 2026-11-08, **HORIZON/R3 active; CN48 ABL EFI-variable error branch bounded offline.**

- [Новая проверка](artifacts/uefi_panel_recon_20261107/selection_followup.md) двух callee из reference CN48 `MotoBootModule` `DisplayPanelVer` GetVariable-error branch: `FUN_00126040` — 5-instruction return; diagnostic `FUN_00001d2c` — условный non-return (`FUN_000b4840`) либо return. Его `uVar6` сначала отражает mask `auVar14 & 0x80000042`, **затем переиспользуется formatter-ом**; финальная ветка зависит от текущего значения, не только от исходного mask. Поэтому нулевой local **может** дойти до `/chosen` лишь при возврате диагностики; ни гарантированный fallback0, ни обязательный abort, ни live status/error не доказаны. Агент читал только Ghidra `brief`/`--lines` excerpts; полный C сохраняется во внешнем cache, но не читался. Независимое review подтвердило условный результат и нашло неточность о `uVar6`, исправленную в отчёте. Текущий bootloader/физическая silicon revision/PWM Hz unknown. A9-only intermediate baseline и A0D1C1 exact-consent gate неизменны; ADB/DSI/camera/settings/flash/reboot не выполнялись.

Checkpoint 2026-11-08, **HORIZON/R3 active; bounded CN48 EFI variable-name scan (offline).**

- [Проверка всех117 EFI PE в двух сохранённых CN48 FV](artifacts/uefi_panel_recon_20261107/selection_followup.md): terminated UTF-16LE `DisplayPanelVer` найден в `MotSolDxe`, `BacklightDxe`, `DisplayDxe` (UEFI116 members /8,421,376bytes) и `MotoBootModule` (ABL1 member); ASCII exact hits нет. [Reproducer/JSON](artifacts/uefi_panel_recon_20261107/version_producer_scan.json) сохраняет адреса/границы. Ghidra direct xrefs на version И соседний `DisplayPanelName` у первых двух модулей пусты; у DisplayDxe прямые version xrefs ранее также пусты. Литерал и пустые direct xrefs **не** доказывают ни writer, ни отсутствие indirect/computed writer; фактический current EFI variable status, UEFI `DC` read и физический PWM Hz остаются unknown. Независимое scoped review повторило117 членов/offsets/xrefs и прошло без дефекта; архивную загрузку не повторяло. Телефоны, камера, DSI/settings/reboot/flash не трогались; A9-only intermediate baseline и A0D1C1 exact-consent gate прежние.

Checkpoint 2026-11-08, **HORIZON/R3 active; новая CN48 bootloader-сверка, offline only.**

- [CN48 XT2611-1 RETCN W3WWL36.65-48-7 bootloader](artifacts/cn_48_7_recon_20261107/result.md): один публичный ZIP member `bootloader.img` извлечён ограниченными Range/If-Match с проверкой CRC32; контейнер36 записей/32 flash filenames, оба FV прошли `7z t`. Все9 BOE XML равны GLOBAL64 reference, включая ILI97701A v2/v3/v4=95/136/95 пакетов; DisplayDxe/BacklightDxe вне11 CodeView bytes равны GLOBAL64. Но `MotoBootModule` иной: CN48 Ghidra xref в `0xdaf28` и 118-line excerpt `DisplayPanelVer`→`mmi,panel_ver` совпадают с GLOBAL64 в этом узком сегменте. Это **не** current bootloader/UEFI executed profile/реальный DC-byte или PWM Hz. [Provenance, воспроизводитель и JSON](artifacts/cn_48_7_recon_20261107/bootloader_comparison.json) — в том же каталоге; script byte-exact, syntax/JSON parse и 7z проверены. Независимое review PASS, подтвердило binary/CRC/extraction/95 packets и excerpt, но не повторяло HTTP ranges. A9-only — лучший промежуточный optical panel baseline (q93 ratio0.2264067, не Hz); A0D1C1 exact consent/run отсутствуют, новые ADB/камера/DSI/settings/reboot/flash отсутствуют. R3 остаётся активной.

Checkpoint 2026-11-08, **HORIZON/R3 active; offline ABL→Linux panelVer bridge, not DDIC revision/Hz.**

- [New bounded reference-bootloader trace](artifacts/uefi_panel_recon_20261107/selection_followup.md): `7z t` both already saved CN11/GLOBAL64 ABL FVs passed; only `MotoBootModule.efi` extracted to approved cache. GLOBAL reference PE Ghidra xref/brief/excerpts show `DisplayPanelVer` UEFI `GetVariable` (shared namespace GUID with DisplayDxe `SetVariable` wrapper), then 64-bit big-endian `/chosen/mmi,panel_ver` write; current target Linux parser reads and sysfs formats this property, not a new DSI read. Same literal strings present in CN reference; its code not qualified, current XT2611-1 bootloader never read. Reference `DisplayDxe` has `DisplayPanelVer` strings but checked direct xrefs to the individual string addresses are empty; producer/actual variable value and live UEFI selected XML remain **unknown**. Android `panelVer=0` cannot be identified as UEFI `DC=0`; a failed/missing variable is a hypothesis, not proven live status. No new ADB/DSI/camera/settings/reboot/flash actions. A9-only remains best intermediate optical panel baseline (q93 ratio0.2264067, not Hz); A0D1C1 exact confirmation/run absent; PWM≥2000Hz unverified.
- Independent reference PE/GUID/DT-format review **PASS** without blocking defects; source GUIDs matched exactly but `DisplayPanelVer` producer was not established. Nine direct `DisplayDxe` SetVariable-wrapper calls span six functions; the three additional caller briefs yielded display override, PLL and generic-variable paths, not a verified version producer (indirect/dynamic names not excluded). [Additional bounded v3 table check](artifacts/uefi_panel_recon_20261107/result.md): all52 selected-v4 DT packet arrays/1101 packets contain **zero page2F packets**; among nine reference XML only ILI97701A v3 has the24-row table. It is not a ready runtime profile in selected DT. No Hz or live UEFI conclusion; R3 still active.

Checkpoint 2026-11-08, **HORIZON/R3 active; BOE UEFI selection evidence, not live boot identity.**

- [Новый offline selection reverse](artifacts/uefi_panel_recon_20261107/selection_followup.md): generic PanelSimConfig46 rows не содержит BOE; reference DisplayDxe содержит отдельный динамический path. Ghidra12.1.4 brief/excerpts `FUN_0000cb00` и `FUN_00009668` связали каталог6 групп/stride0x928, ID config `DA..D2` и version config `DC`, второй read low byte с32 threshold/name entries. [Результат](artifacts/uefi_panel_recon_20261107/selection_validation.json): BOE group0 thresholds `<1→v1,<2→v2,<3→v3,<255→v4`; byte255 без match в группе. Это *условная карта reference bootloader*, не выбранный UEFI-профиль текущего аппарата. Android target v4/IDd2/panelVer0 подтверждён ранее, но panelVer0 не приравнивать к UEFI second readback. Следующее отличимое офлайн-направление — происхождение Linux panelVer; boot-time trace/current UEFI не снимались.
- **Linux panelVer trace завершён**, addendum того же [selection follow-up](artifacts/uefi_panel_recon_20261107/selection_followup.md): current-target `dsi_panel_parse_panel_cfg` читает `/chosen` `mmi,panel_ver(_s)` в cached64bit field+0xad8 (initial default~0ULL); `panelVer_show` форматирует это поле, не читает DSI. Логированные DA/DB/DC — три младших байта *сохранённой property*, не новые аппаратные readbacks. Archived sysfs0 не равно default, но current `/chosen`, все дальнейшие writers и UEFI DC-byte не наблюдались; нельзя объявить ни v1, ни v4 boot selection из Android v4/panelVer0. CN48 static DTBO не содержит этой строки, dynamic `/chosen` не проверен. Independent Ghidra brief/excerpt review PASS; новых device actions нет.
- Для code-level PE понадобилось минимально добавить ARM64 PE32+ validator в `06-tools/ghidra_decompile.py`: ELF provenance неизменна, PE помечен `pe_type`, projects/temp в approved cache. Быстрые12tests/2known-answer SKIP, scoped29tests/2SKIP, независимые validator и selection reviews PASS. Selection JSON воспроизведён byte-exact, отказ от overwrite normal/-O сохраняет bytes/mtime; никаких новых device/DSI/camera/settings/reboot/flash действий. A9-only baseline прежний, A0D1C1 approval/run отсутствуют, PWM≥2000Hz не доказан.

Checkpoint 2026-11-08, **HORIZON/R3 active; UEFI BOE variant comparison (offline only).**

- [UEFI variant follow-up](artifacts/uefi_panel_recon_20261107/result.md): GLOBAL XML ILI97701A v2/v3/v4=95/136/95 init packets; CN=92/133/92 and each CN timing@0 init equals pinned public Motorola source for its own variant. GLOBAL selected v4 still equals saved actual DT timing@0. v2→v4 differ only in 1E:CA/CB/CC LHBM-labelled block; v3 has 41 extra pre-display-on packets including page2F:80..97 (24×3 byte-pairs) and63:F1..F4, latter exactly equal selected v4 native DC OFF. No new portable v4 PWM setter or Hz decoder established; v3 is not current selected software variant, physical revision unknown. [Reproducer/JSON](artifacts/uefi_panel_recon_20261107/variant_comparison.json) compare source/XML/current DT byte-exact; existing-output refusal normal/-O preserves size/mtime. No device/camera/DSI/settings/reboot/flash activity; A9-only baseline and A0D1C1 exact-confirmation gate unchanged.

Checkpoint 2026-11-08, **HORIZON/R3 active; новый offline optical-method check, не измерение Hz.**

- [Stock exposure-envelope check](artifacts/exposure_notch_20261107/supported/envelope_check.md) переиспользовал без новой съёмки шесть×75 сохранённых окон (ROI60×500) и старые decoded profiles: четыре detrend0–3, fine spatial band~93px при выдержке1428.571us даёт0.0400–0.0407 относительно двух100us controls (прежнее fixed-bin q93=0.0328), broad band270–435px остаётся0.415–0.465. Broad занимает лишь1.15–1.85 цикла на ROI, peak иногда на границе/чувствителен к detrend; остаток **не доказывает** физическую низкочастотную envelope. Идеальная integration даёт похожие ненулевые0.028/0.029/0.030 для720/1440/2160Hz: выдержка1428.571us лишь близка к общему zero1388.889us. Один notch не классифицирует частоту или полную безопасность.
- [Reproducer+JSON](artifacts/exposure_notch_20261107/supported/envelope_check.py) / [данные](artifacts/exposure_notch_20261107/supported/envelope_check.json): origin shape5939×500, окна/means/PTS и power partition проверены; source→JSON exact bytes, normal/`-O` refuses overwrite (bytes/mtime сохранены),4 ссылки иsyntax прошли. Independent optical review пересчитал degree2 spectra побитно с archived NPZ и независимо полиномиальным detrend/Fourier (max discrepancy1.33e-15); найденный им неверный термин «точная нулевая точка» исправлен в коде/JSON/report и узко проверен. A9-only baseline и approval gate не менялись, новых ADB/DSI/camera/settings/sensor/flash/reboot нет. Причинный panel-опыт A0D1C1 всё ещё ждёт точного отдельного согласия; его scope не расширяли новым shutter-тестом.
- Следующий независимый offline control на уже сохранённом stock120→144→120→90→120 (100us/ISO6400, тот же ROI/DBV): broad max при трёх одинаковых120 settings имеет периоды230.76→364.09→240.94px в **расширенной** полосе0.0015…0.005 (все максимумы не на границе); fine~94.16/93.62/92.56px. Воспроизводящая read-only команда и ограничения добавлены к тому же `envelope_check.md`. Фиксированный broad spatial peak не годится как численная калибровка, хотя физическая низкочастотная envelope этим не опровергнута.

Checkpoint 2026-11-08, **HORIZON/R3 active; DDIC response framing закрыт только в узком scope.**

- [Новый CRC/repeated-read анализ](artifacts/ddic_response_framing_20261107/result.md): `06-tools/analyze_ddic_transport.py` обработал 38 912 архивных 40-byte чтений / 684 уникальных строк и 80 native controls; `07:EC` и `23:C1` не содержат CRC-хвоста, единственное совпадение у `63:DD` не квалифицирует границу. Ghidra12.1.4 brief/excerpts + target ELF relocations показали запись helper в `ops+0x1F8` в обеих ветках setup; conditional index0 связывает её с controller, фактический live index неизвестен. Модель MRPS10→24→38→40 объясняет перезапись CRC и условный выход helper за **requested** allocation при коротком P≤10; это не доказанная порча памяти или реальные response WC. Независимое узкое binding review прошло без замечаний; сырой Ghidra listing агентом не читался после обновления AGENTS п.9.
- [Модель и тест](06-tools/test_ddic_transport.py): все P1…40 проверены по границам/условной реконструкции;1 regression test прошёл, archived JSON воспроизводится побайтно, normal/`-O` output refusal сохраняет bytes/mtime, целевые JSON/ссылки/syntax зелёные. Сохранённые архивы/кандидат/runner не менялись; устройства, камера, DSI, sensor, settings, flash и reboot не трогались. Веб-поиск exact ILI97701A/A9/9D не дал документированной карты PWM; рекламная региональная спецификация не доказывает её.
- Следующий причинный panel тест — [одна stock→A0D1C1→stock серия](artifacts/dsi_coupled_9d_20261107/proposal.md) с отдельным точным подтверждением владельца; **authorization/run отсутствуют**, общий доступ к обоим телефонам и HORIZON не являются им. Лучший A9-only baseline сохранён, high-PWM≥2000 Hz и пригодность нового профиля неизвестны. Не запускать legacy broad reader для квалификации этих raw.
- Следующий bounded offline lead: module strings показывают `dsi_panel_parse_freq_step_table` и `qcom,mdss-dsi-freq-step-pattern{1..8}-command`, но ни в root, ни во всех выбранных timing nodes BOEv4 (`artifacts/device_tree/selected_boe_v4/`) соответствующих properties нет. Это закрывает гипотезу о готовом **selected DT** freq-step commandset как обходном высокочастотном профиле; не исключает другие firmware/runtime writers и не измеряет физическую PWM.

Checkpoint 2026-11-08, **Ghidra brief/excerpt добавлены; только offline, основной PWM R3 не закрыт.**

- `06-tools/ghidra_decompile.py`: `brief` с обязательным function/address-selector, компактными metadata/xrefs/strings/scalars/jump count; `decompile --lines A:B` сохраняет полный C на диске и отдельный provenance-excerpt, ошибается вне диапазона. AGENTS.md п.9: агент читает brief/excerpt, не полный листинг.
- [DDIC-дистилляция и регенерация](artifacts/ddic_response_framing_20261107/ghidra_distill/README.md): 3 brief (`dsi_ctrl_cmd_transfer`, `dsi_ctrl_hw_cmn_get_cmd_read_data`, `dsi_catalog_ctrl_setup`), точная проекция прежних manifests; entries/515/211instructions/xrefs совпали, framing10→24→38→40 не противоречит brief, но его dataflow brief не доказывает. Исходный timebox неизвестен; команды регенерации с явным480s в README. Existing artifacts не редактировались.
- После сверки удалён **ровно** `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/ddic-response-20261107/`; `test ! -e` OK. Причина — `reported cyber_policy`-инцидент при чтении сырого экспорта соседним провайдером; регенерируемое сырьё заменено компактным представлением, frozen historical ссылку не переписывали.
- Быстрый gate9PASS/2SKIP; единственный полный known-answer11PASS/161.978s (wall162.04s); DDIC FIFO/CRC regression1PASS. Логи в новом `ghidra_distill/`; временные тестовые outputs только во внешнемcache, без перезаписи старых evidence. Актуальное foreground Sol-review `ses_e48264b6effedMBXF0v3Stm240`: PASS без замечаний; после него только запись вердикта в документах. Устройство/GUI/.venv/dependencies не затронуты; DDIC semantics/live framing/PWM Hz остаютсяunknown.

Checkpoint 2026-11-07, **Ghidra toolkit завершён; основной OLED/PWM R3 остаётся active, не решён.** Офлайн-интеграция без ADB/fastboot/DSI/sensor/GUI/flash/reboot; A9 baseline и approval gates не менялись.

- [Toolkit contract](artifacts/ghidra_toolkit_contract_2026-11-07.md) R1–R5 закрыты: Ghidra12.1.4 с официальным ZIP/SHA256 в `~/tools/ghidra-12.1.4`, отдельный offline PyGhidra3.1.0 venv; единый `06-tools/ghidra_decompile.py` (`functions/decompile/xrefs/symbols`, provenance, deterministic exports, timebox, проекты/JVM temp только во внешнем cache).
- [Evidence/команды](artifacts/ghidra_toolkit_20261107/result.md): быстрые5PASS/2SKIP, полный known-answer7PASS/97.237s; `.ko`153instructions/65536clampcases/0mismatches, ALS threshold3601 (из XML, не binary immediate), `.gnu_debugdata`467symbols>164dynsym с восстановленным local imported именем. [Sol review](artifacts/ghidra_toolkit_20261107/review.md): PASS последней runtime-версии, замечаний нет.
- [Supersession-реестр](06-tools/archive/README.md) оставляет исторические evidence на месте; data/build/test-скрипты и `.venv` не менялись. Ghidra не закрывает DDIC-семантику/оптическую PWM-частоту. Основной агент может продолжать; активных toolkit jobs нет.

Checkpoint 2026-11-07, продолжение после рестарта: **R3 active, не решена; A9-only baseline сохранён.** Новых DSI, sensor activation/calibration, settings/flash/reboot нет. Read-only ADB был: прежняя инвентаризация display-каталогов и свежая идентификация двух телефонов; прежняя верхняя формулировка «нет новых ADB» больше не описывает весь follow-up.

- **После нового HORIZON — новый offline reverse завершён, новых ADB нет:** [registry/config→ADC](artifacts/flicker_registry_recon_20261107/result.md). Target callback0xb231adb4 найден в уже сохранённомb21:10literal names→fixedbytes557..566/masks→6triples→initialtable. Packet-binding callback/destination иcallmerge сr0=state+628/r1=6 проверен; CNdefaults сохраняют все24initialbytes (не liveconfigidentity). Writableb22 не означает произвольныйregistrysetter: merge ограничен8addresses01/02/05/06/60/DB/6A/6B иVA≤0xb259ddf7, timing03/04/0E иmode2de00 через него не меняются.785freshrecords/9ranges,6directmodecalls,256register-modelcases; две независимые проверки без замечаний, обаJSON воспроизводятся побайтно, normal/`-O` outputrefusal зелёные. Новый инструмент/evidence: `artifacts/flicker_registry_recon_20261107/verify.py`,2JSON,4reportlinks.
- Registry-вывод **не** исключает всеwriters/indirectpaths: физическийэффектwait05/06, liveconfig иgenericdecoder schemaunknown. Decoder0xb20c854c/7d44 относится к несохранённомуtargetb29 (VA0xb20c7000/filesz181836); для уже восстановленного10-key callback он не нужен. Общийcalibrationtail вызываетbcd8/bac8/indirectmethods, полныеsideeffects не закрыты; поправленыRECONошибки: groupstringb240b3d0, неb328(NUL), bac8кодирует/отправляет513, не доказанное«чтение». Ничего на устройстве не исполнялось; новойбыстройADCнастройки/PWMsetter нет. Отрицательныйboundedрезультат закрывает этотprivate.configпуть, неR3; A9baseline сохранён. Следующий готовыйcausalpanelопытA0D1C1 остаётся заexactapprovalgate, approval/run отсутствуют; активныхjobs нет.
- `confirmed-on-target`, свежий read-only срез после рестарта: Lenovo transport2, XT2611-1/avr, W3WWS36.65-64-4-1, UID0/Enforcing, прежний KSU kernel; BOE ILI97701A cmd_v4/IDd2/Ver0, panelDC0/logger0/nativeDBV828. PacmanPro/A142P — transport1. Выполнены только allowlisted getprop, id, uname, getenforce и чтения software panel/backlight attributes; содержимое калибровок, DDIC registers и камера не читались. Transports не считать постоянными. Доступ к обоим телефонам разрешён владельцем; это не авторизация новой DSI-серии.
- [Transport follow-up](artifacts/ddic_state_marker_20261107/result.md):750 current-target ARM64 words проверены; long-copy проверяет allocation, но не response word count. [C harness](artifacts/ddic_state_marker_20261107/long_read_counterexample.c) под pinned Clang ASan/UBSan:7cases+1модельный panic-path, diagnostics0. Контрпример requested3/WC1 возвращает3 с payload+CRC; **это не доказательство CRC в архивномC1**. Ревью выявило существенную поправку: при нарушении allocation target вызывает`__fortify_panic`, а не возвращает`-1`; ELF CALL26 relocation независимо подтверждена, модель/отчёт исправлены. System GCC runtime отсутствовал; существующий Clang с sanitizers сработал.
- **Новый вывод о готовности A0D1C1:** actual reader запрашивает1/1/2, exact dictionary guard проверяет bytes и длины; controller return проходит через debugfs без дополнения до requested length. При корректном short response long-copy контрпример неприменим. Неожиданный long type в4-byte buffer может вызватьpanic, но такой ответ наA9/9D/52 не установлен; raw response header/WC/HW count в архивных traces нет. Независимое ревью завершено, parent проверил ветки/relocation/length consumer; нового блокирующего guard-дефекта не установлено. Это не live qualification и не разрешение запуска; kernel/runner не правились.
- [Marker/checksum/C1](artifacts/ddic_state_marker_20261107/result.md):07:EC2F/10 остаётся наблюдением, не setter. Target mot_tcmd315words: CRC32 относится к SigRsp, E5 —legacy hub↔display. ILI9881C PDF показывает register-checksum у другого DDIC: зависимость отDBV без зависимости отcontent не доказывает emission. 23:C1`00 00 65/10/55/65`: naive high-nibble×requested-refresh даёт720/720/360 для lowstates; decoder отсутствует. Same-key IL79900A donor имеет иной DSC register map и не даётEC/C1/EM decode; байты не переносились.
- [Calibration consumer](artifacts/display_calibration_recon_20261107/result.md): target только find/ls metadata; reference CN libstcMotoColor читает17³ LUT и3×11 PCC, PostBlendGamut получает16+4913×24bytes.1786ARM64words и полные таблицы повторно сверены после рестарта; independent calibration/C1 review завершено без замечаний. Current target library/content identity не установлена; LUT/PCC не менялись и не предлагаются как PWM.
- Ранее завершённые ветки не переоткрывать как новые результаты: [message700](artifacts/flicker_rate_reachability_20261107/result.md) —220records, descriptor0xb20d635c в несохранённомb29, fixed ADCmode2; [UEFI](artifacts/uefi_panel_recon_20261107/result.md) —95GLOBALv4packets равныactual timing@0, PE отличаются только11CodeViewbytes; [DDIC/source](artifacts/ddic_table_format_20261107/result.md) —8passes/80prefixes/40quartets/407files/902refs; CN48/LUT/LTPO/init/runtimePWM также уже проверены. Ни один отрицательный результат не закрывает R3.
- Следующий подготовленный причинный panel-опыт — [stock→A0D1C1→stock](artifacts/dsi_coupled_9d_20261107/proposal.md), DBV3600/requested120/DC0,7s holds, readback/camera/trace/stock-return и emergency ordinary reboot. **Точное подтверждение отсутствует, authorization/run не созданы, опыт не отправлен.** Старые approvals потреблены. Отдельный07EC/content/DBV scope также не разрешён/не запускался, runner для него не создан; legacy broad reader не запускать. Blocker относится к конкретной аппаратной операции, не к доступности телефонов и не к возможности R3.
- До новой registry-ветки:16ближайших offline unit tests прошли; marker JSON заново вычислен из8rawpasses/52nativearrays,8C1prefixes/арифметика сверены сraw,4modepackets сDT. Scoped gate тогда:15JSON/42локальные ссылки/4Python syntax checks. Независимая проверка short-read guards завершена; аппаратных/build jobs нет. All-repository green не заявляется: отсутствующие05-safety и NUL-содержащие legacy документы не исправлялись догадками.

Follow-through2026-11-07: CN48vendor_boot additionallyrange-extracted(7.37MBdownload),ZIPCRC/LZ4/newc/nativeCPIOverified. [CN48modulecomparison](artifacts/cn_48_7_recon_20261107/result.md): moduleSHA d3519a51…b52d isbyteequaloldGLOBAL64-4;currentOTA differsONLYBuildID/localUNIQUE_IDnames,allothersections+21RELA/103589resolvedentriesequal.8PWM/DC/APLowners and118panel-functionnames equal;no newCN48setter. Parentindependentlycheckedallsectionattributes/relocations;source-rebuild/wholeROM/physicalHz remainunknown. No codeinstalled/deviceactionsinthisfirmwarebranch. Bothnewofflinehypothesesnowhaveevidence,notpendingtasks. R3active,A9baselinepreserved,A0D1C1exactapprovalabsent/notrun;noactivecapture/build/subagentjobs.

Current checkpoint,2026-11-07: **R3 active, not solved; A9baseline preserved.** [Brightness/LTPO reverse](artifacts/brightness_policy_recon_20261107/result.md): targetLUT doesnotreachDBV (153instructions/65536clampcases); currentDolbycaller→id0/val→ioctl0x4008649b→APLgate closed; currentSFloaded1/10thresholds0/9999999,flag1,bothidleprofilesnominal120 (195instructions/16modelcases), notDDIC/PWMHz. Read-only5ELFidentitybridge+policydump, independentreviews passed; cached5base+5selectorholds havenotimingswitch. Then [newCN48-7 DTBO](artifacts/cn_48_7_recon_20261107/result.md) range-acquired withCRC/sourceidentity checks: **53commandproperties =52packetarrays+1TEu32 all equalcurrentv4**,412sharedpropertiesequal;12changesfromoldCN11-18alreadyincurrentGLOBAL. IndependentDTCbinaryroundtrip preservesall14631properties; text-roundtrip's6nonpanelescapechangesdiagnosed/notused. Reproducer/determinism/outputrefusal/syntaxpassed. NoDSI/flash/reboot/settingswrites. Missingnextcausalevidence remains targetemissionregistermapping/opticalresponse; preparedA0D1C1serieshasnoexactapproval andnotrun. Do notmarkgoalcomplete, repeatconsumedtrials, turngenericdimming/LTPOintoHz, ordownloadsameCNtablesagainasnewhypothesis.

Latest checkpoint,2026-11-07: [factory/flicker-sensor reverse](artifacts/flicker_sensor_recon_20261107.md) completed this bounded hypothesis. LiveSTK6A2X/type65588 andconfigFLICKER_ITEM2 confirmed; target/CNqshHAL byte-identical, targetADSPb21/b22/b27/mdt root-read/identified separately. Target0x2bf→event mapping provesvalues[2]=1000×strongestFFTpeak,values[6]=samplingparameter; CQAdivides[2]by1000. Defaultflickermode2 sets03/04/0e masks yieldingX30/Y23or31 → samplingparameter1025or1018, largestFFTcoordinate510/506; conditionalHz model aliases2160to110/124. All256prior0e states and1,048,576timingfield combinations checked; synthetic alias equivalence<2.8e−13; independentpacket-aware reverse corroborates. This rejects stockCQAas≥2kHzmeter, notsensorhardwarecapability/goal. No rawI2Cread/write, sensoractivation, CQA/calibration, DSI/flash/reboot. LegacyPWMhelper currentbyte-range alsoverified: onlyobakem/falcon, brightness51 00, notavrHzsetter. A0D1C1 authorization/run stillabsent;A9baselinepreserved;R3open.

Updated: 2026-11-07, owner-reference photo/video offline experiment completed after camera setup. **R1/R2 done; R3 active, not solved. Analysis resumed on new Nothing reference; no new panel experiment.** Last verified panel return was stock09:58UTC after owner-rejected S0C1. Owner directs large2–3× frequency-increase attempts, forbids small increments and accepts panel destruction; recorded in the [execution contract](artifacts/unlock_pwm_recon_2026-11-06.md). New composed DSI programs still require exact-operation approval. HORIZON requires optical evidence, changed methods after negative hypotheses, no inventedHz and unchanged operation boundaries.

- New [Nothing-reference offline result](artifacts/nothing_reference_20261107/result.md): owner JPEG EXIF99999ns/**ISO6592**,4096×3072; existing owner video read-only copied to private cache,165frames1280×720/~30fps fully decoded.6photo+20video spectra preserve stationary bands; dominant periods58.935–59.796px and18.450–18.789px; medianratio3.1884 vswidthscale3.2. Four local2D fits confirm slanted fine-train. This is a saved optical reference/method baseline, not panel improvement or replacement ofA9. Conditional2160Hz/timeaxis/full-array assumptions imply23.78–24.13ms versus separatepreviewHAL27.01ms; no calibratedHz assigned. Camera2primaryXML confirms activeArray first→last+1 andN/Hcrop scaling;3071→3072 convention fixed.10 nearest tests, syntheticphase checks, full rerun and independent review passed. R3 remains open; A0D1C1 authorization/run remain absent.

- `confirmed-on-target`: [Lenovo reference-camera setup](artifacts/lenovo_reference_camera_20261107.md), Open Camera1.56.2 APK copied from Nothing and installed identity verified. Camera2/ISO6400/100us request (99999ns result), manual focus9.117527 request (9.17431259 result), AE/AF/EIS/OIS OFF results,1280×720 HEVC/~30fps. FPS30 chosen to match Nothing's actual~30, not its stored24. One61-frame2.033s technical video fully decoded; app-restart persistence and final ready/not-recording UI verified; monitoring stopped and own phone test/UI files removed. Evidence private0700/0600 in `lenovo-reference-camera-20261107/`. Nothing2160Hz is owner-confirmed `reported` reference, not a new measurement. Readout skew differs27.01ms vs15.60ms; no direct bands→Hz claim. Nothing display settings untouched; no DSI/flash/reboot or A0D1C1 execution. Camera task complete; optical shot by owner pending.

- `reported`, owner directive now persisted in [.opencode/horizon-goal.md](.opencode/horizon-goal.md): **verified improvement becomes the next experimental baseline**. A9-only q93 total0.2264067 is a valid intermediate panel improvement, not ≥2000Hz proof; retain it while comparing new candidates and stock. Camera-only notch remains measurement evidence, not a panel change. Requested OpenCode service restart verified by PID1404379→1407592 and healthy `/api/info`; same session resumed, no phone reboot. Evidence in `/home/stfu/.cache/opencode-tmp/opencode/pwm-opencode-restart-20261107/{before,after}.json`.
- `reported`, offline target-ELF verified: [runtime PWM branch analysis](artifacts/runtime_pwm_recon_20261107/result.md). All three `pwm_apply_might_sleep` call sites require backlight type0; selected live `bl_ctrl_dcs` maps to type2 and uses DCS brightness. Primary DC map has only0/1; positive values≥2 clamp to1, not ×2/×3. Checked twelve function bodies, target ELF relocations and live DT. No separate OLED frequency field in these checked branches; this rejects that specific ready-runtime-switch hypothesis, not the goal or all possible module paths. No device actions in that analysis.
- `reported`, new [init-payload reverse](artifacts/init_payload_recon_20261107/result.md): all8 live init arrays contain99 chained bytes on07:81/FE =5zero prefix+94bytes exactly matching captured native DSC PPS; remaining34PPS bytes are zero. The long page1E block matches source-labelled LHBM; common2D tail matches source-labelled1Hz transition/low-refresh DBV dimming. No whole-source match or EM field map inferred. Reproducer/byte checks/determinism/exclusive-output refusal passed; no device I/O. This rejects these particular ready-EM-table leads, not high-PWM capability.

- `reported`, new source lead: [community/OTA follow-up](artifacts/community_pwm_followup_20261107.md) identifies Android17 **AI71WWH.15-43**,2.59GB, from original screenshots in the exact Y70-2026/Edge70Max thread. No package in checked TELEU/RETEU mirror indexes; no exact-tag-prefix refs in the two Motorola display repos. Target read-only OTA cache check succeeded after correcting host `su -c` quoting: UID0/ksu/Enforcing/current Android16 reconfirmed, all3SQLite copies quick_check=ok, both OTA version/history tables empty. No download URL available; **no OTA poll/download/install**. Raw prefs/DB contain credentials and remain private0600 in approved cache; never publish them. No novel register map in patent figures, no new DSI sent. New firmware tables cannot yet be compared without the package/source; exact S0C1 approval is still absent.

- `confirmed-on-target`: changed [supported-exposure result](artifacts/exposure_notch_20261107/supported/result.md) completed100/500/1000/1428.571/2000/100us at fixedISO1600/stock120/DC0/DBV3600. Normalized q93 ratios0.9766/0.8891/0.3403/**0.0328**/**0.1725**/1.0234 show a minimum and rebound, not merely altered spatial spacing.5939frames,6×75 windows, six same-DBV writes,33 controller returns>=0/misses0. Better supports~720Hz component under an ideal integration model, but physicalHz/fundamental and>=2000 remain unknown. Decoder input-timebase fix removed two muxer-DTS warnings; redecoded profiles are bit-identical and sourcePTS strictly increasing. The earlier [failed700us control](artifacts/exposure_notch_20261107/failure_validation.json) is preserved: cameraUI jumps500→1000us, not a panel failure; guards/tolerance were not weakened. No hardware/subagent jobs running. Transports47/67 re-identified; refresh before further device actions.

- `confirmed-on-target`: one native120→144→120→90→120 control completed atDC0/DBV3600, fixed camera/redraw. [Result](artifacts/stock_base_rates_20261107/result.md): fine spatial peaks94.16→87.61→93.62→92.56→92.56px; sampled temporal alias stays~1.3cycles/s, not physicalHz.62 timing packets,10 same-DBV writes and1 stock PPS matched;85 controller returns>=0, misses0, no writes during holds.2845 frames decoded,5×75 central windows, full spectra and stationary-preserving phase diagnostic. No raw DSI/read-page writes, ESD disable, reboot or flash. Do not repeat as a small-step solution. Early-source follow-up is complete: [findings](artifacts/em_field_recon_20261106.md) identify24:91 paired-selector hypothesis and many-field v1→v2 replacement by A9/AA plus other tables, not a decodedEM multiplier. No speculative candidate applied.
- `confirmed-on-target`: [S0C1 result](artifacts/dsi_coupled_on_20261107/result.md), separately approved once and returned stock09:44UTC.1671frames/3×75windows;225 table packets,37 tx callbacks0,300 controller returns≥0,9 reads,misses0. q93 total ratio **0.936347949**, same93/46.5/31/23.3px train; no large optical shift or≥2000Hz proof. Owner separately requested manual viewing, then explicitly rejected it as unusable (`reported`). [Manual return](artifacts/dsi_coupled_on_20261107/owner_view/return/validation.json) completed09:58:08UTC, stock/ESD/logger/Enforcing and captured native828/policy restored. Both scoped operations consumed; no replay. Tests14 passed; no emergency reboot needed. A9-only remains the saved intermediate baseline, not a usable≥2000Hz solution.
- `reported`, offline progress: [16 conditional threshold models](artifacts/dsi_coupled_on_20261107/threshold_models.json) reject a plain unsigned A9/AA threshold; signed/flag interpretations remain distinct. Bulk51/52/53/63 source parsing and history do not identify frequency encoding; private supplier reviews are DNS-inaccessible. [OTA metadata reverse](artifacts/ota_metadata_protocol_20261107.md) found device-specific check-in, not an anonymous build catalog; no requests/identifiers sent. [Owner rolling-shutter hint](artifacts/owner_camera_hint_20261107.md) saved with target-geometry caveats. Its stationary-band point also checked on361 cached native-ON frames: [v2 result](artifacts/optical_repair_20261107/native_on_cached_spatial_v2.json), after-redraw total ratio0.3849304, unchanged qualitative conclusion.
- `hypothesis`, next offline-built [A0D1C1 control](artifacts/dsi_coupled_9d_20261107/proposal.md): native ON with only A9 OFF,9D ON. Unlike tested9D-only it uses C1; unlike S0C1 it enables9D. Two parsers validate875bytes/75packets; not previously present among7 archived candidates. **Unapproved/unrun**, not a decoded×2–3 setter. Existing runner/analyzer now bind `--coupled-9d` to its own exact authorization/hash/sequence/readback; [offline validation](artifacts/dsi_coupled_9d_20261107/runner_offline_validation.json):16 tests, syntax/CLI refusal and independent review passed. No new device action; current request is offline work.

- `reported`, offline-verified: repair-kit helpers/tests are in `06-tools/`; spatial-v2 is integrated into the existing `analyze_dsi_redraw.py`, including `--selector-split` and native/readback checks. Twelve tests and syntax checks passed; both original videos reanalysed into separate v2 outputs (2679/4617 frames). Historical analyses, videos, caches and source kit retained. [Verification](artifacts/optical_repair_20261107/spatial_v2_review.json): all14 original windows preserved, old q93 metric reproduced as **incoherent**, and total power = coherent + incoherent. Cached CLI independently reproduces the five selector windows to <1e-12. Both archive audits ran on actual artifacts. No device/camera operations in this integration.
- `confirmed-on-target`, captured selector result: isolated23:A9=8E suppresses the fine image component; isolated24:9D=8E does not. Corrected **total** ratios are **0.2264067 / 1.0214238**, not the historical incoherent0.2241833 /1.0210592. [Result/addendum](artifacts/dsi_selector_split_20261107/result.md). Broad structure remains; physical Hz and a>=2000Hz profile are `unknown`. Each candidate applied once; readback8E/0E versus0E/8E and stock0E/0E,375 table packets,15 reads,61 callbacks0,444 controller returns>=0/no misses. This authorization is consumed, not extended.
- `hypothesis`, completed method check: same-row 2D phase projection can remove panel vertical phase, but current near-parallel geometry has condition number roughly100–1000, varying local slope and unverified sensor/output timing. No trustworthy Hz recovered. Final [2D report](/home/stfu/.cache/opencode-tmp/opencode/pwm-2d-phase-20261107/REPORT.md), [result](/home/stfu/.cache/opencode-tmp/opencode/pwm-2d-phase-20261107/final_result.json) and [synthetic validation](/home/stfu/.cache/opencode-tmp/opencode/pwm-2d-phase-20261107/validation.json) retain stationary stripes. Next optical method would use a physical camera roll near90° relative to OLED rows, not a repeated A9/9D trial or a software image rotation; no such capture performed.
- Latest [stock return](artifacts/dsi_coupled_on_20261107/owner_view/return/run.json),09:58: stock/ESDreg_read/logger0/UID0/Enforcing; own probes/files removed; capturedmanual52/nativeDBV828/requested120/30min restored. Camera recording stopped09:44 and was not touched during manual viewing/return; prepared100us/ISO6400/manualfocus/AE-AF-OIS-EISoff. True original auto/no refresh override/5min/stay-on0 and Pacman originals remain due at final session cleanup. No flash/reboot/persistent PWM change.

## Known facts

- Owner's reference image now received: one original camera JPEG copied from Lenovo `DCIM/OpenCamera/IMG_20261107_103657.jpg` to `/home/stfu/Downloads/Nothing_PWM_Lenovo_20261107_103657.jpg`,995569bytes, source/copy SHA256 equal. Source retained, image opened and visible fine diagonal bands confirmed; Nothing identity/2160Hz remain owner-reported. This supersedes the earlier camera-checkpoint note that the owner's optical shot was pending; no Hz inference or image processing performed.

- Validation note for2026-11-07 readback checkpoint: run/native/readback/cleanup assertions and newly added links passed. A broader legacy-link check did not pass because `05-safety/optical_measurement.md` (the whole `05-safety/` directory) is absent in the current workspace. This task did not delete or recreate it; the existing link in the historical goal remains explicitly unresolved. No all-repository documentation-green claim.

- 2026-11-06,16:53UTC: owner asked for autonomous continuation while away. Target USB ADB remains available; Pacman Wi-Fi ADB disappeared. One reconnect to the owner-provided endpoint returned connection refused; two matching, already-paired mDNS advertisements did not establish a camera transport, and the advertisements subsequently disappeared. No LAN port scan/pairing reset. Exact-brightness audit subsequently passed a bounded target dispatch trial at17:01; another optical capture requires the camera connection to return.

- `confirmed-on-target`: boot SKU `XT2611-1`, hardware revision `pvt`; Android identifies as `motorola edge 70 max` / `avr_g`, carrier `teleu`.
- `confirmed-on-target`: installed global build **`W3WWS36.65-64-4-1`** after the 2026-10-28 OTA (was `W3WW36.65-64-4`), system/vendor security patch `2026-10-01`; full fingerprints in `artifacts/device_inventory.json`.
- `confirmed-on-target`: stock OTA kernel `6.12.58-android16-6-g09eda8c8505a-ab15950084-4k`; current custom KSU kernel adds `-dirty` before `-ab15950084`. Same pinned source/Clang19.0.1/r536225 baseline; saved patch identifies changes.
- `confirmed-on-target`, 2026-11-06 07:37–07:45 UTC: owner-approved OEM unlock, fastboot `flashing_unlocked:SDP`, then ADB boot_completed=1/flash.locked=0/unlocked/orange, same build/kernel/slot b, UID2000 and Enforcing. R1/T00 done. `artifacts/post_unlock_observation_2026-11-06.json`.
- `confirmed-on-target`: ordinary shell UID 2000, SELinux Enforcing; DRM connector `card0-DSI-1`, loaded `msm_drm`; reported display modes 1440×3168 up to 144 Hz. During the display snapshot the screen was OFF.
- `confirmed-on-target`,12:21–12:26: selected BOE ILI97701A cmd_v4/ID0xd2/Ver0 matches sysfs/boot selector/live DT. Physical silicon revision independently undecoded; `artifacts/panel_identity.md`.
- `reported`: pre-wipe Flicker prevention ON without relief. Historical provider observations are not current state. Stock UI0/1 and native DC packet delivery were subsequently confirmed13:49; actual optical PWM Hz remains unknown.
- `reported`: owner cites tests around170/720Hz and now considers~720Hz likely; controlled integration favors a~720Hz fine component (`hypothesis`), not calibrated fundamental Hz. Required>=2000Hz unchanged. Full wipe/device-risking experiments accepted; no user-data backup prerequisite, exact-operation boundaries retained.
- `reported`, owner clarification: no oscilloscope; use visual/comfort assessment plus another smartphone camera, comparing two available phones with owner-reported ~2000 Hz PWM. Owner reports migraine/dry eyes with low-frequency PWM. No instrumentation prerequisite for qualitative trials; exact Hz/envelope remain unverified, and observation stops at discomfort.
- `confirmed-on-target`: mandatory persistent KernelSU-Next33355/v3.4.2 achieved; native PM installed official Manager, only intended research shell granted, UID0 after ordinary reboot/Enforcing/msm_drm verified in `artifacts/kernel/gki_r59/kernelsu_next/persistent/install.json`.
- `confirmed-on-target`: original boot_b kernel body byte-equals official Google r59; offline baseline/root preserve all10210 reference CRCs and Google trust. Actual observed vendor set loads; full current module source match is still unknown. `artifacts/source_inventory.md`.
- `confirmed-on-target`,07:46: actual8085-line config saved; KPROBES/EXT4_FS/MODVERSIONS/MODULE_SIG/CFI enabled. Original boot and current msm_drm ELF subsequently read during RAM root.
- `reported`: Motorola CN source tag, China/global firmware indexes and Pixel HK3 primary patch were inspected earlier; source-to-installed-global matching remains `unknown`.
- `reported`: CN ROM kernel is `g18b507169406-ab14630870`, not installed GLOBAL. Ten ILI97701A DC arrays match published CN DTS byte-for-byte. Native implementation found at display-driver commit `fa008c43c070ff20faa33853649f5dfd4c427e99`; panelDC is read-only software state.
- `reported`: CN matches 10/11 saved pre-OTA vendor fingerprints; downloaded GLOBAL reference matches 11/11. Seven checked vendor ELFs and all 18 BOE DC arrays are equal between archives, but 36 ILI97701A v2-v4 init/timing properties differ. FOSS has one LUT update delta; msm_drm differs. This does not establish optical causality or current-OTA equivalence.
- `reported`: static GLOBAL reference AIDL path closed from DisplayDCMode through Motorola Global provider, PanelsService, JNI, system V1/vendor V2 AIDL and legacy HAL to DRM DC. Java/JNI cache the request without acknowledging hardware success; current OTA implementation not matched.

## Not done

- [x] Read-only phone inventory (`T01`; sanitized JSON and 11 target-file SHA256/size records saved).
- [x] Exact live-selected panel path; independently decoded physical silicon revision remains unknown.
- [x] Final bootloader unlock observed (`flashing_unlocked:SDP`, 07:38 UTC).
- [x] Post-wipe normal stock boot/ADB (`T00=done`, 07:45 UTC).
- [x] Mandatory persistent KernelSU-Next and UID0 after ordinary reboot (`T00R`,12:19 UTC).
- [x] Installed global build identification: `W3WWS36.65-64-4-1`; historical pre-OTA `W3WW36.65-64-4`.
- [x] Trusted current boot_b original before its write; originals of any future changed partitions still required.
- [x] CN display-related inventory/extraction (`T04`).
- [x] GLOBAL reference unpack and scoped regional display comparison (`T05/T07`).
- [x] Static AIDL UI / HAL / DSI call chain for reference `W3WW36.65-64-4`.
- [x] Stock current-OTA UI/driver/DSI application observed (`T08`,13:49; detailed middle-hop source limits retained).
- [ ] Optical baseline on target.
- [x] GKI baseline build/config/reference CRC reproduction (not live Image identity; signing cert/ELF notes differ).
- [x] Root-only KSU build/offline validation and subsequent persistent installation/UID0.
- [x] Evidence-backed PWM no-go report; no guessed PWM patch produced.
- [x] Separate RAM and persistent root-kernel authorizations executed; new PWM/DSI experiment still separate.

## Current blockers

- `unknown`: ILI97701A register/profile→EM pulse count/Hz mapping and optical response. BOE patent ILI97680A example is a useful lead, not target register documentation; candidate map/next stock experiment in `artifacts/dc_transition_recon_2026-11-06.md`.
- Actual stock outgoing packets/DBV and native returns now captured. Missing evidence is optical/camera/owner response; no oscilloscope prerequisite for qualitative comparisons.
- Full current Motorola display-module source match remains unproven. Root/sysfs/selected DT/original boot access blockers are resolved, not reasons to resume FSG/IMEI work. Cross-SKU/full-ROM restoration remains unverified and is not needed for the current read-only path.

## R3 checkpoint — 2026-11-06 13:14–13:21 UTC

- Read-only preflight reconfirms persistent root/Enforcing/_b; native MIPI logger0,
  KPROBE_EVENTS/KRETPROBES support and isolated trace facility available, not enabled.
  Three actual vendor DC service/HAL files byte-equal available CN reference;
  `artifacts/current_display_path/comparison.json`. No broad GLOBAL re-extraction.
- New mechanism hypothesis: DC OFF may be the native low-DBV high-pulse mode; DC ON
  may be global one-pulse DC. BOE/Honor patent examples support testing, not target
  polarity/Hz. Named Qualcomm emsync fields are capability-gated and inactive in live DT.
- Next is one bounded stock OFF→ON→OFF at manual78/40 and requested120Hz, MIPI payload/
  DBV plus native return tracing if supported, then restore effective settings/log flags.
  Exact proposal in `artifacts/dc_transition_recon_2026-11-06.md`; awaiting scoped
  approval for these stock setting/diagnostic changes, no new DSI/flash permission.
  Still no PWM change/optical proof. Camera can follow transport capture; no scope prerequisite.

## R3 checkpoint — stock transport verified 13:49 UTC

- Owner approved exact stock experiment; six phases completed using actual OEM UI,
  requested120Hz/manual78/40. Six full ON/OFF75-packet sets byte/type/order matched live
  DT, including initial wake reapply; `artifacts/stock_dc_trace_analysis_20261106.json`.
- Settled actual DCS brightness: `51 14 4D` (5197), `51 0B 17` (2839). Native parameter
  returns9x0, no negative controller returns/known failure logs/missed probes,590/590 trace.
- Cleanup verified: DC0/logger0/auto1/min-peak absent, own probes/instance removed.
  Effective initial DC0 restored as explicit provider0 (was absent). No image writes,
  unknown register sequences or optical frequency claims. T08 done; T09/optical part
  of R3 pending, next requires owner camera/brief voluntary assessment, not another blind flash.

## R3 checkpoint — camera conditions and owner report 14:09–14:10 UTC

- Separate owner-approved camera run presented four stable12s conditions at brightness
  78/40 and OFF/ON; `artifacts/stock_dc_camera_run_20261106.json`, cleanup verified.
- Owner reported five chronological patterns: broad slow, broad fast, many thin/fast,
  none, then broad after reset. Provisional mapping and caveats recorded in
  `artifacts/optical_baseline.md`; state4 could be high-duty DC/aliasing, not proven high Hz.
- T09 in_progress. Need original ~90s video/host path and camera settings; no clip yet,
  no reference comparison or direct comfort result, no numerical PWM success claim.

## R3 checkpoint — supplied recording inspected offline

- Received the87.810585s/HEVC1080×1920 clip, file359/12fps. Visible switch transitions
  ~10.0/25.8/41.0/56.6s match native taps with0.287s alignment spread; mapping confirmed.
- Narrow low-OFF band structure also precedes USB overlay; low-ON samples44–48s less
  visibly banded. Corrected scene metadata to actual light theme; documented moving
  camera/phone, moiré and USB scrim. No numerical Hz/depth computed from image codes.
- Clip received flag updated; T09 remains in_progress for reference/comfort evidence.
  Mode4 is a candidate stock preset, not verified2000Hz. No phone action/flash in analysis.

## R3 checkpoint — brief mode4 result and ALS threshold

- `artifacts/mode4_brief_trial_20261106.json`:30s reproduction then verified original
  settings restoration15:25:32. Owner subsequently reports remaining bands; no comfort
  or frequency acceptance. Do not keep repeating this preset as a solved PWM profile.
- Actual current sensor-service acquired read-only15:31 (not CN-identical). Its
  `pwmToDcDbv=3601` consumer decoded: compensation selector, no panel frequency setter.
  Evidence: `artifacts/current_display_path/als/threshold_path.{json,disasm.txt}`.
- Numeric findings are DBV2839/5197 and ALS threshold3601, **not Hz**. Need panel-native
  emission timing/count mapping for a justified frequency change; no new register write,
  persistent profile, driver change or image flash in this analysis.

## T01 evidence log — 2026-10-28

- Actions: authorized ADB presence check (transport ID omitted); allowlisted getprop, uname and `/proc/version`; display-only settings/service/dumpsys observations; sysfs/DT metadata read attempts; partition-name and EROFS mount inventory; selected vendor configuration reads/hashes. No privilege escalation, settings changes, reboot, raw block-partition reads, flash or explicit DSI transactions.
- Artifacts: `artifacts/device_inventory.json` (commands, selected results, failures, file sizes/SHA256); `artifacts/panel_identity.md` (evidence and exact-ID blocker); `artifacts/driver_callgraph.md` (observed components, unknown control hops).
- Facts/tasks: refreshed `00-facts/device.yaml`, `00-facts/claims.yaml`, installed-build guidance in `03-investigation/firmware.md`; `T01=done`, `T06=blocked`.
- Interpretation limits: config presence is not live panel selection; absent matching Settings keys is not proof the UI switch does nothing; 120/144 Hz refresh metadata is not optical PWM.
- Validation: JSON and all three edited YAML files parsed; build/kernel/slot/task consistency checked; identifier property keys excluded; all 11 retained target-file SHA256/size pairs matched a second read; all saved identity/build/boot-policy properties matched a verification read. VINTF declaration line numbers checked against target file contents. No kernel build, flash or optical test performed.
- Next atomic task: inventory the source-tagged CN archive and build-matched global reference offline, compare target-file hashes, locate live-panel selection and the `panelDC` / panel HAL implementation. The `XT2611-3` global reference is not an authorized flash/backup image for `XT2611-1`.

## Workflow change — 2026-10-28

По запросу владельца удалён отдельный файл контрольных сумм отчётов и автоматическое хеширование ADB-логов. Убраны общие требования SHA256 для всех источников и артефактов. Хеши используются только для конкретной проверки целостности, сравнения бинарников и идентификации образов перед boot/flash и восстановлением; ранее собранные наблюдения сохранены.

## T04 / partial T03 and T07 — 2026-10-28

- Input: user-downloaded CN ZIP, 14 918 250 042 bytes, 57 members; XT2611-1 RETCN W3WWL36.65-11-18. Mirror/package metadata are not cryptographic provenance.
- Offline: 46 selected ZIP members extracted (CRC passed); 36 chunks reconstructed with simg2img, liblp metadata parsed; vendor/vendor_dlkm/odm/system_ext EROFS extracted without root/mount. Inspected boot kernel, vendor_boot CPIO/module ELF, DTBO, vendor DC code. No ADB or device writes by this task.
- Root: `extracted/XT2611-1/W3WWL36.65-11-18/{images,super.raw.img,partitions,filesystems,vendor_boot_ramdisk}`. Product/system not unpacked. About 39 GB additional disk used; 115 546 202 112 bytes free after extraction inventory. Original ZIP/extracted data not deleted.
- Tools: Android tools 37.0.0, 7-Zip 26.04, Python 3.13.5, LZ4 1.9.4, binutils 2.46.1, kmod 34.2. Local fsck.erofs 1.7.1 from Fedora EPEL RPM, no system install; earlier 1.9.1 RPM lacked libqpl and was not used. Paths/URLs in manifest.
- Findings: CN kernel differs; msm_drm copies in CN vendor_boot/vendor_dlkm equal. Ten DC arrays match pinned DTS; v4 ON/OFF each 875 bytes/75 packets, 34 differences. All five variants present; default-panel is dummy, not live revision. No proven PWM Hz mapping.
- Parallel read-only source work located exact CN display-driver tag; main agent verified tag, key sender/state/lifecycle code, stock symbols and HAL ioctl/relocations. No build or GLOBAL ABI proof.
- 11 saved target fingerprints compared: 10 identical, FOSS differs; no semantic XML diff or full GLOBAL ROM comparison. UI hop/exact panel/optical result unknown.
- Artifacts: `artifacts/firmware_manifest.json`, `artifacts/cn_panel_commands.md`, `.json`, `artifacts/display_diffs.md`, `artifacts/research_report.md`; updated driver_callgraph/panel_identity. `06-tools/inspect_cn_dtbo.py` reproduces read-only decoding. T04 done, T03 in_progress, T07 blocked; T06 remains blocked.
- Validation: manifest JSON matches all 57 ZIP entries and sizes, 46 extracted image sizes and four partition paths; DTBO output reproduced exactly, all 18 DC property offsets and packet round-trips checked; YAML/task states and local report links valid. Exact-panel blocker preserved.
- No blanket checksum files, settings changes, boot/flash/reboot/DSI writes, optical test or kernel build by this task. No guessed patch created.
- Next atomic task: build-matched GLOBAL offline reference; compare same-revision DTBO/DC/core driver/HAL. XT2611-3 is not an authorized flash candidate or established backup for XT2611-1.

## T05 / T07 / static T08 — 2026-10-28

- Input: owner-downloaded GLOBAL XT2611-3 RETEU `W3WW36.65-64-4`, 13 483 677 726 bytes, 56 entries. Source/mirror metadata are not signature verification.
- Offline extraction: 44 selected entries passed 7-Zip CRC; 34 sparsechunks reconstructed with simg2img, liblp v10.2/virtual_ab_device parsed. Five EROFS partitions extracted without root/mount; CN system_a added only to close the framework-library evidence gap. Roots remain per SKU/build. Original ZIP/chunks/raw images retained; 61 401 100 288 bytes free at the post-extraction check.
- DTBO: compared 3330 BOE subtree properties; all 18 DC arrays equal. Found 36 init/timing-switch differences in ILI97701A v2/v3/v4, with raw bytes, packet edits and absolute offsets. Nine differing supply references resolve to equal subtrees, not changed voltage settings. Register-to-PWM-Hz semantics and optical causality remain unknown.
- Native/UI: seven vendor display ELFs equal; exact FOSS delta 8→3 LUT update; msm_drm sizes/build IDs differ. Static reference chain through Motorola Global, provider, PanelsService, JNI registration, system AIDL V1/vendor V2 and legacy HAL closed. HAL table proves 0=OFF/1=ON without inversion; UI/JNI do not acknowledge hardware success. Java DC screen/FOD lifecycle documented; no brightness/Hz gate found in that DC branch.
- Validation during analysis: extraction CRC and EROFS success; key DEX invokes/field references independently resolved; JNI registration and argument-transfer instructions checked. V1 slot 0x10060 verified as APS2 ABS64 relocation (raw 0, symbol 64→0x8f60), service slot 0x8090 as RELR→0x56fc. No inference from misleading PLT labels alone.
- Current-device read-only check at 20:03 UTC: UID 2000, build `W3WWS36.65-64-4-1`, kernel `g09eda8c8505a-ab15950084`, slot `_b`, pre-unlock snapshot locked/green. Verified provider GET_global returned `display_dc_mode_enabled=1`; five panel attributes denied again. No toggle, reboot, settings, AVB/partition or DSI writes by this task.
- Scope limit: GLOBAL ZIP matches historical T01 fingerprint/kernel and 11 vendor fingerprints, not the newer OTA. Exact live panel, waveform, current source/KMI and safe recovery originals remain blockers. Equal AVB keys do not remove CID/security-version and rollback differences.
- Artifacts: `artifacts/eu_panel_commands.md`, `.json`, `artifacts/regional_dtbo_diff.json`, `artifacts/native_display_diff.json`, `artifacts/post_ota_display_observation.json`; refreshed manifest, display_diffs, driver_callgraph, panel_identity and research_report. T05/T07 done, T08 blocked on current/runtime evidence, T06 still blocked.
- Next atomic task: current-OTA source/stock matching and independent live-panel evidence; controlled owner-toggle read-only A/B plus optical baseline only after arranging those inputs. No kernel build or optical test performed, no flashable patch proposed.

## Evidence log template

```text
UTC date:
Task ID:
Actions (read-only / changes):
Observed facts (paths + relevant line numbers):
Unknowns:
Hypotheses promoted/rejected:
Artifacts:
Next atomic task:
```

## Superseded bootloader report — 2026-11-06

- Earlier owner-unlocked interpretation and closure of the unlock track were incorrect. Owner clarified that only the Android-side step is complete; fresh ADB confirms locked/green. Historical observations are preserved; current state: `artifacts/bootloader_state.md`.

## RECON and owner constraints — 2026-11-06

- Actions: repo/facts/firmware/display-path review, independent read-only bootloader-source recon, official Motorola/AOSP documentation checks, narrow live ADB identity/boot-state reads and transport checks. One authorized ADB device, no fastboot device. No serial/IMEI/token retained in the new report.
- Fresh target: XT2611-1/PVT, `W3WWS36.65-64-4-1`, kernel `6.12.58-android16-6-g09eda8c8505a-ab15950084-4k`, slot `_b`, shell UID 2000, locked/green. OEM properties empty, AOSP setting null and oem_lock dump empty: no toggle/eligibility conclusion from those results.
- Changes: owner >=2000 Hz usability requirement and wipe/no-backup policy recorded in AGENTS/facts/safety/optical acceptance; stale completed-unlock assumptions corrected without altering historical target values; T00 reopened. Trusted recovery images remain a requirement for image experiments, not a demand for user-data backup.
- Artifact: `artifacts/unlock_pwm_recon_2026-11-06.md` contains evidence, unknowns, official sources and the three-stage unlock → privileged panel/current-image evidence → measured PWM experiment plan.
- Validation: edited YAML/JSON parsing, focused facts/task/goal/link consistency and document diff review. No kernel build or optical test; no reboot, settings/DSI writes, key submission, unlock, erase, AVB/slot changes or flash.
- Next atomic task: after owner approves the proposed bootloader transition, enter bootloader and collect only the scoped read-only identity/state/unlock-ability queries; establish the exact supported unlock flow before presenting the destructive command for confirmation.

## Available PWM validation methods — 2026-11-06

- Owner clarified: no oscilloscope, subjective differences quickly noticed, low-PWM-frequency screens associated with migraine/dry eyes in personal experience; another smartphone camera and two owner-reported ~2000 Hz phones available for comparison. No new camera/comfort test performed.
- Updated AGENTS/facts, T09, G4, comparison protocol and stage-3 plan: qualitative baseline and practical usability assessment are allowed without instruments. The real >=2000 Hz goal remains, but numerical carrier, modulation and low-frequency envelope cannot be certified from camera bands or symptoms. Adequate metrology is optional later, not a prerequisite for comparative trials or evidence-justified work.
- Observation is brief and voluntary, stops at discomfort; no deliberate symptom provocation or prolonged exposure. Bootloader/image/DSI safety gates are unchanged.
- Validation: edited YAML parsing, local links, focused goal/method/task consistency and document diff review. Documentation-only change; no ADB, reboot, unlock, settings/DSI writes, flash or measurements performed in this clarification.

## Mandatory KernelSU-Next root — 2026-11-06

- Owner clarified that unlocked stock without root is unusable for them and selected `https://github.com/KernelSU-Next/KernelSU-Next`, custom-adapted to this kernel. Updated AGENTS/facts, staged plan, T00R/T06 dependencies and root/image gates; no optional-only root or unrequested substitute.
- Upstream inspected read-only: v3.4.2 → commit `4c706b5938665866ebe16944a481a7b91e3396af`, README support through 6.18, arm64 android16-6.12 release LKM, Kconfig built-in/module and KPROBES/EXT4_FS dependencies. General support is not target compatibility; full audit/build still blocked on matching originals/source/config/KMI.
- Root-only integration must keep display stock and SELinux Enforcing, with image/ABI checks and a separately confirmed operation/restore plan. Exact panel ID is not a prerequisite to this root-only stage; root is intended to enable its investigation. Acceptance: authorized UID 0 and normal boot after reboot, not merely an installed Manager or temporary root.
- Validation: edited YAML parsing, task dependency/requirement/link consistency, upstream line citations and document diff review. No ADB, kernel/source checkout, install-script execution, build, root grant, reboot, unlock or flash in this clarification. The interrupted earlier patch made no project-file changes; this batch records both root requirements.

## Execution started — 2026-11-06 07:23 UTC

- Owner instructed execution and work journaling. Reused the existing staged plan as
  the active execution contract (R1 unlock → R2 persistent KernelSU-Next → R3 PWM);
  detailed sanitized journal: `artifacts/bootloader_worklog_2026-11-06.md`.
- T00=in_progress. Fresh read-only preflight confirms one authorized XT2611-1,
  current build, locked, slot b; no fastboot transport. Next: agreed reboot into
  bootloader and scoped read-only queries, before any destructive command.

## R1 checkpoint — 2026-11-06 07:24–07:25 UTC

- Completed agreed `adb reboot bootloader`; read-only fastboot identity/state confirms
  XT2611-1/PVT, slot b, locked:SDP, bootloader not fastbootd. Bootloader explicitly
  instructs get_unlock_data + Motorola portal. Read unlock-data successfully; stored
  only outside repo with directory 0700/files 0600; no unique values in public artifacts.
- T00=blocked on owner-account/official-key step. No external ID submission, unlock,
  erase/flash/AVB/slot/root/DSI changes. Current phone mode: bootloader. A normal
  `fastboot reboot` is the exit path, not yet executed; no full recovery claim.
- Evidence and private-file location: `artifacts/bootloader_worklog_2026-11-06.md`.
  Independent read-only current-source audit for R2/T03 started while R1 needs owner input.

## Key response and R2 source match — 2026-11-06 07:31 UTC

- Owner reports key already obtained; R1/T00 now awaits the private local key-file
  path, then separate destructive-operation confirmation. No key read/exposed, no
  portal submission/unlock. No secret-directory search beyond the dedicated folder.
- Independent source audit and parent verification locate Google GKI r59 matching
  target commit-prefix/build ID, with real Bazel/defconfig/ABI paths; recorded in
  `artifacts/source_inventory.md`. This removes the absence of a source identifier,
  not the remaining originals/config/manifest/vendor-KMI blockers. No build/checkout.

## Exact unlock proposal — 2026-11-06 07:34 UTC

- Received owner key-file path, checked literal syntax without printing the secret,
  limited file mode to 0600. Repeat read-only target state remains locked:SDP/slot b,
  bootloader mode, XT2611-1; battery-voltage 4325, charge percentage unsupported.
- Standard Motorola `oem unlock` invocation, full wipe/physical-confirmation expectation,
  stop conditions and limited stock-boot/exit path documented in the execution journal.
  T00 awaits specific operation confirmation. No unlock/erase/flash/AVB/slot changes.

- Subsequent explicit owner confirmation: **Yes, execute unlock**, including wipe,
  state verification and normal stock boot, excluding image/AVB/slot changes.
  T00=in_progress; exact execution/result follows in the detailed journal.

## Final unlock verified — 2026-11-06 07:37–07:39 UTC

- Executed exactly one approved OEM unlock after target/state checks; response
  `Bootloader is unlocked!/OKAY` (14.796s). Independent read confirms
  `flashing_unlocked:SDP`, slot b unchanged. No image/AVB/slot/manual-erase operations.
- Initial reboot guard expected no `:SDP` suffix and stopped before reboot; corrected
  against the observed Motorola state, not by repeating unlock. Normal reboot then
  accepted at 07:38:30; one 45s authorized-ADB wait timed out. Stock boot/setup and
  actual wipe outcome still need observation, not guessed from transport absence.
- T00=blocked only on owner setup/ADB/stock-boot confirmation. Current checkpoint:
  owner observes screen and re-enables/authorizes USB debugging if Android has booted.
  Full sanitized chronology: `artifacts/bootloader_worklog_2026-11-06.md`.

## R1 complete; R2 config; requested recovery research — 2026-11-06 07:45–07:46 UTC

- After owner setup, authorized ADB confirms completed stock boot, unlocked/orange,
  unchanged build/kernel/slot, UID2000 and Enforcing. T00=done; machine evidence:
  `artifacts/post_unlock_observation_2026-11-06.json`.
- Read-only target config successfully captured (8085 lines). Source inventory updated;
  matching GKI identifiers + actual config now available, not yet a validated build.
- Owner asked to wait and explicitly summon @general for TWRP/OrangeFox research.
  Delegated read-only exact-model availability/utility/risk investigation with full
  relevant context, no key access, device commands or project edits. Phone remains
  booted stock; no further device actions while that decision is pending.
- Checkpoint validation passed: YAML/JSON, R1/root status and task dependencies,
  post-unlock state consistency, actual config line count/flags, local links and
  secret exclusion/file permissions. No device access by the validation itself.

## Recovery decision and resume — 2026-11-06

- @general reported community AVR trees, but no verified current-build recovery;
  ramdisk-only recovery uses the boot kernel and is not independent kernel-failure
  recovery. No recovery image was downloaded or tried. User explicitly chose to
  proceed **without custom recovery**; no recovery port becomes a new requirement.
- Resume R2: obtain current originals. Smallest next checkpoint: agreed reboot to
  bootloader, read identity/slot/fetch capability, attempt read-only current boot
  readback if supported, then normal Android return. No userdata/super dump, flash,
  AVB/slot/critical-unlock changes or new DSI. Unsupported fetch will be recorded,
  not treated as permission for blind recovery/firmware experimentation.

## R2 readback and pinned baseline inputs — 2026-11-06 07:55–08:03 UTC

- Bootloader fetch checkpoint: identity/unlocked/slot confirmed; max-fetch-size absent,
  one boot_b fetch failed, zero-byte output deleted. Sizes boot/vendor_boot 96 MiB,
  recovery 128 MiB. Stock Android/authorized ADB/boot_completed=1 returned, build/slot
  unchanged. Evidence: `artifacts/boot_readback_2026-11-06.json`. No image writes.
- Official certified Google r59 ZIP acquired (16.8 MB), CRC checked, embedded config
  byte-equals all 8085 actual target lines. Exact 50-project manifest for build15950084
  acquired from public CI artifactUrl; ephemeral URL not retained. These are baseline
  inputs, not verified current Motorola boot originals. `artifacts/source_inventory.md`.
- Started one background checkout of pinned kernel/common and kernel/build with two
  local Git jobs; no build/custom patch/device changes. Wait for completion notification;
  do not poll or claim success. Remaining root writes still require originals/ABI/proposal.

## Source HEADs verified, baseline dependency preparation — 2026-11-06 08:06–08:16 UTC

- Source checkout completed with both exact expected HEADs; provenance in
  `artifacts/kernel/gki_r59/source_checkout.log`. Current physical paths are
  `sources/gki-15950084/common` and `sources/gki-15950084/build/kernel` (relocated
  to match actual Kleaf layout, no source edits). Clang r536225/Rust 1.82.0.p1 pinned.
- Started background native Git dependency preparation from the pinned manifest;
  excluded irrelevant device/GBL/Fuchsia/test trees and unused newer Clang version.
  Two fetch workers; wait for completion notification. No compile/KSU integration yet.
- Acquired official 10210-symbol Module.symvers CRC reference/provenance for later ABI
  comparison, not an already-passed vendor ABI check. No new device actions.
- Focused checkpoint validation passed: YAML/readback JSON, root/unlock statuses,
  absence of a fake boot original after failed fetch, verified core source provenance
  and local evidence links. No device access or dependency-job polling by that check.

## Baseline attempt and pinned KSU audit — 2026-11-06 08:26–08:37 UTC

- Dependency job completed successfully: 29 selected project HEADs verified. Tool checks:
  Clang r536225/19.0.1 build14043575, Rust 1.82.0-dev linux-15123656, Bazel8.0.0.
- Added `06-tools/build_gki_baseline.sh`: pinned/clean source guards, release config,
  six jobs, baseline only. First attempt failed during workspace stamp on intentionally
  omitted external/dtc; artifacts `baseline_build.json/.log` preserved. Switched to
  documented native-Git extra_git_project (no config/KMI weakening); changed-config
  attempt now running, `baseline_build_native_git.json/.log`. Do not poll or claim pass.
- Acquired/audited pinned KSU source, no setup.sh execution/integration. Full pinned
  ancestry confirms version33355/tagv3.4.2, avoiding fallback code1 below Manager's
  minimum33188 in future hermetic build. Provenance in `artifacts/kernel/kernelsu_next*.json`.
- Phone unchanged; persistent root and numerical/qualitative PWM outcome still pending.

## Offline root checkpoint — 2026-11-06 09:38 UTC

- Baseline and built-in KSU33355/v3.4.2 builds/targeted checks passed; full evidence,
  certificate diagnosis, exact patch and build commands: `artifacts/source_inventory.md`.
- Baseline config byte-equals target; baseline/root each retain all 10210 reference
  exports/CRC. Root changes only KSU flags/trusted-key path; protection stays enabled.
  Google reference public certificate retained, local generated certificate also present.
- `artifacts/kernel/gki_r59/kernelsu_next/Image` is a validated raw component, not
  an installed/boot-packaged kernel. Normal Manager digest/cert pin checked, not installed.
- R2 deployment blocked on current originals/header/restore and actual vendor proof.
  Next requires owner consent/login for read-only LMSA catalogue, no Rescue/flash/IDs.
  No new phone actions after 07:58, no UID0-after-reboot or PWM verification; not complete.

## LMSA handoff — 2026-11-06, after owner catalogue consent

- Owner selected authenticated catalogue/download only, without Rescue/flash or IMEI/serial.
- MFD v1.3.4 commit `b5ea93abf5bc02ee56f5f7a9601320b9d80e3396` checked out/audited
  in approved private cache; no installer/global dependency or CLI wizard run.
- Audited native HTTPS login-URL protocol returned HTTP200/code0000; issuer validated
  as passport-glb.lenovo.com, redirect lsa.lenovo.com. Only random session markers,
  not handset IDs. URL/token input live outside repo with directory0700/files0600.
- Waiting for owner browser login/token; this is not catalogue authentication or
  firmware availability proof. `artifacts/lmsa_catalog_2026-11-06.json`. Image gates unchanged.

## Authenticated catalogue / missing FSG — 2026-11-06

- Owner supplied callback JSON privately; successful content URI parsed structurally,
  then pinned CLI token validation passed. Credentials/logs remain outside repo,0600.
- Catalogue returned 1117 models including XT2611-1/Legion Phone Y70 New Generation
  and XT2611-3/motorola edge 70 max. readSupport means property-based matching, not
  partition readback. Required keys: fingerPrint/fsgVersion.qcom/roCarrier.
- Read-only ADB at 10:29 confirms same SKU/build/fingerprint and teleu; ro.boot.fsg-id
  empty, gsm.version.baseband=M8845_DE90_31.179.01.104.17R. Radio version not substituted
  for FSG label. `artifacts/lmsa_match_properties_2026-11-06.json`.
- Documented getNewResource model/market/category/params/matchType1 used, all optional
  IMEI/SN omitted. Both models: HTTP200/code0001/Parameters lack, no candidate. Missing
  required FSG is known; actual firmware availability remains unknown.
- Next proposed diagnostic: agreed reboot to bootloader, only version-baseband/fsg-id
  plus identity/slot guards, normal stock reboot/verification. No image or OEM write,
  no unlock repeat. Await owner consent; current image gates stay unpassed.

## FSG roundtrip completed / next privacy decision — 2026-11-06

- Owner explicitly approved only metadata roundtrip. 10:54:45–10:55:28: guarded
  avr/XT2611-1/b/non-userspace; version-baseband returned literal Done, fsg-id
  not found (remote FAILED despite host0). No usable FSG established, no fabricated value.
- fastboot reboot accepted; sys.boot_completed=1, W3WWS36.65-64-4-1/XT2611-1/_b
  verified. `artifacts/fsg_bootloader_read_2026-11-06.json`.
- Filtered Android FSG property names only dev.mnt.{blk,dev,rootdisk}.vendor.fsg.
  /vendor/fsg stat shows0755, listing Permission denied. No modem/NV files read;
  precise denial cause unconfirmed. GLOBAL -3 manual getResource also null code/content.
- R2 still blocked: documented property-based lookup lacks verified FSG, no current
  Motorola originals/vendor proof. Supported IMEI lookup is a separate privacy boundary:
  proposed official Lenovo request only, needs consent and private owner input. Not sent.

## DDIC register readback — 2026-11-07 05:40–06:30 UTC

- `confirmed-on-target`: msm_drm debugfs `DSI-1/rx_cmd` reads ILI97701A registers. Method: page select
  `FF 5A A5 xx` → DCS read → page 0, ESD temporarily `esd_sw_sim_success`. Tools `06-tools/ddic_regdump.sh`,
  `run_ddic_regdump.py`; owner authorized broad experiments ("yolo", brute force allowed).
- Ground truth: 25/28 DT-written values read back exactly (53:A2 30 bytes, 63:F1, 5A:86, 00:0A=9C). Registers are
  parameter-oriented (5A:87 ≠ 2nd byte of 5A:86); 00–7F are shared DCS across pages.
- Full dumps (19 pages × 256 regs × 40 bytes, 2 passes, 0 errors): `artifacts/ddic_regdump_20261107/s1..s4`
  (DBV3584/3646, 120/144/60 Hz). Config differences only: 60 Hz = `2D:83=01` + `2D:F2=01` (frame skip, internal
  120 Hz scan). Other diffs (4F:9D/9E, 1E:AE/B0, 23:C1, 07:EC) look like live status values.
- Page 4F reads ≠ writes (4F:81 written 10, reads 06; 88/8B written 78, read 00). Pattern 4F:80/81, C0/C1, C8/C9,
  D0/D1 = 01/06, D8/D9 = 01/10. `hypothesis`: 6 matches 6 pulses × 120 Hz ≈ 720 Hz; unproven.
- Optical: Pacman preview screencap (`06-tools/pacman_bands.py`) shows even dark bands, period 203.7 px, identical at
  60 and 120 Hz requests (consistent with fixed internal 120 Hz scan). Pixel→Hz not calibrated.
- Incident: host-side timeout killed S4 → on-device trap missed SIGHUP, ESD stayed simulated; restored manually to
  `reg_read`, trap hardened. Target awake by owner request (`stay_on_while_plugged_in=7`, original 0); refresh
  forced 120 Hz; original settings in `artifacts/ddic_regdump_20261107/session_original_settings.json` + s1 run.json.
- Next: causal write experiments on candidate fields (4F:81 first) with optical readout; no persistence/flash.
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
