"""Inert private sink dependency. No CLI, controller or production admission.

Import with reviewed offline_baseline_adb available to import. Synchronous calls
have checked deadlines, NOT cancellation guarantees. No fsync/durable claim.
"""
from dataclasses import dataclass
import math
import os
import stat
import time
from pathlib import PurePosixPath
from offline_baseline_adb import SinkIdentity


@dataclass(frozen=True)
class ParentPin:
    device: int
    inode: int
    uid: int


@dataclass(frozen=True)
class CapacityPolicy:
    max_video_bytes: int
    reserve_bytes: int


@dataclass(frozen=True)
class SinkFacts:
    created: bool
    confirmed_written: int
    write_outcome_uncertain: bool
    close_outcome: str
    removed_by_sink: bool


class SinkError(RuntimeError):
    def __init__(self, code, facts=None):
        self.code, self.facts = code, facts
        super().__init__(code)


def _metadata(s):
    return (s.st_dev, s.st_ino, s.st_uid, s.st_mode)


def _positive(n):
    return type(n) is int and 0 < n <= 2**63 - 1


class PrivateSinkFactory:
    """One attempt for one exact path/observed size; construction does no I/O.

    Policy values and ParentPin must be independently approved, never derived
    automatically from a failed attempt. No implicit defaults for capacity.
    """
    def __init__(self, *, exact_path, parent_pin, observed_size, capacity,
                 os_api=os, monotonic=time.monotonic):
        p = PurePosixPath(exact_path) if isinstance(exact_path, str) else None
        if (p is None or not p.is_absolute() or str(p) != exact_path
                or exact_path.startswith('//')
                or '..' in p.parts or p.name != 'capture.mp4'
                or len(p.parts) < 3 or len(p.parts) > 64
                or len(exact_path.encode('utf-8')) > 4096 or '\x00' in exact_path):
            raise ValueError('Exact bounded absolute capture path required')
        if (not isinstance(parent_pin, ParentPin)
                or type(parent_pin.device) is not int or parent_pin.device < 0
                or not _positive(parent_pin.inode)
                or type(parent_pin.uid) is not int or parent_pin.uid < 0):
            raise ValueError('Approved parent device/inode/owner required')
        if (not isinstance(capacity, CapacityPolicy)
                or not _positive(capacity.max_video_bytes)
                or type(capacity.reserve_bytes) is not int
                or not 0 <= capacity.reserve_bytes <= 2**63 - 1
                or not _positive(observed_size)
                or observed_size > capacity.max_video_bytes):
            raise ValueError('Explicit admitted size and capacity policy required')
        self.path, self.pin, self.size = exact_path, parent_pin, observed_size
        self.policy, self.os, self.clock = capacity, os_api, monotonic
        self.parts, self.attempted = p.parts[1:-1], False

    def __call__(self, exact_path, deadline):
        if self.attempted:
            raise SinkError('sink_attempt_spent')
        if exact_path != self.path:
            raise SinkError('destination_mismatch')
        if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
                or not math.isfinite(deadline)):
            raise SinkError('invalid_deadline')
        self.attempted = True
        sink = _Sink(self, deadline)
        try:
            sink._acquire()
            return sink
        except BaseException as exc:
            sink._cleanup()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            code = exc.code if type(exc) is SinkError else 'sink_create_failed'
            raise SinkError(code, sink.facts) from None


