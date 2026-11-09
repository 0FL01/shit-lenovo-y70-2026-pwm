import unittest
from dataclasses import replace,FrozenInstanceError
from custody_model import *

D='a'*64
R='b'*64

def fixture(component=Component.TARGET, action=Action.READ_STATUS, physical_boot='phone-old'):
    domain1=Domain('local','local-boot','monotonic_ns')
    domain2=Domain('remote','remote-boot','monotonic_ns')
    hops=[]; qs=[];obs=[]
    for i,hop in enumerate(Hop):
        domain=domain1 if i<2 else domain2
        start=100 if i<2 else 10000;end=start+10
        binding=Binding(D,domain.boot,'task-'+str(i),'exe-'+str(i),'socket-'+str(i),
                        'namespace-'+str(i),'ssh-fixed','server-fixed','transport-fixed','phone',physical_boot)
        hops.append(HopContract(hop,domain,start,binding))
        caps=[Capability.PIDFD_LIVE,Capability.HELD_CHANNEL,Capability.EXE_SNAPSHOT,Capability.HOLDER_SNAPSHOT]
        if hop is Hop.SSH_SESSION:caps.append(Capability.SSH_AUTH)
        if hop is Hop.TRANSPORT_DEVICE:caps.extend([Capability.PHYSICAL_SNAPSHOT,Capability.TRANSPORT_BINDING_SNAPSHOT])
        qs.append(Qualification('reader-'+str(i),R,'external-review-'+str(i),hop,domain,frozenset(caps)))
        for seq,cap in enumerate(caps):
            continuous=cap in (Capability.PIDFD_LIVE,Capability.HELD_CHANNEL)
            obs.append(Observation(hop,domain,start if continuous else end,end,binding,cap,
                       'reader-'+str(i),R,'external-review-'+str(i),format(i*100+seq,'064x'),seq,'capture-epoch'))
    c=RouteContract('incident','independent-route',D,component,'phone',physical_boot,
                    'external-association-review','capture-epoch',tuple(hops),tuple(qs),2)
    clocks=((domain1,110),(domain2,10010))
    route=assess_route(c,tuple(obs),clocks)
    state=RecoveryState('incident',D,'old-route',True,True,'phone-old',
                        IncidentCause.VERIFIED_NONSERVER_EXIT,'external-failure-attribution')
    req=Request('incident','independent-route','capture-epoch','op1',component,'phone',action)
    auth=Authority(req,'explicit-independent-recovery-authority')
    return c,tuple(obs),clocks,route,state,req,auth

