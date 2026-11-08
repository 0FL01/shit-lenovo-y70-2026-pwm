"""Pure finite synthetic transition model. No producer, controller, IO or live adapter."""
from dataclasses import dataclass, replace
from enum import Enum, auto
from decimal import Decimal, localcontext
import math
import re

class Refused(ValueError):
    pass

class Phase(Enum):
    SHAM15_WRITE = auto()
    SHAM_P85 = auto()
    RETURN15_WRITE = auto()
    RETURN_P85 = auto()
    RETURN_C1 = auto()

ORDER = tuple(Phase)

class Verdict(Enum):
    PASS = auto()
    FAIL = auto()
    UNKNOWN = auto()

class Unknown(Enum):
    VALUE = auto()

UNKNOWN = Unknown.VALUE

class Protocol(Enum):
    NORMAL_RESERVED = auto()
    EXPLORATORY_FACTORY15 = auto()

class Classification(Enum):
    NORMAL = auto()
    RECOVERY_DEGRADED_PROTOCOL = auto()

class State(Enum):
    NEW = auto()
    STAGED = auto()
    BASELINE_READY = auto()
    CLOCK_GRANTED = auto()
    READY = auto()
    RESERVED = auto()
    DISPATCHED = auto()
    PRODUCED = auto()
    SEALED = auto()
    QUIET = auto()
    HOLD_START = auto()
    HOLD_WAIT = auto()
    RETURN_PROOF = auto()
    LOCAL_RETURNED = auto()
    AUDIT = auto()
    RESTORE = auto()
    OFFLINE = auto()
    RUN_COMPLETE = auto()
    EXPLORATORY_STOCK_SAMPLE = auto()
    DEGRADED_COMPLETE = auto()
    UNCERTAIN = auto()
    CRASHED = auto()

class Obligation(Enum):
    TARGET_RESTORE = auto()
    CAMERA_STOP_COLLECT = auto()
    SCRATCH_CLEANUP = auto()
    WATCHDOG_RECONCILE = auto()
    OWNER_RELEASE = auto()

class Watchdog(Enum):
    UNARMED = auto()
    ARMED = auto()
    DISARMED = auto()
    EXPIRED = auto()

class EventKind(Enum):
    STAGE = auto()
    BASELINE = auto()
    BOUND_GRANT = auto()
    ARM = auto()
    RESERVE = auto()
    DISPATCH = auto()
    PRODUCER_RESULT = auto()
    SEALED_EVIDENCE = auto()
    GATE_VERDICT = auto()
    QUIET = auto()
    CAMERA_START = auto()
    CAMERA_END = auto()
    SAFE_RETURN = auto()
    DISCONNECT = auto()
    RECONNECT = auto()
    CLOCK_TICK = auto()
    TIMEOUT = auto()
    SHORT_DISARM = auto()
    FINAL_CAPTURE = auto()
    AUDIT_ACCEPT = auto()
    AUDIT_REJECT = auto()
    VERIFIED_CHANGED_BOOT = auto()
    VERIFIED_CLEANUP = auto()
    OFFLINE_OPTICAL_VERDICT = auto()
    CRASH = auto()
    RESTART = auto()

def require(ok, reason):
    if not ok:
        raise Refused(reason)

def number(x):
    require(type(x) in (int, float) and 0 <= x <= 10**12 and math.isfinite(x),
            "finite nonnegative number, never bool")

def text_id(x):
    require(type(x) is str and x.startswith("SYNTHETIC:") and len(x) <= 160,
            "only bounded synthetic fixture identities")

def enum(x, cls):
    require(type(x) is cls, "typed enum required")

@dataclass(frozen=True)
class KnownCost:
    seconds: float
    qualification: str
    def __post_init__(self):
        number(self.seconds)
        text_id(self.qualification)

@dataclass(frozen=True)
class Budget:
    current: object
    downstream: object
    jitter: object
    uncovered: object
    # Disjoint successful costs, including disarm. Not timeout/kill bounds.
    def __post_init__(self):
        for v in (self.current, self.downstream, self.jitter, self.uncovered):
            require(type(v) is KnownCost or v is UNKNOWN, "cost must be Known or UNKNOWN")
    def total(self):
        vals = (self.current, self.downstream, self.jitter, self.uncovered)
        require(all(type(v) is KnownCost for v in vals), "UNKNOWN_BOUND")
        return sum(v.seconds for v in vals)

