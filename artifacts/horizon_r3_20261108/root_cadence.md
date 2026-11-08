# Pixel-frame delivery: новый проверяемый пробел между командой и эмиссией

Статус: `reported`, офлайн-анализ публичного Motorola reference source и
сохранённых target-origin журналов. **Не подтверждённый PWM setter.**
Ни телефон, ни камера, ни ADB/DSI в этой работе не использовались.

## Новое наблюдение

Историческая проверка redraw доказывала отсутствие дополнительных
**зарегистрированных control transfers**. Она не измеряла число pixel-frame
transfers, TE edges, момент внутреннего DDIC latch или внутреннюю scan cadence.
Публичный source показывает конкретный отдельный путь, который такой observer
не обязан видеть: command-mode frame kickoff → SDE CTL_START MMIO.

Это существенно для следующего шага: переход после открытия/закрытия диалога
нельзя однозначно назвать внутренним latch. Обновление изображения, frame
delivery, переход active/idle и просто elapsed time остаются альтернативами.

## Первичные source anchors

Все ссылки ниже закреплены на MotorolaMobilityLLC
`kernel-msm-5.4-techpack-display`, commit
`fa008c43c070ff20faa33853649f5dfd4c427e99`. Репозиторий называется `5.4`,
это не утверждение о версии kernel целевого аппарата. Источники получены
через read-only GitHub file API 2026-11-08.

- [`msm/sde/sde_encoder_phys_cmd.c:2563–2591`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_encoder_phys_cmd.c#L2563-L2591):
  `sde_encoder_phys_cmd_trigger_start` читает connector autorefresh property.
  При ненулевом frame count вызывает `_sde_encoder_phys_cmd_config_autorefresh`,
  иначе `sde_encoder_helper_trigger_start`. Привязка callback к ops — строка2740.
- [`sde_encoder_phys_cmd.c:82–131`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_encoder_phys_cmd.c#L82-L131):
  property — `CONNECTOR_PROP_AUTOREFRESH`; конфигурация хранит frame_count
  и enable, затем вызывает hardware setup operation. Это параметры frame
  delivery, **не названное число OLED emission pulses**.
- [`msm/sde/sde_encoder.c:5543–5544,5563–5579`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_encoder.c#L5563-L5579):
  physical ops callback и helper передают управление `ctl->ops.trigger_start`.
- [`msm/sde/sde_hw_ctl.c:497–503,1815`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_hw_ctl.c#L497-L503):
  HWIO operation пишет1 в `CTL_START` через `SDE_REG_WRITE`. Определение register
  offset — строка27 (`0x01C`). **Это source evidence, не предложение писать MMIO.**
- Для сравнения, [`msm/dsi/dsi_display.c:1527–1613`](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_display.c#L1527-L1613)
  разбирает command buffer и отправляет descriptors через `dsi_host_transfer_sub`;
  downstream `dsi_ctrl_cmd_transfer` — в том же файле4009–4085.

В проверенной reference-цепочке frame kickoff нет вызова
`dsi_display_cmd_transfer`/`dsi_ctrl_cmd_transfer`. Это ограниченный разбор
указанных прямых веток, не полная теорема об отсутствии всех побочных вызовов.

## Что связано с целевым аппаратом

[`06-tools/run_dsi_mode_trial.py:24–28`](../../06-tools/run_dsi_mode_trial.py)
определяет только probes `dsi_display_cmd_transfer` entry/return и
`dsi_ctrl_cmd_transfer` return. В `observe_redraw:417–429` отсутствие записей
проверяется по строкам `dsi_ctrl_cmd_transfer`. `repaint_settings:371–398`
открывает/закрывает Settings chooser; это не контролируемая доставка одного
неизменного pixel buffer и не matched sham.

В сохранённом target symbol listing
[`runtime_pwm_recon_20261107/evidence/symbols.txt`](../runtime_pwm_recon_20261107/evidence/symbols.txt)
есть `sde_encoder_helper_trigger_start` (строка16429, `.text+0x962e0`),
`_sde_encoder_phys_cmd_config_autorefresh` (16489, `0xb5a00`),
`sde_encoder_phys_cmd_trigger_start` (16526, `0xb367c`) и
`sde_hw_ctl_trigger_start` (16913, `0x13dbb0`).
**Наличие symbols не устанавливает совпадение тел с reference source.**
В текущем checkout target ELF отсутствует, новый binary review этих функций
не выполнялся; function body и фактическая вызванная ветка на target — `unknown`.

Проверка арифметики и coverage observer воспроизводится
[`root_offline_audit.py`](root_offline_audit.py) →
[`root_offline_audit.json`](root_offline_audit.json). Она не декодирует видео
и не реконструирует отсутствующие trace events.

## Независимый временной confound

Agent A дополнительно извлёк timestamps из сохранённого
[`dsi_stock_on_control_20261106/with_redraw/run.json`](../dsi_stock_on_control_20261106/with_redraw/run.json):
ON передан21:33:03.348524Z; DBV replay21:33:03.630454Z;
before-redraw hold заканчивается через7.357898s после replay,
after-redraw hold начинается через14.796735s. Эти интервалы относятся
к журналу host, не к аппаратному времени эмиссии.
Подробные JSON pointers и независимый parser —
[`agent_a_factorization.json`](agent_a_factorization.json).

Поэтому гипотеза отложенного применения, не требующего redraw, не была
отделена equal-duration sham. Это новый audit существующего результата;
само историческое подавление fine после ON+redraw остаётся валидным.

## Управляющий рычаг и минимальное различение

**Кандидат:** менять доставку кадров/момент data update при неизменных
stock-backed DDIC profile, DBV, requested refresh и измерительном ROI.
Причинная гипотеза: DDIC применяет emission configuration только по data event
либо выбирает другой scan/emission schedule в active-update и idle состояниях.
Лишь после подтверждения этой зависимости имеет смысл искать доступ к её
cadence/scan policy для изменения физической эмиссии.

Минимальный причинный дизайн после отдельного разрешения:
сравнить одинаковое время ожидания после одного profile application в двух
ветках: sham без pixel update и заданный update event, логируя **саму доставку
кадров**, а не только control DSI. Изображение в optical ROI одинаково;
display-wide content/APL и thermal условия также контролируются. Прежний
dialog-open/cancel не заменяет такой контроль. После подтверждённого latch
однократного события отдельно сравнить static hold и непрерывные одинаковые
frame commits; нельзя смешать эти два вопроса в одну причинную оценку.

Если sham в те же сроки меняет optical response — frame-triggered latch как
необходимая причина отвергается для данного режима. Если одно событие вызывает
устойчивый переход без ongoing cadence — поддерживается event-latch, а не
необходимость постоянных updates. Если эффект появляется только при ongoing
cadence и обратим — появляется конкретный software lever для следующей
optical-frequency проверки. Любой такой результат ещё не равен ≥2000Hz.

Риск app-level stimulus ниже новой DDIC-последовательности, но forced DRM
autorefresh/MMIO не разрешены и не предлагаются. Нужны квалификация target
frame-observer и отдельный bounded runner; сейчас такого hardware-runner нет.
Рычаг имеет высокий information gain по причине старого redraw-effect и
неизвестную/низкую априорную вероятность достижения ≥2000Hz без новой DDIC карты.
Это самостоятельная ветка после готового A0D1C1, не повод повторить S0C1
или назначить requested refresh физической PWM-частотой.