class _Sink:
    def __init__(self, factory, deadline):
        self.f, self.deadline = factory, deadline
        self.dirs, self.edges, self.fd = [], [], None
        self.file_meta = None
        self.created, self.written, self.uncertain = False, 0, False
        self.close_state, self.closed = 'not_attempted', False
        self.identity = None

    @property
    def facts(self):
        return SinkFacts(self.created, self.written, self.uncertain,
                         self.close_state, False)

    def _remaining(self):
        now = self.f.clock()
        if not math.isfinite(now) or now >= self.deadline:
            raise SinkError('deadline_exceeded')

    def _call(self, function, *args, **kwargs):
        self._remaining()
        result = function(*args, **kwargs)
        self._remaining()
        return result

    def _open_owned(self, path, flags, mode=0o777, **kwargs):
        # Register ownership BEFORE post-return deadline check.
        self._remaining()
        fd = self.f.os.open(path, flags, mode, **kwargs)
        if flags & self.f.os.O_CREAT:
            self.fd, self.created = fd, True
        else:
            self.dirs.append(fd)
        self._remaining()
        return fd

    def _verify(self):
        api = self.f.os
        for parent, name, child, meta in self.edges:
            actual = self._call(api.fstat, child)
            linked = self._call(api.stat, name, dir_fd=parent,
                                follow_symlinks=False)
            if _metadata(actual) != meta or _metadata(linked) != meta:
                raise SinkError('directory_identity_changed')
        s = self._call(api.fstat, self.dirs[-1])
        expected = (self.f.pin.device, self.f.pin.inode,
                    self.f.pin.uid, stat.S_IFDIR | 0o700)
        if _metadata(s) != expected:
            raise SinkError('private_parent_rejected')
        if self.fd is not None:
            a = self._call(api.fstat, self.fd)
            b = self._call(api.stat, 'capture.mp4', dir_fd=self.dirs[-1],
                           follow_symlinks=False)
            if (not stat.S_ISREG(a.st_mode) or a.st_uid != self.f.pin.uid
                    or a.st_mode != stat.S_IFREG | 0o600 or a.st_nlink != 1
                    or a.st_size != self.written or _metadata(a) != _metadata(b)
                    or b.st_nlink != 1 or b.st_size != self.written
                    or (self.file_meta is not None and _metadata(a) != self.file_meta)):
                raise SinkError('private_file_rejected')
            self.file_meta = _metadata(a)

    def _acquire(self):
        api = self.f.os
        flags = api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC
        parent = self._open_owned('/', flags)
        for name in self.f.parts:
            child = self._open_owned(name, flags, dir_fd=parent)
            s = self._call(api.fstat, child)
            if not stat.S_ISDIR(s.st_mode):
                raise SinkError('directory_rejected')
            self.edges.append((parent, name, child, _metadata(s)))
            parent = child
        self._verify()
        v = self._call(api.fstatvfs, parent)
        if (type(v.f_bavail) is not int or v.f_bavail < 0
                or type(v.f_frsize) is not int or v.f_frsize <= 0
                or v.f_bavail * v.f_frsize < self.f.size + self.f.policy.reserve_bytes):
            raise SinkError('insufficient_capacity')
        self._open_owned('capture.mp4',
                         api.O_WRONLY | api.O_CREAT | api.O_EXCL |
                         api.O_NOFOLLOW | api.O_CLOEXEC, 0o600, dir_fd=parent)
        self._verify()
        self.identity = SinkIdentity(self.f.path, self.f.pin.uid,
                                     stat.S_IFREG | 0o600, self.f.pin.uid,
                                     stat.S_IFDIR | 0o700, True, True)

    def write(self, data):
        if self.closed:
            raise SinkError('sink_closed', self.facts)
        try:
            view = memoryview(data)
            if (view.ndim != 1 or view.itemsize != 1 or not view.contiguous
                    or not 0 < len(view) <= 65536
                    or self.written + len(view) > self.f.size):
                raise SinkError('write_bound_rejected')
            self._verify()
            self._remaining()
            self.uncertain = True
            count = self.f.os.write(self.fd, view)
            if type(count) is not int or not 0 < count <= len(view):
                raise SinkError('write_count_rejected')
            self.written += count
            self.uncertain = False
            self._remaining()
            self._verify()
            return count
        except BaseException as exc:
            self._cleanup()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            code = exc.code if type(exc) is SinkError else 'sink_write_failed'
            raise SinkError(code, self.facts) from None

    def _cleanup(self):
        if self.closed:
            return
        self.closed = True
        # All descriptors attempted exactly once, including after deadline.
        # Never retry close: EINTR/error may mean FD number already released.
        failed = False
        interrupted = None
        fds = ([self.fd] if self.fd is not None else []) + list(reversed(self.dirs))
        self.fd, self.dirs = None, []
        for fd in fds:
            try:
                self.f.os.close(fd)
            except BaseException as exc:
                failed = True
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    interrupted = exc
        self.close_state = 'uncertain' if failed else 'closed'
        if interrupted is not None:
            raise interrupted

    def close(self):
        if self.closed:
            if self.close_state == 'uncertain':
                raise SinkError('close_outcome_uncertain', self.facts)
            return
        error = None
        try:
            self._verify()
            self._remaining()
        except BaseException as exc:
            error = exc
        self._cleanup()
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise error
        if self.close_state == 'uncertain':
            raise SinkError('close_outcome_uncertain', self.facts) from None
        if error is not None:
            code = error.code if type(error) is SinkError else 'close_verify_failed'
            raise SinkError(code, self.facts) from None
        try:
            self._remaining()
        except SinkError:
            raise SinkError('deadline_exceeded', self.facts) from None