@dataclass(frozen=True)
class Tick:
    host: float
    device: float
    def __post_init__(self):
        number(self.host)
        number(self.device)

@dataclass(frozen=True)
class Grant:
    anchor: float
    host_elapsed: float
    margin: float
    budget: Budget
    clock_contract: Verdict
    def __post_init__(self):
        for v in (self.anchor, self.host_elapsed, self.margin):
            number(v)
        require(type(self.budget) is Budget, "budget")
        enum(self.clock_contract, Verdict)

@dataclass(frozen=True)
class Producer:
    rc: int
    stderr: bytes
    def __post_init__(self):
        require(type(self.rc) is int and -255 <= self.rc <= 255, "finite rc")
        require(type(self.stderr) is bytes and len(self.stderr) <= 1024, "bounded stderr")

@dataclass(frozen=True)
class Gates:
    E: Verdict
    C: Verdict
    S: Verdict
    I: Verdict
    W: Verdict
    def __post_init__(self):
        for v in (self.E, self.C, self.S, self.I, self.W):
            enum(v, Verdict)
    def passed(self, phase):
        # Read has no writer-wire gate; writer has no read-interval gate.
        v = (self.E, self.C, self.S,
             self.W if phase in (Phase.SHAM15_WRITE, Phase.RETURN15_WRITE) else self.I)
        return all(x is Verdict.PASS for x in v)

@dataclass(frozen=True)
class Binding:
    epoch: str
    boot: str
    phase: Phase
    nonce: str
    manifest: str
    source: str
    plan: str
    origin: str
    artifacts: tuple
    seal: str
    payload: tuple
    def __post_init__(self):
        enum(self.phase, Phase)
        for v in (self.epoch, self.boot, self.nonce, self.manifest, self.source,
                  self.plan, self.origin, self.seal):
            text_id(v)
        require(type(self.artifacts) is tuple and len(self.artifacts) == 3,
                "exact three published identities")
        for v in self.artifacts:
            text_id(v)
        require(type(self.payload) is tuple and all(type(v) is int and 0 <= v <= 255
                for v in self.payload), "byte tuple")

@dataclass(frozen=True)
class Receipt:
    binding: Binding
    producer: object
    gates: Gates
    def __post_init__(self):
        require(type(self.binding) is Binding and type(self.gates) is Gates, "receipt types")
        require(type(self.producer) is Producer or self.producer is UNKNOWN, "actual result")

@dataclass(frozen=True)
class Prerequisite:
    identity: str
    verdict: Verdict
    def __post_init__(self):
        text_id(self.identity)
        enum(self.verdict, Verdict)

@dataclass(frozen=True)
class Guard:
    binding: Binding
    timing: bytes
    native_state_owner_boot_esd: Verdict
    retained_origin_interval: Verdict
    nonce_collision_free: Verdict
    freshness: str
    def __post_init__(self):
        require(type(self.binding) is Binding and type(self.timing) is bytes, "guard types")
        require(len(self.timing) <= 128, "guard cap")
        for v in (self.native_state_owner_boot_esd, self.retained_origin_interval,
                  self.nonce_collision_free):
            enum(v, Verdict)
        text_id(self.freshness)

@dataclass(frozen=True)
class Quiet:
    identity: str
    duration: float
    verdict: Verdict
    def __post_init__(self):
        text_id(self.identity)
        number(self.duration)
        enum(self.verdict, Verdict)

@dataclass(frozen=True)
class Ack:
    epoch: str
    boot: str
    camera: str
    manifest: str
    stage: str
    nonce: str
    sequence: int
    session: str
    requested_profile: str
    observed_profile: str
    frame: int
    timestamp: float
    metadata: str
    start_reference: str
    settled: Verdict
    continuity: Verdict
    def __post_init__(self):
        for key in ("epoch", "boot", "camera", "manifest", "stage", "nonce", "session",
                    "requested_profile", "observed_profile", "metadata", "start_reference"):
            text_id(getattr(self, key))
        require(type(self.sequence) is int and self.sequence in (1, 2), "ACK sequence")
        require(type(self.frame) is int and 0 <= self.frame < 2**63, "sensor frame")
        number(self.timestamp)
        enum(self.settled, Verdict)
        enum(self.continuity, Verdict)

