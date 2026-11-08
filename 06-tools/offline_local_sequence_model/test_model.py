"""Synthetic only. unittest checks remain active under python -O."""
import unittest
from dataclasses import replace, FrozenInstanceError
from model import *
from model import _Snapshot as Model, _LedgerSnapshot as Ledger
from model import Model as Session, Ledger as SpentLedger

PASS = Verdict.PASS
FAIL = Verdict.FAIL
ALL = Gates(PASS, PASS, PASS, PASS, PASS)
COST = KnownCost(1, "SYNTHETIC:qualified-for-model-only")
BUDGET = Budget(COST, KnownCost(10, "SYNTHETIC:disjoint-suffix"), COST, COST)
UNBOUNDED = Budget(UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN)

def event(k, v=None):
    return Event(k, v)

def guard(m):
    return Guard(m.expected(), b"GUARD_TIMING 1.0 9.0\n", PASS, PASS, PASS,
                 m.epoch + ":fresh:" + m.expected().phase.name)

def ack(m, start=True):
    p = m.epoch + (":start" if start else ":end")
    return Ack(m.epoch, m.boot, "SYNTHETIC:camera", m.manifest,
               "SYNTHETIC:SHAM15_HOLD", p + ":nonce", 1 if start else 2,
               "SYNTHETIC:recording", "SYNTHETIC:full-profile", "SYNTHETIC:full-profile",
               10 if start else 130, 100 if start else 105, p + ":metadata",
               "SYNTHETIC:none" if start else m.start_ack.metadata, PASS, PASS)

def q(m):
    return Quiet(m.epoch + ":quiet:" + str(m.phase_index), 2, PASS)

def cleanup(m, o):
    return Cleanup(o, PASS, PASS, m.epoch + ":cleanup:" + o.name, m.boot, m.incident)

def recovery(m):
    return Recovery(m.target, m.boot, "SYNTHETIC:boot" + str(len(m.seen_boots)),
                    PASS, PASS, m.epoch, m.incident, m.epoch + ":recovery:" + str(m.incident))

def initial(protocol=Protocol.NORMAL_RESERVED):
    m = Model("SYNTHETIC:epoch", protocol, Ledger())
    return m

def ready(protocol=Protocol.NORMAL_RESERVED):
    m = initial(protocol)
    m = m._step(event(EventKind.STAGE, Prerequisite(m.epoch + ":stage", PASS)))
    m = m._step(event(EventKind.BASELINE, Prerequisite(m.epoch + ":baseline", PASS)))
    b = BUDGET if protocol is Protocol.NORMAL_RESERVED else UNBOUNDED
    m = m._step(event(EventKind.BOUND_GRANT, Grant(0, 0, 0, b, PASS)))
    return m._step(event(EventKind.ARM, Prerequisite(m.epoch + ":arm", PASS)))

def child(m, keep=None):
    b = BUDGET if m.protocol is Protocol.NORMAL_RESERVED else UNBOUNDED
    events = [
        event(EventKind.RESERVE, b),
        event(EventKind.DISPATCH, guard(m)),
        event(EventKind.PRODUCER_RESULT, Producer(0, b"")),
        event(EventKind.SEALED_EVIDENCE, Receipt(m.expected(), Producer(0, b""), ALL)),
        event(EventKind.GATE_VERDICT, ALL),
    ]
    if keep is not None:
        keep.append(m)
    for e in events:
        m = m._step(e)
        if keep is not None:
            keep.append(m)
    return m

def at_phase(index, protocol=Protocol.NORMAL_RESERVED):
    m = ready(protocol)
    while m.phase_index < index:
        m = child(m)
        if m.state is State.QUIET:
            m = m._step(event(EventKind.QUIET, q(m)))
        if m.state is State.HOLD_START:
            m = m._step(event(EventKind.CAMERA_START, ack(m)))
            m = m._step(event(EventKind.QUIET, q(m)))
            m = m._step(event(EventKind.CLOCK_TICK, Tick(4.5, 4.5)))
            m = m._step(event(EventKind.CAMERA_END, ack(m, False)))
    return m

def local(protocol=Protocol.NORMAL_RESERVED):
    m = at_phase(4, protocol)
    m = child(m)
    return m._step(event(EventKind.SHORT_DISARM, PASS))

def restored(m):
    for o in Obligation:
        if o in m.pending:
            m = m._step(event(EventKind.VERIFIED_CLEANUP, cleanup(m, o)))
    return m

def finish(m):
    if not m.connected:
        m=m._step(event(EventKind.RECONNECT,Prerequisite(m.epoch+":camera-reidentified",PASS)))
    m = m._step(event(EventKind.FINAL_CAPTURE, PASS))
    m = m._step(event(EventKind.AUDIT_ACCEPT))
    m = restored(m)
    return m._step(event(EventKind.OFFLINE_OPTICAL_VERDICT, PASS))

