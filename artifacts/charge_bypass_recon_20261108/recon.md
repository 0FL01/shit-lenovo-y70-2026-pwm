# Charge bypass / direct power supply — RECON 2026-11-08

Цель: заставить телефон 24/7 работать от USB, не заряжая/не циклируя батарею.

## Устройство

- Lenovo Legion Y70 (XT2611-1), глобальная прошивка Motorola Edge 70 Max.
- `ro.build.display.id=W3WWS36.65-64-4-1`, kernel `6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k`.
- adb-устройство `avr_g` (второе подключённое `cancunf` — moto g54, не цель).
- KernelSU-Next `ksud 3.4.2`, UID0 через `su` работает (`u:r:ksu:s0`).

## Текущее состояние питания

- `capacity=100`, `status=Full`, `health=Good`, `temp=27 °C`, `cycle_count=0`, SoH 100 %.
- `charge_full=7 714 000 µAh`, `charge_full_design=8 000 000 µAh`.
- USB online, тип SDP (USB 2.0), 5 V, `input_current_limit=500 000 µA`, измеренный ток 147–497 мА.
- Базовая конфигурация драйвера: `CDIS=0, CSUS=0, CFULL=1` (до экспериментов).

## Найденные узлы управления (все — sysfs, без записи разделов)

Платформенное устройство:
`/sys/devices/platform/soc/soc:pmic-glink/soc:pmic-glink:battery-charger/`

| Узел | Права | Смысл |
|---|---|---|
| `direct_power_supply` | 0664 system:system | Официальный «direct power supply» / bypass: `1` → голос `disable_charging` от `MMI_DIRECT`, `CDIS=1`; `0` → снять голос |
| `force_charger_suspend` | 0644 root | `1` → `CSUS=1`, вход зарядки отключён, телефон работает от батареи (ADB сохраняется) |
| `force_charging_disable` | 0200 root | принудительный disable зарядки (фабричный) |
| `force_charging_enable` | 0660 vendor_tcmd | обратный фабричный enable |
| `factory_charge_upper` | 0444 | фабричный лимит 70 % |

Лимит заряда Motorola Adaptive Charging:
`/sys/module/qpnp_adaptive_charge/parameters/upper_limit` и `lower_limit` (0664 system).
`-1` — значение по умолчанию «выключено»; через sysfs `-1` обратно не выставляется
(store клампит в 100), восстанавливается только перезагрузкой/перезагрузкой модуля.

## Эксперименты (обратимые, только sysfs)

### 1. Bypass: `direct_power_supply=1` — подтверждён на цели

- dmesg: `mmi_vote: disable_charging:MMI_DIRECT voter: en:1`, затем
  `mmi_configure_charger: CDIS=1, CSUS=0, CFULL=1`.
- 60 с выборки (12×5 с): `battery/current_now=0`, `charge_counter=7 714 000` без изменений,
  `usb/online=1`, USB-ток ~187–347 мА (в среднем ~200 мА), ADB жив.
- Вывод: телефон питается от USB, батарея не заряжается и не разряжается.
  Порт SDP 500 мА для idle-нагрузки достаточно.

### 2. Дренаж: `force_charger_suspend=1` — подтверждён на цели

- dmesg: `force_charger_suspend_store: set force_charger_disabled`,
  `mmi_configure_charger: CDIS=0, CSUS=1, CFULL=1`.
- Батарея: `batt_ua=-198 000` (разряд ~200 мА), `usb/online=1`, ADB не отвалился.
- Авто-возврат через 20 с (тестовый watchdog) сработал; состояние вернулось в `CSUS=0`.
- Вывод: можно разряжать телефон до целевого SoC, не теряя ADB. Оценка 100 %→60 %:
  ~3.1 А·ч / 0.2 А ≈ 15–16 ч.

### 3. Adaptive charge limit — проверен, есть нюанс

- `upper_limit=60`, `lower_limit=55` → драйвер сразу голосует `suspend_charging`/`stop_charging`
  (`ADAPTIVE_CHARGING_VOTER`), dmesg: `Batt cap is 100, upper limit is 60`.
- Попытка вернуть `-1` дала `upper_limit=100` (store не принимает `-1` из состояния ≠ -1).
  Функционально это «заряд до 100 %», не поломка; `-1` вернётся после reboot.
- Текущий побочный эффект: `upper_limit=100` держит `CDIS=1` при 100 % (батарея idle).
  Это безвредно; для чистого stock-состояния нужен reboot.

### 4. Официальная реализация Motorola

