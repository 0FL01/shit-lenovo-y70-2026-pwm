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

From the repository root in the same environment as the agent:

```sh
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export ADB_SERVER_SOCKET="localfilesystem:$XDG_RUNTIME_DIR/legion-y70-adb/adb.sock"
PYTHONPATH=06-tools python3 -B -c 'from guarded_adb_socket import GuardedADB; GuardedADB().preflight()' || exit 1
```

The preflight requires the private socket, live server protocol 41 and the
same pinned Debian client build as the USB host checks at SSH startup. After a
package upgrade reconcile the pins on both hosts before resuming operations.

**Stop if the service/probe fails or versions differ.** An ADB client can start
a local daemon when the tunnel socket is missing; a version mismatch can cause
it to restart the upstream server. Even after a successful preflight there is a
race if the tunnel fails before the next command, so re-check after errors and
never treat an empty device list as proof of disconnection or switch to another
server automatically. Do not run `adb kill-server`, `adb start-server` or
automatic reconnects against the shared server.

After preflight, `adb devices -l` and `adb -t "$TRANSPORT_ID" ...` use this
server. Reidentify the target and camera independently from current device
properties before choosing a transport; IDs can change on reconnect. Do not
assume the first device is the target. Pass `ADB_SERVER_SOCKET` in the
environment of every Python script that launches `adb`; an export in the TUI's
shell is not guaranteed to reach an already-running OpenCode backend. Existing
experiment scripts may still reference private paths from the old host and
must be audited before use.

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
therefore not proven. `05-safety/optical_measurement.md` is absent in the
current checkout; locate its authoritative instructions before relying on it.
