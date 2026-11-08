# Минимальная проверка FD / байтов (только подготовка offline)

## Последующие target observations, 2026-11-08

Первоначальный offline контракт ниже сохранён как исторический. Теперь имеются
[probe01 STOP + exact inspection/cleanup](../../artifacts/android_fd_byte_microprobe_20261108_01/result.md)
и [отдельный owner-shell probe02 limited observation](../../artifacts/android_fd_byte_microprobe_20261108_02/result.md),
оба с независимым saved-evidence replay.01 external cat /proc/self/fd/8 получил
ENOENT; CLOEXEC cause не доказана.02 /proc/$$/fd/8 сохранил LF1 и LF+NUL2 после
unlink, а substitution потеряла оба; собственная cleanup отдельно подтверждена.

Новые probe_owner_fd.sh.in/probe_owner_fd.py/test_probe_owner_fd.py не заменяют
original probe.sh.in/probe.py/test_probe.py и command_example.txt. Source pins и
точные пределы в result02. Существующий validate_capture.sh применяет self-FD
только к builtin -f/-s:01 не доказывает его несовместимость/необходимость patch.
Host7 normal/-O (dash/bash), acquisition8 normal/-O independently PASS.
Full batch/root lifecycle/clock/PWM не квалифицированы; runtime13 unchanged.

## Первоначальный offline контракт (исторический)

Статус: **confirmed-other-device (host Linux/dash и bash)**, Android — **unknown**.
Ни одного обращения к устройству, установки или изменения runtime не сделано.
Независимый модуль, не supervisor и не расширение timeout-пробы.

## Что проверяется

Один новый каталог, один audit inode, FD8 открыт на append. После unlink
audit записываются сначала LF (1 байт), затем NUL (суммарно 2 байта).
Отдельные вызовы cat читают /proc/self/fd/8 в собственные файлы снимков.
cmp сравнивает снимки с независимо созданными бинарными fixtures;
wc -c и cat передают реальный размер и сами байты в stdout.
Проверка -s показывает, что и LF, и LF+NUL не являются пустой диагностикой.
FD8 закрывается явно. Статусы утилит проверяются до продолжения.

Отдельно фиксируются результаты $(printf '\n') и $(printf '\000').
На host dash оба становятся пустой строкой без диагностики. Это НЕ
доказательство безопасности command substitution для бинарных данных.
Brace-group redirection охватывает само вычисление substitution и сохраняет
предупреждение bash об NUL в sub-err: это проверено реальным host regression.
Оно передаётся отдельной записью и остаётся доступным парсеру. Возможные
другие внешние диагностики по-прежнему означают limited/unknown, не PASS.

## Точная команда и привязка

probe.sh.in — полный короткий shell payload, не отдельная устанавливаемая программа.
probe.py проверяет SHA-256 исходника и возвращает точный argv и точный каталог:
    argv, directory = render(fresh_24_lowercase_hex_nonce)

Android mapping жёстко задан:
sh=/system/bin/sh; mkdir/rm/rmdir/cat/cmp/wc=/system/bin/<имя>.
Ни PATH lookup, ни произвольных команд/путей утилит в API нет.
Host mapping: /bin/sh и /usr/bin/<имя>. Host tests никогда не используют
Android mapping для исполнения.

command_example.txt содержит точную shell-quoted команду для фиксированного
демонстрационного nonce 0123456789abcdef01234567. Она создана offline,
не выполнена на устройстве. Это образец для review, НЕ nonce для запуска:
parent должен выбрать новый nonce, зафиксировать argv/его хеш и не переиспользовать
каталог /data/local/tmp/fdbyte-<nonce> после любого неопределённого результата.
Ни модуль, ни тесты не импортируют транспорт устройства.

Parent отвечает за UID2000 без su, identity/binding, mutex, доверенный parent
directory и штатные утилиты, отдельные stdout/stderr/rc и лимиты транспорта.
Не вызывать это до отдельной квалификации timeout-пути. Этот модуль не
доказывает остановку дерева процессов и не трактует rc124 как такое доказательство.

## Private layout и протокол

