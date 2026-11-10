# Actual read-only observation

Status: confirmed-on-target read-only snapshot, 2026-11-10 14:06:07.083594
through 14:06:08.327389 UTC. The separately approved one-shot retry completed
with SSH exit0, final receipt and closed host descriptors. The preceding denied
attempt had no job or local execution begin/outcome files. No device settings,
camera recording, native brightness, DSI, selectors or recovery changed.

The reviewed cfc4e06 wrapper deployed the exact unchanged observer and ran its
source-only validation before device reads. Frozen dependencies remain d5a522c.
See ACTUAL_READINESS.json for the sanitized result; full role/boot provenance
remains private. The fresh destination is spent and must not be reused.

Both role identities and before/after boots verified. Lenovo was Awake, with
native DBV828, power0, DC0, logger0 and no ownership mutex. Framework values:
brightness98, manual0, minimum/peak120.0, timeout1800000ms. Native DBV differs
from the 12:26 postcheck6438 while these settings match. The cause is unknown;
neither value is a future restore default. Capture setup must snapshot fresh
actual originals and recheck stability.

The camera was stopped PREVIEW. Installed version96/1.56.2 matches the researched
Open Camera version string, but that does not establish binary/source identity.
Manual profile: exposure100000ns, ISO6400, focus2.0387485 diopters, zoom1.0,
frame duration33350000ns. A PREVIEW snapshot does not prove future finite stopping.

Actual native120 timing, unlocked Settings scene, video-space geometry, current
duration/restart/filesize-restart preferences and recording progress remain
unqualified. Null scene/lock fields are parser unknowns, not proof of a wrong
scene or locked phone. Setup/admission and acquisition remain false. No physical
PWM frequency or candidate result follows.
