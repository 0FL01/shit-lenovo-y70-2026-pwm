# Verified sources and provenance

Dates and links checked on **2026-10-28**. Links are sources for investigation, not firmware endorsement or proof of compatibility.

## A. Pixel 8 Pro: actual modification

1. **Primary source: patch diff**
   - https://github.com/updateing/android_kernel_google_zuma/commit/6f7795dcf7b6a5c6f1c344c9de05ca10489b7d4d
   - One file: `google-devices/shusky/display/panel-google-hk3.c`; `+50/-11`; panel DCS `0xBD,0x21`, mode handling, `module_param_array(freq_cmd, byte, NULL, 0644)`.
   - Author says commands found by trial and error; higher frequency has severe artifacts. The code alone does NOT certify PWM by metrology.
2. **Hands-on followup (reported results and complications)**
   - https://www.androidcentral.com/phones/google-pixel-8-pro-display-upgrade
   - 240 Hz stock; temporary boot image and adjustable module parameter; reported steady use at 3840 Hz and an upper experiment at 4800 Hz; green tint, inconsistent colors with LTPO refresh transitions.
3. **Discussion / independent caveats**
   - https://discuss.grapheneos.org/d/15067-feature-request-pwm-display-options-to-reduce-screen-flickering
   - https://github.com/GrapheneOS/os-issue-tracker/issues/3850
   - Comments caution that this is NOT a generic one-line fix without a custom kernel; official GrapheneOS did not adopt it.
4. **Older project (different method, worth inspection only)**
   - Android Central links a different developer that reportedly disabled PWM on older Samsung/Pixel; **identify actual code and hardware before assuming relevance**.

## B. Target platform and kernel sources

1. **Motorola official source issue**
   - https://github.com/MotorolaMobilityLLC/kernel-msm/issues/854
   - Exact `XT2611-1`, requested `W3WWL36.65-11-18`, published July 28 2026. Issue text includes kernel line `6.12.58-android16-6-g18b507169406-ab14630870-4k`; this is from requester, NOT yet read from owner device.
2. **Official tagged kernel**
   - https://github.com/MotorolaMobilityLLC/kernel-msm/releases/tag/MMI-W3WWL36.65-11-18
   - Tag `MMI-W3WWL36.65-11-18`, release note `Avr push for Android 16`.
3. **Additional Motorola repos to inspect, not yet validated for target**
   - https://github.com/MotorolaMobilityLLC/kernel-display-devicetree
   - https://github.com/MotorolaMobilityLLC/kernel-devicetree
   - https://github.com/MotorolaMobilityLLC/kernel-kernel_device_modules-6.12 (WARNING: default tree appears to include MediaTek paths; don't assume relevant to Snapdragon / avr)
   - Motorola organization contains many modular repos; find target-specific releases/tags or their actual absence.
4. **China firmware exact-model index**
   - https://mirrors.lolinet.com/firmware/lenowow/2026/Legion_Y70_2026/XT2611-1/
   - Listed `XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18...zip` and `...W3WWL36.65-48-7...zip`.
5. **Global firmware related-model index**
   - https://mirrors.lolinet.com/firmware/lenomola/2026/avr/official/TELEU/
   - Listed `XT2611-3_AVR_RETEU_16_W3WW36.65-25-3-4...zip` and `...W3WW36.65-64-4...zip`. Distinct model SKU; offline diff only.
6. **Official device product page**
   - https://en-us.support.motorola.com/app/answers/detail/a_id/193097/~/specifications---moto-edge-70-max
   - Android 16; Snapdragon 8 Gen 5; 144 Hz display. Says nothing about panel IC.

## C. PWM observations and distinction

1. **China spec/review: 720 Hz, DC-like**
   - https://mobile.zol.com.cn/1183/11838624.html
   - https://www.donews.com/news/detail/5/6561781.html
2. **Independent Chinese model review with setting behavior**
   - https://mt.today/obzor_lenovo_legion_y70_new_generation_vozvraschenie_legendy!8vlpht
   - Reports BOE Q10 and a DC Dimming setting; shutter-band behavior differs; frequency not measured.
3. **Notebookcheck global Edge 70 Max**
   - https://www.notebookcheck.net/Motorola-Edge-70-Max-smartphone-review-Record-breaking-battery-life-and-flagship-features-at-a-low-price.1430009.0.html
   - Reports 167 Hz and amplitude 14%; **not proof of owner unit or exact operating condition**.

## D. Reference extraction tools (AOSP or identifiable upstream)

- Android dynamic partitions: https://source.android.com/docs/core/ota/dynamic_partitions/implement
- AOSP partition tools (`lpunpack`, `lpdump`): https://android.googlesource.com/platform/system/extras/+/refs/heads/master/partition_tools/
- AOSP mkbootimg and unpack_bootimg: https://android.googlesource.com/platform/system/tools/mkbootimg/
- AOSP libufdt / `mkdtboimg`: https://android.googlesource.com/platform/system/libufdt/
- AOSP Android Verified Boot: https://android.googlesource.com/platform/external/avb/
- Firmware zip might be XML + sparsechunks, `payload.bin`, `super.img` or standalone images: inspect archive before choosing extraction path.