- В `com.motorola.gamemode` (GameMode) есть строки
  «Bypass charging», «Use Bypass charging»,
  «Bypass charging is enabled/disabled during gameplay»,
  ключи `direct_power_supply_state`, `direct_power_supply_tile`, `direct_power_supply_status`;
  permission `direct_power_supply`, activity `.ui.PreferenceSettingsActivity`.
- Это подтверждает, что `direct_power_supply` — штатный механизм bypass,
  но штатный UI включает его только на время игры, не 24/7 для ADB.

## План

### Phase 0 — чистый baseline (по желанию)

- Reboot → проверка: `direct_power_supply=0`, `upper_limit=-1`, `CDIS=0`, зарядка снова активна.
- Это также снимет побочный эффект `upper_limit=100`.

### Phase 1 — парковка на 60 %

- Включить `force_charger_suspend=1`.
- Watchdog (host или on-device) каждые 60 с читает `capacity`; при `<=60`:
  `force_charger_suspend=0`, сразу `direct_power_supply=1`.
- Жёсткий стоп на 55 %, если 60 проскочили.
- Оценка: ~15–16 ч в idle при сохранённом ADB; альтернатива — отключить кабель
  и разрядить телефон обычным использованием.

### Phase 2 — включить bypass

```sh
P=/sys/devices/platform/soc/soc:pmic-glink/soc:pmic-glink:battery-charger
echo 1 > $P/direct_power_supply
# опционально страховка:
echo 60 > /sys/module/qpnp_adaptive_charge/parameters/upper_limit
echo 55 > /sys/module/qpnp_adaptive_charge/parameters/lower_limit
```

Проверка: `dmesg | grep CDIS=` → `CDIS=1, CSUS=0`; `current_now≈0`;
`charge_counter` стабилен; `usb/online=1`; ADB жив.

### Phase 3 — persistence (KernelSU)

KernelSU 3.4.2 поддерживает `/data/adb/service.d` (подтверждено строками `ksud`).
Минимальный скрипт `/data/adb/service.d/bypass_charge.sh` (0755, root):

```sh
#!/system/bin/sh
NODE=/sys/devices/platform/soc/soc:pmic-glink/soc:pmic-glink:battery-charger/direct_power_supply
BASE=/data/adb/bypass_charge
mkdir -p "$BASE"
# страховка от заряда выше 60 %, если bypass выключен
echo 60 > /sys/module/qpnp_adaptive_charge/parameters/upper_limit 2>/dev/null
echo 55 > /sys/module/qpnp_adaptive_charge/parameters/lower_limit 2>/dev/null
while [ ! -e "$NODE" ]; do sleep 5; done
(
  while true; do
    [ -e "$BASE/off" ] || { [ "$(cat "$NODE" 2>/dev/null)" = 1 ] || echo 1 > "$NODE" 2>/dev/null; }
    sleep 15
  done
) &
```

- `bypass_off`: `touch /data/adb/bypass_charge/off; echo 0 > $NODE`
- `bypass_on`: `rm -f /data/adb/bypass_charge/off; echo 1 > $NODE`
- Watchdog нужен, потому что GameMode/framework может писать `0` при выходе из игры.
- После reboot проверить: `direct_power_supply=1`, `CDIS=1`, батарея idle.
- Физический тест: выдернуть/воткнуть USB — bypass должен сохраниться.

### Phase 4 — суточная проверка

- `capacity` стабилен на 60 %, `current_now≈0`, `charge_counter` не растёт/не падает,
  `temp` в норме, `dmesg` без `CDIS=0` при подключённом кабеле.
- Если при включённом экране/нагрузке батарея проседает (USB не тянет),
  добавить powered hub / USB-C PD dock с data passthrough.

### Rollback

```sh
P=/sys/devices/platform/soc/soc:pmic-glink/soc:pmic-glink:battery-charger
echo 0 > $P/direct_power_supply
rm -f /data/adb/service.d/bypass_charge.sh
reboot   # вернёт upper_limit=-1
```

Никаких записей в разделы, boot image и AVB не требуется; KSU-root не трогается.

## Риски и неизвестные

- `direct_power_supply` — штатный, но decompile показывает только голос `disable_charging`
  без проверки типа зарядника; проверено на SDP 500 мА. Поведение с PD/hub не проверено.
- При 100 % SoC календарное старение остаётся; поэтому парковка на 60 %.
- Если USB не покрывает пиковую нагрузку, батарея подмешивает ток (это не краш).
- `upper_limit=-1` не восстанавливается через sysfs; только reboot/перезагрузка модуля.
- GameMode может перезаписывать узел; watchdog это закрывает.
- Точная семантика `MMI_DIRECT` в прошивке charger-ADSP не документирована;
  вывод основан на dmesg и поведении токов.
