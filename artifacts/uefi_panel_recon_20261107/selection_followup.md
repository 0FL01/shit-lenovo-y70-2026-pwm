# BOE XML variant selection: bounded offline check (2026-11-08)

**R3 active.** Hypothesis: the existence of v3-only bootstrap packets might mean
the bootloader on the physical XT2611-1 initialized v3 even while Android reports
the selected software profile v4. This is a question, **not** evidence that a
v3 command can be sent to v4 or that PWM ≥2000 Hz exists.

Inputs: previously verified CN11/GLOBAL64 reference `DisplayDxe.efi` and
`PanelSimConfig.csv.raw` in
`/home/stfu/.cache/opencode-tmp/opencode/uefi-panel-recon-20261107/`;
actual selected Android DT/profile in [panel identity](../panel_identity.md).
Current device bootloader image and live UEFI selection trace were **not** read.

- The two reference `PanelSimConfig.csv.raw` files are byte-identical, 46 CSV
  rows including header; no row contains BOE, ILI97701A, or the v3/v4 panel
  names. This generic simulation catalog is **not** the BOE selection map.
- GLOBAL `DisplayDxe.efi` does contain names/XML filenames for all BOE
  ILI97701A v0–v4 and strings `MotDynamicDSIPanelDetection readback(_ver)` and
  `Detected panel name %a & version:%08x`. These strings show a detection path
  is compiled into this **reference**, not that a particular branch ran on the
  owner device or that software `panelVer=0` is decoded silicon revision.
- For code-level offline analysis the existing `06-tools/ghidra_decompile.py`
  initially rejected PE input before a project/device action. Its minimal input
  validator now also admits ARM64 PE32+; ELF output provenance remains unchanged,
  PE records `pe_type`. Fast tests: **12 passed, 2 known-answer skipped**;
  repository's 29 scoped tests passed, 2 skipped. Independent PE-validator review
  found no regression. Ghidra project/temp/output stay under the approved
  external cache; no new dependency, PE execution, ADB or flash.
- The reference GLOBAL PE has ImageBase0, `.text` RVA0x1000 and `.data`
  RVA0x4b000. Ghidra12.1.4 xref of detection-version log at import address
  `0x3b23d` points to instruction `0xa370` within `FUN_00009668` (entry
  `0x9668`, 1144 recognized instructions). The XML filename v3 at `.data`
  `0x55828` has **no direct xref** in this auto-analysis; an inline catalog
  lookup is not thereby excluded. These are import addresses, not runtime VA.

The bounded Ghidra `decompile --lines` excerpts of `FUN_00009668` (import
`0x9668`) and `FUN_0000cb00` (import `0xcb00`) give a stronger **reference-only**
mapping. On the detection path the latter supplies a panel catalog at
`0x4e338 + index × 0x928`, with up to six groups. In the first group the data
at offsets `+0x48..4b` include `DA 00 D2 00`, and at `+0x80..83` include
`DC 00 00 00`: ID/second-read configuration literals, not captured DSI
responses. After ID comparison the code requests a second read and compares
its **low byte** (`local_80[0]&0xff`) with up to 32 unsigned threshold/name
entries at `group+0xa8 + i×0x44`. First match supplies the selected name.

[selection_validate.py](selection_validate.py) independently maps PE RVAs to
raw data offsets, checks all 32 entries, both reference code/data regions,
and reproduces the [compact JSON](selection_validation.json). First BOE group
is `boe_ili97701A_682_1440x3168_dsc_cmd_v1`, and the four nonempty entries
are **`<1→v1`, `<2→v2`, `<3→v3`, `<255→v4`**. Thus the conditional mapping for
this *reference* and group is byte0→v1, 1→v2, 2→v3, 3…254→v4; byte255 has
no matching threshold in the checked loop (subsequent fallback unknown). Another
group names v0, so the six-group catalog is not a monotonic v0–v4 enum.

