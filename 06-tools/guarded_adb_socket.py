"""Minimal existing-server-only ADB transport. Never invokes an ADB daemon.

Only the runner's bounded shell-v2, sync and identity/reboot operations exist.
No default server, reconnect, TCP fallback, or automatic command retries.
"""
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import time


class GuardedADB:
    def __init__(self, spec=None):
        spec = spec or os.environ.get('ADB_SERVER_SOCKET', '')
        prefix = 'localfilesystem:'
        if not spec.startswith(prefix) or not spec[len(prefix):].startswith('/'):
            raise ValueError('Explicit absolute localfilesystem ADB socket required')
        self.path = spec[len(prefix):]
        self.protocol = None
        self.identities = {}

    @staticmethod
    def exact(sock, count):
        data = bytearray()
        while len(data) < count:
            part = sock.recv(count - len(data))
            if not part:
                raise RuntimeError('ADB connection closed; operation outcome may be uncertain')
            data.extend(part)
        return bytes(data)

    def connect(self, timeout=25):
        info = os.stat(self.path)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError('ADB socket must be current-user-owned and private')
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(timeout)
        try:
            sock.connect(self.path)
            return sock
        except BaseException:
            sock.close()
            raise

    def request(self, sock, service):
        data = service.encode()
        if len(data) > 65535:
            raise ValueError('ADB service too long')
        sock.sendall(f'{len(data):04x}'.encode() + data)
        if self.exact(sock, 4) != b'OKAY':
            # Never expose daemon error strings (may contain private identifiers).
            raise RuntimeError('ADB service refused; no retry or alternate server')

    def host(self, service):
        with self.connect(12) as sock:
            self.request(sock, service)
            size = int(self.exact(sock, 4), 16)
            return self.exact(sock, size)

    def preflight(self):
        subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'legion-y70-adb.service'],
                       check=True, capture_output=True, timeout=10)
        version = self.host('host:version')
        if version != b'0029':
            raise RuntimeError('Expected ADB protocol 41')
        local = subprocess.run(['adb', 'version'], check=True, capture_output=True, timeout=10)
        remote = subprocess.run(['ssh', '-F', str(Path.home() / '.config/legion-y70/ssh_config'),
                                 'research-usb', 'adb version'], check=True, capture_output=True, timeout=15)
        if local.stdout.splitlines()[:2] != remote.stdout.splitlines()[:2]:
            raise RuntimeError('Local and remote ADB versions differ')
        self.protocol = version

    def bind(self, transport):
        serial = self.host('host-transport-id:' + str(transport) + ':get-serialno').strip()
        if not serial or serial == b'unknown':
            raise RuntimeError('Cannot bind device identity')
        self.identities[str(transport)] = serial
        return serial

    def selected(self, transport, service, timeout):
        if self.protocol is None or self.host('host:version') != self.protocol:
            raise RuntimeError('ADB version preflight missing or changed')
        if not str(transport).isdigit() or int(transport) <= 0:
            raise ValueError('Positive transport ID required')
        sock = self.connect(timeout)
        try:
            if str(transport) in self.identities:
                # Bind on THIS socket by the captured serial. Transport ID reuse
                # after an upstream server restart cannot select the other phone.
                self.request(sock, 'host:transport:' + self.identities[str(transport)].decode())
            else:
                self.request(sock, 'host:transport-id:' + str(transport))
            self.request(sock, service)
            return sock
        except BaseException:
            sock.close()
            raise

    def shell(self, transport, command, timeout):
        stdout, stderr = bytearray(), bytearray()
        deadline = time.monotonic() + timeout
        with self.selected(transport, 'shell,v2,raw:' + command, timeout) as sock:
            while True:
                sock.settimeout(max(.001, deadline - time.monotonic()))
                channel, size = struct.unpack('<BI', self.exact(sock, 5))
                if size > 16 * 1024 * 1024:
                    raise RuntimeError('Oversized shell-v2 frame')
                data = self.exact(sock, size)
                if channel == 1:
                    stdout.extend(data)
                elif channel == 2:
                    stderr.extend(data)
                elif channel == 3:
                    if len(data) != 1:
                        raise RuntimeError('Invalid shell-v2 exit frame')
                    return data[0], bytes(stdout), bytes(stderr)
                else:
                    raise RuntimeError('Unexpected shell-v2 channel')

    def sync(self, transport, local, remote, *, pull, timeout):
        with self.selected(transport, 'sync:', timeout) as sock:
            def send(kind, payload):
                sock.sendall(kind + struct.pack('<I', len(payload)) + payload)
            if pull:
                send(b'RECV', remote.encode())
                with Path(local).open('xb') as output:
                    os.chmod(local, 0o600)
                    while True:
                        kind, size = struct.unpack('<4sI', self.exact(sock, 8))
                        if kind == b'DONE':
                            break
                        if kind != b'DATA' or size > 65536:
                            raise RuntimeError('ADB pull rejected or malformed')
                        output.write(self.exact(sock, size))
            else:
                path = Path(local)
                send(b'SEND', (remote + ',33216').encode())  # regular file, 0600
                with path.open('rb') as source:
                    while data := source.read(65536):
                        send(b'DATA', data)
                sock.sendall(b'DONE' + struct.pack('<I', int(path.stat().st_mtime)))
                kind, size = struct.unpack('<4sI', self.exact(sock, 8))
                if kind != b'OKAY' or size:
                    raise RuntimeError('ADB push failed; outcome uncertain')
            send(b'QUIT', b'')

    def run(self, argv, *, capture_output=True, text=False, timeout=25, check=False):
        if argv[0] != 'adb' or len(argv) < 4 or argv[1] != '-t':
            raise ValueError('Only explicit transport commands supported')
        transport, action, *args = argv[2:]
        rc, out, err = 0, b'', b''
        if action == 'shell' and len(args) == 1:
            rc, out, err = self.shell(transport, args[0], timeout)
        elif action == 'get-serialno' and not args:
            out = self.identities.get(str(transport))
            if out is None:
                out = self.host('host-transport-id:' + str(transport) + ':get-serialno')
        elif action == 'reboot' and not args:
            with self.selected(transport, 'reboot:', timeout) as sock:
                # Disconnect is expected; acceptance is NOT proof of reboot.
                while sock.recv(4096):
                    pass
        elif action == 'push' and len(args) == 2:
            source, dest = Path(args[0]), args[1]
            if not source.is_dir():
                raise ValueError('Runner push expects a chunks directory')
            rc, _, _ = self.shell(transport, 'mkdir ' + dest.rstrip('/') + '/' + source.name, timeout)
            if rc:
                raise RuntimeError('Cannot create device chunks directory')
            for path in sorted(source.iterdir()):
                if not path.is_file() or not path.name.replace('_', '').replace('.', '').isalnum():
                    raise ValueError('Unexpected chunk file')
                self.sync(transport, path, dest.rstrip('/') + '/' + source.name + '/' + path.name,
                          pull=False, timeout=timeout)
        elif action == 'pull' and len(args) == 2:
            self.sync(transport, args[1], args[0], pull=True, timeout=timeout)
        else:
            raise ValueError('Unsupported guarded ADB action')
        if text:
            out, err = out.decode(errors='replace'), err.decode(errors='replace')
        result = subprocess.CompletedProcess(['adb', '<redacted>'], rc, out, err)
        if check and rc:
            raise RuntimeError('Guarded ADB command failed')
        return result

    def wait_target(self, serial, timeout=75):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                lines = self.host('host:devices-l').decode().splitlines()
                matches = [line.split() for line in lines if line.split()[:2] == [serial, 'device']]
                if len(matches) == 1 and 'device:avr' in matches[0]:
                    ids = [part.split(':', 1)[1] for part in matches[0] if part.startswith('transport_id:')]
                    if len(ids) == 1 and ids[0].isdigit():
                        return int(ids[0])
            except (OSError, RuntimeError):
                pass  # Only read-only enumeration is retried, never device commands.
            time.sleep(1)
        raise RuntimeError('Same target did not return before deadline')
