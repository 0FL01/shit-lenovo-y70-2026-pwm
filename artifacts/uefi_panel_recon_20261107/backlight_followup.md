# CN48 boot backlight: brightness path versus PWM-frequency control

Status: **confirmed-other-device** for the saved XT2611-1 RETCN CN48 reference,
**unknown** for the currently installed XT2611-1 GLOBAL bootloader and for
physical OLED PWM Hz. Offline code/data inspection only; no device commands.

## Falsifiable hypothesis and evidence

Hypothesis: the boot-time `BacklightDxe` path has an independent panel PWM-period
setter not represented by the BOE XML/selected Android DT. The following
bounded path does **not** reveal one; this does not rule out another writer or
identify the actual emission period.

The saved CN48 `BacklightDxe.efi` and `DisplayDxe.efi` are respectively 45,056
and 442,368 bytes, SHA256 `a8733a566ae2cd07b4cb278092745a9fc50921fc9ef2a16eb6599ec59fc75338`
and `e806740b2d69d9e2a736f149909a36fc4a70fd00360d80f02892055270fe8313`.
The prior [CN48 comparison](../cn_48_7_recon_20261107/result.md) verifies that
each differs from the separate GLOBAL64 reference only in 11 NB10 path bytes;
**neither reference is an identified dump of the owner's current bootloader**.
The members are saved under
`/home/stfu/.cache/opencode-tmp/opencode/cn48-bootloader-recon-20261108/display/`.
Ghidra 12.1.4 PE import addresses below are not runtime addresses. Only `brief`,
`--lines` excerpts and bounded instruction windows from manifests were read;
full decompiled C remains in the approved external cache, unread.

1. `BacklightDxe` `FUN_00003740` (`control-excerpt/excerpt.c:13–38` in
   `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/cn48-backlight-20261108/`)
   locates Display Power Ctrl protocol and calls its **method `+0x18`** for
   display indices **0 and 3**, both with the same saved brightness value.
   Index 3 is not a frequency multiplier; no DSI transmit appears in this
   bounded function. The protocol GUID at PE offset `0x9088` is exactly the
   16 bytes at `DisplayDxe` offset `0x4b0e8`:
   `9342fa7ba47a7543b63cb6aab786c43c`.
2. `DisplayDxe` install site `FUN_00001b84`, instructions `0x23bc/0x23c0`
   load that GUID and `0x23c8/0x23cc` load the interface at `0x4b390`, before
   the install call at `0x2480` (`registration-head/manifest.json`). Its
   **`+0x18` pointer** at file/RVA `0x4b3a8` is `0x4138`.
   `FUN_00004138` (`control-impl-excerpt/excerpt.c:14–38` and
   `control-impl-tail-correct/excerpt.c:2–6`) accepts index 0 and a
   16-bit-bounded brightness value, then calls `FUN_000192f4(index,0,...)`;
   the other index in this implementation returns an unsupported-status path.
   These `DisplayDxe` artifacts are under
   `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/cn48-display-backlight-20261108/`.
3. `FUN_000192f4` (`dispatch-head/excerpt.c:83–100`,
   `dispatch-brightness/excerpt.c:2–26`) handles property **0** as a brightness
   value and forwards configuration **5** to `FUN_00009668`. In the already
   saved `uefi-selection-20261108/detection-excerpt-2/excerpt.c:64–91`,
   configuration 5 invokes a **platform function pointer** for backlight level,
   not an inline PWM-frequency literal.
4. **Binding, not address proximity:** `FUN_0000cfb0`
   (`catalog-match-excerpt/excerpt.c:52–60` and
   `catalog-match-tail-correct/excerpt.c:2–7`) searches at most 87 static
   descriptor names from `0x51a28`, stride `0xd0`; an exact name match stores
   its row pointer. The BOE ILI97701A **v4** row is #77, `0x558b8`.
   `FUN_0000ce6c` (`panel-select-correct/excerpt.c:10–24`) takes that row's
   pointer at **row+200 = `0x55980`**, and copies six fields from its table
   into the platform state when the match succeeds. This table pointer is
   **`0x56128`**; the sixth copied slot at `0x56128+0x28=0x56150` is
   **`FUN_0000bd74`**. `FUN_00009544`
   (`platform-state-pointer-correct/excerpt.c:4–14`) places the copied slot
   at state+`0x3418+0x30=0x3448`, which is exactly the config-5 indirect
   backlight-level slot in `FUN_00009668` (`0xd12` words). All five static
   BOE ILI97701A rows point to this same table. The **neighboring** slots
   at `0x56120`/`0x56210` instead point to `FUN_0000bbbc`; they must **not**
   be attributed to the v4 descriptor. These are conditional reference-code
   mappings, not proof of the owner's actual UEFI selection.
5. The **v4-bound** `FUN_0000bd74`
   (`selected-v4-backlight-excerpt/excerpt.c:12–38`, 52 decoded instructions)
   accepts `BacklightType=3`, and sends DCS **`0x51` brightness** (for the
   selected 14-bit configuration, two value bytes) through `FUN_0000ddc0`;
   it has no WLED branch. The *different*, neighboring
   `FUN_0000bbbc` (`dcs-branch-excerpt/excerpt.c:17–42`,
   `dcs-branch-tail/excerpt.c:2–20`) contains an alternate type-3 DCS
   brightness calculation and a WLED-duty-cycle branch requiring type **1**
   plus PMIC control type **2**; it is **not** v4's bound handler.
   CN48 BOE ILI97701A v4 XML, lines 180–184, specifies
   `BacklightType=3`, `BacklightBitWidth=14` and **no**
   `BacklightPmicPWMFrequency` field. All nine archived CN48 BOE XML variants
   have type 3 and no PMIC PWM-frequency field. The literal
   `BacklightPmicPWMFrequency` exists in generic `DisplayDxe` data, but is
   not a configured OLED PWM setter in this reference profile.

Validation: checked both PE SHA256 against the Ghidra manifests, the 16-byte
GUID match, the registered protocol pointer, v4 descriptor and its copied
callback pointers against the actual PE bytes; independently computed row
`(0x558b8-0x51a28)/0xd0=77` and state slot `0x3418+0x30=0x3448`;
checked the selected reference XML with `ElementTree`. Code excerpts
and their listed source-line ranges are retained in the approved external
cache. No claim is made that DCS `0x51`, brightness bit width, a boot display
index or a generic PMIC PWM frequency establishes OLED emission Hz.

## Consequence for R3

The specific boot **brightness** path is not a discovered large PWM-frequency
step. This negative result closes only that hypothesis. The current selected
Android BOE v4 path, actual bootloader and physical PWM remain separate
questions. The saved A9-only panel result remains the best intermediate
optical baseline (q93 ratio `0.2264067` at its recorded conditions, **not**
a Hz measurement); the proposed A0D1C1 stock→candidate→stock interaction is
neither authorized nor run. This conditional reference binding now excludes
the adjacent `0xbbbc` as the v4 handler; it does not establish the actually
executed boot path or a panel-specific frequency writer. The already prepared
panel interaction test requires its separate exact-operation confirmation.
