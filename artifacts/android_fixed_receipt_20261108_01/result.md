# Fixed synthetic receipt01: HOLD до producer

Статус: **confirmed-on-target access-gate STOP; independent saved-evidence
replay PASS для остановки**, не успешный receipt. [Frozen result](result.json),
[frozen acquisition](acquire.py), [исходный контракт](README.md).
Source SHA256:15a25485992feba95d70bca478fff9777330a252163b22423e08c610b933063c.
15 events /346 accepted B; завершение2026-11-08T23:54:39.110789 UTC.

Root reserve вернул rc0/exact RESERVED. Затем plain UID2000 pre-capture access
check вернул rc1/empty stdout/stderr при completed transport. Fixed main остановился
**до producer/capture/seal**. Их rendered scripts/hashes были подготовлены заранее,
но это не execution; capture/seal dispatch event/command file отсутствуют.
Root BASE сохранён как permanent spent state: ни retry, ни cleanup/adoption.
Original source, PINSET/README и executed result bytes сохранены без изменений.
Lead повторил frozen template27 и acquisition19 tests normal/-O: PASS;
acquire --check подтвердил acquisition/pinset/transport pins. Host PASS не
отменяет фактический target access denial.

Предшествующий [read-only parent inventory](../receipt_parent_inventory_20261108_01/result.json)
проверял directory metadata/access predicates, не доказал будущую work writability
или полный root↔shell lifecycle. [Последующая diagnosis/AVC](diagnosis.md)
локализует work_w=false, но не устанавливает причину отказа.

Direct Sequence API позволяет caller пропустить access gate; fixed acquisition
main всегда вызывает его. Это ограничение API, не CLI bypass и не наблюдавшееся
unsafe execution. Independent saved replay сверил order, caps, exact streams,
source/render pins и отсутствие capture/seal. Preflight/binding flags опираются
на frozen source + lead record; отдельный raw host preflight transcript отсутствует.

Никакого receipt/lifecycle/PWM успеха не заявлено. После access denial запрещены
alternate paths; начатая split host-only implementation остановлена, не запускалась
на устройствах и не входит в публикацию. Нет security/label changes, DSI/settings/
trace/reboot; камера только identity. Brightness/current restore не измерены,
текущее brightness неизвестно. Full validators/clock/lifecycle integration остаётся
перед factory15; generic57 batch не допущен. Unknown14 disabled;37/45/8/60/600
сохранены; physical PWM>=2000 Hz не доказаны.
