# Agent D — независимая adversarial проверка HORIZON R3

**TL;DR:** новые расчёты A и C воспроизводятся независимыми методами. Главная
оговорка для синтеза: готовая A0D1C1 — проверяемое составное вмешательство,
а не расшифрованный 9D-регулятор частоты; прежний redraw-опыт не различает
pixel-event, elapsed time и обновление содержимого.

2026-11-08. База `fffb0feeda534add90dfaf7056964d40adefc183`. Только локальные
сохранённые файлы и уже материализованный публичный reference source. Нового
доступа к телефону, камерной съёмки, DSI-программ или разрешений не создавалось.

## 1. Независимая проверка байтов и дизайна: PASS с причинной оговоркой

[agent_d_verify.py](agent_d_verify.py) не импортирует реализации A, C или root.
[agent_d_verify.json](agent_d_verify.json) содержит исходные пути и результаты.
Семь программ самостоятельно разобраны через `struct.unpack_from('>5BH')`.
Их длина875 bytes, число packets75, headers совпадают. Адреса единственных
A9/9D payload-байтов найдены из page/opcode, а не назначены по модели:
`23:A9` offset68 (`0x44`), `24:9D` offset97 (`0x61`).

Относительно полного native OFF получено:

- A9-only:1 byte /1 packet; 9D-only:1/1; selector pair:2/2.
- C=S0C1:83 bytes /32 packets.
- native ON:85/34; A0D1C1:84/33.

Это подтверждает существование независимого *программного* взаимодействия
между D и совокупностью C, но C не становится одним физическим параметром.
Семантика этих83 bytes отдельно не декодирована.

Шесть известных вершин имеют rank6/8: независимое доказательство использует
целочисленную Gram-матрицу Walsh-кодировки, точно `8·I₆`. Обратимое преобразование
к0/1 monomials сохраняет rank. Все четыре заполнения недостающих вершин011/101
проверены через subset Möbius inversion, независимо от формулы A; коэффициенты
совпали с `F=A+(v−1)AC+uDC+(1−v−u)ADC`.

Первичные qualitative labels согласуются с отчётами
[selector result:4–6,14–35,97–108](../dsi_selector_split_20261107/result.md),
[block trials:3–7,35–45](../dsi_block_trials_20261106/with_redraw/result.md),
[S0C1:8–33](../dsi_coupled_on_20261107/result.md) и
[prepared proposal:11–34](../dsi_coupled_9d_20261107/proposal.md).
Это шесть исторических классов камерного результата. Полное динамическое
состояние между разными сериями не установлено.

**Оговорка, обязательная для итогового текста:** фраза «011 непосредственно
измеряет D×C contrast» верна внутри условной модели с переносимостью старых
контролей. Одна будущая stock→011→stock ABA непосредственно измеряет эффект
всего профиля из33 изменённых packets. Она не изолирует9D и не оценивает causal
interaction без допущения, что старые000/010/001 сопоставимы с новым011 по
неучтённым состояниям. Ради исправления формулировки повторять отвергнутый
S0C1 не требуется: достаточно не заявлять больший уровень причинности.

Uniform prior по четырём completions даёт каждому отсутствующему углу1 bit;
это иллюстрация, не эмпирическая вероятность PWM≥2000 и не доказательство
превосходства011 над101 по mathematical EIG. Практический приоритет011 разумен:
есть точная старая программа, A9-ветвь не маскирует возможный ответ D+C.
Сам кандидат и его подготовка не являются открытием этой сессии.

## 2. Reachability выбранного DT: PASS, без вывода о hardware semantics

Независимый parser получил52 command arrays /1101 packets. Для заданного
набора `4F:80/81/C0/C1/C8/C9/D0/D1/D8/D9`, `07:EC`, `23:C1` найдено только
четыре writes `4F:81`: два значения10 в DC ON/OFF и два06 в timing@4/@5.
Точные пути/headers/payloads включены в JSON `selected_command_corpus/writers`.
Проверены сохранённые файлы `artifacts/device_tree/selected_boe_v4/`.

