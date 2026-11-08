# P85 stock-only 02: preflight keyguard, без register trial

Код из committed/clean source `47a7782490f940560525865fefffdf38d8e4f728`
остановился в setup до native anchor, baseline reads, camera recording и P85 writer.
Экран был ON/AWAKE, но KeyguardStateMonitor сообщил `mIsShowing=true` и
`mInputRestricted=true`. Проверка unlocked не ослаблялась.

[run.json](run.json): zero candidate attempts, пустой список register85 writes,
unknown-value writes отсутствуют. Исходные settings/native DBV828/logger
восстановлены, watchdog снят, mutex освобождён; reboot не выполнялся.
Камера только опрошена на preflight, запись не начиналась. Ошибок cleanup нет.

Отдельно координатор один раз вызвал обычный OS `wm dismiss-keyguard`.
Никакие credentials не вводились и security settings не изменялись.
Две последующие read-only проверки подтвердили ON/AWAKE и `mIsShowing=false`:
[keyguard_postcheck.json](keyguard_postcheck.json). Это не обход защищённого замка
или изменение его политики. Новый опыт требует нового ID и всех прежних guards.

Same-value85 runtime write остаётся неквалифицированным; неизвестный14 и
физические >=2000Hz не проверялись. Исходный failed run сохранён без изменений.
