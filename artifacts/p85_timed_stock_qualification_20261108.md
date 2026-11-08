# Три timed factory-15 rehearsal: результат и границы

**Все три штатные серии завершены и независимо проверены. Неизвестный 14
не записывался; реальные PWM >=2000 Гц не доказаны.**

Одинаковые 13 runtime blobs из `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`:

- [01 hardware](p85_timed_stock_a001_20261108_01/hardware_result.md),
  [оптика](p85_timed_stock_a001_20261108_01/optical_result.md): G 31.039259346 с;
  main fine sham/baseline 1.0076336263, return/baseline 0.9940139036.
- [02 hardware](p85_timed_stock_a001_20261108_02/hardware_result.md),
  [оптика](p85_timed_stock_a001_20261108_02/optical_result.md): G 31.636799846 с;
  main fine sham/baseline 1.0094375428, return/baseline 1.0092808148.
- [03 hardware](p85_timed_stock_a001_20261108_03/hardware_result.md),
  [оптика](p85_timed_stock_a001_20261108_03/optical_result.md): G 31.614684608 с;
  main fine sham/baseline 1.0108993932, return/baseline 0.9917413496.

## Что установлено

Во всех стадиях P85 `15 00 00`; baseline/return C1 `00 00 60`. Middle C1
намеренно не измеряется по явной новой схеме и нигде не подменён соседним
значением. Exact native-return/wire/framing/profile, protected-origin/tail,
identity/state/owner/boot/ESD проверки независимо воспроизведены. Ошибок,
reboot и неизвестных записей нет.

Каждый run сохранил и восстановил собственный исходный native DBV 828,
пять Android settings, logger 0 и ESD `reg_read`; root/Enforcing подтверждены.
Камера остановлена, собственные temporary files/probes/mounts очищены,
оба watchdog disarmed и owner/mutex released. Это не распространяется задним
числом на другие runs: у прежних stock-only03/04 исходный DBV был 6438.

Fine-компонента с периодом около 50.568 camera rows и mean Y проходят
ограниченный 5% diagnostic control во всех трёх сериях. Fresh ROI/PTS,
60 центральных кадров, условные timing margins, независимые native-Y/Fourier
расчёты и второй полный decode прошли. JSON и все 32 NPZ-массива каждого
повтора точно воспроизведены; сырое видео и идентификаторы приватны.

## Что не установлено

Полная waveform/broad equivalence остаётся неизвестной. В 01/02 return
full-spectrum L2 отличается примерно на 11–13%; в 03 большая разница
появляется у sham (14.03–15.41%), а return составляет 5.39–5.50%. Около
единицы у одного fixed fine peak не означает равенства всей кривой. Blanket
optical approval, частота в Hz и оценка комфорта не выдавались.

Same-value 15 не доказывает read/write-plane identity, writable semantics,
volatile поведение или то, что 85 является frequency setter. Риск driver
panic на malformed long0 и неизвестная физическая восстанавливаемость DDIC
не исчезли. Host cutoff не доказывает прекращение удалённого child.

## Timing и следующий шаг

[Полная сводка](p85_timed_stock_three_run_timing_20261108.md) сохраняет все
медленные samples. Worst actual G с reserve 8 с и предложенным J 2 с даёт
41.636799846 с и наблюдаемый запас 3.363200154 с до 45 с. Но conservative
role-specific all-phase-max model с residual даёт 38.449625270 с до reserve/J,
то есть **48.449625270 с** с ними. Этот model не проходит, а причина
baseline slowdown не установлена. Три близких G не являются robust bound.

Дальнейших одинаковых физических повторов сейчас не планируется. Малое
объединение read-only calls само по себе не закрывает весь model deficit.
Следующая работа только offline: feasibility spike эквивалентных shell/AWK/
file validators и differential fault-tests против нынешнего Python oracle
для возможного одноразового device-local sequencer. Это новый protocol,
а не удаление host checks; camera barriers/scientific success должны быть
отделены от безопасного возврата при потере host. Ни local controller,
ни candidate 14, ни Android UI ещё не реализованы или допущены к live.
Ограничения 45/37/8 и независимый 60-секундный watchdog не расширялись.
