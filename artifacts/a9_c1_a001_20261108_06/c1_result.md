# A9 меняет квалифицированный C1 статус: 60 → 10 → 60

Статус: **confirmed-on-target для DSI payload и обратимости**.
Physical PWM Hz и цель >=2000 Гц остаются **unknown**.

Серия [run.json](run.json) завершена 2026-11-08 в 15:42:11 UTC.
Три этапа stock → A9-only → stock отправили по 75 точных пакетов;
единственное отличие кандидата — штатный 23:A9 0E → 8E.
Native DBV 3600, software peak 120, native actual 120 / group 3 / timing@0
сохранялись одинаковыми. Fresh stock-only 90 → 120 anchor и тихие интервалы
проверены до отправки. Неизвестных register values не использовали.

## Квалифицированные ответы

- Baseline: `00 00 60`.
- A9-only: `00 00 10`.
- Stock return: `00 00 60`.

Каждый ответ имеет DCS long3 header `1c 03 00 16`, WC 3, валидный header ECC,
raw/normalized count 9, scratch 16, один receive и точный return trace.
Payload CRC не захвачен. Это snapshot перед соответствующим optical hold,
не непрерывная запись или самостоятельное измерение физической частоты.
Перед/после hold проверены A9/9D/DBV; native writes/mode changes в выдержках
отсутствовали. C1 нигде не записывался.

## Интерпретация

Stock sweep при DBV 3600 дал 80/60/50 для software 90/120/144,
а при DBV 3646 / 120 — 10. Модель условного emission count `BE24 >> 4`
теперь даёт для A9 переход 6 → 1 → 6 при неизменной native базе.
Это усиливает гипотезу DC-like/high-DBV branch, а не увеличения счётчика
или несущей. Назначение и ширина поля не декодированы. Данные сами по себе
не устанавливают ни 720/120 Гц, ни отсутствие огибающей.

Уменьшение тонких полос в прежней A001 серии не следует называть high-PWM
эффектом. Новое видео сохранено приватно; отдельный optical analysis проверяет
именно эту серию, не подменяя её старым ROI/периодом.

## Завершение

Stock, исходные Android settings, native DBV 828, panelDC 0 и Enforcing
восстановлены. ESD reg_read, остановка камеры, снятие watchdog и mutex
подтверждены; `cleanup_errors=[]`, неизвестной pending queue не осталось.
Видео 201954498 bytes / 179131 ms полностью получено в приватный каталог.

Серии 02–05 сохранены как guard/preflight failures, не переименованы в успех.
Исправлены native-mode qualification, локальная отправка пяти блоков и per-run
markers. Guards остаются fail-closed; compositor mutex не заявляется.