@dataclass(frozen=True)
class Recovery:
    target: str
    old_boot: str
    new_boot: str
    verified: Verdict
    no_child_alive: Verdict
    epoch: str
    incident: int
    proof_id: str
    def __post_init__(self):
        require(type(self.incident) is int and self.incident >= 0, "recovery incident")
        for v in (self.target, self.old_boot, self.new_boot, self.epoch, self.proof_id):
            text_id(v)
        enum(self.verified, Verdict)
        enum(self.no_child_alive, Verdict)

@dataclass(frozen=True)
class Cleanup:
    obligation: Obligation
    verdict: Verdict
    no_child_alive: Verdict
    identity: str
    boot: str
    incident: int
    def __post_init__(self):
        text_id(self.boot)
        require(type(self.incident) is int and self.incident >= 0, "cleanup incident")
        enum(self.obligation, Obligation)
        enum(self.verdict, Verdict)
        enum(self.no_child_alive, Verdict)
        text_id(self.identity)

@dataclass(frozen=True)
class _LedgerSnapshot:
    spent: frozenset = frozenset()
    authoritative: Verdict = Verdict.PASS
    def __post_init__(self):
        require(type(self.spent) is frozenset, "immutable ledger")
        for v in self.spent:
            text_id(v)
        enum(self.authoritative, Verdict)

@dataclass(frozen=True)
class Event:
    kind: EventKind
    value: object = None
    def __post_init__(self):
        enum(self.kind, EventKind)

