# S0C1: выполнен, крупного оптического эффекта нет, владелец отклонил

2026-11-07. `confirmed-on-target` — исполнение/камера/возврат; `reported` —
субъективная оценка владельца. PWM Hz остаются `unknown`, цель≥2000 не достигнута.

## Контролируемая серия09:42:57–09:44:16UTC

По [отдельной авторизации](authorization.json) выполнено один раз:
stock → полный native ON с A9/9D оставленными0E → stock. Остальные32 отличающихся
payload-пакета соответствовали ON. DBV3600, requested120, providerDC0;
одинаковый DBV replay/redraw/readback, камера100us/ISO6400, focus9.11752701,
AE/AF/OIS/EIS OFF. Возврат и cleanup завершены без ошибок, reboot не потребовался.

[Run](run.json), [spatial-v2](analysis_spatial_v2.json),
[phase diagnostic](temporal_alias.json),
[comparison](../optical/pacman_dsi_coupled_on_comparison_spatial_v2_20261107.png).
Полностью декодированы1671 кадр/64,885,511bytes; анализ3×75 кадров. Просмотрен
contact sheet. Проверены225 table packets,3 DBV writes,9 коротких чтений,
37 нулевых tx returns,300 controller returns≥0, misses0; записей во время holds нет.
Во всех состояниях readback A9/9D/DBV =0E/0E/0E10; это не полный readback32 полей.

| Стадия | q93 total, Y codes | raw mean Y | Пространственные периоды основных пиков, px |
|---|---:|---:|---|
| Stock before |4.625121|33.454160|93.09 /46.55 /31.03 /23.27|
| S0C1 |4.240548|33.428842|93.09 /46.55 /31.03 /23.27|
| Stock return |4.434536|33.410453|93.09 /46.55 /31.03 /23.27|

Нормированное q93 ratio S0C1 к двум stock =**0.936347949**. Мелкий train и широкая
структура сохраняются; нет наблюдаемого сдвига пространственного семейства ×2–3.
Это не измерение глубины модуляции и не доказательство неизменной физическойHz.
Небольшую разницу амплитуд не объявляем крупным эффектом или новым лучшим baseline.
Сохранённый A9-only0.2264067 остаётся существенно более сильным **промежуточным**
результатом по этой метрике; сравнение историческое, не simultaneous head-to-head.

Фаза исходной q93 семьи без temporal demeaning даёт sampled alias первого
компонента1.28938 →1.24391 →1.13662cycles/s; дрейф есть и после stock-return.
Это не PWM Hz и не доказанный новый период. Скрипт `temporal_alias.py` прошёл
syntax-check и синтетические stationary/positive/negative alias проверки.

## Отдельный ручной просмотр и выход

Владелец затем отдельно попросил включить тот же профиль и посмотреть напрямую.
[Owner-view run](owner_view/run.json):150 table packets,25 callbacks,6 reads,
224 controller returns≥0; профиль передан для просмотра09:56:13UTC, служебные
ESD/logger/probes/files очищены, камерных действий не было. Это отдельный запрос,
не скрытый повтор измерительной серии и не повторное использование её разрешения.

Оценка владельца (`reported`, точная цитата): **«текущий результат который включен
не приемлем и не юзабелен»**; потребовал продолжить офлайн и достичь≥2000Hz.
Профиль **отклонён**, не сохранён как улучшение и не включён постоянно.

[Return](owner_view/return/run.json), [validation](owner_view/return/validation.json):
завершён09:58:08UTC,75 stock packets,13 callbacks,91 controller returns≥0;
ESDreg_read/logger0/Enforcing, native828 и captured manual52/requested120/
timeout1800000 восстановлены. Reboot не понадобился. Текущий авторитетный итог —
`owner_view/return/run.json`, а не исторический active-handoff в `owner_view/run.json`.
После этого аппаратных действий не было; исследования продолжаются офлайн.

## Новый вывод для реверса

[Проверка16 простых моделей](threshold_models.json), воспроизводитель
`threshold_models.py`: если предположить A9/AA одним словом и напрямую связать
fine-train с сравнением DBV, **обычный unsigned16 threshold не объясняет A9-only**:
3600<3601 и3600<36369, но train во втором случае подавлен. Signed16 comparison
и отдельный управляющий bit15 оба согласуются с этими наблюдениями. Поэтому
нельзя назвать bit15 единственным доказанным mode flag или умножать это слово
как count/period. Формат самого слова остаётся гипотезой.

Новый offline разбор bulk-полей подтвердил структуру, но не frequency map:
- `53:A2`: один opcode+30 data bytes, три повторённые10-byte группы. OFF/ON
  различаются только позициями7–9 внутри каждой группы.
- `63:F1–F4`: четыре opcode+16 data bytes; пять20 в позициях5–9 переносятся F3→F2.
  Обрамление `53:F0=1/0` не даёт само по себе названия CMDQ или bank selector.
- `51:A1/A2`, `52:81/82`: каждый opcode+6 data bytes; v2/v4 значения различаются,
  тогда как A2/F1–F4 совпадают. Полная неделимость всех этих настроек не следует
  из их соседства. В v1 отдельные FE имеют похожую форму продолжения, но parent
  comparison не нашёл полного равенства склеенных v1 и v2 данных: значения другие.
- Mirror commit`077337a3ae72b5fd75abb3f92188201d124fea5b`, строки67–85, независимо
  изменяет A2 позиции5–6 (`30 50→10 10`) вместе с другими полями. Описание лишь
  «optimize panel effect», не «increase PWM». Source review3746226 недоступен.

Источники: pinned v4 common DTS в approved cache
`pwm-primary-followup-20261106/display/...common_v4.dtsi:74–200` и mirror patch
`ilitek-em-external-20261106/077337a3ae72b5fd75abb3f92188201d124fea5b.patch`.
Parent перепарсил и подтвердил полное равенство875-byte v4 ON/OFF сохранённому liveDT.
Нужны аннотации supplier review3746226/3807108 либо DDIC field map. Прямое получение
обоих review завершилось transport error, локальный DNS `gerrit.mot.com` —
`Name or service not known`. Public exact-byte/English/Chinese поиск не дал register
guide. Это конкретный пробел источника, не доказательство аппаратной невозможности.
