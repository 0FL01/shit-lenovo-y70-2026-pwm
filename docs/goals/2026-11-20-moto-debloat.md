# Цель: debloat Motorola ROM на Legion Y70

Статус: blocked — закреплён один штатно неотключаемый пакет; остальной debloat проверен.

Источник: решение владельца после live RECON от 2026-11-20 — отключить рекламные компоненты, ненужный AI и проверенных кандидатов диагностики; удалить навязанные игры; проверить и задокументировать.

Цель: Lenovo Legion Y70 XT2611-1, Motorola Android 16 W3WWS36.65-64-4-1, пользователь 0.

| ID | Приёмка | Доказательство | Статус |
| --- | --- | --- | --- |
| R1 | 7 рекламных и установочных компонентов, 5 AI-компонентов и 3 кандидата диагностики отключены для пользователя 0 без очистки данных. | 14 из 15: `installed=true`, `enabled=3`. `com.motorola.installer` остался в исходном `enabled=1`: `pm disable-user --user 0` → `Failure: package is non-disable`; кнопка Disable в App info неактивна. | blocked |
| R2 | Удалены только 9 обычных приложений, назначенных `com.dti.motorola`. | Входной installer attribution повторён непосредственно перед удалением; девять `Success`, все девять отсутствуют даже в `pm list packages -u --user 0`. `/data` показал +2,35 ГиБ свободного места за время удаления. | verified |
| R3 | Nothing HOME, Moto Recents, Play Store/штатный установщик и выбор звуков не регрессируют в пределах доступной проверки; сравнить состояние связи. | Жесты HOME и Recents, панель уведомлений, запуск Play Store, установка и удаление тестового APK, неизменный выбор обработчиков APK/звонков/SMS/OTA. Настройки звуков совпали; штатный picker вновь открылся с `oi!`. Статус Wi-Fi/сети совпал с исходным. | verified |

## Согласованный список

- Реклама и автоустановка: `com.dti.motorola`, `com.aura.oobe.motorola`, `com.motorola.installer`, `com.motorola.playautoinstallext`, `com.taboola.mip`, `com.motorola.smartfeed`, `com.motorola.ccc.notification`.
- AI: `com.lenovo.qira`, `com.lenovo.qiracore`, `com.motorola.aicore`, `com.motorola.aiservices`, `com.motorola.aitranslation`.
- Диагностика, по одному: `com.motorola.motocare`, `com.motorola.help.extlog`, `com.motorola.wifi.motowifimetrics`. Постоянные `com.motorola.dciservice`, `com.motorola.android.nativedropboxagent` и связанные с OTA/модемом службы не в списке.
- Удалить: `ball.sort.puzzle.color.sorting.bubble.games`, `com.block.juggle`, `com.king.candycrushsodasaga`, `com.nebula.mahjongtile`, `com.nebula.rotaterings`, `com.oupeng.sugarburst`, `com.pixel.art.coloring.color.number`, `sorting.games.goods.sort.triple.match3d.puzzle.stuff`, `water.sort.puzzle.game.color.sorting.free`.

## План и границы

1. По [регламенту ADB](../../03-investigation/adb-remote.md) опознать оба устройства и активного пользователя; снять исходное состояние пакетов, ролей и звуков. Логи и идентификаторы вне Git.
2. Отключить установщиков и ленты, проверить основные функции, затем отключить AI и кандидатов диагностики отдельными шагами. При регрессии вернуть состояние соответствующего пакета: `pm default-state --user 0` для исходного `enabled=0` или `pm enable --user 0` для `enabled=1`.
3. Только после отключения DTI и успешной проверки удалить девять подтверждённых DTI-игр. Данные игр не сохраняются; возврат — переустановка, без обещания возврата прогресса. Перепроверить состояние пакетов и UI, записать результат.

Не менять ROM, лаунчеры, телефонию, OTA, MediaStore, выбор звуков, KernelSU/PWM, остальной софт и уже отключённые пакеты. Без root и перезагрузки. Работать только до прохождения R1–R3 или установленного блокера.

## Итоговый checkpoint

- Отключены все перечисленные пакеты, кроме `com.motorola.installer`. Из фактически отключённых до прогона `enabled=1` имели `com.dti.motorola`, `com.aura.oobe.motorola`, `com.taboola.mip`, `com.lenovo.qira`; все остальные имели `enabled=0`. Откат индивидуальный по шагу 2.
- DTI был отключён до удаления игр. Штатный установщик APK остался `com.google.android.packageinstaller`; одноразовый APK без кода и разрешений установлен через ADB и удалён. В crash buffer за время прогона нет новых падений HOME, Recents, SystemUI, Settings, Play Store, штатного установщика или `system_server`.
- На стенде Wi-Fi исходно выключен, голосовая и пакетная связь исходно `OUT_OF_SERVICE`; звонок, SMS, скачивание из Play Store и повтор после перезагрузки не проверялись. Проверены запуск Play Store, обработчики связи, панель уведомлений и сохранённые `crossing` для двух SIM, `oi!`, `trad`.
- Блокер R1 не распространяется на остальные 14 пакетов. Следующее действие возможно только по отдельному решению о работе с защищённым Moto Installer; текущий прогон его не меняет. Сырые отчёты вне репозитория.
