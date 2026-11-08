# Qualified C1 observation, not a PWM setter

`capture_ddic_c1.py` changes no brightness, refresh rate, DC profile or panel
parameter. It sends the known page23 selector, one DCS C1 read requesting three
bytes, and page0 restoration. The coordinator alone prepares each stock state
and owns all physical operations. Do not run concurrently with another trial.

## Invocation

After the remote ADB preflight and current target identification, prepare the
exact native DBV and refresh independently. Example syntax, not an automatic
experiment or permission record:

```
python3 06-tools/capture_ddic_c1.py TARGET_ID --dbv 3600 --refresh 120 \
  --output artifacts/NEW_UNIQUE_C1_STATE.json --offline-check
```

Removing `--offline-check` performs the one capture. Use a fresh output for each
explicit stage; existing output is never overwritten as a retry. Native DBV828
or any other unexpected state must not be passed off as3600. The CLI will not
change the state to make its checks pass. No camera is touched by this tool.

Raw capture/stderr are saved0600 under the invoking user's private cache
`~/.cache/legion-y70-c1/NONCE/` before parser validation, including failed framing.
The public JSON has only relevant values, status and exact module provenance.
An uncertain shell transport cannot supply a complete raw record. Do not repeat
an uncertain capture or unlink its device lock without diagnosing the outcome.

## Firmware evidence and safe-width boundary

Saved target ELF SHA256:
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
Ghidra12.1.4 bounded excerpts independently checked with pinned LLVM objdump:

- `dsi_ctrl_cmd_transfer`: request3 selects MRPS3,16-byte zeroed scratch,
  exactly one16-byte FIFO helper call. No40-byte repeated-read allocation issue.
- Long parser `.text+0x1975f8..0x197628` copies requested length without checking
  response word count. Therefore rc3 alone is insufficient: long1 can produce
  payload1+CRC2, and long2 can produce payload2+CRC1.
- A malformed zero-length long response leaves only two bytes after the header,
  so copying3 invokes the stock driver's fortify panic. No claim that this reader
  makes arbitrary malformed responses safe. It cannot repair the loaded driver.
- Old40-byte C1 dumps lack headers/WC/HWcounts. Their third byte is a useful lead,
  not independently qualified data. CRC absence does not establish framing.

Probe `dsi_ctrl_cmd_transfer+0x494` observes the aligned four-byte response header,
requested length, scratch allocation, normalized count and helper selector.
Probe `dsi_ctrl_hw_cmn_get_cmd_read_data+0x5c` observes the original controller
status before ACK normalization/clamping, helper width and MRPS. No kernel pointer
values are intentionally included in those fields. Offsets are symbol-relative,
not live addresses. Actual installation/execution remains a separate live check.

Acceptance requires one corresponding pair of events on the same task:
DCS-long type1C, WC3, correct header ECC, normalized count9, original count9 or13
(four-byte ACK prefix), MRPS3,16-byte allocation/helper width, helper selector0,
three printed bytes, nonnegative expected returns and zero probe misses.
Payload CRC itself is not captured. Header/ECC stripping or a different actual
helper path causes refusal, not silent relaxation or an assumed third byte.

## Lock and cleanup

Standalone atomically creates root-owned0700
`/data/local/tmp/legion-pwm-research.lock`, with its own root-owned0600 `owner`
token. This excludes the A9 runner's directory-only lock as well. No stale-lock
removal exists. The callable `capture(..., held_token=...)` additionally requires
that token file; it cannot yet join a directory-only parent lock.

The read uses a private mount namespace, private trace instance and unique probe
names. A device-side30-second timeout,3-second kill grace and EXIT/HUP/INT/TERM
traps attempt page0 return, ESD `reg_read` restoration, probe removal and namespace
cleanup. The lock is removed only after clean completion. An inherited lock is
never removed. A hung kernel or hard kill can defeat cleanup. The coordinator
must independently recover page/ESD or perform its authorized ordinary reboot
when the result is uncertain; this tool never reboots by itself.

## Testable hypothesis

Historical C1 prefixes are00 00 65 at lowDBV120/60,00 00 55 at lowDBV144, and
00 00 10 above the3601 boundary. High nibbles6×120 and5×144 both give720 under
an unproven count/base-clock interpretation. Selected DT uses the same00:60=00
base selector at120/60, with2D:83=0/1 frame division. The hypothesis predicts8
at stock90, and a change to1 under A9-only would instead support DC-like reduction
of pulse count. None of these predictions establishes writability or≥2000Hz.
Never write C1 based on these observations.

Offline validation:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools -p test_capture_ddic_c1.py -v`.
Nine tests cover normal/ACK framing, invalid widths/counts/WC/ECC, duplicates,
probe misses, state mismatch, shell syntax, cleanup structure, inherited locks,
conditional bounds and no-overwrite refusal under optimized Python.
Controller/page return sequences are checked exactly, including rejection of
missing, extra or reordered controller operations.

## First live pre-query stop and correction

Capture nonce14aaef2774b5 stopped before page23/C1. Header/helper probes had zero
hits; only the final page0 cleanup writer returned0. The post-write ESD guard
correctly rejected the still-stock mode. Saved module analysis established why:
`debugfs_alter_esd_check_mode` uses exact strcmp against newline-terminated
`esd_sw_sim_success\n` (rodata+1a085, call.text1b14f4) and `reg_read\n`
(rodata+f479, call.text1b14e0). The read handler returns the bare tokens.
The original bare printf writes were accepted-bytecount no-ops. Both set and
restore now explicitly include LF; the exact readback guard remains mandatory.
Initial/active/restored ESD states are logged independently. No query was
executed in that attempt, and the coordinator owns recovery/lock verification.

The captured cleanup also proves Android printf runs in a separate task for
individual writes. The validator therefore requires matching header/helper/read
return PID, but separately validates page-write returns across their task IDs.
It no longer incorrectly requires all independent printf processes to share
the C1 read task. Synthetic tests now use distinct writer PIDs.

## Qualified live observations, executed by the coordinator

`artifacts/c1_live_20261108/` contains five completed qualified captures:
stock120/DBV3600=`00 00 60`; stock90/3600=`00 00 80`;
stock144/3600=`00 00 50`; stock120-return/3600=`00 00 60`;
stock120/3646=`00 00 10`. Each has header`1c 03 00 16`, normalized/raw count9,
one receive and verified cleanup. Each private trace has controller returns
`[0,3,0,0]` and page-writer returns`[0,0,0]`, on separate printf tasks.

The90 prediction now has real qualified support: a candidate count interpreted
as`BE24>>4` gives8×90=5×144=6×120=720, then1 above the brightness boundary.
This is strong evidence for a count/status relationship, not independently
measured physical Hz or a writable control. Every qualified low nibble is0;
the old unqualified65/55 prefixes must not define a fixed secondary field.
An A9 comparison can next distinguish count reduction toward1 from a different
duty/gain mechanism. No C1 write or new count profile is proposed.
