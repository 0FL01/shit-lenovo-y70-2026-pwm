# Stock method control: replay the same DBV after each table

Scope: unchanged native OFF→ON→OFF under the existing autonomous stock-test scope;
no extra custom candidate/combination is authorized here. This is not a repeat of
the unchanged failed control: add the concrete missing post-table native brightness
operation present in the previous UI trial.

Each full875B/75packet stock table is followed by a standard sysfs write3600,
with native `51 0e 10` verification, then7seconds of camera recording. DBV remains
3600; camera100µs/ISO6400/manualfocus and software120Hz remain unchanged. Restore
full OFF **and** its DBV update before original target policy. Same native guards,
DMA-error log coverage and normal-reboot fallback; no flash or persistent profile.

The [control without DBV replay](../analysis.json) did not reproduce UI ON suppression.
Source/target-binary audit confirms same-value brightness is not skipped; the stock
DC wrapper itself does not issue that brightness update. A positive result here
would identify dependency on this operation/order, not prove an internal DDIC latch:
the standard brightness setter also issues DRM/dimming notifications.
