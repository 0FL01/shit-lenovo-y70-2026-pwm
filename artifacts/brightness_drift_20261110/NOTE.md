# Native DBV drift: offline assessment, 2026-11-10

## Вывод и границы

Причина переходов 828 ↔ 6438 **unknown**. Эта работа не выполняла Android/ADB/research-usb calls, device reads/writes, capture, commit или push. Новая диагностика остаётся за действующим execution/action gate. Нет доказательства повреждения, внешнего вмешательства или переключения feature flag.

**confirmed-on-target (исторические отчёты):** `../pwm_resume_20261108.md:328–342` фиксирует native828 в setup02 и6438 в03 при прежнем Android98/manual. `../p85_stock_a001_20261108_04/hardware_result.md`, раздел «Восстановлен именно saved original», подтверждает отдельный saved/native restore6438, пять Android settings и проверки cleanup. Пять settings сами по себе недостаточны для native equivalence; это не отменяет отдельно выполненную native проверку прошлого run и не доказывает, что restoration тогда провалился. Позднейший drift нельзя датировать или объяснять этими двумя snapshots.

**reported (assignment координатора):** 2026-11-10 12:26 native6438 и14:06 native828 при одинаковых screen_brightness98, manual0, min/peak120.0, timeout1800000. В этой offline работе сегодняшние snapshots независимо не перечитывались.

## Подтверждённый reference механизм, не доказательство target runtime

Официальный AOSP `android-16.0.0_r1`:

- [BrightnessSynchronizer.java](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/com/android/internal/display/BrightnessSynchronizer.java): строки96–120 startup предпочитает float, fallback на int;149–160 legacy `brightnessIntToFloat` линейно отображает integer1..255;300–332 `brightnessIntSettingToFloat` нормализует1..255, применяет gamma→linear и отображает в текущие BrightnessInfo minimum/maximum. Строки519–527 выбирают эти пути по `mIntRangeUserPerceptionEnabled`. Строки264–279 читают float через **DisplayManager.getBrightness(DEFAULT_DISPLAY)** и integer через Settings для CURRENT user. Поэтому дополнительный `settings screen_brightness_float` сам по себе не является чтением authoritative float в этой версии AOSP.
- [BrightnessUtils.java](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/com/android/internal/display/BrightnessUtils.java): строки28–31 предупреждают, что transfer function требует линейного backlight control;49–63 задают HLG gamma conversion.
- Сохранённый reference `../../06-tools/transient_display_recovery_20261109/reference/DisplayManagerService.java:663–664` передаёт флаг `isBrightnessIntRangeUserPerceptionEnabled`. Это AOSP reference, не decompile фактически запущенной Motorola реализации.

**hypothesis:** разные semantics conversion, reconciliation, pending/temporary/window override, power/brightness clamp или vendor mapping могут объяснить расхождение. Один неизменный флаг и неизменные bounds сами по себе не объясняют внезапную смену; нужен фактически иной source/path/state. Target firmware implementation/flag/bounds/mapping и причина остаются **unknown**. Наличие сохранённых framework/services JAR не доказывает их кодовый путь; их decompile в этой работе не выполнялся.

## Численный clue слабее точного соответствия

Только при условной линейной native шкале0..16383:

- rough98/255: linear6296.21, gamma806.57;
- AOSP normalization(98−1)/254: linear6256.50, gamma796.43;
- наблюдавшиеся828/6438 соответствовали бы0.05054019/0.39296832.

Ни один расчёт не совпадает точно. BrightnessInfo bounds и vendor mapping неизвестны. Это основание проверить semantics, не установленный диагноз и не готовая формула target DBV.

## Минимальная будущая read-only дискриминация

Только после разрешённого assignment: два bounded snapshots с timestamps, current user/display ID и тем же boot, без setters, UI действий и общего неотфильтрованного dump.

1. Native DBV/power/actual mode/DC вместе с теми же пятью settings.
2. BrightnessSynchronizer: mLatestIntBrightness, mLatestFloatBrightness, mIntRangeUserPerceptionEnabled, mCurrentUpdate, mPendingUpdate. AOSP dump этих полей: строки134–143.
3. DisplayManager brightness / BrightnessInfo brightnessMinimum, brightnessMaximum и доступные effective brightness/adjusted values. Optional screen_brightness_float прочитать только как secondary setting, не источник истины.
4. DisplayBrightnessController current/pending/last-user float и выбранная brightness strategy; temporary/window override; DisplayPowerController mBrightnessReason и modifiers, applied/effective brightness/ramp target. При mismatch смотреть bounded clamp/range state, а не сразу новые mutations.

Reference dump anchors: DisplayBrightnessController.java:559–582; TemporaryBrightnessStrategy.java:72–74; OverrideBrightnessStrategy.java:69; DisplayPowerController.java:2702,2732–2747, все под `06-tools/transient_display_recovery_20261109/reference/`.

Если float меняется с native при прежнем int, исследовать source/reconciliation/override. Если float и bounds стабильны, а native различается, искать ниже framework либо effective adjustment/ramp. Даже при совпадении int+float нужен native verification: settings equivalence не равно физической яркости или optical/PWM equivalence. Наблюдение read-only не гарантирует атомарность; повторение помогает выявить переходный state, но не устанавливает causality.
