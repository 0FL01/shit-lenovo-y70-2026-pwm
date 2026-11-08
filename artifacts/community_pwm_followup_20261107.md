# Новая внешняя ветка: Android17 для AVR, без установки

2026-11-07. R3 остаётся открытой; A9-only сохраняется как промежуточный
экспериментальный baseline. Это поиск новых исходных panel tables, не обновление
телефона и не новый PWM-опыт.

## Проверенная гипотеза и полученные данные

`hypothesis`: более новая прошивка того же семейства AVR может дать новый
panel-specific diff, которого нет в уже разобранных CN/GLOBAL Android16.

`reported`: в точной теме
[Lenovo Legion Y70 2026 / Motorola Edge 70 Max, topic1121132](https://4pda.to/forum/lofiversion/index.php?t1121132.html)
найден rollout Android17 с5–6 ноября2026. Не путать с Y70-2022/topic1050561.
Проверены страницы135–140; это не полный аудит140 страниц.

- [Сообщение с предложением OTA, 05.11](https://4pda.to/forum/index.php?showtopic=1121132&view=findpost&p=145858450):
  опубликованный скриншот содержит **AI71WWH.15-43**, размер **2,59 ГБ** и Android17.
- [Сообщение после установки, 06.11](https://4pda.to/forum/index.php?showtopic=1121132&view=findpost&p=145876068):
  отдельный скриншот сообщает Android17 и security patch1октября2026.
- На страницах137/138 есть отдельные сообщения о канале TELEU. Это заявления
  участников и изображения, не собственная проверка модели/сборки другого телефона.
  Не делать из них вывод об OTA compatibility или изменении PWM.

Оригинальные PNG получены и просмотрены, не только OCR/snippet:
`/home/stfu/.cache/opencode-tmp/opencode/pwm-community-followup-20261107/`
содержит `android17-offer.png` (172554байт), `android17-update.png` (129578байт)
и соответствующие `.json` с URL/MIME/размером. Проверены PNG signatures и размеры.

## Доступность нового материала

На момент проверки оба публичных index:

- https://mirrors.lolinet.com/firmware/lenomola/2026/avr/official/TELEU/
- https://mirrors.lolinet.com/firmware/lenomola/2026/avr/official/RETEU/

перечисляют только старые Android16 W3WW36.65-25-3-4 и W3WW36.65-64-4.
В `MotorolaMobilityLLC/kernel-display-devicetree` и
`MotorolaMobilityLLC/kernel-msm-5.4-techpack-display` GitHub
`git/matching-refs/tags/MMI-AI71WWH.15-43` вернул HTTP200/пустой список.
Это отсутствие **точного префикса в этих двух repos**, не доказательство
отсутствия всех новых исходников или прошивки в интернете.

Файла OTA/нового dtbo/vendor_boot пока нет: побайтовое сравнение новых tables
**не выполнено**. Для него нужен сам AI71WWH.15-43 package или отдельные официальные
образы/соответствующий supplier source. Обновлять телефон ради получения этих
данных не предлагалось и не выполнялось.

## Read-only проверка существующего OTA-кэша цели

`confirmed-on-target`: transport47 заново идентифицирован как avr/XT2611-1,
`ro.build.display.id=W3WWS36.65-64-4-1`, Android16; UID0, `u:r:ksu:s0`, Enforcing.
Нельзя путать build ID с `ro.build.version.incremental=c9a7f-8fbf58`.

Без запуска OTA app/poll/download/install прочитаны уже существующие
`com.motorola.ccc.ota` preferences и три небольшие SQLite базы:

- `ota.db`: vt0/status0;
- `cus.db`: vt0/status0;
- `otaApp.db`: одна config запись SmartUpdateKey, нового build нет;
- `PRAGMA quick_check` всех трёх копий = `ok`;
- сохранённые smartUpdateOS/MR/общий enable = false,
  IS_UPDATE_PENDING_ON_REBOOT = false. USER_AUTO_DOWNLOAD_OPTION = WiFi,
  поэтому ручной запуск проверки OTA не считался инертным чтением.

Кэш не содержит ожидаемого download URL/manifest. Snapshots лежат **только**
в private cache `pwm-community-followup-20261107/ota-cache/`: directory0700,
исходные XML/DB0600. Там есть vendor application credentials: **не публиковать
сырые XML/DB и не передавать их поисковикам/в отчёты**. Значения секретов/идентификаторов
в публичные артефакты не копировались. Sanitized результат:
`ota-cache/sanitized-cache-check.json`.

Диагностика: первоначальный compound ADB command неправильно сериализовал
`su -c`; команды после `;` выполнялись как shell, что дало Permission denied.
Исправлена только host quoting через `shlex.quote` всей root-команды; повторная
проверка UID/context и чтение прошли. **SELinux/access blocker не установлен**,
политики не менялись. Результат — пустой кэш, не невозможность root-доступа.

## Отсеянные/ограниченные ответвления

- Рисунки11/12 уже сохранённого CN119811288A повторно рассмотрены именно на
  предмет регистровой схемы: fig2 — Gamma/Duty для1/3/6/9/12/15/18 pulses;
  fig4 — flowchart перехода Gamma через CMDQ. Адресов A9/91, encoding mask или
  latch recipe там нет. Это не новый register map и не основание выбрать hex18.
- В шапке темы найден [Rakkashin Kernel3.0.2](https://4pda.to/forum/index.php?showtopic=1121132&view=findpost&p=145568654).
  Автор описывает performance/thermal/battery, не PWM. Малый control ZIP по
  опубликованному URL `https://4pda.to/forum/dl/post/36361354/Rakkashin-Kernel-Control-v3.0.2.zip`
  вернул HTTP404; публичный точный indexed search не дал другого источника.
  Его код не получен/не проверен, отсутствие PWM в коде не заявляется. Ничего
  из AnyKernel/Magisk не запускалось и KernelSU-Next не заменялся.
- MCP извлекает body лишь до первого nested closing div; отсутствие текста
  после spoiler не принималось за отсутствие материала. Full HTML сохранил
  ссылку на Rakkashin; screenshots получены через Code Mode `fetch().bytes()`.
  Обычные urllib/curl получили403, а text-webfetch не поддержал PNG; это
  преодолённые transport/format ограничения, не блокеры самой цели.

## Следующая развилка, без фиктивного результата

Новый AI71WWH.15-43 — конкретный источник для будущего **offline** panel-table diff,
но не готовый high-PWM profile. Добыча пакета по уже доступным публичным индексам
и локальному кэшу результата не дала; сам package/source пока недоступен.
Нельзя заменить отсутствующие байты догадкой или установить OTA без отдельного
плана сохранения root/rollback.

Независимая аппаратная ветка — точный одноразовый S0C1 опыт из
`dsi_coupled_on_20261107/proposal.md` — имеет подготовленные байты и возврат,
но operation-specific confirmation отсутствует. Для её исполнения нужен
ответ владельца, включая emergency ordinary reboot при неопределённой очереди.
Готовность принять damage risk и HORIZON-nudge этого разрешения не заменяют.
Цель ≥2000Гц не объявляется невозможной или выполненной.
