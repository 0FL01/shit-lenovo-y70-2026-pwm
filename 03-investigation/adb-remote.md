# Remote ADB and fastboot

The R&D host consumes an authenticated reverse tunnel from a separate USB host.
The research target and a second phone used as the optical camera are distinct
devices. The owner reports they are available 24/7; connectivity, USB state,
camera framing, exposure and target display state must be checked each time.
The USB host's address, SSH identity and device identifiers are private; do not
commit them or unredacted command output.

## ADB

The USB host initiates an SSH reverse Unix forward to its loopback ADB server.
On the R&D host the socket-activated user proxy preserves the private agent
endpoint (0700 directory, 0600 socket). There is no SSH login back to the USB
host through this path. Linger is enabled. A socket alone is not proof of ADB.

For read-only bench RECON, run this block from the repository root. It uses
the existing socket, not an ADB daemon-starting command, and emits no serials.
A closed/mismatched socket fails the check; retry this **read-only** block
after the tunnel returns, not the preceding device operation.

```sh
(
set -eu
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export ADB_SERVER_SOCKET="localfilesystem:$XDG_RUNTIME_DIR/legion-y70-adb/adb.sock"
systemctl --user is-active --quiet legion-y70-adb.socket
PYTHONPATH=06-tools python3 -B - <<'PROBE'
from guarded_adb_socket import GuardedADB
import subprocess
a = GuardedADB()
local = subprocess.check_output(["adb", "version"], timeout=10).splitlines()[:2]
if local != [b"Android Debug Bridge version 1.0.41", b"Version 34.0.5-debian"]:
    raise SystemExit("unexpected local ADB client build")
if a.host("host:version") != b"0029":
    raise SystemExit("unexpected ADB server protocol")
print("existing socket OK; upstream protocol 41; local client 34.0.5-debian")
PROBE
)
```

This probe checks the **local** client build and the **upstream protocol**
(41 / 0029). It cannot establish the upstream binary's package/build version.
It does not authorize the old experiment runners or any device change. Their
source-bound `GuardedADB.preflight()` and pins are intentionally unchanged:
that historical preflight expects outbound SSH, which this carrier does not
provide. Do not bypass it or rewrite its pins to run an old experiment.

Reidentify both models in the current session and bind to the intended device
before any use; transport IDs can change on reconnect. Never use list order.
After a connection error repeat read-only identification, not an interrupted
device operation. Do not fall back to another endpoint or run `adb kill-server`,
`adb start-server` or automatic reconnects against the shared server.

## Fastboot and recovery

Fastboot talks to USB directly. The ADB carrier does not provide fastboot,
SSH login, or file transfer to the USB host. Arrange separate operator LAN
access and run the enumeration locally on the USB host before any such work.

Select the confirmed target explicitly for `getvar` and subsequent operations;
do not publish identifiers. Fastboot was installed on the USB host at the
checkpoint, but no device was in bootloader mode, so actual bootloader access
and physical recovery remain unverified. `fastboot boot`/`flash` read images on
the USB host: an explicitly approved experiment must transfer its exact image
privately, compare its SHA-256 with the approved source, and verify the recovery
route before the operation. No implicit reboot, retry, slot change or flash.

## Verified scope

At the earlier research checkpoint, two authorized Android devices were identified and shell,
binary `exec-out` and `pull` worked through the tunnel. A controlled service
restart and a simulated unexpected SSH exit both recovered the connection.
No AWG interruption, host reboot, camera capture, bootloader transition or
device write was tested. Real 24/7 availability and post-reboot recovery are
therefore not proven. On 2026-11-18, the read-only checks returned upstream protocol 41 / 0029
and local client 34.0.5-debian. The upstream package build was not queried. Read-only manufacturer/model properties matched
Nothing A001 (scope camera) and Motorola Edge 70 Max (research target).
See [optical bench protocol](../05-safety/optical_measurement.md).