class ModelTests(unittest.TestCase):
    def test_policy_terminals_and_exact_five(self):
        self.assertEqual(len(ORDER), 5)
        for p, s in ((Protocol.NORMAL_RESERVED, State.RUN_COMPLETE),
                     (Protocol.EXPLORATORY_FACTORY15, State.EXPLORATORY_STOCK_SAMPLE)):
            with self.subTest(policy=p.name):
                m = finish(local(p))
                self.assertEqual(m.state, s)
                self.assertEqual(len(m.consumed), 5)
                self.assertEqual(len(set(m.consumed)), 5)
                self.assertEqual(len(m.receipts), 5)
                self.assertEqual(m.receipts[1].binding.payload, (21, 0, 0))
                self.assertEqual(m.receipts[4].binding.payload, (0, 0, 96))
                self.assertFalse(m.pending)
                self.assertEqual(m.overall, Watchdog.DISARMED)
                self.assertEqual(m.short, Watchdog.DISARMED)

    def test_each_child_every_fault_position(self):
        # 5 phases x 5 checkpoints x 4 faults. No retry or reconstructed success.
        for i in range(5):
            trace = []
            child(at_phase(i), trace)
            for before in trace[:5]:
                for fault in (EventKind.CRASH, EventKind.RESTART, EventKind.TIMEOUT,
                              EventKind.AUDIT_REJECT):
                    with self.subTest(phase=ORDER[i].name, state=before.state.name, fault=fault.name):
                        n = before._step(event(fault))
                        self.assertTrue(n.target_uncertain)
                        self.assertEqual(n.classification, Classification.RECOVERY_DEGRADED_PROTOCOL)
                        with self.assertRaises(Refused):
                            n._step(event(EventKind.RESERVE, BUDGET))
                        with self.assertRaises(Refused):
                            n._step(event(EventKind.GATE_VERDICT, ALL))

    def test_actual_result_not_success_marker(self):
        for i in range(5):
            m = at_phase(i)
            m = m._step(event(EventKind.RESERVE, BUDGET))._step(event(EventKind.DISPATCH, guard(m)))
            for result in (UNKNOWN, Producer(1, b""), Producer(0, b"warning")):
                with self.subTest(phase=i, result=result):
                    n = m._step(event(EventKind.PRODUCER_RESULT, result))
                    self.assertTrue(n.target_uncertain)
                    for e in (event(EventKind.PRODUCER_RESULT, Producer(0, b"")),
                              event(EventKind.SEALED_EVIDENCE,
                                    Receipt(m.expected(), Producer(0, b""), ALL))):
                        with self.assertRaises(Refused):
                            n._step(e)
            with self.assertRaises(Refused):
                m._step(event(EventKind.PRODUCER_RESULT, "SUCCESS"))

    def test_binding_swaps_and_sealed_gates(self):
        for i in range(5):
            m = at_phase(i)
            m = m._step(event(EventKind.RESERVE, BUDGET))._step(event(EventKind.DISPATCH, guard(m)))
            m = m._step(event(EventKind.PRODUCER_RESULT, Producer(0, b"")))
            b = m.expected()
            changes = {x: "SYNTHETIC:wrong" for x in ("epoch", "boot", "nonce", "manifest",
                       "source", "plan", "origin", "seal")}
            changes.update(phase=ORDER[(i+1) % 5], payload=(14,),
                           artifacts=("SYNTHETIC:a", "SYNTHETIC:b", "SYNTHETIC:c"))
            for key, value in changes.items():
                with self.subTest(phase=i, swap=key):
                    n = m._step(event(EventKind.SEALED_EVIDENCE,
                        Receipt(replace(b, **{key:value}), Producer(0, b""), ALL)))
                    self.assertTrue(n.target_uncertain)
            n = m._step(event(EventKind.SEALED_EVIDENCE, Receipt(b, Producer(0, b""), ALL)))
            with self.assertRaises(FrozenInstanceError):
                n.receipt.producer = UNKNOWN
            with self.assertRaises(Refused):
                n._step(event(EventKind.SEALED_EVIDENCE, n.receipt))
            for gate in ("E", "C", "S", "W" if i in (0,2) else "I"):
                for verdict in (FAIL, Verdict.UNKNOWN):
                    gates = replace(ALL, **{gate:verdict})
                    bad = m._step(event(EventKind.SEALED_EVIDENCE, Receipt(b, Producer(0,b""), gates)))
                    self.assertTrue(bad._step(event(EventKind.GATE_VERDICT,gates)).target_uncertain)
                    self.assertTrue(bad._step(event(EventKind.GATE_VERDICT,ALL)).target_uncertain)

    def test_guard_exact_origin_freshness_and_timing(self):
        for i in range(5):
            m = at_phase(i)
            m = m._step(event(EventKind.RESERVE, BUDGET))
            g = guard(m)
            for timing, good in ((b"GUARD_TIMING 0.0 0.0\n", True),
                (b"GUARD_TIMING 0.0 8.0\n", True), (b"GUARD_TIMING 0.0 8.0001\n", False),
                (b"GUARD_TIMING 9.0 1.0\n", False), (b"GUARD_TIMING nan 1\n", False),
                (b"GUARD_TIMING 1 2", False), (b"GUARD_TIMING 1e0 2\n", False),
                (b"GUARD_TIMING 1 2\nSUCCESS\n", False)):
                with self.subTest(phase=i, timing=timing):
                    n = m._step(event(EventKind.DISPATCH,replace(g,timing=timing)))
                    self.assertEqual(n.state is State.DISPATCHED, good)
            huge=b"100000000000000000000000000000000000000000000000000"
            timing=b"GUARD_TIMING "+huge+b".0 "+huge[:-1]+b"9.0\n"
            self.assertTrue(m._step(event(EventKind.DISPATCH,replace(g,timing=timing))).target_uncertain)
            rounded=b"GUARD_TIMING 536870904.00000007 536870912.00000007\n"
            self.assertTrue(m._step(event(EventKind.DISPATCH,replace(g,timing=rounded))).target_uncertain)
            for key in ("native_state_owner_boot_esd", "retained_origin_interval", "nonce_collision_free"):
                self.assertTrue(m._step(event(EventKind.DISPATCH,replace(g,**{key:FAIL}))).target_uncertain)
            self.assertTrue(m._step(event(EventKind.DISPATCH, replace(g,
                freshness="SYNTHETIC:stale"))).target_uncertain)
            self.assertTrue(m._step(event(EventKind.DISPATCH, replace(g,
                binding=replace(g.binding,origin="SYNTHETIC:later-quiet")))).target_uncertain)

    def test_deadline_boundaries_unknown_and_no_renewal(self):
        m = initial()._step(event(EventKind.STAGE, Prerequisite("SYNTHETIC:epoch:stage",PASS)))
        m = m._step(event(EventKind.BASELINE, Prerequisite(m.epoch+":baseline",PASS)))
        for b in (UNBOUNDED, Budget(KnownCost(30,"SYNTHETIC:nominal-timeout"), COST, COST,
                                  KnownCost(5,"SYNTHETIC:uncovered")),
                  Budget(KnownCost(38,"SYNTHETIC:nominal-timeout"), COST,COST,COST)):
            with self.assertRaises(Refused):
                m._step(event(EventKind.BOUND_GRANT,Grant(0,0,0,b,PASS)))
        for field in ("current","downstream","jitter","uncovered"):
            with self.assertRaises(Refused):
                m._step(event(EventKind.BOUND_GRANT,Grant(0,0,0,replace(BUDGET,**{field:UNKNOWN}),PASS)))
        n=m._step(event(EventKind.CLOCK_TICK,Tick(5,10)))
        n=n._step(event(EventKind.BOUND_GRANT,Grant(8,5,0.2,BUDGET,PASS)))
        self.assertEqual(n.expiry,39)  # floor(8+37-5-.2), not target-now+37
        with self.assertRaises(Refused):
            n._step(event(EventKind.BOUND_GRANT,Grant(8,5,0,BUDGET,PASS)))
        m=ready()
        for t in (37,45,60,600):
            n=m._step(event(EventKind.CLOCK_TICK,Tick(t,t)))
            self.assertTrue(n.target_uncertain)
        for cost, allowed in ((36.999,True),(37,False),(37.001,False)):
            b=Budget(KnownCost(cost,"SYNTHETIC:boundary"),KnownCost(0,"SYNTHETIC:z"),KnownCost(0,"SYNTHETIC:z"),KnownCost(0,"SYNTHETIC:z"))
            if allowed:
                self.assertEqual(m._step(event(EventKind.RESERVE,b)).state,State.RESERVED)
            else:
                with self.assertRaises(Refused):
                    m._step(event(EventKind.RESERVE,b))
        n=m._step(event(EventKind.RESERVE,BUDGET))
        self.assertEqual(n._step(event(EventKind.CLOCK_TICK,Tick(.999,.999))).state,State.RESERVED)
        self.assertTrue(n._step(event(EventKind.CLOCK_TICK,Tick(1,1))).target_uncertain)
        n=m._step(event(EventKind.CLOCK_TICK,Tick(2,3)))
        self.assertTrue(n._step(event(EventKind.CLOCK_TICK,Tick(1,3))).target_uncertain)
        self.assertTrue(n._step(event(EventKind.CLOCK_TICK,Tick(2,2))).target_uncertain)

    def test_ack_binding_hold_and_no_replacement(self):
        start=child(at_phase(1))
        for key in ("epoch","boot","camera","manifest","stage","nonce","session",
                    "requested_profile","observed_profile","metadata","start_reference"):
            with self.subTest(field=key):
                n=start._step(event(EventKind.CAMERA_START,replace(ack(start),**{key:"SYNTHETIC:wrong"})))
                self.assertTrue(n.optics_invalid)
                self.assertFalse(n.target_uncertain)
                with self.assertRaises(Refused):
                    n._step(event(EventKind.CAMERA_START,ack(start)))
        m=start._step(event(EventKind.CAMERA_START,ack(start)))
        with self.assertRaises(Refused):
            m._step(event(EventKind.CAMERA_START,ack(start)))
        m=m._step(event(EventKind.QUIET,q(m)))
        for t, good in ((4.499,False),(4.5,True),(4.501,True)):
            n=m._step(event(EventKind.CLOCK_TICK,Tick(t,t)))
            n=n._step(event(EventKind.CAMERA_END,ack(n,False)))
            self.assertEqual(n.state is State.READY,good)
        n=m._step(event(EventKind.CLOCK_TICK,Tick(4.5,4.5)))
        for key,value in (("frame",129),("timestamp",100),("sequence",1),
                          ("session","SYNTHETIC:replacement"),("continuity",FAIL),
                          ("settled",Verdict.UNKNOWN),("start_reference","SYNTHETIC:old")):
            bad=n._step(event(EventKind.CAMERA_END,replace(ack(n,False),**{key:value})))
            self.assertTrue(bad.optics_invalid)
            self.assertFalse(bad.target_uncertain)
        delayed=start._step(event(EventKind.CLOCK_TICK,Tick(10,10)))
        delayed=delayed._step(event(EventKind.CAMERA_START,ack(delayed)))
        self.assertEqual(delayed.ack_received,10)
        self.assertEqual(delayed.expiry,37)

    def test_safe_return_distinct_and_exploratory_forbidden(self):
        for p in Protocol:
            m=child(at_phase(1,p))
            m=m._step(event(EventKind.QUIET,q(m)))
            m=m._step(event(EventKind.DISCONNECT))
            if p is Protocol.EXPLORATORY_FACTORY15:
                with self.assertRaises(Refused):
                    m._step(event(EventKind.SAFE_RETURN,guard(m)))
                continue
            for field in ("current","downstream","jitter","uncovered"):
                with self.assertRaises(Refused):
                    replace(m,budget=replace(BUDGET,**{field:UNKNOWN}))._step(
                        event(EventKind.SAFE_RETURN,guard(m)))
            m=m._step(event(EventKind.SAFE_RETURN,guard(m)))
            self.assertTrue(m.optics_invalid)
            self.assertEqual(m.classification,Classification.RECOVERY_DEGRADED_PROTOCOL)
            while m.phase_index<5:
                m=child(m)
                if m.state is State.QUIET:
                    m=m._step(event(EventKind.QUIET,q(m)))
            m=m._step(event(EventKind.SHORT_DISARM,PASS))
            m=finish(m)
            self.assertEqual(m.state,State.DEGRADED_COMPLETE)

    def test_cleanup_watchdogs_late_audit_recovery(self):
        m=local()
        self.assertTrue(m.local_proof)
        self.assertEqual(m.short,Watchdog.DISARMED)
        self.assertEqual(m.overall,Watchdog.ARMED)
        self.assertEqual(m.pending,frozenset(Obligation))
        with self.assertRaises(Refused):
            m._step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS))
        bad=m._step(event(EventKind.AUDIT_REJECT))
        with self.assertRaises(Refused):
            bad._step(event(EventKind.VERIFIED_CLEANUP,cleanup(bad,Obligation.TARGET_RESTORE)))
        for changes in (dict(target="SYNTHETIC:other"),dict(new_boot=bad.boot),
                        dict(no_child_alive=Verdict.UNKNOWN)):
            with self.assertRaises(Refused):
                bad._step(event(EventKind.VERIFIED_CHANGED_BOOT,replace(recovery(bad),**changes)))
        bad=bad._step(event(EventKind.VERIFIED_CHANGED_BOOT,recovery(bad)))
        self.assertTrue(bad.target_uncertain)
        bad=restored(bad)
        self.assertEqual(bad._step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS)).state,State.DEGRADED_COMPLETE)
        m=m._step(event(EventKind.FINAL_CAPTURE,FAIL))._step(event(EventKind.AUDIT_ACCEPT))
        for o in Obligation:
            receipt=cleanup(m,o)
            self.assertEqual(m._step(event(EventKind.VERIFIED_CLEANUP,replace(receipt,verdict=Verdict.UNKNOWN))),m)
        with self.assertRaises(Refused):
            m._step(event(EventKind.VERIFIED_CLEANUP,cleanup(m,Obligation.OWNER_RELEASE)))
        m=restored(m)
        self.assertEqual(m._step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS)).state,State.DEGRADED_COMPLETE)
        completed=finish(local())
        bad=completed._step(event(EventKind.AUDIT_REJECT))
        self.assertTrue(bad.target_uncertain)
        self.assertEqual(bad.pending,frozenset(Obligation))
        expiry=local()._step(event(EventKind.CLOCK_TICK,Tick(600,600)))
        self.assertTrue(expiry.target_uncertain)
        self.assertEqual(expiry.overall,Watchdog.EXPIRED)

    def test_crash_proof_disarm_and_ledger_persistence(self):
        proof=child(at_phase(4))
        for m in (proof,local(),finish(local())):
            for k in (EventKind.CRASH,EventKind.RESTART):
                n=m._step(event(k))
                self.assertTrue(n.target_uncertain)
                self.assertEqual(n.ledger,m.ledger)
                with self.assertRaises(Refused):
                    n._step(event(EventKind.SHORT_DISARM,PASS))
        self.assertTrue(proof._step(event(EventKind.SHORT_DISARM,Verdict.UNKNOWN)).target_uncertain)
        m=finish(local())
        for ledger in (m.ledger,Ledger(authoritative=Verdict.UNKNOWN),Ledger(authoritative=FAIL)):
            n=Model(m.epoch,m.protocol,ledger)
            with self.assertRaises(Refused):
                n._step(event(EventKind.STAGE,Prerequisite(n.epoch+":stage",PASS)))

    def test_typed_numeric_schema(self):
        for bad in (True,False,float("nan"),float("inf"),-1,"1",None,10**1000):
            for ctor in (lambda: Tick(bad,0),lambda: KnownCost(bad,"SYNTHETIC:q"),
                         lambda: Quiet("SYNTHETIC:q",bad,PASS)):
                with self.subTest(bad=repr(bad)):
                    with self.assertRaises(Refused):
                        ctor()
        with self.assertRaises(TypeError):
            Event(EventKind.CRASH,command="fake")
        with self.assertRaises(Refused):
            Event("SHAM15_WRITE")
        with self.assertRaises(Refused):
            Producer(True,b"")
        with self.assertRaises(Refused):
            replace(ready().expected(),payload=(True,))
        with self.assertRaises(Refused):
            initial()._step(event(EventKind.STAGE,True))
        for changes in (dict(host=True),dict(device=float("nan")),dict(phase_index=True),
                        dict(pending=set()),dict(target_uncertain=1),dict(state="READY")):
            with self.assertRaises(Refused):
                replace(initial(),**changes)

    def test_all_state_event_pairs_are_total_and_invariant_preserving(self):
        # Named matrix is finite transition coverage, NOT universal correctness.
        states={}
        def save(m):
            states.setdefault(m.state,m)
            return m
        m=save(initial())
        m=save(m._step(event(EventKind.STAGE,Prerequisite(m.epoch+":stage",PASS))))
        m=save(m._step(event(EventKind.BASELINE,Prerequisite(m.epoch+":baseline",PASS))))
        m=save(m._step(event(EventKind.BOUND_GRANT,Grant(0,0,0,BUDGET,PASS))))
        m=save(m._step(event(EventKind.ARM,Prerequisite(m.epoch+":arm",PASS))))
        for i in range(5):
            trace=[]
            m=child(m,trace)
            for n in trace: save(n)
            if m.state is State.QUIET:
                m=save(m._step(event(EventKind.QUIET,q(m))))
            if m.state is State.HOLD_START:
                m=save(m._step(event(EventKind.CAMERA_START,ack(m))))
                m=m._step(event(EventKind.QUIET,q(m)))
                m=m._step(event(EventKind.CLOCK_TICK,Tick(4.5,4.5)))
                m=save(m._step(event(EventKind.CAMERA_END,ack(m,False))))
        m=save(m._step(event(EventKind.SHORT_DISARM,PASS)))
        m=save(m._step(event(EventKind.FINAL_CAPTURE,PASS)))
        m=save(m._step(event(EventKind.AUDIT_ACCEPT)))
        m=save(restored(m))
        save(m._step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS)))
        save(finish(local(Protocol.EXPLORATORY_FACTORY15)))
        failed=save(ready()._step(event(EventKind.TIMEOUT)))
        save(ready()._step(event(EventKind.CRASH)))
        save(restored(failed._step(event(EventKind.VERIFIED_CHANGED_BOOT,recovery(failed))))._step(
            event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS)))
        self.assertEqual(set(states),set(State))
        local_edges = {
            State.NEW:{EventKind.STAGE}, State.STAGED:{EventKind.BASELINE},
            State.BASELINE_READY:{EventKind.BOUND_GRANT}, State.CLOCK_GRANTED:{EventKind.ARM},
            State.READY:{EventKind.RESERVE}, State.RESERVED:{EventKind.DISPATCH},
            State.DISPATCHED:{EventKind.PRODUCER_RESULT}, State.PRODUCED:{EventKind.SEALED_EVIDENCE},
            State.SEALED:{EventKind.GATE_VERDICT}, State.QUIET:{EventKind.QUIET},
            State.HOLD_START:{EventKind.CAMERA_START,EventKind.QUIET},
            State.HOLD_WAIT:{EventKind.CAMERA_END,EventKind.QUIET},
            State.RETURN_PROOF:{EventKind.SHORT_DISARM}, State.LOCAL_RETURNED:{EventKind.FINAL_CAPTURE},
            State.AUDIT:{EventKind.AUDIT_ACCEPT}, State.RESTORE:{EventKind.VERIFIED_CLEANUP},
            State.OFFLINE:{EventKind.OFFLINE_OPTICAL_VERDICT},
            State.UNCERTAIN:{EventKind.VERIFIED_CHANGED_BOOT},
            State.CRASHED:{EventKind.VERIFIED_CHANGED_BOOT}}
        cases=0
        for state,m in states.items():
            fixture=at_phase(min(m.phase_index,4))
            values={
                EventKind.STAGE:Prerequisite(m.epoch+":stage",PASS),
                EventKind.BASELINE:Prerequisite(m.epoch+":baseline",PASS),
                EventKind.BOUND_GRANT:Grant(0,m.host,0,BUDGET,PASS),
                EventKind.ARM:Prerequisite(m.epoch+":arm",PASS),
                EventKind.RESERVE:BUDGET,EventKind.DISPATCH:guard(fixture),
                EventKind.PRODUCER_RESULT:Producer(0,b""),
                EventKind.SEALED_EVIDENCE:Receipt(fixture.expected(),Producer(0,b""),ALL),
                EventKind.GATE_VERDICT:ALL,EventKind.QUIET:q(m),
                EventKind.CAMERA_START:ack(fixture),
                EventKind.CAMERA_END:ack(replace(fixture,start_ack=ack(fixture)),False),
                EventKind.SAFE_RETURN:guard(fixture),EventKind.CLOCK_TICK:Tick(m.host,m.device),
                EventKind.RECONNECT:Prerequisite(m.epoch+":camera-reidentified",PASS),
                EventKind.SHORT_DISARM:PASS,EventKind.FINAL_CAPTURE:PASS,
                EventKind.VERIFIED_CHANGED_BOOT:recovery(m),
                EventKind.VERIFIED_CLEANUP:cleanup(m,Obligation.TARGET_RESTORE),
                EventKind.OFFLINE_OPTICAL_VERDICT:PASS}
            for kind in EventKind:
                with self.subTest(state=state.name,event=kind.name):
                    cases+=1
                    allowed=local_edges.get(state,set()) | {EventKind.CLOCK_TICK}
                    if state is not State.NEW:
                        allowed=allowed | {EventKind.CRASH,EventKind.RESTART,EventKind.AUDIT_REJECT}
                        if state not in (State.RUN_COMPLETE,State.EXPLORATORY_STOCK_SAMPLE,State.DEGRADED_COMPLETE):
                            allowed=allowed | {EventKind.TIMEOUT,EventKind.DISCONNECT}
                    if kind not in allowed:
                        with self.assertRaises(Refused):
                            m._step(event(kind,values.get(kind)))
                        continue
                    n=m._step(event(kind,values.get(kind)))
                    self.assertTrue(not m.target_uncertain or n.target_uncertain)
                    self.assertTrue(not m.optics_invalid or n.optics_invalid)
                    self.assertTrue(m.ledger.spent <= n.ledger.spent)
                    self.assertEqual(len(n.consumed),len(set(n.consumed)))
                    if m.expiry is not None: self.assertEqual(m.expiry,n.expiry)
                    if n.state in (State.RUN_COMPLETE,State.EXPLORATORY_STOCK_SAMPLE):
                        self.assertFalse(n.pending)
                        self.assertFalse(n.target_uncertain)
                        self.assertFalse(n.optics_invalid)
        self.assertEqual(cases,len(State)*len(EventKind))


    def test_public_cursor_caught_errors_and_shared_ledger(self):
        from unittest.mock import patch
        # Record one complete reducer path, then exercise only public cursors.
        events=[]
        original=Model._step
        def record(snapshot, e):
            events.append(e)
            return original(snapshot,e)
        with patch.object(Model,"_step",record):
            finish(local())
        session=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,SpentLedger())
        self.assertFalse(hasattr(session,"_step"))
        self.assertFalse(hasattr(session,"admit"))
        for e in events:
            session.step(e)
        self.assertEqual(session.snapshot.state,State.RUN_COMPLETE)
        # Capture-and-continue at every consumed invocation checkpoint.
        checkpoints=0
        for end in range(len(events)):
            prefix=events[:end+1]
            probe=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,SpentLedger())
            for e in prefix: probe.step(e)
            if probe.snapshot.state not in (State.RESERVED,State.DISPATCHED,State.PRODUCED,State.SEALED):
                continue
            checkpoints+=1
            for bad in ({"SUCCESS":True},event(EventKind.SEALED_EVIDENCE,"SUCCESS"),
                        event(EventKind.RESERVE,BUDGET)):
                with self.subTest(public_phase=probe.snapshot.phase_index,checkpoint=probe.snapshot.state.name,bad=repr(bad)):
                    cursor=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,SpentLedger())
                    for e in prefix: cursor.step(e)
                    with self.assertRaises(Refused): cursor.step(bad)
                    self.assertTrue(cursor.snapshot.target_uncertain)
                    for retry in (event(EventKind.RESERVE,BUDGET),
                                  event(EventKind.PRODUCER_RESULT,Producer(0,b""))):
                        with self.assertRaises(Refused): cursor.step(retry)
                        self.assertTrue(cursor.snapshot.target_uncertain)
        self.assertEqual(checkpoints,20)
        store=SpentLedger()
        cursor=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,store)
        for e in events: cursor.step(e)
        duplicate=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,store)
        with self.assertRaises(Refused): duplicate.step(events[0])
        self.assertIn("SYNTHETIC:epoch",store.snapshot.spent)
        # A cursor constructed BEFORE consumption also sees the latest shared ledger.
        store=SpentLedger()
        a=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,store)
        b=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,store)
        a.step(events[0])
        with self.assertRaises(Refused): b.step(events[0])
        # Typed malformed ACK stays optics-only; it cannot be repaired into normal.
        cursor=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,SpentLedger())
        for e in events:
            if e.kind is EventKind.CAMERA_START: break
            cursor.step(e)
        with self.assertRaises(Refused): cursor.step(event(EventKind.CAMERA_START,False))
        self.assertTrue(cursor.snapshot.optics_invalid)
        self.assertFalse(cursor.snapshot.target_uncertain)
        with self.assertRaises(Refused): cursor.step(e)
        self.assertFalse(cursor.snapshot.target_uncertain)


    def test_review_late_camera_terminal_and_quiet_order(self):
        from unittest.mock import patch
        def path(protocol):
            events=[]
            original=Model._step
            def record(snapshot,e):
                events.append(e)
                return original(snapshot,e)
            with patch.object(Model,"_step",record): finish(local(protocol))
            return events
        for protocol in Protocol:
            events=path(protocol)
            for kind in (EventKind.CAMERA_START,EventKind.CAMERA_END,EventKind.RECONNECT):
                for malformed in (False, None, "SUCCESS"):
                    with self.subTest(protocol=protocol.name,late=kind.name,payload=repr(malformed)):
                        cursor=Session("SYNTHETIC:epoch",protocol,SpentLedger())
                        for e in events: cursor.step(e)
                        historical=cursor.snapshot.receipts
                        with self.assertRaises(Refused): cursor.step(event(kind,malformed))
                        self.assertEqual(cursor.snapshot.state,State.DEGRADED_COMPLETE)
                        self.assertTrue(cursor.snapshot.optics_invalid)
                        self.assertFalse(cursor.snapshot.target_uncertain)
                        self.assertFalse(cursor.snapshot.pending)
                        self.assertEqual(cursor.snapshot.receipts,historical)
                        with self.assertRaises(Refused):
                            cursor.step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS))
                        self.assertEqual(cursor.snapshot.state,State.DEGRADED_COMPLETE)
            start_index=next(i for i,e in enumerate(events) if e.kind is EventKind.CAMERA_START)
            for add_fresh_quiet in (False,True):
                with self.subTest(protocol=protocol.name,fresh_in_hold_quiet=add_fresh_quiet):
                    cursor=Session("SYNTHETIC:epoch",protocol,SpentLedger())
                    for e in events[:start_index]: cursor.step(e)
                    cursor.step(event(EventKind.QUIET,q(cursor.snapshot)))
                    self.assertTrue(cursor.snapshot.hold_quiet)
                    cursor.step(events[start_index])
                    self.assertFalse(cursor.snapshot.hold_quiet)
                    # The next original event is the in-hold quiet.
                    for e in events[start_index+1:]:
                        if e.kind is EventKind.QUIET and cursor.snapshot.state is State.HOLD_WAIT:
                            if not add_fresh_quiet: continue
                        if e.kind is EventKind.CAMERA_END and not add_fresh_quiet:
                            cursor.step(e)
                            self.assertTrue(cursor.snapshot.optics_invalid)
                            self.assertFalse(cursor.snapshot.target_uncertain)
                            with self.assertRaises(Refused):
                                cursor.step(event(EventKind.RESERVE,BUDGET))
                            break
                        cursor.step(e)
                    if add_fresh_quiet:
                        self.assertEqual(cursor.snapshot.state,State.RUN_COMPLETE if protocol is
                            Protocol.NORMAL_RESERVED else State.EXPLORATORY_STOCK_SAMPLE)

    def test_review_recovery_and_all_cleanup_generation_replays(self):
        from unittest.mock import patch
        events=[]
        original=Model._step
        def record(snapshot,e):
            events.append(e)
            return original(snapshot,e)
        with patch.object(Model,"_step",record): local()
        cursor=Session("SYNTHETIC:epoch",Protocol.NORMAL_RESERVED,SpentLedger())
        for e in events: cursor.step(e)
        history=cursor.snapshot.receipts
        cursor.step(event(EventKind.TIMEOUT))
        first=recovery(cursor.snapshot)
        cursor.step(event(EventKind.VERIFIED_CHANGED_BOOT,first))
        self.assertEqual(cursor.snapshot.boot,first.new_boot)
        self.assertIn(first.proof_id,cursor.snapshot.consumed_recovery)
        old_cleanup=[]
        for o in Obligation:
            old=cleanup(cursor.snapshot,o)
            old_cleanup.append(old)
            cursor.step(event(EventKind.VERIFIED_CLEANUP,old))
        cursor.step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS))
        cursor.step(event(EventKind.AUDIT_REJECT))
        incident=cursor.snapshot.incident
        fresh=recovery(cursor.snapshot)
        bad_proofs=(first,replace(fresh,incident=first.incident),
                    replace(fresh,old_boot=first.old_boot),
                    replace(fresh,proof_id=first.proof_id),
                    replace(fresh,new_boot=first.old_boot),
                    replace(fresh,epoch="SYNTHETIC:other-epoch"))
        for index,bad in enumerate(bad_proofs):
            with self.subTest(recovery_replay=index):
                with self.assertRaises(Refused):
                    cursor.step(event(EventKind.VERIFIED_CHANGED_BOOT,bad))
                self.assertFalse(cursor.snapshot.recovered)
                self.assertIn(Obligation.TARGET_RESTORE,cursor.snapshot.pending)
                self.assertEqual(cursor.snapshot.incident,incident)
        cursor.step(event(EventKind.VERIFIED_CHANGED_BOOT,fresh))
        self.assertEqual(cursor.snapshot.boot,fresh.new_boot)
        self.assertTrue(cursor.snapshot.target_uncertain)
        self.assertEqual(cursor.snapshot.receipts,history)
        self.assertTrue(all(r.binding.boot=="SYNTHETIC:boot0" for r in history))
        for old in old_cleanup:
            for stale in (old,replace(old,boot=cursor.snapshot.boot),
                          replace(old,incident=cursor.snapshot.incident)):
                with self.subTest(cleanup=old.obligation.name,stale_boot=stale.boot,incident=stale.incident):
                    before=cursor.snapshot
                    with self.assertRaises(Refused):
                        cursor.step(event(EventKind.VERIFIED_CLEANUP,stale))
                    self.assertEqual(cursor.snapshot,before)
            current=cleanup(cursor.snapshot,old.obligation)
            cursor.step(event(EventKind.VERIFIED_CLEANUP,current))
            with self.assertRaises(Refused):
                cursor.step(event(EventKind.VERIFIED_CLEANUP,current))
        self.assertEqual(cursor.snapshot.state,State.OFFLINE)
        cursor.step(event(EventKind.OFFLINE_OPTICAL_VERDICT,PASS))
        self.assertEqual(cursor.snapshot.state,State.DEGRADED_COMPLETE)

    def test_review_guard_decimal_grammar(self):
        m=ready()._step(event(EventKind.RESERVE,BUDGET))
        for timing in (b"GUARD_TIMING 1 9\n",b"GUARD_TIMING 1.0 9\n",
                       b"GUARD_TIMING 1 9.0\n",b"GUARD_TIMING 1. 9.0\n",
                       b"GUARD_TIMING .1 1.0\n"):
            with self.subTest(grammar=timing):
                self.assertTrue(m._step(event(EventKind.DISPATCH,
                    replace(guard(m),timing=timing))).target_uncertain)

if __name__ == "__main__":
    unittest.main(verbosity=2)
