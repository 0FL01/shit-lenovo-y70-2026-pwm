# Реестр supersession: исторические ad-hoc RE-экстракторы

Это реестр, не физический архив. Исторические файлы остаются на исходных местах
в `artifacts/` как **замороженные evidence**; не редактировать и не перемещать их.
Для новых code-level работ не копировать per-recon экстракторы: использовать
[`../ghidra_decompile.py`](../ghidra_decompile.py) из PyGhidra venv
`~/tools/ghidra-12.1.4-pyvenv/bin/python` (Ghidra 12.1.4).

| Исторический путь / кейс | Назначение и статус |
| --- | --- |
| [`artifacts/runtime_pwm_recon_20261107/analyze.py`](../../artifacts/runtime_pwm_recon_20261107/analyze.py) | Ad-hoc symbols/relocations/ARM64 disassembly `msm_drm.ko` (также DT data). **Code-level часть superseded** единым Ghidra-входом для новых работ; прежние выводы и data-level часть не переписываются. |
| [`artifacts/brightness_policy_recon_20261107/result.md`](../../artifacts/brightness_policy_recon_20261107/result.md) | Использовал расширенный `runtime_pwm_recon_20261107/analyze.py` (см. result.md:216–220); отдельного `brightness_policy_recon_20261107/analyze.py` нет. Для нового code-level анализа — Ghidra; прежний clamp-model остаётся evidence. |
| [`artifacts/display_calibration_recon_20261107/result.md`](../../artifacts/display_calibration_recon_20261107/result.md) | Исторические code-level листинги `libstcMotoColor.so`, сохранённые в private cache, описаны отчётом; отдельного repo-local `analyze.py` нет. Метод ad-hoc дизассемблирования superseded для новых ARM64 работ, без публикации private cache. |
| [`artifacts/ddic_state_marker_20261107/analyze.py`](../../artifacts/ddic_state_marker_20261107/analyze.py) | **Data-level, не superseded Ghidra:** архивные raw reads, маркеры/DBV/DT arrays. Файл заморожен на месте; для новых data-level работ переиспользовать подходящие `06-tools` Python-инструменты, не копировать per-recon скрипт. |

Ни один существующий data/build/test-скрипт `06-tools` не архивирован и не заменён.
Ghidra помогает с control/dataflow кода, но не устанавливает семантику DDIC,
физическую PWM-частоту или runtime-исполнение ветки; независимые проверки обязательны.
Пин, команды и known-answer evidence: [`result.md`](../../artifacts/ghidra_toolkit_20261107/result.md).
