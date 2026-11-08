# Предложение page23:85: только offline, исполнение не разрешено этим документом

## Вывод

Предлагается только отдельный однократный причинный опыт stock15 → candidate14 →
restore15. Это не найденный PWM-регистр, не делитель и не профиль для использования.
В этой работе не было ADB/device операций, commit/push или изменений действующего
runner/C1/85. Активный A9+C1 attempt05 принадлежит координатору.

Подтверждено по сохранённому timing@0 init: единственная page23:85 запись имеет
payload85 15, descriptor39 00 00 40 00 00 02, offset310, до sleep-out offset1160.
В stock DC ON/OFF по75 пакетов такой записи нет. Поэтому обычный stock DC rollback
не восстанавливает85. Существующая long3 запись15 00 00 квалифицирована отдельно:
artifacts/p85_live_20261108/stock828_long3_reanalysis.json. CRC payload не захвачен.
Физическая ширина, read/write plane, latch, volatility и семантика14 неизвестны.
15→14 и15→11 меняют по одному биту; близость14 численно не означает безопасность.
Нормальный reboot не гарантирует восстановления повреждённого DDIC.

## Минимальные пакеты и transport

Рекомендуется переиспользовать identity/lock/watchdog/native-state/optical guards,
но НЕ 875-byte stock/A9 programs и НЕ hard-coded five-block validator.
Три standalone callback в одном bounded device shell, с проверкой после каждого:

1. 39 00 00 00 00 00 04 FF 5A A5 23
2. 39 00 00 00 00 00 02 85 14
3. 39 00 00 00 00 00 04 FF 5A A5 00

Explicit restore отличается только14→15 во втором пакете. Это derivative
standalone framing (flags0), а не утверждение о побайтном replay init: оригинальный
init использует defer40. Не склеивать31 byte в один callback с первым flags40 и
не переносить five-block assumptions. Предлагаемые delta: pending/length/flags
(0,11,0),(0,9,0),(0,11,0); три return0 и controller0; wire trace ровно три
HS/type39 payload из списка. Standalone85 live framing ещё не проверен.
Три отдельных callback не дают атомарности DDIC и не блокируют системного writer.

Helper06-tools/p85_single_bit_plan.py создаёт только immutable bytes, не имеет CLI,
shell builder, transport, I/O или произвольного значения. execution_approved=false.
validate_callback_delta проверяет только уже разобранную форму delta, НЕ raw trace,
не доказывает ownership/queue emptiness. До live нужен полноценный reviewed raw
trace validator: неизменный prefix, точные PID/callsite/time, потери/пропуски,
wire bytes, native transitions и отсутствие посторонних операций.

## Предложенный порядок, после окончания A9 и отдельного решения координатора

1. Свежий private-ADB preflight/reidentify обоих устройств; один root mutex owner,
   независимый watchdog same-target reboot, свежий experiment ID и точный manifest.
   Проверить SKU/build/kernel/module hash/panel/slot/Enforcing и recovery route.
   Не снимать/воровать чужой lock. Ни одного write до готовности rollback/watchdog.
2. Stock DC0/DBV828/software120, одна статичная сцена, native timing anchor и
   quiet interval. Если иной DBV нужен, отдельный manifest; не менять его внутри
   причинной серии. Не предполагать, что software120 означает native120.
   Фиксировать actual120/group3 или actual1/group8 и сохранять один native state.
3. Одна непрерывная камера с проверенными manual shutter/ISO/focus/WB и metadata.
   На stock получить P85 MRPS3 long3 и C1 long3, сохранить raw+framing+timestamps,
   проверить page0/ESD restoration. P85 baseline должен быть15 00 00 для этой
   узкой серии. Записать baseline optical hold. Диагностические page/read операции
   сами могут возмущать состояние; одинаковый порядок на всех трёх стадиях и
   stock-only sham/read контроль требуются до причинного вывода.
4. ЕДИНСТВЕННЫЙ candidate14; до отправки отметить candidate_may_be_active=true и
   pending_uncertain=true. Каждая callback и wire trace проверяется до следующей.
   После успешного окончания всех трёх и подтверждения состояния: clear uncertainty.
   В ограниченном заранее заданном времени получить P85+C1 в том же порядке,
   затем короткий optical hold. No read retries, no other value, no ladder/search.
5. Если transport/queue точно известны, explicit85=15 тройкой выше; затем P85+C1,
   native/DBV/DC/ESD/page0, stock optical hold в том же видео. Stock DC replay
   не заменяет это действие. Ожидаемый causal readback14 00 00 →15 00 00 является
   критериями опыта, не предположением о поведении железа. Иной ответ означает
   неуспех/неопределённость, без автоматического повторения или latch-команд.
6. Завершить recovery проверки, снять watchdog/lock только после stock return.
   Если readback вернулся, а optical baseline нет, stock recovery НЕ подтверждён.
   Если candidate optical отличается, но native timing/DBV/экспозиция изменилась,
   causal вывод не подтверждён. Readback изменение само по себе не доказывает PWM;
   неизменность не доказывает отсутствие эффекта или безвредность записи.

## Ошибки и границы

Неизвестный queue, timeout, shell disconnect, failed callback, lost trace,
неквалифицированное cleanup или непонятная конкуренция: НЕ дописывать page0,
stock или85=15 в эту очередь; same-target reboot/independent watchdog согласно
плану, затем свежая identity и stock qualification. Это касается и cleanup traps
в заимствуемых reader: existing unconditional page0 cleanup нельзя без аудита
считать безопасным для любого pending-uncertain состояния. Если сами read/cleanup
не завершены точно, rollback-write запрещён. Отдельный проверенный failure path
нужен до подключения этих helpers к live orchestration.

Не replay full init live; не write C1; не guessed unlock/latch/voltage; не менять
boot/module/SELinux/AVB или persistence. Не провоцировать дискомфорт владельца.
При изображении с аномалиями приоритет немедленному recovery, не сбору серии.
У read MRPS3 остаётся риск malformed long0 panic до userspace validation.

## Оставшиеся блокеры и тесты

Нынешний capture_ddic_85.py принимает только short1 и корректно отвергает уже
наблюдавшийся long3. Нужен отдельный explicit long3 validator с сохранённой raw
fixture и negative tests; не ослаблять существующий parser незаметно. Нужен
спроектированный срок candidate dwell, end-to-end bounded rollback/watchdog,
интегрированный raw transaction validator и failure-path review. Нужен результат
текущего attempt05 и отсутствие его активной ownership перед любым live решением.
Даже после этого семантика/безопасность14 остаётся экспериментальной неизвестной.

7 новых offline unit tests PASS обычным python3 и python3 -O:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools -p test_p85_single_bit_plan.py -v
Проверены точные packets, одиночный бит, запрет других stages, мутация каждого byte,
missing/extra/reorder, callback shapes, существующий init и повреждённые fixtures.
Это focused offline pass, не full regression и не live qualification.

### Координаторское уточнение после offline подготовки

Координатор сообщил: attempt05 остановился ДО table write из-за повторяющегося
markertext и сохранившегося dmesg attempt04, затем закрыл physical trial чисто.
Это не основание повторить85 или изменить evidence gates. Будущий orchestrator
обязан использовать свежий validated experimentID/hash во ВСЕХ markers, отдельный
mutex owner и fresh output reservation с отказом при существовании. Сохранённые
логи не очищать, unique count1 не ослаблять. Данный pure byte helper не генерирует
markers/locks/outputs и не реализует runtime guards; это остаётся blocker интеграции.
