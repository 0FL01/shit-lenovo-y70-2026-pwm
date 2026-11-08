# Competing hypotheses and falsification strategy

## H1: Chinese ROM exposes a real high-frequency PWM mode hidden in global ROM

Why plausible: China reviews explicitly claim 720 Hz PWM + DC-like mode; stock RETCN images and related global RETEU images available.

Support needed: exact owner-panel ID; code path or DSI command set differing by region; captured optical waveform of the same hardware under stock conditions and different modes.

Falsifiers: command bytes identical, Chinese description refers to harmonics/measurement methodology, hardware panel revision differs, or optical waveform shows no material improvement.

Next: compare firmware, identify CN DC setting, trace control path. No region flash just to test this claim.

## H2: Existing global Flicker prevention already switches DC-like mode but changes waveform little

Why plausible: user reports no perceived relief; DC-like dimming can still have LTPO/scan-driven luminance changes; multiple optical signal components.

Support needed: system setting -> vendor route -> command/profile plus waveform delta. UI toggle alone insufficient.

Falsifiers: no command/value change, broken switch, globally disabled setting, or error in settings binding.

Next: ADB snapshots off/on, optical before/after, source trace.

## H3: Panel IC has undocumented programmable PWM multiplication, analogous to Pixel HK3

Why plausible: Pixel demonstrates software-configurable panel PWM is possible on some OLED controllers.

Support needed: BOE panel model and IC docs/known-good vendor profile, command semantics, successful reversible bench testing on exact display.

Falsifiers: locked controller, fixed waveform intrinsic to panel driver, zero public docs or command path, unacceptable artifacts.

Next: disassemble original panel initialization tables, search vendor Qualcomm implementations on matching controller; HK3 bytes are not reused.

## H4: Physical brightness/duty modulation already contains fast PWM plus slow LTPO envelope

Why plausible: 167 Hz global review vs claimed 720 Hz CN; optical instruments may report different frequency components or mode-specific behavior.

Support needed: sufficiently fast photodiode waveform and FFT at multiple refresh rates / brightness levels, compare harmonics and slow envelope.

Falsifiers: clean single fundamental under identical measurement parameters.

Next: baseline optical protocol before claiming success.

## H5: Only software pseudo-DC / sustained high hardware brightness is achievable

Why plausible: no usable programmable high-frequency DSI mode or proprietary panel firmware path.

Support needed: comprehensive negative research with sources/partitions enumerated; software workaround changes brightness/waveform/symptoms but does not physically raise PWM.

Next: mark fallback distinct from native PWM patch. This is an acceptable research outcome, but not completion of native PWM objective.
