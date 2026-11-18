# R12 operator QA: два исхода, два независимых критерия

Только offline-анализ архивов, без управления устройствами. Этот пакет не читает assignment, HTML или слепые predictions. Operator evidence не передавался decoder до фиксации predictions. Изображения и raw dumps остаются приватными; абсолютные sensor clock/frame IDs в исходе заменены смещениями.

## R12a

0/18: все 18 комплектов acquisition отсутствуют. `INCOMPLETE_OR_REJECTED`; нет source-phase или optical результата. До/после подтверждены наблюдаемые target settings и центральный crop, BRIGHT/6879→BRIGHT/6879, затем stock Camera2× с двумя advancing readbacks. Отсутствие capture нельзя называть successful collection.

## R12b

18/18 уникальных PNG, 36 advancing raw pre/post, шесть phase early/late target snapshots и шесть стабильных source image областей. Все actuals156000ns/ISO6400, frameDuration33350000ns, rollingShutterSkew31824000ns, id2, AE OFF, focus0, crop3264×2448, preview1440×1080. SPEC actual metadata criterion проходит.

**Exact R11 request reproduction FAIL.** В R11 last request200000ns, в R12b156250ns; actual в обоих156000ns. R11 UI1/5000 нельзя переносить на новый run как доказанное точное воспроизведение режима. Request ISO0 и actual ISO6400 раздельны. Первоначальный verifier с R11 request200000 отверг все18; критерий не переписан в успешный. Поздний explicit `--request-exposure 156250` даёт только `SPEC_ACTUAL_PASS_R11_REQUEST_FAIL`, не composite PASS. Исходный core сохранён в `operator_core_frozen_r11.py`. Дополнительная классификация фиксирует отличие, а не переаттестовывает старый критерий.

Parsed JSON сверяется с raw для экспортированных полей. OIS и videoStabilization отсутствуют в экспортированном JSON, поэтому исключены только из этого пересечения; оба по-прежнему строго OFF в raw. Повторённые dump/frame identity, изменения actual, неверные summaries, отсутствующие файлы и повторные PNG отвергаются. Лог pre/post и bracket IDs должен совпадать с raw; временной порядок phase early→pre→post→bracket→late проверяется.

## Source и возврат

Ручная яркость105/mode0, BRIGHT6879,120Hz, DC0, RBC выключен/три отсутствующих ключа, SDR без HDR и одна matrix сохраняются на12 phase readbacks. В каждой фазе x0:1440,y332:3090 early source PNG совпадает с late попиксельно. Это **не** проверка всей страницы: Android status/toolbar исключены; HTML семантика, label/code и равенство бюджетов пикселей между фазами здесь не проверяются. Нет утверждения, что физическое излучение непрерывно сохранялось между readbacks.

Target исходное приложение и центральный crop восстановлены; пользовательские settings сравниваются точно, BRIGHT6879→BRIGHT6879 явно сохранено в outcome. Expert wide/main возвращены к наблюдаемым AE ON/lockOFF и исходным lens/crop/mode fields; stock2× вернулся с advancing results. Auto-exposure/focus values не обязаны точно повторить динамические initial measurements. PHOTO UI отдельно не удостоверена этим metadata replay; скрытые remembered settings и исходный idle counter не считаются восстановленными побайтно.

Отдельный release readback R12b: actual/current brightness0.40987244, HBMoff, DCprovider0 и исходное приложение. В самом файле нет timestamp, поэтому это подтверждение состояния, не независимо датированная временная привязка. R12a absence release не подменяется новым файлом R12b.

## Воспроизведение

Python3 с Pillow; подключений или acquisition imports нет.

```
python replay.py PRIVATE_R12A
python replay.py PRIVATE_R12B --request-exposure 156250
python test_core.py HISTORICAL_SHORT_RAW PRIVATE_R12A/log.jsonl
python test_replay.py PRIVATE_R12A
python test_full.py PRIVATE_R12B
```

Default `--request-exposure 200000` сохраняет первоначальный критерий. CLI exit2 для неполноты/отказа и также для SPEC-pass/R11-fail; его нельзя трактовать как полный PASS. Normal/−O:10 core+7 incomplete/restore+8 full negative+5 release tests (30/30); повторный outcome совпадает побайтно. Нет временной калибровки: bracket не идентифицирует конкретный sensor frame screenshot, skew не выдаётся за preview row-time. Никаких f-PWM, duty или физических амплитуд этот пакет не устанавливает.