class Tests(unittest.TestCase):
    def test_positive_is_snapshot_scoped_not_continuous(self):
        c,e,n,v,s,r,a=fixture()
        self.assertTrue(v.admitted_model_only)
        self.assertTrue(all(h.task_lifetime and h.connection_lifetime and h.holder_snapshot and h.executable_snapshot for h in v.hops))
        self.assertTrue(all(not h.continuous_custody for h in v.hops))
        s2,d=admit(s,r,a,v,dispatch_now_by_domain=n)
        self.assertTrue(d.admitted_model_only);self.assertEqual(d.source_digest,D)
        self.assertTrue(s.old_adapter_terminal);self.assertIsNone(s.pending)
        with self.assertRaises(FrozenInstanceError):r.route_id='new'
    def test_missing_each_evidence(self):
        c,e,n,*_=fixture()
        for i in range(len(e)):
            with self.subTest(i=i):self.assertFalse(assess_route(c,e[:i]+e[i+1:],n).admitted_model_only)
    def test_changed_every_binding_field(self):
        c,e,n,*_=fixture()
        for f in fields(Binding):
            changed='c'*64 if f.name=='source_digest' else 'changed'
            bad=replace(e[0],binding=replace(e[0].binding,**{f.name:changed}))
            self.assertFalse(assess_route(c,(bad,)+e[1:],n).admitted_model_only,f.name)
    def test_every_fault_terminal(self):
        c,e,n,*_=fixture()
        for fault in Fault:
            if fault is Fault.NONE:continue
            v=assess_route(c,(replace(e[0],fault=fault),)+e[1:],n)
            self.assertFalse(v.admitted_model_only,fault)
    def test_pidfd_held_socket_peercred_not_custody(self):
        c,e,n,*_=fixture()
        kept=tuple(x for x in e if x.capability in (Capability.PIDFD_LIVE,Capability.HELD_CHANNEL))
        v=assess_route(c,kept,n)
        self.assertFalse(v.admitted_model_only)
        self.assertTrue(all(x.task_lifetime and x.connection_lifetime for x in v.hops if x.hop is not Hop.SSH_SESSION))
        # Even qualified local peercred cannot replace missing remote evidence.
        q=c.qualifications[0];c=replace(c,qualifications=(replace(q,capabilities=q.capabilities|{Capability.UNIX_PEERCRED}),)+c.qualifications[1:])
        p=replace(e[0],capability=Capability.UNIX_PEERCRED,sequence=99)
        self.assertFalse(assess_route(c,kept+(p,),n).admitted_model_only)
    def test_time_domains_gaps_staleness(self):
        c,e,n,*_=fixture()
        for bad in [replace(e[0],start_ns=101),replace(e[0],end_ns=109),
                    replace(e[0],end_ns=111),replace(e[0],domain=n[1][0]),
                    replace(e[2],start_ns=107,end_ns=107),replace(e[0],end_ns=True)]:
            self.assertFalse(assess_route(c,(bad,)+e[1:] if bad.capability is e[0].capability else e[:2]+(bad,)+e[3:],n).admitted_model_only)
        self.assertFalse(assess_route(c,e,n[:1]).admitted_model_only)
        self.assertFalse(assess_route(c,e,n+n[:1]).admitted_model_only)
        self.assertFalse(assess_route(c,e,((n[0][0],n[0][1]+1),n[1])).admitted_model_only)
    def test_bad_provenance_and_replay(self):
        c,e,n,*_=fixture()
        for bad in [replace(e[0],reader_source_digest='c'*64),replace(e[0],capture_digest=''),
                    replace(e[0],qualification_id='unreviewed'),replace(e[0],reader_id='new')]:
            self.assertFalse(assess_route(c,(bad,)+e[1:],n).admitted_model_only)
        self.assertFalse(assess_route(c,e+(e[0],),n).admitted_model_only)
        self.assertFalse(assess_route(c,tuple(reversed(e)),n).admitted_model_only)
    def test_unknown_denial_and_old_route_never_admit(self):
        c,e,n,v,s,r,a=fixture()
        for cause in (IncidentCause.UNRESOLVED,IncidentCause.DENIAL):
            self.assertFalse(admit(replace(s,incident_cause=cause),r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
        self.assertFalse(admit(replace(s,incident_explanation_id=''),r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
        r2=replace(r,route_id=s.old_route_id)
        self.assertFalse(admit(s,r2,Authority(r2,'yes'),v,dispatch_now_by_domain=n)[1].admitted_model_only)
    def test_exact_request_authority_and_verdict(self):
        c,e,n,v,s,r,a=fixture()
        for f in fields(Request):
            value=Action.REBOOT_TARGET if f.name=='action' else Component.CAMERA if f.name=='component' else 'different'
            r2=replace(r,**{f.name:value})
            self.assertFalse(admit(s,r2,a,v,dispatch_now_by_domain=n)[1].admitted_model_only,f.name)
        self.assertFalse(admit(s,r,a,replace(v,reasons=('fake',)),dispatch_now_by_domain=n)[1].admitted_model_only)
        later=((n[0][0],111),n[1])
        self.assertFalse(admit(s,r,a,v,dispatch_now_by_domain=later)[1].admitted_model_only)
    def test_failed_assessment_cannot_be_healed_by_snapshot(self):
        c,e,n,v,s,r,a=fixture()
        for fault in (Fault.DENIED,Fault.UNKNOWN,Fault.NEW_HOLDER,Fault.CUSTODY_GAP):
            bad=assess_route(c,(replace(e[0],fault=fault),)+e[1:],n)
            stopped,decision=admit(s,r,a,bad,dispatch_now_by_domain=n)
            self.assertFalse(decision.admitted_model_only)
            self.assertTrue(stopped.terminal_reason)
            self.assertFalse(admit(stopped,r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)

    def test_one_shot_unknown_denied(self):
        c,e,n,v,s,r,a=fixture()
        for outcome in Outcome:
            s1,d=admit(s,r,a,v,dispatch_now_by_domain=n);self.assertTrue(d.admitted_model_only)
            self.assertFalse(admit(s1,r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
            done=complete(s1,r,outcome)
            self.assertFalse(admit(done,r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
            r2=replace(r,operation_id='op2')
            self.assertFalse(admit(done,r2,Authority(r2,'yes'),v,dispatch_now_by_domain=n)[1].admitted_model_only)
            r2=replace(r2,evidence_nonce='next-capture')
            c2=replace(c,evidence_nonce='next-capture')
            v2=assess_route(c2,tuple(replace(x,evidence_nonce='next-capture') for x in e),n)
            allowed=admit(done,r2,Authority(r2,'yes'),v2,dispatch_now_by_domain=n)[1].admitted_model_only
            self.assertEqual(allowed,outcome is Outcome.SUCCESS)
            with self.assertRaises(ValueError):complete(done,r,outcome)
    def test_restore_requires_changed_same_target_boot(self):
        c,e,n,v,s,r,a=fixture(action=Action.RESTORE_TARGET,physical_boot='phone-new')
        p=RebootProof('incident','phone','phone-old','phone-new','independent-verified-reboot',True,True)
        self.assertTrue(admit(s,r,a,v,p,dispatch_now_by_domain=n)[1].admitted_model_only)
        for f in fields(RebootProof):
            value=False if f.name in ('boot_completed','identity_root_enforcing_module_panel_stock') else ''
            self.assertFalse(admit(s,r,a,v,replace(p,**{f.name:value}),dispatch_now_by_domain=n)[1].admitted_model_only,f.name)
        self.assertFalse(admit(s,r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
    def test_reboot_success_not_reboot_proof_camera_separate(self):
        c,e,n,v,s,r,a=fixture(action=Action.REBOOT_TARGET)
        s1,d=admit(s,r,a,v,dispatch_now_by_domain=n);s2=complete(s1,r,Outcome.SUCCESS)
        r2=replace(r,operation_id='op2',action=Action.RESTORE_TARGET)
        self.assertFalse(admit(s2,r2,Authority(r2,'yes'),v,dispatch_now_by_domain=n)[1].admitted_model_only)
        c,e,n,v,s,r,a=fixture(Component.CAMERA,Action.STOP_CAMERA)
        self.assertTrue(admit(s,r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
        r2=replace(r,action=Action.REBOOT_TARGET)
        self.assertFalse(admit(s,r2,Authority(r2,'yes'),v,dispatch_now_by_domain=n)[1].admitted_model_only)
    def test_malformed_and_missing_hop(self):
        c,e,n,v,s,r,a=fixture()
        for cc in [replace(c,hops=c.hops[:-1]),replace(c,hops=tuple(reversed(c.hops))),replace(c,max_snapshot_age_ns=True),replace(c,qualifications=[])]:
            self.assertFalse(assess_route(cc,e,n).admitted_model_only)
        self.assertFalse(assess_route(c,list(e),n).admitted_model_only)
        self.assertFalse(admit(s,replace(r,action='DSI'),a,v,dispatch_now_by_domain=n)[1].admitted_model_only)
        self.assertFalse(admit(replace(s,old_adapter_terminal=False),r,a,v,dispatch_now_by_domain=n)[1].admitted_model_only)

if __name__=='__main__':unittest.main()
