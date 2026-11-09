from fixtures import fixture_gate
import unittest
from copy import deepcopy
from dataclasses import replace
from custody_bridge import model as m
from harness import Blocked, FakeBackend, QualifiedReceipt, RecoveryGate, joint_result
from fixtures import setup, finish_target, finish_camera, NEW, OLD, FAILED


class HarnessTests(unittest.TestCase):
    def assertTerminalNoRetry(self, c, retry):
        before = len(fixture_gate(c).backend.log)
        with self.assertRaises(Blocked): retry()
        self.assertEqual(len(fixture_gate(c).backend.log), before)
        self.assertEqual(c.state, 'RECOVERY_FAILED')

    def test_full_separate_components(self):
        target, route, _ = setup('target'); camera, _, _ = setup('camera')
        finish_target(target, route); finish_camera(camera)
        r = joint_result(target, camera)
        self.assertEqual(r['status'], 'fake_components_verified')
        self.assertFalse(r['physical_admission']); self.assertEqual(r['stock_admission'], 'HOLD')
        self.assertFalse(r['watchdog60_600_proves_camera_stop'])
        self.assertEqual(sum(x['action']=='REBOOT_TARGET' for x in fixture_gate(target).backend.log), 1)
        self.assertEqual(sum(x['action']=='STOP_CAMERA' for x in fixture_gate(camera).backend.log), 1)
        self.assertEqual(target.summary()['original_failed_state'], FAILED)
        self.assertTrue(all(d.admitted_model_only for d in fixture_gate(target).admission.decisions))

    def test_old_route_is_terminal(self):
        c, _, _ = setup('target', gate_route='failed-old-route')
        with self.assertRaises(Blocked): c.precheck()
        self.assertEqual(fixture_gate(c).backend.log, [])
        self.assertTerminalNoRetry(c, c.precheck)

    def test_incident_denied_or_unresolved_not_new_client_escape(self):
        for cause in (m.IncidentCause.DENIAL, m.IncidentCause.UNRESOLVED):
            c, _, _ = setup('target', incident_cause=cause)
            with self.assertRaises(Blocked): c.precheck()
            self.assertEqual(fixture_gate(c).backend.log, [])

    def test_unqualified_reader_or_custody_gap(self):
        for mode in ('unqualified', 'gap', 'foreign_binding'):
            c, route, _ = setup('camera')
            def mutate(contract, evidence, clocks):
                if mode == 'unqualified': return replace(contract, qualifications=()), evidence, clocks
                if mode == 'gap':
                    evidence = tuple(e for e in evidence if e.capability is not m.Capability.HELD_CHANNEL)
                else:
                    evidence = (replace(evidence[0], binding=replace(evidence[0].binding, physical_id='foreign')),)+evidence[1:]
                return contract, evidence, clocks
            route.mutate = mutate
            with self.assertRaises(Blocked): c.precheck()
            self.assertEqual(fixture_gate(c).backend.log, [])

    def test_missing_exact_authority(self):
        c, _, _ = setup('target', authority=lambda r: None)
        with self.assertRaises(Blocked): c.precheck()
        self.assertEqual(fixture_gate(c).backend.log, [])

    def test_stale_route_evidence_no_dispatch(self):
        c, route, _ = setup('target')
        route.mutate = lambda a,e,t: (a,e,tuple((d,n+1000) for d,n in t))
        with self.assertRaises(Blocked): c.precheck()
        self.assertEqual(fixture_gate(c).backend.log, [])

    def test_fake_reboot_failure_timeout_unknown_terminal(self):
        for status in ('failed', 'timeout', 'unknown'):
            c, _, _ = setup('target'); fixture_gate(c).backend.script[1]['status'] = status
            c.precheck()
            with self.assertRaises(Blocked): c.reboot()
            self.assertTerminalNoRetry(c, c.reboot)
            self.assertTrue(c.reboot_attempted)
            self.assertTrue(fixture_gate(c).admission.state.terminal_reason)

    def test_reboot_ack_not_changed_boot_or_restore(self):
        c, route, _ = setup('target'); c.precheck(); c.reboot()
        self.assertEqual(c.state, 'NEED_CHANGED_BOOT')
        with self.assertRaises(Blocked): c.restore()
        self.assertFalse(any(x['action']=='RESTORE_TARGET' for x in fixture_gate(c).backend.log))

    def test_postboot_needs_independent_route_boot_binding(self):
        c, _, _ = setup('target'); c.precheck(); c.reboot()
        with self.assertRaises(Blocked): c.changed_boot()
        self.assertIn('admitted device/boot', c.failure)

    def test_same_boot_fails_even_ack(self):
        c, _, _ = setup('target'); fixture_gate(c).backend.script[2]['payload']['boot_id'] = OLD
        c.precheck(); c.reboot()
        with self.assertRaises(Blocked): c.changed_boot()
        self.assertFalse(c.restore_attempted)

    def test_target_exact_postboot_gates(self):
        variants = [('root_uid', 2000), ('selinux', 'Permissive'), ('boot_completed', False),
                    ('dc_stock_safe', None), ('esd', 'unknown'), ('identity', {'model':'foreign'})]
        for key,value in variants:
            c, route, _ = setup('target'); fixture_gate(c).backend.script[2]['payload'][key] = value
            c.precheck(); c.reboot(); route.boot=NEW
            with self.assertRaises(Blocked): c.changed_boot()
            self.assertFalse(c.restore_attempted)

    def test_target_restore_ack_not_readback(self):
        c, route, _ = setup('target'); fixture_gate(c).backend.script[4]['payload']['settings']['native_dbv'] += 1
        c.precheck(); c.reboot(); route.boot=NEW; c.changed_boot(); c.restore()
        with self.assertRaises(Blocked): c.restored()
        self.assertTerminalNoRetry(c, c.restore)

    def test_foreign_camera_session_never_stop(self):
        for key,value in [('session_id','foreign'), ('owner','foreign'), ('recording_active',False),
                          ('session_binding_verified',None), ('stop_only_capability_verified',False)]:
            c, _, _ = setup('camera'); fixture_gate(c).backend.script[0]['payload'][key]=value
            with self.assertRaises(Blocked): c.precheck()
            self.assertFalse(any(x['action']=='STOP_CAMERA' for x in fixture_gate(c).backend.log))
            self.assertTerminalNoRetry(c, c.stop)

    def test_unknown_camera_stop_no_repeat(self):
        c, _, _ = setup('camera'); fixture_gate(c).backend.script[1]['status']='timeout'
        c.precheck()
        with self.assertRaises(Blocked): c.stop()
        self.assertTerminalNoRetry(c, c.stop)

    def test_callback_before_stop_not_success(self):
        c, _, _ = setup('camera')
        fixture_gate(c).backend.script[2]['payload'].update(cap_callback_observed=True, recording_active=True, stop_observed=False)
        c.precheck(); c.stop()
        with self.assertRaises(Blocked): c.stopped()
        self.assertTerminalNoRetry(c, c.stop)

    def test_session_changes_after_stop_ack(self):
        c, _, _ = setup('camera'); fixture_gate(c).backend.script[2]['payload']['session_id']='new-session'
        c.precheck(); c.stop()
        with self.assertRaises(Blocked): c.stopped()
        self.assertTerminalNoRetry(c, c.stop)

    def test_stop_not_finalized_valid_retained_media(self):
        for key in ('finalized','original_retained','decode_valid','metadata_retained'):
            c, _, _ = setup('camera'); fixture_gate(c).backend.script[3]['payload'][key]=None
            c.precheck(); c.stop(); c.stopped()
            with self.assertRaises(Blocked): c.finalized()
            self.assertFalse(c.restore_attempted)

    def test_camera_task_profile_and_original_settings_independent(self):
        for field in ('activity','task','profile','settings','idle_preview_verified'):
            c, _, _ = setup('camera'); d=fixture_gate(c).backend.script[5]['payload']
            if field=='profile': d[field]['focus_diopters']=9.0
            elif field=='settings': d[field]['duration_limit']=60
            else: d[field]=None
            c.precheck();c.stop();c.stopped();c.finalized();c.restore()
            with self.assertRaises(Blocked): c.restored()

    def test_stale_foreign_mutated_replayed_receipts(self):
        for mode in ('stale','foreign','mutated','replay'):
            c, _, clock = setup('target')
            receipt=fixture_gate(c)._call('READ_STATUS','target_precheck')
            if mode=='stale': clock.now += 6
            elif mode=='foreign': receipt=deepcopy(receipt)
            elif mode=='mutated': receipt.payload['root_uid']=1
            else: fixture_gate(c)._consume(receipt,'target_precheck')
            with self.assertRaises(Blocked): c.precheck(receipt)
            self.assertTerminalNoRetry(c,c.reboot)

    def test_component_success_does_not_cover_other_failure(self):
        for fail_component in ('target','camera'):
            t, route, _=setup('target');c,_,_=setup('camera')
            if fail_component=='camera':
                finish_target(t,route); fixture_gate(c).backend.script[0]['payload']['session_id']='foreign'
                with self.assertRaises(Blocked):c.precheck()
            else:
                finish_camera(c);fixture_gate(t).backend.script[0]['payload']['root_uid']=2000
                with self.assertRaises(Blocked):t.precheck()
            result=joint_result(t,c)
            self.assertTrue(result['recovery_failed']);self.assertEqual(result['status'],'recovery_failed')
            self.assertFalse(result['physical_admission']);self.assertEqual(result['stock_admission'],'HOLD')

    def test_forbidden_actions_never_dispatched(self):
        for action in ('DSI','RETURN15','SHUTTER_TOGGLE','WATCHDOG_REBOOT_CAMERA'):
            c,_,_=setup('target')
            with self.assertRaises(Blocked):fixture_gate(c)._call(action,'forbidden')
            self.assertEqual(fixture_gate(c).backend.log,[])

    def test_expired_pre_action_semantics_never_mutate(self):
        for component, action in [('target', 'reboot'), ('camera', 'stop')]:
            c,_,clock=setup(component);c.precheck();clock.now+=6
            with self.assertRaises(Blocked):getattr(c,action)()
            self.assertEqual([x['action'] for x in fixture_gate(c).backend.log], ['READ_STATUS'])

    def test_receiver_guard_prevents_foreign_session_race(self):
        c,_,_=setup('camera');fixture_gate(c).backend.script[1]['guard']['session_id']='replacement-session'
        c.precheck()
        with self.assertRaises(Blocked):c.stop()
        self.assertFalse(fixture_gate(c).backend.log[-1]['effect_applied'])
        self.assertTerminalNoRetry(c,c.stop)

    def test_boolean_only_admission_rejected(self):
        class BooleanAdmission:
            def authorize(self, binding, now):return {'admitted':True,'binding':binding}
        with self.assertRaises(Blocked):
            RecoveryGate(component='target',incident='i',route='r',device='d',admission=BooleanAdmission(),
                         backend=FakeBackend([]),clock=lambda:100)

    def test_non_fake_backend_rejected(self):
        c,_,_=setup('target')
        with self.assertRaises(Blocked):
            RecoveryGate(component='target',incident='i',route='r',device='d',admission=fixture_gate(c).admission,
                         backend=object(),clock=lambda:100)


    def test_exact_reviewed_public_replay_blocked(self):
        for component, action in [('target','reboot'), ('camera','stop')]:
            c,_,_=setup(component);fixture_gate(c).backend.script[1]['status']='unknown'
            c.precheck();saved=fixture_gate(c).admission.state
            with self.assertRaises(Blocked):getattr(c,action)()
            for obj,name,value in [(c,'state','READY_REBOOT'),(c,action+'_attempted',False),
                                   (fixture_gate(c),'terminal',False),(fixture_gate(c).admission,'state',saved)]:
                with self.assertRaises(AttributeError):setattr(obj,name,value)
            fixture_gate(c).backend.script.insert(0, {'action':'REBOOT_TARGET' if component=='target' else 'STOP_CAMERA','status':'ok'})
            self.assertTerminalNoRetry(c,getattr(c,action))
            self.assertEqual(len(fixture_gate(c).backend.log),2)

    def test_all_public_lifecycle_surfaces_read_only(self):
        for component in ('target','camera'):
            c,_,_=setup(component);c.precheck()
            for obj in (c,fixture_gate(c),fixture_gate(c).admission):
                for name in obj._snapshots | obj._references:
                    with self.assertRaises(AttributeError):setattr(obj,name,None)
                    with self.assertRaises(AttributeError):delattr(obj,name)
                with self.assertRaises(AttributeError):obj.new_public_state=True
                with self.assertRaises(AttributeError):obj.summary=lambda:None
            c.events.clear();c.original_failed_state.clear();c.identity.clear()
            fixture_gate(c).receipts.clear();fixture_gate(c).admission.pending.clear();fixture_gate(c).admission.decisions.clear()
            self.assertTrue(c.events);self.assertTrue(c.identity);self.assertEqual(c.original_failed_state,FAILED)
            self.assertTrue(fixture_gate(c).admission.decisions)
            for name in ('authorize','record','confirm_reboot','claim_gate','initialize_once'):
                self.assertFalse(hasattr(fixture_gate(c).admission,name))
            self.assertFalse(hasattr(c,'transition'))

    def test_constructor_reentry_and_resource_rebinding_blocked(self):
        from custody_bridge import CustodyAdmission
        from harness import Controller
        for component in ('target','camera'):
            c,route,clock=setup(component);c.precheck()
            with self.assertRaises(ValueError):Controller.__init__(c,fixture_gate(c),FAILED)
            with self.assertRaises(ValueError):Controller(fixture_gate(c),FAILED)
            with self.assertRaises(ValueError):
                fixture_gate(c).__init__(component=component,incident='fixture-incident',route='r',device='d',
                    admission=fixture_gate(c).admission,backend=fixture_gate(c).backend,clock=clock)
            with self.assertRaises(ValueError):
                RecoveryGate(component=component,incident='i',route='r',device='d',
                    admission=fixture_gate(c).admission,backend=fixture_gate(c).backend,clock=clock)
            with self.assertRaises(ValueError):
                CustodyAdmission(fixture_gate(c).admission.state,route,lambda r:None)
            with self.assertRaises(ValueError):
                fixture_gate(c).admission.__init__(fixture_gate(c).admission.state,route,lambda r:None)
            self.assertIn(c.state,('READY_REBOOT','READY_STOP'))

    def test_receipt_registry_snapshot_cannot_issue_or_replay(self):
        c,_,_=setup('target');r=fixture_gate(c)._call('READ_STATUS','target_precheck')
        registry=fixture_gate(c).receipts;registry[r.operation_id]=(r,deepcopy(r.payload))
        c.precheck(r)
        fixture_gate(c).receipts.update(registry)
        with self.assertRaises(Blocked):fixture_gate(c)._consume(r,'target_precheck')


    def test_public_mutation_helper_bypass_unavailable(self):
        for component, action, command in [('target','reboot','REBOOT_TARGET'),('camera','stop','STOP_CAMERA')]:
            c,_,_=setup(component);g=fixture_gate(c)
            c.precheck();getattr(c,action)()
            g.backend.script.insert(0, {'action':command,'status':'ok'})
            with self.assertRaises(AttributeError):
                c.gate.call(command,'bypass',{'expected_boot':OLD})
            self.assertFalse(hasattr(g,'call'));self.assertFalse(hasattr(g,'consume'))
            snapshot=c.gate;snapshot.update(terminal=False,counter=0,state='READY_REBOOT')
            self.assertEqual(g.counter,2)
            self.assertEqual([x['action'] for x in g.backend.log],['READ_STATUS',command])
            self.assertTerminalNoRetry(c,getattr(c,action))
            self.assertEqual(len(g.backend.log),2)

    def test_controller_gate_diagnostics_have_no_live_handles(self):
        c,_,_=setup('target')
        self.assertIs(type(c.gate),dict)
        for name in ('admission','backend','clock','receipts','call','consume'):
            self.assertNotIn(name,c.gate)
        with self.assertRaises(AttributeError):c.gate={}


if __name__=='__main__':unittest.main()