Каталог mode700, umask077, noclobber. Имена только точные:
owner, owner.ref, expected-lf, expected-both, audit, lf, both,
sub-lf, sub-nul, sub-err.
owner и owner.ref содержат fdbyte-owner-<nonce> плюс LF.
audit удаляется после открытия FD8 и до записей. Остальные файлы остаются
внутри собственного каталога до успешного завершения наблюдений.

stdout: FDMB1 LF, затем пять записей в фиксированном порядке
lf, both, sub-lf, sub-nul, sub-err.
Каждая запись: имя+LF, wc-count+LF, ровно count необработанных байтов.
После успешной очистки END+LF. Никакой оболочки вокруг бинарных данных.
Внешний stderr хранится отдельно, rc отдельно. Непустой внешний stderr,
неzero rc, лишние/обрезанные байты, неправильный порядок/размер/fixtures
не допускают успешный parse. Максимум stdout 4096, запись 1024.
Это ограничения parser; транспорт обязан ограничивать acquisition раньше.
Длина данных фиксирована; бесконечных циклов, произвольной нагрузки нет.

Парсер требует реальные снимки LF и LF+NUL, а не слова «успешно».
Но он не аутентифицирует транспорт/утилиты и не доказывает filesystem state
по тексту END. Все исходные stdout/stderr/rc надо сохранить даже при ошибке.
substitution_stderr — отдельное поле bytes, не терять его при отчёте.
Любой неуспешный parse — limited/unknown, а не «FD не поддерживается».

## Завершение и ошибки one-shot

- Неуспешный mkdir: exit90, каталог не принимается во владение, ничего не удаляется.
  Даже отсутствие предварительного пути не разрешает считать uncertain mkdir своим.
- Ошибка создания marker/fixture, открытия FD, unlink, /proc, printf, cmp/wc/cat:
  exit90 или native shell rc; без cleanup trap и без retry. Частичное состояние
  сохраняется. После выхода shell kernel закрывает его FD; это не доказательство
  отсутствия потомков или прекращения transport command.
- На полном пути после наблюдений: close FD8, cmp двух owner files,
  rm только точного списка собственных файлов, rm owner, rmdir точного каталога.
  Никаких rm -rf, globs, принудительного удаления, переименований или adoption.
- Неуспешная очистка: нет END, rc90/неzero, остатки не удаляются автоматически.
  Если owner уже удалён перед неуспешным rmdir, происхождение остатка заново
  не предполагается. Parent сохраняет исходные границы и точный путь для review.
- Signal, timeout, обрыв сети или потерянный rc: unknown, не запускать ещё раз
  на этом пути и не выполнять «на всякий случай» cleanup.
- Модель исключает враждебный concurrent same-UID writer. Marker и noclobber
  не являются защитой от такого TOCTOU.

Минимальный независимый device post-read, только после отдельно установленного
завершения команды: проверить для ровно возвращённого directory оба условия
! -e и ! -L и сохранить отдельные stdout/stderr/rc. Никакого ls glob/find/rm.
Если путь существует или результат не получен, cleanup остаётся contradicted/
unknown. При неизвестном завершении чтение отсутствия — лишь снимок момента,
не доказательство невозможности дальнейшего создания/записи.
В parse(..., post_absent=True) передаётся только независимое установленное
отсутствие, а не текст END. По умолчанию cleanup=unverified.
Квалификация на target применима только к фактически проверенным shell,
tool paths, /proc semantics, UID и invocation; host pass не переносится на Android.

## Offline tests

Из этого каталога:
    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest -v test_probe
    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -O -m unittest -v test_probe

Семь тестов: реальное host FD/unlink/cmp/wc наблюдение; все обрезания и лишние
байты; повреждение NUL/count/rc/stderr; независимость cleanup verdict;
валидация nonce и render Android БЕЗ исполнения; коллизия собственного
host fixture directory без adoption/removal; реальный /bin/bash regression,
который требует пустой внешний stderr и captured NUL warning в sub-err.
Тестовые временные каталоги создаются только здесь, внутри разрешённого нового
подкаталога. Нет asserts, пропадающих при -O, автоматического recursive cleanup
или установки ПО. При неожиданном отказе tests намеренно оставляют остатки.