@dataclass(frozen=True)
class _Snapshot:
    epoch: str
    protocol: Protocol
    ledger: _LedgerSnapshot
    state: State = State.NEW
    boot: str = "SYNTHETIC:boot0"
    target: str = "SYNTHETIC:target"
    manifest: str = "SYNTHETIC:manifest"
    source: str = "SYNTHETIC:source"
    host: float = 0
    device: float = 0
    expiry: object = None
    budget: object = None
    phase_index: int = 0
    consumed: tuple = ()
    producer: object = None
    receipt: object = None
    operation_started: object = None
    receipts: tuple = ()
    target_uncertain: bool = False
    optics_invalid: bool = False
    classification: Classification = Classification.NORMAL
    pending: frozenset = frozenset(Obligation)
    short: Watchdog = Watchdog.UNARMED
    short_expiry: object = None
    overall: Watchdog = Watchdog.ARMED
    overall_expiry: float = 600
    start_ack: object = None
    ack_received: object = None
    hold_quiet: bool = False
    local_proof: bool = False
    audited: bool = False
    recovered: bool = False
    final_capture: bool = False
    connected: bool = True
    incident: int = 0
    consumed_recovery: tuple = ()
    seen_boots: tuple = ("SYNTHETIC:boot0",)
    def __post_init__(self):
        text_id(self.epoch)
        enum(self.protocol, Protocol)
        require(type(self.ledger) is _LedgerSnapshot, "ledger")
        for key in ("boot", "target", "manifest", "source"):
            text_id(getattr(self, key))
        for key in ("host", "device", "overall_expiry"):
            number(getattr(self, key))
        for key in ("expiry", "short_expiry", "ack_received", "operation_started"):
            if getattr(self, key) is not None:
                number(getattr(self, key))
        for key in ("target_uncertain", "optics_invalid", "hold_quiet", "local_proof",
                    "audited", "recovered", "final_capture", "connected"):
            require(type(getattr(self, key)) is bool, "typed sticky/fixture flag")
        enum(self.state, State)
        enum(self.classification, Classification)
        enum(self.short, Watchdog)
        enum(self.overall, Watchdog)
        require(type(self.phase_index) is int and 0 <= self.phase_index <= 5, "phase index")
        require(type(self.consumed) is tuple and len(set(self.consumed)) == len(self.consumed), "consumed nonces")
        for nonce in self.consumed:
            text_id(nonce)
        require(type(self.pending) is frozenset and all(type(o) is Obligation for o in self.pending), "obligations")
        require(self.budget is None or type(self.budget) is Budget, "budget")
        require(self.producer is None or self.producer is UNKNOWN or type(self.producer) is Producer, "producer")
        require(self.receipt is None or type(self.receipt) is Receipt, "receipt")
        require(type(self.receipts) is tuple and all(type(r) is Receipt for r in self.receipts), "receipts")
        require(self.start_ack is None or type(self.start_ack) is Ack, "ACK")
        require(type(self.incident) is int and self.incident >= 0, "failure incident")
        for values in (self.consumed_recovery, self.seen_boots):
            require(type(values) is tuple and len(set(values)) == len(values), "unique proof/boot identities")
            for value in values:
                text_id(value)

    def expected(self):
        require(self.phase_index < 5, "no sixth child")
        p = ORDER[self.phase_index]
        stem = self.epoch + ":" + p.name
        payload = (21, 0, 0) if p in (Phase.SHAM_P85, Phase.RETURN_P85) else (
            (0, 0, 96) if p is Phase.RETURN_C1 else (21,))
        origin = "SYNTHETIC:prequiet" if self.phase_index < 2 else "SYNTHETIC:SHAM15_HOLD_BEGIN"
        return Binding(self.epoch, self.boot, p, stem + ":nonce", self.manifest,
                       self.source, "SYNTHETIC:plan:" + p.name, origin,
                       tuple(stem + ":" + x for x in ("out", "err", "state")),
                       stem + ":seal", payload)

    def failed(self):
        return replace(self, state=State.UNCERTAIN, target_uncertain=True,
                       classification=Classification.RECOVERY_DEGRADED_PROTOCOL,
                       incident=self.incident + 1, recovered=False, audited=False,
                       pending=self.pending | frozenset(Obligation))

    def admit(self):
        require(not self.target_uncertain and self.expiry is not None, "uncertain/no grant")
        require(self.device < self.expiry and self.host < 37, "active cutoff")
        require(self.short is Watchdog.ARMED and self.overall is Watchdog.ARMED, "watchdogs")
        if self.protocol is Protocol.NORMAL_RESERVED:
            require(self.device + self.budget.total() < self.expiry, "strict successful suffix")

    def _step(self, event):
        require(type(event) is Event, "typed event")
        k, v = event.kind, event.value
        # Expected payload types: unknown fields are rejected by dataclass constructors.
        types = {
            EventKind.STAGE: Prerequisite, EventKind.BASELINE: Prerequisite,
            EventKind.BOUND_GRANT: Grant, EventKind.ARM: Prerequisite,
            EventKind.RESERVE: Budget, EventKind.DISPATCH: Guard,
            EventKind.PRODUCER_RESULT: (Producer, Unknown), EventKind.SEALED_EVIDENCE: Receipt,
            EventKind.GATE_VERDICT: Gates, EventKind.QUIET: Quiet,
            EventKind.CAMERA_START: Ack, EventKind.CAMERA_END: Ack,
            EventKind.SAFE_RETURN: Guard, EventKind.CLOCK_TICK: Tick,
            EventKind.SHORT_DISARM: Verdict, EventKind.FINAL_CAPTURE: Verdict,
            EventKind.VERIFIED_CHANGED_BOOT: Recovery, EventKind.VERIFIED_CLEANUP: Cleanup,
            EventKind.OFFLINE_OPTICAL_VERDICT: Verdict,
            EventKind.RECONNECT: Prerequisite,
        }
        wanted = types.get(k, type(None))
        require(type(v) in (wanted if type(wanted) is tuple else (wanted,)), "event payload")
        if k is EventKind.CLOCK_TICK:
            if v.host < self.host or v.device < self.device:
                return self.failed()
            n = replace(self, host=v.host, device=v.device)
            if n.short is Watchdog.ARMED and n.device >= n.short_expiry:
                n = replace(n, short=Watchdog.EXPIRED)
            if n.overall is Watchdog.ARMED and n.host >= n.overall_expiry:
                n = replace(n, overall=Watchdog.EXPIRED)
            active = self.state in {State.CLOCK_GRANTED, State.READY, State.RESERVED,
                State.DISPATCHED, State.PRODUCED, State.SEALED, State.QUIET,
                State.HOLD_START, State.HOLD_WAIT, State.RETURN_PROOF}
            if (active and (n.host >= 37 or n.device >= n.expiry)) or (
                n.short is Watchdog.EXPIRED or n.overall is Watchdog.EXPIRED):
                return n.failed()
            if self.state in (State.RESERVED, State.DISPATCHED, State.PRODUCED, State.SEALED):
                if type(self.budget.current) is KnownCost and (
                        n.device - self.operation_started >= self.budget.current.seconds):
                    return n.failed()
            return n
        if k in (EventKind.CRASH, EventKind.RESTART):
            require(self.state is not State.NEW, "not started")
            return replace(self.failed(), state=State.CRASHED,
                           pending=self.pending | frozenset(Obligation))
        if k is EventKind.DISCONNECT:
            require(self.state not in (State.NEW, State.RUN_COMPLETE,
                    State.EXPLORATORY_STOCK_SAMPLE, State.DEGRADED_COMPLETE), "not active")
            return replace(self, connected=False,
                           pending=self.pending | {Obligation.CAMERA_STOP_COLLECT})
        if k is EventKind.RECONNECT:
            require(not self.connected and v.identity == self.epoch + ":camera-reidentified"
                    and v.verdict is Verdict.PASS, "reidentify camera before host cleanup")
            return replace(self, connected=True)
        if k is EventKind.AUDIT_REJECT:
            require(self.state is not State.NEW, "no epoch")
            # Even late contradictions invalidate earlier local/host success.
            return replace(self.failed(), audited=False, recovered=False,
                           pending=self.pending | frozenset(Obligation))
        if k is EventKind.TIMEOUT:
            require(self.state not in (State.NEW, State.RUN_COMPLETE,
                    State.EXPLORATORY_STOCK_SAMPLE, State.DEGRADED_COMPLETE), "no active attempt")
            return self.failed()
        if k is EventKind.VERIFIED_CHANGED_BOOT:
            require(self.state in (State.UNCERTAIN, State.CRASHED), "recovery only")
            require(v.target == self.target and v.old_boot == self.boot and
                    v.new_boot not in self.seen_boots and v.verified is Verdict.PASS and
                    v.epoch == self.epoch and v.incident == self.incident and
                    v.proof_id not in self.consumed_recovery and
                    v.no_child_alive is Verdict.PASS, "same-target changed boot proof")
            return replace(self, state=State.RESTORE, recovered=True, boot=v.new_boot,
                           consumed_recovery=self.consumed_recovery + (v.proof_id,),
                           seen_boots=self.seen_boots + (v.new_boot,))
        if k is EventKind.STAGE:
            require(self.state is State.NEW, "one staging")
            require(self.ledger.authoritative is Verdict.PASS and
                    self.epoch not in self.ledger.spent, "spent/missing/ambiguous ledger")
            require(v.identity == self.epoch + ":stage" and v.verdict is Verdict.PASS,
                    "fixture stage refusal; real sealing unimplemented")
            return replace(self, state=State.STAGED,
                           ledger=_LedgerSnapshot(self.ledger.spent | {self.epoch}))
        if k is EventKind.BASELINE:
            require(self.state is State.STAGED, "baseline order")
            require(v.identity == self.epoch + ":baseline" and v.verdict is Verdict.PASS,
                    "baseline fixture prerequisite")
            return replace(self, state=State.BASELINE_READY)
        if k is EventKind.BOUND_GRANT:
            require(self.state is State.BASELINE_READY and self.expiry is None, "one immutable grant")
            require(v.host_elapsed == self.host and 0 <= v.anchor <= self.device and
                    v.host_elapsed < 37 and v.clock_contract is Verdict.PASS, "clock fixture")
            expiry = math.floor(v.anchor + 37 - v.host_elapsed - v.margin)
            require(expiry > self.device, "spent grant")
            if self.protocol is Protocol.NORMAL_RESERVED:
                require(self.device + v.budget.total() < expiry, "UNKNOWN or insufficient reserved budget")
            return replace(self, state=State.CLOCK_GRANTED, expiry=expiry, budget=v.budget)
        if k is EventKind.ARM:
            require(self.state is State.CLOCK_GRANTED, "arm order")
            if v.identity != self.epoch + ":arm" or v.verdict is not Verdict.PASS:
                return self.failed()
            return replace(self, state=State.READY, short=Watchdog.ARMED,
                           short_expiry=self.device + 60)
        if k is EventKind.RESERVE:
            require(self.state is State.READY, "reserve order")
            require(not self.optics_invalid or self.classification is
                    Classification.RECOVERY_DEGRADED_PROTOCOL, "explicit degraded return required")
            n = replace(self, budget=v)
            n.admit()
            b = n.expected()
            require(b.nonce not in n.consumed, "consumed invocation")
            return replace(n, state=State.RESERVED, consumed=n.consumed + (b.nonce,),
                           producer=None, receipt=None, operation_started=n.device)
        if k is EventKind.DISPATCH:
            require(self.state is State.RESERVED, "reserve before dispatch")
            self.admit()
            if not self.guard_ok(v):
                return self.failed()
            return replace(self, state=State.DISPATCHED)
        if k is EventKind.PRODUCER_RESULT:
            require(self.state is State.DISPATCHED, "result exactly once")
            n = replace(self, producer=v)
            if v is UNKNOWN or v.rc != 0 or v.stderr != b"":
                return n.failed()
            return replace(n, state=State.PRODUCED)
        if k is EventKind.SEALED_EVIDENCE:
            require(self.state is State.PRODUCED, "seal after actual producer")
            if v.binding != self.expected() or v.producer != self.producer:
                return self.failed()
            return replace(self, state=State.SEALED, receipt=v)
        if k is EventKind.GATE_VERDICT:
            require(self.state is State.SEALED, "gates after seal")
            if v != self.receipt.gates or not v.passed(self.expected().phase):
                return self.failed()
            idx = self.phase_index + 1
            state = (State.QUIET, State.HOLD_START, State.QUIET,
                     State.READY, State.RETURN_PROOF)[self.phase_index]
            return replace(self, state=state, phase_index=idx,
                           receipts=self.receipts + (self.receipt,),
                           local_proof=(idx == 5))
        if k is EventKind.QUIET:
            require(self.state in (State.QUIET, State.HOLD_START, State.HOLD_WAIT), "quiet order")
            require(not (self.state is State.HOLD_WAIT and self.hold_quiet), "quiet once")
            if v.identity != self.epoch + ":quiet:" + str(self.phase_index) or (
                    v.duration < 2 or v.verdict is not Verdict.PASS):
                return self.failed()
            hold = self.state in (State.HOLD_START, State.HOLD_WAIT)
            return replace(self, state=self.state if hold else State.READY, hold_quiet=hold)
        if k in (EventKind.CAMERA_START, EventKind.CAMERA_END):
            start = k is EventKind.CAMERA_START
            require(self.state is (State.HOLD_START if start else State.HOLD_WAIT), "ACK phase/once")
            require(self.connected, "no cross-phone access on host loss")
            require(not self.optics_invalid, "failed ACK cannot be replaced; explicit degraded branch only")
            valid = self.ack_ok(v, start)
            if not start:
                valid = valid and self.hold_quiet and self.device - self.ack_received >= 4.5
            if not valid:
                return replace(self, optics_invalid=True)
            self.admit()
            if start:
                return replace(self, state=State.HOLD_WAIT, start_ack=v,
                               ack_received=self.device, hold_quiet=False)
            return replace(self, state=State.READY)
        if k is EventKind.SAFE_RETURN:
            require(self.state in (State.HOLD_START, State.HOLD_WAIT), "return branch phase")
            require(self.protocol is Protocol.NORMAL_RESERVED, "no exploratory degraded policy")
            self.admit()
            require(self.hold_quiet, "complete return prequiet required")
            if not self.guard_ok(v):
                return self.failed()
            return replace(self, state=State.READY, optics_invalid=True,
                           classification=Classification.RECOVERY_DEGRADED_PROTOCOL)
        if k is EventKind.SHORT_DISARM:
            require(self.state is State.RETURN_PROOF and self.local_proof, "exact local proof first")
            if v is not Verdict.PASS or self.device >= self.short_expiry:
                return self.failed()
            return replace(self, state=State.LOCAL_RETURNED, short=Watchdog.DISARMED)
        if k is EventKind.FINAL_CAPTURE:
            require(self.state is State.LOCAL_RETURNED, "final capture before audit/restore")
            require(v is not Verdict.PASS or self.connected, "camera stop/collection needs reidentified host")
            pending = self.pending
            if v is Verdict.PASS:
                pending = pending - {Obligation.CAMERA_STOP_COLLECT}
            return replace(self, state=State.AUDIT, final_capture=v is Verdict.PASS,
                           optics_invalid=self.optics_invalid or v is not Verdict.PASS,
                           pending=pending)
        if k is EventKind.AUDIT_ACCEPT:
            require(self.state is State.AUDIT and self.local_proof and
                    not self.target_uncertain, "hardware audit order")
            return replace(self, state=State.RESTORE, audited=True)
        if k is EventKind.VERIFIED_CLEANUP:
            require(self.state is State.RESTORE, "guarded restore only")
            require(self.recovered or (self.audited and not self.target_uncertain), "recovery before restore")
            require(v.obligation in self.pending, "cleanup once")
            require(v.identity == self.epoch + ":cleanup:" + v.obligation.name, "cleanup identity")
            require(v.boot == self.boot and v.incident == self.incident, "fresh cleanup boot/incident")
            if v.verdict is not Verdict.PASS or v.no_child_alive is not Verdict.PASS:
                return self
            o = v.obligation
            if o is Obligation.CAMERA_STOP_COLLECT:
                require(self.connected, "camera cleanup pending until reidentified host")
            if o is Obligation.TARGET_RESTORE:
                require(self.short is Watchdog.DISARMED or self.recovered, "short reconcile/recovery")
            if o in (Obligation.SCRATCH_CLEANUP, Obligation.WATCHDOG_RECONCILE):
                require(Obligation.TARGET_RESTORE not in self.pending, "target restore first")
            if o is Obligation.WATCHDOG_RECONCILE:
                require(self.overall is not Watchdog.UNARMED, "overall lifecycle")
            if o is Obligation.OWNER_RELEASE:
                require(self.pending == frozenset({o}), "owner release last")
            pending = self.pending - {o}
            return replace(self, pending=pending,
                           overall=Watchdog.DISARMED if o is Obligation.WATCHDOG_RECONCILE else self.overall,
                           short=Watchdog.DISARMED if o is Obligation.WATCHDOG_RECONCILE else self.short,
                           state=State.OFFLINE if not pending else State.RESTORE)
        if k is EventKind.OFFLINE_OPTICAL_VERDICT:
            require(self.state is State.OFFLINE and not self.pending, "restore before PTS/FFT")
            bad = self.optics_invalid or v is not Verdict.PASS
            clean = (not bad and not self.target_uncertain and self.audited and self.final_capture
                     and self.classification is Classification.NORMAL)
            state = (State.RUN_COMPLETE if self.protocol is Protocol.NORMAL_RESERVED
                     else State.EXPLORATORY_STOCK_SAMPLE) if clean else State.DEGRADED_COMPLETE
            return replace(self, state=state, optics_invalid=bad)
        raise Refused("unsupported state/event")

    def guard_ok(self, v):
        match = re.fullmatch(rb"GUARD_TIMING ([0-9]+\.[0-9]+) ([0-9]+\.[0-9]+)\n", v.timing)
        timing_ok = False
        if match:
            with localcontext() as context:
                context.prec = 160  # More than the entire bounded 128-byte input.
                a, b = (Decimal(x.decode("ascii")) for x in match.groups())
                timing_ok = a.is_finite() and b.is_finite() and 0 <= b - a <= 8
            fa, fb = (float(x) for x in match.groups())
            timing_ok = timing_ok and math.isfinite(fa) and math.isfinite(fb) and 0 <= fb - fa <= 8
        return (v.binding == self.expected() and timing_ok and
                v.freshness == self.epoch + ":fresh:" + self.expected().phase.name and
                all(x is Verdict.PASS for x in (v.native_state_owner_boot_esd,
                    v.retained_origin_interval, v.nonce_collision_free)))

    def ack_ok(self, v, start):
        prefix = self.epoch + (":start" if start else ":end")
        base = (v.epoch == self.epoch and v.boot == self.boot and v.camera == "SYNTHETIC:camera"
                and v.manifest == self.manifest and v.stage == "SYNTHETIC:SHAM15_HOLD"
                and v.nonce == prefix + ":nonce" and v.sequence == (1 if start else 2)
                and v.session == "SYNTHETIC:recording"
                and v.requested_profile == v.observed_profile == "SYNTHETIC:full-profile"
                and v.metadata == prefix + ":metadata"
                and v.settled is Verdict.PASS and v.continuity is Verdict.PASS)
        if start:
            return base and v.start_reference == "SYNTHETIC:none"
        a = self.start_ack
        return (base and a is not None and v.start_reference == a.metadata and
                v.session == a.session and v.frame - a.frame >= 120 and
                v.timestamp > a.timestamp)