Отсутствующий writer в этих52 arrays не означает read-only hardware register,
отсутствие runtime arithmetic writer или невозможность управления PWM. Однако
готового основания для новой записи в остальные «слоты» этот корпус не даёт.
Равные readback06/10 и расстояния C1/C9/D1/D9 сами по себе не декодируют pointer,
pulse count или банк. Идентификация transaction/latch остаётся открытой.

## 3. Frame delivery: подтверждён новый пробел наблюдения, latch не идентифицирован

Самостоятельно прочитана pinned reference-цепочка Motorola
`kernel-msm-5.4-techpack-display@fa008c43c070ff20faa33853649f5dfd4c427e99`:

- [`sde_encoder_phys_cmd.c:2563–2591`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_encoder_phys_cmd.c#L2563-L2591)
  выбирает autorefresh либо helper trigger_start.
- [`sde_encoder.c:5563–5579`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_encoder.c#L5563-L5579)
  вызывает `ctl->ops.trigger_start`.
- [`sde_hw_ctl.c:497–503`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_hw_ctl.c#L497-L503)
  пишет1 в CTL_START. Это объясняет отдельный *reference* path через MMIO.

[Runner:24–28,417–429](../../06-tools/run_dsi_mode_trial.py) наблюдает только
`dsi_display_cmd_transfer` и `dsi_ctrl_cmd_transfer`; дополнительное утверждение
во время redraw проверяет найденные control log lines. Это не счётчик delivered
pixel frames, TE или panel scan. Наличие target symbols по offsets0xb367c,
0x962e0,0x13dbb0 в
[symbols.txt:16526,16429,16913](../runtime_pwm_recon_20261107/evidence/symbols.txt)
поддерживает релевантность вопроса, но **не устанавливает равенство function bodies**.
Target ELF здесь отсутствует; точная ветка, активная на target, остаётся unknown.

Независимо восстановленная chronology из
[run.json:132–139,196–197,248–250,298–299,348](../dsi_stock_on_control_20261106/with_redraw/run.json):

- ON verified21:33:03.348524Z; DBV replay21:33:03.630454Z.
- До redraw hold лежит в интервале replay+0.357375…7.357898s.
- После redraw hold лежит в replay+14.796735…21.800891s.
- `new_table_sent=false`, `writes_during_redraw_and_hold=[]`.

Одинаковой задержки в sham-ветви нет. Объяснение «профиль применился позже без
необходимости redraw» совместимо с этим журналом. Кроме того,
[repaint_settings:371–398](../../06-tools/run_dsi_mode_trial.py) открывает и
закрывает chooser и допускает scrolling; это меняет временную историю
содержимого/APL и submissions, даже если итоговый ROI одинаков.

**Минимальное различение:** после отдельного разрешения — два сопоставимых
применения одного уже известного профиля из одинакового начального состояния:
sham с ожиданием и одно подтверждённо доставленное событие обновления при
неизменном изображении. Сравнивать одинаковые elapsed-time окна; событие должно
быть видно отдельному frame observer. Если потребуется повтор для устойчивости,
разнести момент события между повторами, чтобы отделить event-locked transition
от time-locked transition. Нельзя считать сам вызов userspace commit доказательством
физической доставки: compositor/PSR/ROI optimization могут убрать его.

Sham-переход отвергает необходимость события в проверенном режиме. Устойчивый
переход только после одного события поддерживает activation latch. Эффект,
требующий непрерывных commits, поддерживает cadence/active-idle механизм. Ни
один исход самостоятельно не измеряет PWMHz. Сейчас нет проверенного target
frame-observer/runner, поэтому этот рычаг **не ready-to-run**; forced autorefresh,
MMIO и новые kernel hooks не следуют из public source автоматически.

## 4. Оптический контрпример: PASS; дополнительный falsifier вычислен

Численный контрпример C проверен прямым интегрированием положительного
`E(y,t)` восемью узлами Gauss–Legendre, полученными из корней полинома Legendre.
Код не использует `sinc`, analytic exposure expression C или его Simpson routine.
Интегрированы все3×37,500 samples для hypothetical721.3363/1441.3363/2161.3363Hz.
Максимальная разница между изображениями **2.47646×10⁻¹²**, строгая нижняя
граница положительной эмиссии **0.7837629807**. Значения относятся к нормированному
синтетическому irradiance, не Y-кодам target.

Вариант fine+broad с одной локальной temporal frequency и вариант с отдельной
более низкой частотой тоже совпали: max difference **3.45501×10⁻¹³**, общий
positive bound **0.6974168262**. Для broad-компоненты коэффициент был получен
самостоятельным complex quadrature response, без phase/sinc формулы C.

**Новый ограничивающий тест:** те же самые emitters, без повторной подгонки
амплитуд/фаз, при увеличении exposure100→400µs уже дают различие до
**0.1712809218** между первым и третьим frequency model. Это намеренный
контрпример чрезмерному обобщению: конструкция доказывает неоднозначность
одного fixed-exposure observation operator даже при известном row-time,
но не доказывает, что весь реальный exposure sweep совместим с этими тремя
фиксированными emitters. C сам корректно ограничивает scope.

Также одна temporal frequency у двух spatial terms требует одинакового
frame-sampled temporal alias в стационарной линейной модели. Надёжно различные
alias beats таких компонент опровергли бы именно эту простую модель. Два
spatial periods без такого разделённого temporal evidence этого не делают.
Дальнейшей подгонки старых кадров в этом review не выполнялось.

Это sinusoidal modulation counterexample, **не** найденный прямоугольный PWM
режим или утверждение, что ILI97701A умеет воспроизводить построенные поля.
Отсутствующие mp4/NPZ не декодировались. Для физической частоты нужен независимый
временной канал; малый неподвижный optical aperture и DC-coupled photodiode/ADC
устраняют именно camera row/ISP оператор и сохраняют возможную low-frequency
огибающую. FFT peak без waveform/fundamental проверки не достаточен.

## 5. TOP-3 с adversarial позиции

1. **Составной A0D1C1 при A9=OFF.** Высокая доказанность точного intervention,
   низкая семантическая уверенность; вероятность достижения≥2000 unknown.
   Information gain относится к ещё не измеренной ветви D+C. Это наиболее
   конкретный следующий кандидат, но весь profile меняет84 bytes. Риск смешанного
   vendor state; возврат — полный native OFF, DBV replay, проверенный redraw,
   короткий readback и cleanup по существующему scoped runner. Не переписывать
   это как «проверку только9D» или новый открытый frequency setter.
2. **Pixel update / active-idle cadence как software lever.** Исторический
   transition и reference MMIO path делают вопрос конкретным. Пока вероятность
   meaningful PWM improvement неизвестна; information gain высокий для отделения
   delivery/latch от delayed response. Риск app-level stimulus потенциально ниже
   нового vendor register, но target observer ещё не квалифицирован. Следующий
   отдельный опыт — matched sham/event; никаких новых DDIC bytes.
3. **Внешний Qualcomm EMSYNC как альтернативный физический канал.** После
   нового source-результата B этот механизм обоснованнее «4F slots» для TOP-3:
   reference code задаёт EM rate, period и width, а pinctrl выводит ESYNC наружу.
   Уверенность высокая для архитектуры reference, низкая для target applicability;
   вероятность≥2000 неизвестна. Имеющийся target subtree не активирует эту ветку.
   Минимальное следующее доказательство — точный panel/FPC/board документ,
   соединяющий совместимый sync-input ILI97701A с SoC output и описывающий DDIC
   external-sync mode. Это информационный gate, не предложение включить GPIO
   или записать новые DSI bytes. До прохождения gate hardware feasibility низкая,
   риск активации неизвестен; гарантированный rollback ещё не определён.

### Дополнительная независимая проверка EMSYNC

Прочитаны непосредственно материализованные pinned source files в
`b_source_cache/`, затем сопоставлены с
[точными excerpts B](agent_b_esync_primary_excerpts.md), а не только с его выводом.
В `sde_encoder_phys_vid.c:916–939` получены разные управления:
`emsync_period_lines = floor(vtotal·vrefresh/emsync_fps)` и
`emsync_pulse_width = floor(emsync_milli_pulse_width·hsync_period_cycles/1000)`.
`msm_drv.h:996–1008` прямо называет emsync_fps частотой EM pulses в Hz.
`sde_hw_intf.c:340–353` упаковывает period и width в16-bit поля
`INTF_ESYNC_EMSYNC_CTL`. Pinctrl reference
`canoe-sde-display-pinctrl-common.dtsi:141–179` содержит `mdp_esync0_out` и
`mdp_esync1_out`. Ссылки закреплены B на exact commits, GPIO номера reference
не переносились на XT2611-1.

Есть четыре обязательных ограничения:

- Width масштабируется длительностью **одной строки**, а не заявленной
  EM-period. Нельзя читать значение500 как50% duty всей OLED EM-последовательности.
  В binding «pulse period» неоднозначно; arithmetic source точнее этого пересказа.
- Integer line quantization и16-bit packing не позволяют объявить requested
  emsync_fps точной измеренной output frequency или безопасным непрерывным диапазоном.
- `dsi_panel.c:2493–2527` требует qcom,mdss-esync; connector property
  `emsync_fps` устанавливается только при emsync_switch_enabled
  (`sde_connector.c:4244–4264`). Mode match требует существующего соответствующего
  режима, иначе `-ENOENT` (`dsi_display.c:9194–9197,9255–9258,9288–9294`).
  Это не доступный произвольный setter, куда достаточно вписать2160.
- Проверенный генератор находится в `sde_encoder_phys_vid.c` и требует
  esync_enabled/hardware op. Самостоятельное чтение всех425 target property
  files подтвердило `qcom,mdss-dsi-panel-type = dsi_cmd_mode` и ноль имён
  esync/em-pulse-switch. Это несовпадение активного режима/конфигурации,
  **не доказательство отсутствия физической линии или DDIC capability**.

Следовательно, внешний EMSYNC заслуживает TOP-3 как reference-semantic lever
с явно высоким transfer blocker. Физический input mode и проводка, допустимый
EM rate, согласование panel command и host mode остаются неизвестными.
Даже измеренные внешние EM edges не докажут локальный OLED PWM без фотометрии.
Отсутствие ESYNC в выбранном DT закрывает готовую штатную ветку; цель R3 и
внутренний DDIC emission controller этим не закрываются. Native4F transaction
остаётся резервной semantic-discovery веткой с более слабой декодировкой.

## 6. Итог ревью и воспроизводимость

Критических арифметических дефектов A/B/C/root не найдено. В итоговой интеграции
требуются три ограничения: historical factorial assumption; MMIO/reference
не target-body proof; optical counterexample fixed-exposure, не full-video fit.
Наиболее сильный новый отрицательный вывод — прежняя redraw-атрибуция не является
уникальной. Он открывает полезный software delivery вопрос, сохраняя A9 baseline.

Воспроизведение без устройства:

```sh
python artifacts/horizon_r3_20261108/agent_d_verify.py --output NEW_REVIEW_JSON
```

Output создаётся exclusive; C JSON используется только как набор параметров
явного модельного контрпримера. Для формального independent check исходные
program bytes, run timestamps и DT corpus читаются прямо из первичных файлов.
Текущий branch/dirty state не принимается за новое состояние физического телефона.
