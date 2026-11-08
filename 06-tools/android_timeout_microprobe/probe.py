"""Offline transcript construction/parsing only. No live runner or device I/O."""
from dataclasses import dataclass
import hashlib
import re
import shlex

LIMIT = 4096
CHILD = """printf 'M1 PID %s\\n' "$$"
IFS= read -r statline < "/proc/$$/stat" || exit 111
printf 'M1 STAT %s\\n' "$statline"
exec /system/bin/sleep 2s"""
BODY = "/system/bin/timeout -k 1s 1s /system/bin/sh -c " + shlex.quote(CHILD) + """
rc=$?
printf 'M1 TIMEOUT_RC %s\\n' "$rc"
printf 'M1 END\\n'
exit 0"""
ANDROID_COMMAND = "/system/bin/sh -c " + shlex.quote(BODY)
COMMAND_SHA256 = hashlib.sha256(ANDROID_COMMAND.encode("ascii")).hexdigest()

class Invalid(ValueError):
    pass

@dataclass(frozen=True)
class Identity:
    pid: int
    start: int

@dataclass(frozen=True)
class Observation:
    identity: Identity
    timeout_rc: int
    meaning: str
    authorizes_next_test: bool = False

def decimal(value, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,19}", value):
        raise Invalid("noncanonical decimal")
    number = int(value)
    if number > 18446744073709551615 or (positive and number == 0):
        raise Invalid("decimal out of range")
    return number

def lines(raw):
    if not isinstance(raw, bytes) or len(raw) > LIMIT or not raw.endswith(b"\n"):
        raise Invalid("missing, oversized or truncated transcript")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise Invalid("non-ASCII transcript") from exc
    if "\r" in text or "\x00" in text:
        raise Invalid("invalid control")
    return text[:-1].split("\n")

def stat_identity(text, expected_pid):
    # Linux proc stat: greedy comm terminator handles spaces and ')' in comm.
    match = re.fullmatch(r"([1-9][0-9]{0,9}) \(([^\n\r\x00]*)\) ([RSDZTtXxKWPI]) (.*)", text)
    if not match:
        raise Invalid("malformed stat")
    pid = decimal(match[1], True)
    if pid != expected_pid or pid > 2147483647:
        raise Invalid("stat PID mismatch")
    fields = match[4].split(" ")
    if len(fields) != 49 or any(not re.fullmatch(r"-?(0|[1-9][0-9]{0,19})", f) or f == "-0" for f in fields):
        raise Invalid("malformed stat fields")
    start = decimal(fields[18], True)  # field22, fields starts at field4
    return Identity(pid, start)

def parse_probe(stdout, stderr, wrapper_rc, transport_complete):
    if transport_complete is not True or type(wrapper_rc) is not int or wrapper_rc != 0 or stderr != b"":
        raise Invalid("UNKNOWN transport/wrapper/stderr")
    rows = lines(stdout)
    if len(rows) != 4 or not rows[0].startswith("M1 PID ") or not rows[1].startswith("M1 STAT ") or not rows[2].startswith("M1 TIMEOUT_RC ") or rows[3] != "M1 END":
        raise Invalid("missing, duplicated or unexpected record")
    pid = decimal(rows[0][7:], True)
    ident = stat_identity(rows[1][8:], pid)
    rc = decimal(rows[2][14:])
    if rc > 255:
        raise Invalid("invalid shell exit status")
    meaning = "observed-timeout-124" if rc == 124 else "UNKNOWN"
    return Observation(ident, rc, meaning)

def reconciliation_command(observation):
    # Only parser-derived 124 permits proposing this independent read, not running it.
    if type(observation) is not Observation or observation.timeout_rc != 124 or observation.meaning != "observed-timeout-124":
        raise Invalid("no reconciliation proposal for unknown result")
    ident = observation.identity
    if type(ident) is not Identity or type(ident.pid) is not int or type(ident.start) is not int or not 1 <= ident.pid <= 2147483647 or not 1 <= ident.start <= 18446744073709551615:
        raise Invalid("invalid identity")
    pid = str(ident.pid)
    body = """printf 'R1 PID %s\\n' """ + pid + """
if IFS= read -r statline < /proc/""" + pid + """/stat; then
  printf 'R1 STAT %s\\n' "$statline"
elif [ ! -d /proc/""" + pid + """ ]; then
  printf 'R1 NOT_VISIBLE\\n'
else
  printf 'R1 READ_FAILED\\n'
fi
printf 'R1 END\\n'
exit 0"""
    # Redirection error is suppressed, disposition remains explicit.
    return "/system/bin/sh -c " + shlex.quote(body) + " 2>/dev/null"

def parse_reconciliation(raw, stderr, wrapper_rc, transport_complete, observation):
    reconciliation_command(observation)  # validates eligible observation and identity
    if transport_complete is not True or type(wrapper_rc) is not int or wrapper_rc != 0 or stderr != b"":
        raise Invalid("UNKNOWN reconciliation transport")
    rows = lines(raw)
    if len(rows) != 3 or rows[0] != "R1 PID " + str(observation.identity.pid) or rows[2] != "R1 END":
        raise Invalid("invalid reconciliation framing")
    if rows[1] == "R1 NOT_VISIBLE":
        return "NOT_VISIBLE_OBSERVATION_ONLY"
    if rows[1] == "R1 READ_FAILED":
        return "UNKNOWN_READ_FAILED"
    if not rows[1].startswith("R1 STAT "):
        raise Invalid("invalid reconciliation record")
    current = stat_identity(rows[1][8:], observation.identity.pid)
    return "ORIGINAL_IDENTITY_PRESENT" if current == observation.identity else "PID_REUSED_OBSERVATION_ONLY"