class Ledger:
    """Synthetic authoritative store shared by public cursors, never cleared by cleanup.
    In-memory only: actual durability and interprocess atomicity are unimplemented.
    """
    def __init__(self, authoritative=Verdict.PASS):
        enum(authoritative, Verdict)
        self._record = _LedgerSnapshot(authoritative=authoritative)

    @property
    def snapshot(self):
        return self._record

    def _consume(self, epoch):
        require(self._record.authoritative is Verdict.PASS and
                epoch not in self._record.spent, "spent/missing/ambiguous authoritative ledger")
        self._record = _LedgerSnapshot(self._record.spent | {epoch})

class Model:
    """Public one-shot cursor. Rejected post-arm events cannot be caught and repaired.
    Private reducer snapshots are for explicit independent test worlds, not live cursors.
    No execution or IO occurs. A cursor never adopts externally supplied state.
    """
    def __init__(self, epoch, protocol, ledger):
        require(type(ledger) is Ledger, "shared synthetic authoritative Ledger required")
        self._ledger = ledger
        self._snapshot = _Snapshot(epoch, protocol, ledger.snapshot)

    @property
    def snapshot(self):
        return self._snapshot

    def step(self, event):
        previous = self._snapshot
        try:
            # Check the latest authoritative record, not a retained pre-cleanup snapshot.
            if type(event) is Event and event.kind is EventKind.STAGE:
                previous = replace(previous, ledger=self._ledger.snapshot)
            updated = previous._step(event)
            if type(event) is Event and event.kind is EventKind.STAGE:
                self._ledger._consume(previous.epoch)
                updated = replace(updated, ledger=self._ledger.snapshot)
            self._snapshot = updated
            return self
        except (Refused, TypeError, ValueError):
            # A failed input after any modeled invocation/arm cannot be repaired by
            # catching an exception and submitting a different phase or SUCCESS.
            # Preflight NEW/STAGED/BASELINE_READY/CLOCK_GRANTED has no child side effect.
            active = previous.short is Watchdog.ARMED or previous.state in (
                State.RESERVED, State.DISPATCHED, State.PRODUCED, State.SEALED,
                State.QUIET, State.HOLD_START, State.HOLD_WAIT, State.RETURN_PROOF)
            camera_only = type(event) is Event and event.kind in (
                EventKind.CAMERA_START, EventKind.CAMERA_END, EventKind.RECONNECT)
            if camera_only and previous.state is not State.NEW:
                terminal = previous.state in (State.RUN_COMPLETE, State.EXPLORATORY_STOCK_SAMPLE,
                                              State.DEGRADED_COMPLETE)
                self._snapshot = replace(previous, optics_invalid=True,
                    state=State.DEGRADED_COMPLETE if terminal else previous.state,
                    classification=Classification.RECOVERY_DEGRADED_PROTOCOL if terminal
                    else previous.classification)
            elif active:
                self._snapshot = previous.failed()
            raise
