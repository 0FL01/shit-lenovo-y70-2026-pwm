# P85 stock-only 04: runtime transport и возврат квалифицированы

**Подтверждено на target:** baseline → same-value15 sham → explicit15 return
прошли при native DBV3600, driver actual120/group3 и DC0. Обе последовательности
состоят из трёх standalone packets: page23,85=15,page0. Точные native callbacks,
wire bytes, pending/flags, trace/profile gates и проверки состояния прошли.
Это первая успешная live-квалификация данного writer. Значение14 не применялось.

Во всех трёх фазах framed long3 P85=`15 00 00`, C1=`00 00 60`; header/WC/ECC/count
и native intervals подтверждены. Same-value write и неизменный readback не
доказывают тождество read/write planes, runtime-latching другой величины,
volatile semantics или частотное назначение85. Физические PWM Hz неизвестны.

Источник: [run.json](run.json), committed/clean executable provenance
`86ffbfd76aed81b95ca0e990362dd55aacca99a8` с десятью Git blob IDs.
Окончание 2026-11-08 17:43:19.855379 UTC, status=`awaiting_optical_review`.

## Независимый replay сохранённых raw данных

Отдельный reviewer повторно проверил обе writer traces: gates0/1/2/3/3,
standalone lengths11/9/11, pending/flags0, все native returns0, три точных
factory15 wire packets, profile counts3/3/3 без misses. Все шесть reads имеют
header `1c030016`, count9 и ожидаемые payloads; holds не содержат DSI или mode
transition. Все 245 target shell calls завершились с rc0, 27 boot checks неизменны, восемь
child cleanups и owner/watchdog cleanup успешны. Source blobs совпали с commit.

У shared C1 helper ESD возвращается до snapshot profile, в отличие от нового
P85/writer freeze. Это сохраняет возможность консервативного abort при гонке,
но все три фактических C1 profiles этой серии точны, без extras/misses.
Это ограничение не скрывается и не отменяет успешную квалификацию этих captures.

## Время и оптическая граница

Baseline/sham/return заняли32.640/32.738/30.713с. Успешные writers с pre-quiet
заняли17.211/16.694с. Эти реальные значения пока не проходят candidate budget45с
с отдельным60с watchdog; лимиты не увеличены. Пакетирование roundtrips потребует
своей новой stock-only квалификации, даже если child DSI scripts не изменятся.

Один приватный H2641280×720 ролик:140.631667с,158584155bytes, без audio.
В metadata windows продвижение150/156/149 sensor frames; это continuity,
а не обещание такого же числа стабильных encoded frames. [Отдельный optical
review](optical_result.md) проверил fresh ROI/PTS, по 60 кадров и повторный decode.
Fine-контроль воспроизведён, но полная broad/waveform equivalence не установлена.
Этот hardware report не является безусловной optical qualification или разрешением14.

## Восстановлен именно saved original

В начале04 native DBV был **6438**, Android brightness98/manual,
min/peak120.0, timeout1800000 и logger0. В конце восстановлены именно эти
сохранённые значения, включая6438, а не828 из более ранних попыток.
Root/Enforcing, DC0, ESD reg_read и неизменный boot подтверждены. Камера
остановлена, watchdog снят, собственный mutex освобождён; reboot и cleanup
errors отсутствуют. Raw video/screenshots/kernel/identity данные приватны.

Ранее координатор ошибочно назвал828 в сообщении о cleanup03–04. Saved run и
реальное восстановление не менялись; исправлено только описание. Между02 и03
native уровень изменился при прежнем Android98/manual, причина пока неизвестна.
