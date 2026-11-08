# P85 stock-only 01: остановка до первого writer packet

**Серия не квалифицирована.** Baseline прошёл, но same-value writer остановился
на gate0 до первой DSI-команды своей трёхпакетной последовательности.
Неизвестное значение 14 не использовалось. Факт попытки `sham15` в журнале
не означает, что байт 85=15 был передан панели.

Источник: [run.json](run.json). Опыт начался 2026-11-08 в 16:57:48 UTC и
завершился после recovery/cleanup в 17:00:57 UTC. Raw logs, screenshot и
видеозапись сохранены только в приватном кеше.

## Квалифицированный baseline

При native DBV 3600 и driver actual 120/group 3 прочитаны framed long3:
P85 `15 00 00`, C1 `00 00 60`. Header/WC/ECC/count, реальные callback returns,
native/DBV/ESD и metadata/hold guards прошли. Это не частота и не доказательство
семантики/ширины/volatile или runtime-latching свойства регистра 85.

Фаза заняла 34.389 с: P85 read 7.404 с, C1 read 6.977 с, hold с metadata 10.459 с.
Остальное включает quiet/state checks. Текущий conservative candidate gate
`2 * max(stage duration) + 10 < 45` с такой задержкой не проходит.
Лимиты 45/60 с не увеличивались; candidate остаётся неквалифицированным.

## Причина отказа

Device stderr: `/system/bin/sh: /system/bin/printf: Argument list too long`.
Первый writer gate захватывал полный retained dmesg в shell variable и передавал
его внешнему printf одним аргументом. Android ограничивает длину отдельного
argv; короткие offline fixtures с host shell builtin printf это не выявили.

Сохранённый writer trace пуст; все header/hardware/controller/tx/entry profile
hits и misses равны нулю. Вывод содержит `RECOVERY_REQUIRED 43`. Статический
порядок gate0 перед page23 packet согласуется с этой динамической картиной:
до writer DSI дело не дошло. Ранее baseline reads и штатный brightness dispatch
были реальными командами и этим утверждением не отменяются.

Нужное исправление: streaming/owned-file snapshots и сравнение prefix без
передачи неограниченного журнала через argv. Нельзя очищать dmesg, ослаблять
точность wire/profile guards или выдавать эту попытку за успешный sham.

## Проверенное восстановление

После отказа ESD оставался изолированным; runner не дописывал page0/15/stock в
неопределённую очередь. Выполнен один обычный reboot того же привязанного target,
проверены изменившийся boot_id, завершённая загрузка, прежние identity/module,
UID0, Enforcing, DC0 и ESD reg_read. Затем восстановлены исходные Android settings,
native DBV 828 и logger0; камера остановлена, watchdog снят, собственный mutex
освобождён. Ошибки recovery/cleanup не зафиксированы. Повторная read-only inventory
видит target и отдельную камеру онлайн, без публикации их идентификаторов.

Это проверка software recovery, не гарантия восстановления любого повреждения
DDIC. Полной sham/return видеосерии нет, optical success analyzer её отвергает.
Ни аппаратный PWM setter, ни >=2000 Гц этим опытом не установлены. Следующая
попытка требует исправленного и независимо проверенного writer и нового ID.
