# Unmodified stock ON — positive control of the replay method

Scope: existing autonomous stock DC/camera testing, not a fourth hybrid candidate.
No new DSI bytes, combined experimental blocks, images or persistent override.
The completed three-block authorization is not extended to more custom profiles.

Sequence: complete live stock OFF → complete live stock ON → complete stock OFF,
each7seconds atDBV3600/software120Hz. Camera720p/100µs/ISO6400, AE/AFoff/fixedfocus.
Both875B/75packet arrays are read **unchanged** from the selected live DT snapshot;
the ON sequence was already observed through native UI in the stock transport and
manual-camera trials. The existing replay path already demonstrated a physical
signal change for mode90, but full ON through that path lacks a positive control.

Use the same native packet/HS/batch/pending-count/return checks, also inspect the
DMA completion error log through each hold: its void wait may not propagate an
errno. On uncertainty stop and reboot normally; otherwise return the complete
OFF program before restoring target settings. No image write or permanent mount.

Stock software `panelDC` remains0 during raw ON; this is intentionally a method
control, not an assertion that replay updates the UI/kernel DC bookkeeping.
Compare with the previously recorded native-UI ON effect. Suppression of the fine
train would validate this optical effect through replay, **not certify higher Hz**.
If the effect is absent, investigate the path difference before more custom bytes.
