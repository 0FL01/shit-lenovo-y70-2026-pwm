# Experiment 1: temporary KernelSU-Next kernel, RAM ONLY

Status: experiment1 **completed successfully** at11:54; experiment2 **completed successfully** at12:19 after separate owner authorization. Exactly one boot_b flash, UID0 after ordinary reboot/Enforcing/msm_drm verified: [install.json](kernel/gki_r59/kernelsu_next/persistent/install.json). Proposals below preserve their pre-execution scope; no further flash is implied.

## Device and image
- `confirmed-on-target`, [11:32 preflight](kernel/gki_r59/kernelsu_next/ram_preflight.json):
  XT2611-1 PVT/avr, W3WWS36.65-64-4-1, active `_b`, unlocked/orange, stock r59,
  Android boot complete, SELinux Enforcing. Panel revision unknown; no display edits.
- File: `artifacts/kernel/gki_r59/kernelsu_next/boot-ram-test.img`, **41644032 bytes**.
- SHA256: `d58ca6ed816f9ce508dea5b6ca50584dc8f942ed4ec9cfda51461c983aad2cfd`.
- Pinned Google r59 common + built-in KernelSU-Next v3.4.2/33355; native pinned
  mkbootimg v4, zero ramdisk/cmdline/OS field/signature. No cross-SKU payload,
  OEM signature or AVB footer claimed. Existing active init_boot/vendor_boot are needed;
  their use by this device's RAM path and actual vendor loading remain **unknown**.
- [Packaging validation](kernel/gki_r59/kernelsu_next/ram_boot_validation.json) passed;
  [kernel proof](kernel/gki_r59/kernelsu_next_validation.json): live config baseline,
  all10210 reference CRCs retained, Google module public certificate retained, CFI/Enforcing
  configuration preserved. This is not an OEM stock/recovery image; **NEVER flash it**.
- Reproduce offline: `python3 06-tools/package_kernelsu_ram_boot.py`.

## One approved experiment
1. Owner first demonstrates physical bootloader entry: disconnect USB, power phone off,
   hold Volume Down + Power until bootloader menu, reconnect. **Do not select Recovery,
   Wipe or Erase.** Generic [Motorola key sequence](https://en-us.support.motorola.com/app/answers/detail/a_id/137630/~/external-reset),
   only power-off/key-entry steps; applicability must be checked on this handset.
2. Agent checks avr/XT2611-1/PVT/slotb/unlocked/non-userspace and image identity, then once:
   `fastboot -s <private target> boot artifacts/kernel/gki_r59/kernelsu_next/boot-ram-test.img`.
   This is boot/download to RAM, **not** `flash`. Rejection/unsupported → stock reboot/stop.
3. On boot, check expected r59-dirty kernel, same build/slot, boot completion, display/msm_drm
   and Enforcing. Install prepared official normal Manager via native PackageManager
   verification (no bypass); initialize userspace only, **no Direct Install/boot patch**.
   Approve research root only for shell UID2000, check `su -c id` → UID0.
4. With root, read `/dev/block/by-name/boot_b` to host, expected96MiB, validate image/header/hash;
   read relevant vendor module evidence. No modem/NV/userdata dump. No partition writes.
5. Normal reboot to untouched stock kernel; verify build/slot/boot. Manager/its userdata may
   remain, but temporary root is not permanent success. A later persistent install requires
   its own proposal/approval using the newly obtained original for rollback.

## Return, risk and stop
- Physical key entry must work **before** the trial; ordinary stock fastboot reboot already
  verified. On rejected image use `fastboot reboot`; on no ADB/black screen/bootloop after
  about120s, owner uses verified physical return, then stock reboot. No blind repeat.
- Kernel/vendor/signature/init_boot incompatibility may prevent boot. No full rescue set
  exists; recovery depends on bootloader remaining accessible and untouched stock partitions.
  Do not promise zero risk or successful temporary boot.
- No flash/erase, slot switch, relock/critical-unlock, AVB disabling, custom recovery,
  DSI/PWM changes or Manager kernel installation. Unexpected slot/state or failed return → stop.

## Experiment 2: permanent KernelSU, boot_b ONLY

Result: **passed**. Root-only candidate below is now the known-good PWM-kernel rollback
baseline; stock original removes the custom kernel/root, not all Manager userdata or
changes to other partitions. No PWM override has been installed.

- Owner now explicitly requests permanent KernelSU installation and subsequent PWM research.
- Candidate: `artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img`,96MiB.
  SHA256: `42db701abff335256e41d8b2ce591088512a172c7a4a7af3d37b0d2d489f5c17`.
- Rollback: `artifacts/originals/W3WWS36.65-64-4-1/boot_b.img`,96MiB.
  SHA256: `49dcb9dd513ed5b364b9f84c6be4ab7bdc015a50562f5cca4779e46bf9287049`.
  Read directly from unchanged target boot_b during successful UID0 RAM trial;
  kernel is byte-equal to Google r59. Native AVB hash verification passed for both files.
- Candidate executable payload is byte-equal to successful RAM image. Native AVB footer
  regenerated with actual stock boot properties/salt, same algorithmNONE/flags0/index0,
  correct partition size. Old signed Google certification trailers not copied onto
  changed bytes. No OEM signature claimed, no vbmeta partition/verification-disable flags.
  Persistent boot acceptance is still an experiment, not proven by RAM success.
- [Packaging proof](kernel/gki_r59/kernelsu_next/persistent/validation.json).
  Reproduce: `python3 06-tools/package_kernelsu_persistent_boot.py`.
- Guard unchanged build/kernel/slot, avr/XT2611-1/PVT/b/unlocked/non-userspace,96MiB boot_b;
  verify both file identities, then exactly:
  `fastboot -s <private target> flash boot_b artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img`.
- `fastboot reboot`; verify expected r59-dirty/UID0/Enforcing/build/_b/msm_drm, then one
  ordinary `adb reboot` and repeat UID0/Enforcing/identity checks to prove persistence.
- If flash/boot/root/security checks fail, return via verified physical bootloader entry
  (owner action if ADB unavailable), restore ONLY boot_b:
  `fastboot -s <private target> flash boot_b artifacts/originals/W3WWS36.65-64-4-1/boot_b.img`,
  `fastboot reboot`, verify original stock state. No automatic alternative candidate/retry.
- Only boot_b written; no other slot/partition, critical unlock, relock, wipe, AVB disabling,
  custom recovery or DSI/PWM commands. Manager's UID2000 research authorization retained;
  other apps not granted root. Physical bootloader entry and stock reboot already verified.
