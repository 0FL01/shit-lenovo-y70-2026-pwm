# Remote ADB and fastboot

The R&D host reaches a separate USB host over an authenticated SSH connection.
The research target and a second phone used as the optical camera are distinct
devices. The owner reports they are available 24/7; connectivity, USB state,
camera framing, exposure and target display state must be checked each time.
The USB host's address, SSH identity and device identifiers are private; do not
commit them or unredacted command output.

## ADB

On the R&D host, user service `legion-y70-adb.service` forwards a private Unix
socket to the USB host's loopback ADB server. The service is enabled with
automatic restart; its directory is mode 0700 and its socket mode 0600.
The user service manager has linger enabled. The private SSH configuration is
`~/.config/legion-y70/ssh_config`, with alias `research-usb`. It and the unit
are host-local, not repository files. A working service or socket alone does
not prove that the upstream ADB server or either device is available.

Before ADB use, from the same shell that will run the command or Python tool:

```sh
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
export ADB_SERVER_SOCKET="localfilesystem:$XDG_RUNTIME_DIR/legion-y70-adb/adb.sock"
preflight() {
systemctl --user is-active --quiet legion-y70-adb.service || return 1

# This probes ADB's host:version over the socket without invoking the ADB client.
python3 - <<'PY' || return 1
import os, socket
path = os.environ['ADB_SERVER_SOCKET'].removeprefix('localfilesystem:')
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(5)
    s.connect(path)
    s.sendall(b'000chost:version')
    def read_exact(n):
        data = b''
        while len(data) < n:
            part = s.recv(n - len(data))
            if not part:
                raise RuntimeError('ADB server closed the connection')
            data += part
        return data
    if read_exact(4) != b'OKAY':
        raise RuntimeError('ADB server rejected the probe')
    version = read_exact(int(read_exact(4), 16))
    print('ADB server protocol version:', version.decode('ascii'))
PY

# Compare before issuing any command that connects to the server.
local_version=$(adb version | head -2) || return 1
remote_version=$(ssh -F "$HOME/.config/legion-y70/ssh_config" research-usb 'adb version | head -2') || return 1
[ "$local_version" = "$remote_version" ] || return 1
}
preflight || { echo 'STOP: ADB preflight failed' >&2; exit 1; }
echo 'ADB preflight passed'
```

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

Fastboot talks to USB directly and does not use the ADB socket. From the R&D
host, enumerate through the private SSH alias without an interactive login:

```sh
ssh -F "$HOME/.config/legion-y70/ssh_config" research-usb 'fastboot devices -l'
```

Select the confirmed target explicitly for `getvar` and subsequent operations;
do not publish identifiers. Fastboot was installed on the USB host at the
checkpoint, but no device was in bootloader mode, so actual bootloader access
and physical recovery remain unverified. `fastboot boot`/`flash` read images on
the USB host: an explicitly approved experiment must transfer its exact image
privately, compare its SHA-256 with the approved source, and verify the recovery
route before the operation. No implicit reboot, retry, slot change or flash.

## Verified scope

At the checkpoint, two authorized Android devices were identified and shell,
binary `exec-out` and `pull` worked through the tunnel. A controlled service
restart and a simulated unexpected SSH exit both recovered the connection.
No AWG interruption, host reboot, camera capture, bootloader transition or
device write was tested. Real 24/7 availability and post-reboot recovery are
therefore not proven. `05-safety/optical_measurement.md` is absent in the
current checkout; locate its authoritative instructions before relying on it.
