# Independent wrapper review

2026-11-10; development HEAD 2a53eb40ada847836d02a92511efac9dd159a7a9.
Result: PASS for the scoped host deployment and optional read-only observation
wrapper. This review is not physical execution, setup or capture qualification.

## Exact reviewed bytes

- deploy_readonly.py: `99ac1b5aeafd1205ea71e18fa320edaf4e5150825cc6e4de38ec395ec4645b21`
- test_deploy_readonly.py: `de69d720114b11f1e637f7fe70b87880eee5869e3a5ac9b6cb4321c8720a5aed`
- DEPLOYMENT.md: `2929411d43e711166663145c7bb8986b377f3f7f045e5d4a7bcd675d0755b421`
- Existing launch.py unchanged: `da270f0de24d5fe769b6f876dffd18b7f972c3608ebee3e7f80b60a96164e826`
- Existing probe.py unchanged: `d72d1f8dd25605e3dae9d2b1ad95a753494423d0b150918dcc2495f963b909b1`

All match DEPLOY_FREEZE.json. Independently reran aggregate unittest discovery
with PYTHONDONTWRITEBYTECODE=1, normal Python and python3 -O: 29 PASS in each
mode (18 observer/launcher and 11 wrapper tests). Tests use fake child execution
and temporary host paths; no deployment, device, ADB or research-usb access.

## Checked boundaries

Strict bounded stdin JSON rejects duplicate/extra keys and wrong source hashes,
typed config and fixed host/source pins before writes. Only exact reviewed
public launch.py bytes execute as an inert config parser; no opaque payload
command or private script executes. Wrapper authenticity must be checked by
the operator before starting the trusted interpreter.

Default creates exclusive host0700 directories and0600 files, then runs only
the source-validation child. Device observation requires the single explicit
--execute-read-only flag and a successful exact zero-device source-only receipt.
Fixed /usr/bin/python3 -I -B argv uses no shell, inherited stdin or alternative
server. Existing destination, partial write or source validation failure does
not overwrite, adopt, clean up, retry or enter the observer.

Root, code, created directory and evidence identity/namespace edges are checked
before and after children. Frozen dependency root is not modified. Output is
independently allowlisted; exceptions/raw child output/config/serials are not
echoed. Timeout or failure after read-only launch remains uncertain, without
retry or claiming remote cancellation. No capture/settings/DSI/reboot route exists.

## Findings resolved during review

1. Earlier outcome.json could look final despite a later descriptor-close error.
   Final code marks disk receipt before_descriptor_close with cleanup false;
   final stdout receipt plus exit status is authoritative. Injected close failure
   yields uncertain, cleanup false, without leaking error text.
2. Post-child checks now include the same code/evidence namespace edges as the
   pre-child checks. Short/failed writes retain evidence and never launch a child.

## Limits and use

No unresolved blocking code finding for this narrow scope. Actual independent
private pins and current host compatibility remain execution-time checks, not
facts established by synthetic tests. Trusted host/root/interpreter/stdlib/Git
and no concurrent namespace mutation remain assumptions. No race-proof hostile
root defense, hard syscall deadline, cancellation or durability claim is made.
Successful completion requires final stdout receipt, exit0 and
host_cleanup_verified=true; provisional disk receipt alone is insufficient.

Observer still reports partial non-atomic readiness: no actual native120Hz proof,
no Settings scene classification, no complete recording geometry/progress proof,
and duration/restart remain unknown. Setup/acquisition admission stays false.
This wrapper cannot authorize a subsequent camera mutation or capture by itself.

Separate planned observationv2 uses preregistered windows [30,90), [90,150),
[150,210), [210,270), native10s limit and15s start-to-verified-stop acceptance.
It does not pass originalv1. Adjacent windows are not independent trials. Native
duration is a preventive media bound with asynchronous/OEM residual limits,
not an absolute wall-time guarantee under every OS failure. No new observation
data was obtained during this review.

Only public repository source/tests were inspected. No host deployment,
device operation, commit or push was performed during this review.