Additional bounded catalog check: all six group records at `0x4e338 + i×0x928`
are byte-identical in the saved GLOBAL64 and later acquired CN48 reference
`DisplayDxe.efi` (not the owner's bootloader). The first BOE group expects
`DA 00 D2 00` in its ID configuration (`group+0x48..0x4b`); **the BOE v0
group at index 3 expects `DA 00 BF 00`**, has zero named version thresholds,
and its version configuration at `+0x78..0x83` is
`04 00 00 00 00 00 00 00 00 00 00 00`. Among these six groups only group 0
has expected-ID bytes `D2 00`. Therefore `v0` is **not** a fallback chosen
merely because the second-read byte is zero *after a D2 ID match in this
reference catalog*. Android's saved `panelId=0xd2` is a different cached
`/chosen` field, **not** a new observation of the bootloader's first read.
The current bootloader, actual ID/version readbacks and selected UEFI profile
remain unknown; no v3/v4 commands or physical PWM Hz follow from this test.

The archived Android result **v4 / panelId `0xd2` / panelVer `0`** is
`confirmed-on-target`, but the equality of Android `panelVer=0` and the
bootloader's second-read low byte is **unknown**. Nor is the current target
UEFI binary or selected index known. It would be incorrect to conclude either
"bootloader sent v1" or "bootloader sent v4", or to copy the v3-only 2F
sequence into the live v4 path. The reference provides a falsifiable bridge:
determine whether the current boot's second-read/selection source is accessible
*without* sending any new DSI; separately trace where Linux `panelVer` gets
its value. Neither alone is PWM Hz. A0D1C1 remains unapproved/unrun.

Reproduce the data-level check without touching a device:

```sh
python3 artifacts/uefi_panel_recon_20261107/selection_validate.py \
  /home/stfu/.cache/opencode-tmp/opencode/uefi-panel-recon-20261107 \
  NEW_NONEXISTENT_OUTPUT.json
```

Ghidra source excerpts (only these excerpts/brief were read by agents):
`/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/uefi-selection-20261108/`
`detection-excerpt-0` lines110–205, `detection-excerpt-4` lines200–360,
`panel-catalog-excerpt` lines1–35, `detection-brief` and
`detection-ver-xrefs` manifests. The PE import addresses are not live VAs;
Ghidra pseudocode and static reference are not evidence that those branches
ran on XT2611-1. Physical PWM ≥2000 Hz remains **unverified**.

## Linux `panelVer` source: second bounded offline check

Current stored target `artifacts/kernel/gki_r59/target_vendor/msm_drm.ko`
(SHA256 `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`):
Ghidra `panelVer_show` (ET_REL `.text+0x1aed7c`) **formats a cached 64-bit
field**, without a DSI read. The same offset `+0xad8` is written in
`dsi_panel_parse_panel_cfg` (`.text+0x1b6ca4`). This parser opens `/chosen`,
initializes panel version and ID fields at `+0xad8/+0xad0` to `~0ULL`, then
reads `mmi,panel_ver`/`mmi,panel_id` (or `_s` variants for a different
instance) via `of_property_read_u64`; it does not check those read results.
The logged DA/DB/DC values are **three low bytes of this cached version
property**; the log labels are not independent physical register reads.

The archived target sysfs `panelVer=0` is not that parser's initial fallback
`~0ULL`, but without a saved `/chosen` snapshot, all possible writers, or a
boot-time trace this still does **not** show that the PE's DC-read byte was 0.
The saved CN48 Android DTBO has no static `mmi,panel_ver(_s)` string; this
absence does not prove what the bootloader added dynamically to `/chosen`.
The current UEFI version and any v3-only bootstrap execution remain unknown.

Provenance: Ghidra briefs/excerpts only, under
`/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/panelver-recon-20261108/`:
`show-brief`, `show-excerpt-corrected` lines1–30,
`dtprop-xrefs` (string import `0x12fe4e` → function),
`property-consumer-brief`, `parse-cfg-excerpt1` lines1–85.
An initial `--lines 1:35` was refused (only30 source lines); the excerpt
was regenerated with correct bounds. Independent code-level review checked
the field paths/defaults/log byte extraction without reading full C exports;
no blocking defect found. Neither reference firmware nor kernel code yields
physical OLED PWM Hz. No new ADB, DSI, camera, flash or reboot in this branch.

## Bootloader-to-`/chosen` bridge: third bounded offline check

The already archived CN11 XT2611-1 and GLOBAL64 XT2611-3 bootloader containers
also contain `abl.elf.1000.fv`. Both FVs passed `7z t`; extracting **only**
`9E21FD93/EE4E5898/VOLUME/MotoBootModule.efi` through `7z e -so` yielded
ARM64 PE32+ files of 1,617,920 and 1,601,536 bytes respectively, under the
same approved external cache. These are **reference** binaries, not the current
XT2611-1 bootloader; nothing was booted or flashed. The GLOBAL module used for
code-level analysis is SHA256
`6ca256dff0379c343a677532158b0186fe27aae3e60721ce2e7933a1a0d6268c`.

GLOBAL Ghidra12.1.4 `prop-xrefs` resolves the `mmi,panel_ver` string at PE
import address `0x12e2f5` to instruction `0xdaf28` in
`FUN_000d7d74` (entry `0xd7d74`). Its bounded `chosen-writer-panel`
excerpt (source lines 1501–1618, excerpt lines 53–170) shows the primary path:
after a panel-ID getter, it initializes an eight-byte local value to zero,
requests UEFI variable **`DisplayPanelVer`** through a runtime-service call
using GUID at import `0x160ce8`, then passes the value to
`FUN_000dccb0(...,"mmi,panel_ver", value)`. The same path contains separate
secondary `DisplayPanelIdSec`/`DisplayPanelVerSec` reads and `_s` properties.
`u64-property-excerpt` source lines 1–20 shows `FUN_000dccb0` converts the
64-bit input to big-endian and writes eight bytes to the DT property. This
matches the *format* consumed by current Linux `of_property_read_u64`. The
reference `DisplayDxe` variable setter wrapper `FUN_0001f970`
(`setvar-wrapper-head` lines 1–20) calls the runtime service at `+0x58`
with GUID at import `0x4b048`; its 16 bytes
`2b8c2f8846965f438de5f208ff80c1bd` match the GUID supplied to the
BootModule's `+0x48` read at import `0x160ce8`. This proves the reference
set/get calls use the same UEFI namespace, **not** that a producer for this
particular version key was executed. The reference path does
not prove this reference module ran on the owner device. If the UEFI variable
read reports an error, the shown caller logs it and has no explicit success
guard before the property write; the behavior of error-reporting callees and
the actual boot remain unqualified. Therefore a zero Android `panelVer` is
**not** evidence of a `DC=0` readback or of a particular UEFI-selected XML.

The reference `DisplayDxe.efi` contains two UTF-16 occurrences of
`DisplayPanelVer` (import addresses `0x45862`/`0x46588`), but Ghidra's direct
xrefs to these *individual* string addresses are empty. The name alone does
not establish the variable's producer or equality with the detection function's
second DSI read. The `FUN_00023ab0` helper writes **`DisplayPanelId`**,
and `FUN_00023b14` references **`DisplayPanelDetectionResult`**, not
`DisplayPanelVer`; neither may be relabelled as a verified version writer.
Ghidra projects/briefs/excerpts are in the approved cache at
`ghidra-toolkit-20261107/{boot-panelver-20261108,uefi-selection-20261108}/`;
only briefs and `--lines` excerpts were read, never full decompiler listings.
Both regional BootModules contain the same *literal* property and variable
names; their code equivalence was not asserted.

This closes a false inference from Android `panelVer=0` to UEFI `DC=0`, not
the physical-revision or PWM question. The exact target bootloader, executed
selection, variable value/status and physical PWM Hz remain **unknown**. No
ADB, camera, DSI, settings, reboot, or flash action was taken. A9-only remains
the experimental panel baseline; A0D1C1 remains unapproved/unrun.
An independent review of the PE/xref excerpts, GUID bytes, input integrity and
the inference boundaries found no defect in this bounded bridge; it did not
qualify the current target bootloader or physical PWM.

## CN48 `DisplayPanelVer` literal ownership: fourth bounded offline check

The new [CN48 XT2611-1 bootloader comparison](../cn_48_7_recon_20261107/result.md)
established that its display PEs match the GLOBAL reference outside CodeView,
while `MotoBootModule` differs overall. Hypothesis: **another UEFI module** might
be the unrecognized producer of the variable read by the ABL-to-`/chosen` path.
The [literal-scan reproducer](scan_version_producers.py) used `7z e -so` to
check exactly all **116 `.efi` members / 8,421,376 bytes** in the already saved
CN48 `uefi.elf.1000.fv` and the single `.efi` /1,601,536bytes in its ABL FV.
It scanned terminated UTF-16LE `DisplayPanelVer` and `DisplayPanelVerSec`, and
terminated ASCII `DisplayPanelVer`, with file sizes/PE signatures checked; no
other FV members, boot stages or dynamically constructed names were covered.
[Machine result](version_producer_scan.json):

| FV | Literal-containing PE | UTF-16LE version/secondary offsets |
|---|---|---|
| UEFI | `MotSolDxe.efi` | `0x417a / 0x419a` |
| UEFI | `BacklightDxe.efi` | `0x7c4c / 0x7c6c` |
| UEFI | `DisplayDxe.efi` | `0x45862,0x46588 / 0x4583c,0x465a8` |
| ABL | `MotoBootModule.efi` | `0x14f826 / 0x14f846` |

The three UEFI PEs have a nearby sequence of related EFI variable names; a
literal is not evidence of a write. Ghidra12.1.4 **direct xrefs** to the version
literal in `MotSolDxe` (`0x417a`) and `BacklightDxe` (`0x7c4c`) were empty.
Direct xrefs to the nearby `DisplayPanelName` base (`0x40ee`/`0x7bc0`) were
also empty. The two `DisplayDxe` version literals had already yielded empty
direct xrefs. These are bounded negative xref results, **not** a proof that
the variable has no producer, that the strings are dead, or that no computed
reference/indirect call exists. Ghidra manifests are under the external
approved cache `ghidra-toolkit-20261107/cn48-version-producers-20261108/`;
full decompiler listings were not read. No emitter/PWM mapping was found by
this literal check; R3 and the unknown source/status of the current
`DisplayPanelVer` remain open. No phone/camera/DSI/flash operation took place.
Independent scoped review repeated the 116+1 member scan in memory, confirmed
all literal offsets and four Ghidra xref manifests, and found no defect; it did
not repeat the earlier public-ZIP CRC acquisition or qualify live firmware.

### Follow-up: static pointer-table hypothesis (offline)

The empty *direct code* xrefs above leave open indirect pointers. Tested the
distinct hypothesis that a saved CN48 UEFI PE keeps a static pointer to (or near)
`DisplayPanelVer` in its `.data` or PE base-relocation table. For the three
already-extracted PE32+ files, independently parsed section RVA/raw mappings and
the `.reloc` block entries of type `DIR64=10`, then checked both 32-bit aligned
`.data` values and relocated 64-bit targets within 512 bytes of **each**
terminated UTF-16LE `DisplayPanelVer` literal:

| PE | Literal file offsets (=RVA in these PEs) | DIR64 slots | Nearby static pointers |
|---|---|---:|---:|
| CN48 `DisplayDxe.efi` | `0x45862`, `0x46588` | 675 | 0 |
| CN48 `BacklightDxe.efi` | `0x7c4c` | 7 | 0 |
| CN48 `MotSolDxe.efi` | `0x417a` | 7 | 0 |

An exact 32/64-bit little-endian RVA pointer to any of those literals is also
absent from the respective entire files. Positive control for relocation
parsing: the **already established** v4 backlight function pointer at CN48
`DisplayDxe.efi` RVA/source `0x56150` is a DIR64 slot and holds `0xbd74`.
Inputs are the saved files in
`/home/stfu/.cache/opencode-tmp/opencode/cn48-bootloader-recon-20261108/display/`;
no PE was executed. This closes only the *static pointer-table-near-literal*
hypothesis: PC-relative/computed references, lookup by string contents, an
unarchived boot component or a different producer are **not** excluded. No
observed EFI variable write, physical panel-revision decoding or PWM Hz follows.
The A9-only baseline and A0D1C1 exact-consent gate are unchanged; no device I/O.

### Follow-up: page-base xrefs are not a producer test (offline)

Tested another proposed explanation for the empty `DisplayPanelVer` xrefs using
Ghidra 12.1.4 on the already saved CN48 `DisplayDxe`, `MotSolDxe` and
`BacklightDxe` PE files. The page-base addresses containing the version
strings (`0x45000`, `0x46000`, `0x4000`, `0x7000`, respectively) all have
empty incoming xrefs. **Positive control in the same CN48 DisplayDxe:**
`DisplayPanelName` at `0x4577c` has two direct incoming references
(`0x237d8`, `0x237fc`), while its enclosing page `0x45000` has none. Thus
an empty page-base xref is *not a valid discriminator* for an ADRP/ADD-style
or otherwise PC-relative reference: Ghidra can attach the reference to the
final literal instead. This attempt cannot establish or exclude a producer
for `DisplayPanelVer`; the earlier empty exact-literal xrefs and static
pointer-table limits remain unchanged. Manifests: approved external cache
`ghidra-toolkit-20261107/cn48-version-page-20261108/`; the PE was not run
and no full decompiler listing was read. No device action, DDIC revision or
OLED PWM-frequency inference follows.

## CN48 `GetVariable` error path: fifth bounded offline check

The CN48 `MotoBootModule` primary panel-writer excerpt at source lines
1501–1618 calls `FUN_00126040` and then `FUN_00001d2c` when the EFI
`DisplayPanelVer` `GetVariable` status is nonzero. Hypothesis: a read error
**always** aborts (or **always** writes zero). Neither unconditional statement
is supported by these callees:

- Ghidra `brief`/`decompile --lines 1:9` for `FUN_00126040` at PE import
  `0x126040` (5 instructions/20bytes) shows a plain `return`.
- `FUN_00001d2c` at `0x1d2c` (179instructions/716bytes) is a conditional
  diagnostic/formatting path. Its bounded excerpts `1:60`, `61:109`, `110:151`
  initially compute `uVar6 = (auVar14._0_8_ & 0x80000042) == 0`, with
  `auVar14` from `FUN_001264e4()`. **`uVar6` is reused** by the formatter
  (`*pbVar8 == 0x25`, then `lVar7 == 0x69`); the final test is of its **current**
  value, not necessarily the initial mask result. Near the end it calls
  `FUN_0012574c()` and, when `!uVar6`, calls `FUN_000b4840()` which Ghidra
  marks non-returning; otherwise it calls `FUN_00126468()` and returns.
  There are also conditional assert helpers in the formatting path. The
  runtime diagnostic/format state and exact caller arguments have **not** been
  qualified.

Thus a **conditional return path** exists in this reference binary; the
initial zero-valued local could reach the DT writer after a failed read **if**
the diagnostic returns. Whether a real failed read takes that path, whether
the variable is ever missing, or whether another writer supplies a value on
the owner's **different current bootloader** is unknown. Android
`panelVer=0` is still neither proven fallback nor a decoded DDIC `DC` byte.
All code-level evidence came from the approved-cache
`ghidra-toolkit-20261107/cn48-boot-version-20261108/` briefs/`--lines`
excerpts, **not** full decompiler listings. No device operation or PWM/Hz
measurement was performed; A0D1C1 remains unapproved/unrun and R3 active.
An independent review confirmed the conditional outcome and caught the
overly simple flag interpretation; the variable-reuse correction above
preserves the conditional result without attributing the final branch solely
to the original flag mask.

## Saved kernel traces: no archived version diagnostic

`hypothesis`, offline only: an earlier capture might contain the actual boot
panel-version readback even though the saved sysfs `panelVer=0` is cached from
`/chosen`. Searched all **99** `*kernel.txt` files (52,144,946 bytes) under the
approved private cache `/home/stfu/.cache/opencode-tmp/opencode/`, without
printing their contents or identifiers. Case-insensitive literal searches for
`DisplayPanelVer`, `MotDynamicDSIPanelDetection`, `readback_ver`,
`mmi,panel_ver`, `panelVer`, `detected panel name`, and `panel version` found
**zero** matches. Three traces from the older `dsi-mode-trial-20261106-dd-fixed`
contain the software name `ili97701a` once each, but those lines do not contain
`ver`, `panelid` or `readback`. This closes only the proposal to **reuse these
particular saved traces** as a boot-time version diagnostic. A string search
cannot exclude unlogged, differently formatted, rotated, or earlier boot
events; no current bootloader image, UEFI response, silicon revision or PWM Hz
was recovered. No device operation or new DSI read was performed; R3 and the
A0D1C1 exact-consent boundary are unchanged.

## Version diagnostic wrapper (offline reference only)

The saved GLOBAL64 `DisplayDxe.efi` detection path calls `FUN_0001f66c`
when logging `Detected panel name %a & version:%08x`. Its complete **29-line
bounded Ghidra excerpts** (`version-log-head/excerpt.c`, lines 1–20, and
`version-log-tail-correct/excerpt.c`, lines 21–29, under the approved external
`ghidra-toolkit-20261107/uefi-selection-20261108/` cache) show a call to
formatter `FUN_00026e74`, then logger `FUN_00005330`, with canary failure
handled by `FUN_000010d0`. The corresponding `version-log-brief/manifest.json`
lists exactly these direct callees. No direct call to the known EFI SetVariable
wrapper `FUN_0001f970` appears in **this function**. PE import RVA `0x1f66c`
is not a device runtime address.

This closes only the hypothesis that the version **diagnostic wrapper itself
directly** writes `DisplayPanelVer`. Formatter/indirect side effects and other
UEFI producers remain unqualified; neither the actual owner bootloader nor its
version readback, physical silicon revision or OLED PWM Hz was established.
No device, DSI or camera operation was performed; R3 and the separate A0D1C1
authorization gate remain unchanged.
Independent scoped review verified the reference PE hash, complete excerpt coverage
and exact direct callee list without a proven defect or broader UEFI claim.

## Detection thunk copy path (offline reference only)

In the saved GLOBAL64 `DisplayDxe.efi`, detection `FUN_00009668` calls
`thunk_FUN_00005668` (PE import RVA `0x1f8c4`). The target `FUN_00005668`
(`0x5668`) returns for zero length/equal pointers, guards pointer-plus-length
overflow, then calls `FUN_00005a4c` (`0x5a4c`). Its complete 27-line bounded
Ghidra excerpt (`version-thunk-target-head-correct/excerpt.c`) and brief list
only `FUN_00005430` and `FUN_00005a4c` as direct callees. The latter's brief
(`copy-target-brief/manifest.json`, 43 instructions) lists **no direct callees**;
its bounded excerpts `copy-target-{excerpt,middle,tail,end,final,last-correct}`
cover source lines 1–239 and handle word/byte copies, including overlap. These
are all under the approved external `ghidra-toolkit-20261107/uefi-selection-20261108/`
cache; the full decompiler C was not read. PE import RVAs are not device runtime
addresses.

This rules out a **direct** call from this detection thunk/copy path to the
known EFI SetVariable wrapper `FUN_0001f970`; it does **not** rule out other
UEFI version producers, indirect/transitive effects elsewhere, or establish the
owner's executed bootloader, DDIC revision or physical OLED PWM Hz. No device,
DSI or camera operation was performed; R3 remains active and A0D1C1 remains
unapproved/unrun.
Independent scoped review verified the saved PE hash, bounded excerpt coverage,
zero-length/equal-pointer/last-byte-overflow guards and overlap-copy behavior;
no defect or broader UEFI conclusion was established.
