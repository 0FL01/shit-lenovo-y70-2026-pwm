"""Source renderer and strict byte parser. This module never executes commands."""
from hashlib import sha256
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parent
SOURCE_SHA256 = "86e01f66afee1c7849813ed5968e9698c5267c9f17597c34094fa60b445068a2"
HOST_TOOLS = {name: "/usr/bin/" + name.lower()
              for name in ("MKDIR", "RM", "RMDIR", "CAT", "CMP", "WC")}
ANDROID_TOOLS = {name: "/system/bin/" + name.lower() for name in HOST_TOOLS}
MAX_OUTPUT = 4096

def render(nonce, *, host=False):
    """Return (argv, exact-owned-directory). Only two fixed tool mappings."""
    if not isinstance(nonce, str) or re.fullmatch(r"[0-9a-f]{24}", nonce) is None:
        raise ValueError("nonce must be 24 lowercase hex characters")
    if type(host) is not bool:
        raise ValueError("host must be bool")
    raw = (ROOT / "probe_owner_fd.sh.in").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("source pin mismatch")
    directory = str(ROOT / ("host-fixture-" + nonce)) if host else (
        "/data/local/tmp/fdbyte-" + nonce)
    tools = HOST_TOOLS if host else ANDROID_TOOLS
    source = raw.decode("ascii").replace("@DIR@", shlex.quote(directory))
    source = source.replace("@TOKEN@", "fdbyte-owner-" + nonce)
    for name, path in tools.items():
        source = source.replace("@" + name + "@", path)
    if "@" in source:
        raise ValueError("unresolved source placeholder")
    return (["/bin/sh" if host else "/system/bin/sh", "-c", source], directory)

def parse(stdout, stderr, rc, *, post_absent=None):
    """No authenticity claim: parent owns binding, transport and independent post-read."""
    if type(stdout) is not bytes or type(stderr) is not bytes or type(rc) is not int:
        raise ValueError("separate bytes stdout/stderr and integer rc required")
    if post_absent is not None and type(post_absent) is not bool:
        raise ValueError("post_absent must be independently observed bool or None")
    if rc != 0 or stderr or len(stdout) > MAX_OUTPUT:
        raise ValueError("nonzero rc, outer diagnostic, or exceeded byte cap; retain/reconcile")
    pos = 0
    def line():
        nonlocal pos
        end = stdout.find(b"\n", pos)
        if end < 0:
            raise ValueError("truncated line")
        result = stdout[pos:end]
        pos = end + 1
        return result
    if line() != b"FDMB1":
        raise ValueError("wrong header")
    records = {}
    for name in (b"lf", b"both", b"sub-lf", b"sub-nul", b"sub-err"):
        if line() != name:
            raise ValueError("wrong record order")
        count = line()
        # GNU and Android wc may pad. No sign, CR, NUL, tab or leading-zero alias.
        if re.fullmatch(rb" *([0-9]|[1-9][0-9]{1,3})", count) is None:
            raise ValueError("noncanonical count")
        n = int(count)
        if n > 1024 or pos + n > len(stdout):
            raise ValueError("invalid/truncated payload")
        records[name] = stdout[pos:pos+n]
        pos += n
    if stdout[pos:] != b"END\n":
        raise ValueError("missing completion or extra bytes")
    if records[b"lf"] != b"\n" or records[b"both"] != b"\n\x00":
        raise ValueError("FD binary observation mismatch")
    if records[b"sub-lf"] != b"":
        raise ValueError("unexpected trailing-LF substitution behavior")
    if records[b"sub-nul"] not in (b"", b"\x00"):
        raise ValueError("unclassified NUL substitution behavior")
    return {
        "fd_bytes": "observed LF=1 and LF+NUL=2 after unlink",
        "command_substitution_lf": "lost trailing LF",
        "command_substitution_nul": "lost NUL" if not records[b"sub-nul"] else "preserved here only",
        "substitution_stderr": records[b"sub-err"],
        "cleanup": "independently absent" if post_absent is True else
                   "contradicted; investigate exact path" if post_absent is False else
                   "unverified; exact-path post-read required",
        "portability": "only this invocation; Android remains unqualified by host tests",
    }
