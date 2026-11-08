#!/usr/bin/env python3
"""Exploratory timed factory15 rehearsal. No candidate interface or admission.

Only new scheduling; qualified DSI children remain byte-identical. Unknown
whole-return bounds are measured, never asserted. 37s host cutoff reserves8s
within45s; the independent60s watchdog is never renewed. Timeout means reboot.
"""
import argparse
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import threading
import uuid

import run_p85_batched_trial as batch

env=batch.env;base=batch.base;s=batch.s;p85=batch.p85;check=s.check;q=s.q
SOURCE_FILES=batch.SOURCE_FILES+('06-tools/run_p85_timed_stock_trial.py',)
SCOPE='p85-timed-stock-surrogate-v1'
OMITTED_C1={'status':'not_measured','reason':'diagnostic omitted by timed-stock protocol'}
ACTIVE_SECONDS=37.0


def guard_command(plan,owner,boot,protected,writer_nonce):
    check(re.fullmatch(r'[0-9a-f-]{36}',boot),'Invalid boot')
    check(re.fullmatch(r'[A-Za-z0-9_]{8,180}',protected),'Invalid protected marker')
    check(re.fullmatch(r'[0-9a-f]{12}',writer_nonce),'Invalid writer nonce')
    path=plan.work+'/guard-kernel'
    # Same rejected events as qualify_quiet, with LOST additionally fail-closed.
    awk=r'''BEGIN {good=0;seen=0;bad=0}
 /dsi_display_set_mode/ {if(seen)bad=1;good=($0 ~ /hactive=1440, vactive=3168, fps=120\(actual=120, group=0x3\), clk_rate=1234000000([^0-9]|$)/)}
 index($0,collision) {bad=1}
 index($0,mark) {seen++;if(!good)bad=1}
 seen && (/dsi_display_set_mode/ || /dsi_ctrl_cmd_transfer len=/ || /Command transfer failed/ || /LOST/) {bad=1}
 END {if(seen!=1 || !good)bad=1;exit bad?1:0}'''
    return ("guard_start=$(cut -d ' ' -f 1 /proc/uptime); "+owner+'; '+f'test "$(id -u)" = 0; test "$(cat {s.CON}panelName)" = {q(s.c1.PANEL)}; '+f'test "$(cat /proc/sys/kernel/random/boot_id)" = {q(boot)}; '
        f'test "$(cat {s.BL}brightness)" = 3600; test "$(cat {s.BL}bl_power)" = 0; '
        f'test "$(cat {s.CON}panelDC)" = 0; test "$(getenforce)" = Enforcing; '
        f'test ! -L {q(path)}; test ! -e {q(path)}; dmesg > {q(path)}; '
        f'test "$(wc -c < {q(path)})" -le 16777216; '
        f'awk -v mark={q(protected)} -v collision={q("PWM_P85_WRITE_"+writer_nonce)} {q(awk)} {q(path)}; '
        f'rm {q(path)}; guard_end=$(cut -d \' \' -f 1 /proc/uptime); '+
        'printf \'GUARD_TIMING %s %s\\n\' "$guard_start" "$guard_end"')


def guarded_writer_plan(nonce,owner,token,label,begin,end,tmp,boot,protected):
    check(label in ('sham15','return15'),'Factory15 only')
    plan=env.child_envelope(nonce,owner,token,label,begin,end,tmp)
    parts=list(plan.parts);index=next(i for i,x in enumerate(parts) if x.label=='CHILD')
    parts.insert(index,env.Part('PRE_GUARD',guard_command(plan,owner,boot,protected,nonce),True,128,8))
    return replace(plan,parts=tuple(parts))


def envelope_script(plan):
    command=env.script(plan)
    # Only new fixed scratch basename; old envelope scripts remain unchanged.
    command=command.replace('$W/stdout" "$W/stderr" "$W/owner',
                            '$W/guard-kernel" "$W/stdout" "$W/stderr" "$W/owner')
    env.command_sizes(command)
    return command


def cleanup_command(record):
    work=record['work']
    command=env.remnant_cleanup(work,record['owner_digest'])
    old='rm -f '+work+'/stdout '
    check(command.count(old)==1,'Changed owned cleanup grammar')
    return command.replace(old,'rm -f '+work+'/guard-kernel '+work+'/stdout ')


def size_preflight():
    result=env.size_preflight();n='f'*12;t='x'*128;m='X'*180;owner=s.lock_commands(t)['verify']
    for label in ('sham15','return15'):
        plan=guarded_writer_plan(n,owner,t,label,m,m,'/data/local/tmp/'+'x'*64,
                                '0'*8+'-'+'0'*4+'-'+'0'*4+'-'+'0'*4+'-'+'0'*12,m)
        result['timed_'+label]=env.command_sizes(envelope_script(plan))
    return result


class DeadlineTransport:
    def __init__(self,trial,transport):self.trial=trial;self.transport=transport
    def __getattr__(self,name):return getattr(self.transport,name)
    def shell(self,target,command,timeout):
        trial=self.trial
        if trial.active_start is None:return self.transport.shell(target,command,timeout)
        remaining=trial.remaining();check(remaining>0,'Timed stock deadline; reboot only')
        item={'at_monotonic':trial.monotonic(),'remaining_active_seconds':remaining,
              'timeout_seconds':min(timeout,remaining),'return_estimate':trial.return_estimate(),
              'label':trial.current_action,'target_role':'camera' if target==trial.camera else 'panel'}
        trial.report['active_actions'].append(item)
        try:
            result=self.transport.shell(target,command,min(timeout,remaining))
            check(trial.remaining()>0,'Late transport result; reboot only')
            return result
        except BaseException:
            trial.panel_uncertain=True;trial.active_failed=True;raise
        finally:item['end_monotonic']=trial.monotonic()


class TimedStockTrial(batch.BatchedTrial):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.active_start=None;self.active_failed=False;self.prepared={};self.guard_context=False;self.current_action='none';self.timed_observed=set();self.timed_arm_attempted=False;self.timed_watchdog_verified=False
        self.g=DeadlineTransport(self,self.g)
        self.report.update(scope=SCOPE,candidate_enabled=False,timed_stock_exploratory=True,
            active_actions=[],timed_watchdog_seconds=60,timed_watchdog_renewals=0,active_limit_seconds=37,host_limit_seconds=45,recovery_reserve_seconds=8,
            admission='Factory15 exploratory measurement only; no proven whole-return bound',
            diagnostic_change='Sham C1 not measured; baseline and return C1 mandatory')

    def shell(self,command,**kwargs):
        previous=self.current_action;self.current_action=kwargs.get('label','shell')
        try:return super().shell(command,**kwargs)
        finally:self.current_action=previous

    def cam(self,command,label,timeout=15):
        previous=self.current_action;self.current_action='camera-'+label
        try:return super().cam(command,label,timeout)
        finally:self.current_action=previous

    def remaining(self):
        check(self.active_start is not None,'No active clock')
        check(not self.active_failed,'Uncertain active operation; reboot only')
        return ACTIVE_SECONDS-(self.monotonic()-self.active_start)

    def return_estimate(self):
        if not self.report['stages']:return {'status':'unknown_not_a_bound'}
        phases=self.report['stages'][0]['phase_seconds']
        known=sum(phases.get(k,0) for k in ('quiet','p85','c1'))
        return {'status':'provisional_partial_not_a_bound','known_read_quiet_seconds':known,
                'unbounded_components':['writer','freshness_gap','disarm','variability'],
                'partial_margin_seconds':self.remaining()-known}

    @contextmanager
    def active_window(self):
        check(threading.current_thread() is threading.main_thread(),'Main thread required')
        check(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'Existing alarm refused')
        handler=signal.getsignal(signal.SIGALRM)
        def deadline(signum,frame):
            self.active_failed=True;self.panel_uncertain=True
            raise TimeoutError('Timed stock37s exhausted; remote child may still run')
        self.active_start=self.monotonic();self.guard_context=True
        self.report['active_start_monotonic']=self.active_start
        signal.signal(signal.SIGALRM,deadline)
        try:
            remaining=self.remaining();check(remaining>0,'Alarm setup exhausted window')
            signal.setitimer(signal.ITIMER_REAL,remaining)
            yield
            check(self.remaining()>0,'Late active completion')
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.signal(signal.SIGALRM,handler)
            self.report['host_alarm_restored_before_cleanup']=True
            self.guard_context=False;self.active_start=None

    def envelope(self,plan,label):
        check(not self.recovery_failed and not self.active_failed,'No envelope after uncertainty')
        self.event+=1;stem=f'{self.event:04d}-envelope-{label}'
        record={'nonce':plan.nonce,'work':plan.work,'owner_digest':plan.owner_digest,'cleaned':False,'label':label}
        self.envelopes.append(record)
        event={'label':label,'at_utc':s.now(),'raw_record':stem,'has_child':plan.child_command is not None,
               'start_monotonic':self.monotonic()}
        self.report['envelope_timings'].append(event);self._persist('before-'+label)
        try:
            command=envelope_script(plan);start=self.monotonic()
            previous=self.current_action;self.current_action='envelope-'+label
            try:rc,out,err=self.g.shell(self.target,command,plan.seconds+5)
            finally:self.current_action=previous
            event.update(return_code=rc,transport_start_monotonic=start,
                transport_end_monotonic=self.monotonic(),transport_seconds=self.monotonic()-start)
            for name,data in (('stdout',out),('stderr',err)):
                path=self.private/(stem+'.'+name)
                with path.open('xb') as f:f.write(data)
                path.chmod(0o600)
            start=self.monotonic();data=env.parse(out,plan,returncode=rc,stderr=err)
            self._timing(label,start,'framing_validation')
            if plan.child_command:
                marker=next(p.command.split('<6>',1)[1].split('\\n',1)[0] for p in plan.parts if p.label=='END')
                check(data['KERNEL'].count(marker)==1,'Missing child tail marker')
                tail=data['KERNEL'].split(marker,1)[1]
                check(not any(x in tail for x in ('dsi_ctrl_cmd_transfer len=','dsi_display_set_mode','Command transfer failed','LOST')),'Native activity after child END')
            record['cleaned']=True
            return data
        except BaseException as error:
            self.panel_uncertain=True;event['error_type']=type(error).__name__;raise
        finally:
            event['end_monotonic']=self.monotonic()
            event['elapsed_seconds']=event['end_monotonic']-event['start_monotonic']
            self._persist('after-'+label)

    def quiet(self,label,dbv,initial=False):
        result=super().quiet(label,dbv,initial=initial)
        bounds=[]
        for marker in (result['begin_marker'],result['end_marker']):
            rows=[line for line in self._last_quiet_kernel.splitlines() if marker in line]
            check(len(rows)==1,'Ambiguous quiet timestamp')
            match=re.search(r'\[\s*([0-9]+\.[0-9]+)\]',rows[0])
            check(match is not None,'Missing kernel quiet timestamp')
            bounds.append(float(match[1]))
        check(bounds[1]-bounds[0]>=2,'Quiet interval shorter than2s')
        result['kernel_marker_bounds']={'begin_seconds':bounds[0],'end_seconds':bounds[1],
            'clock':'target kernel printk monotonic; not host/camera clock'}
        return result

    def prepare_writer(self,label):
        check(label in ('sham15','return15') and label not in self.prepared,'No repeated/unknown writer')
        nonce=self.child_nonce('writer');start=self.monotonic()
        quiet=self.quiet(label+'_PRE',3600)
        check('PWM_P85_WRITE_'+nonce not in self._last_quiet_kernel,'Writer collision')
        record={'nonce':nonce,'quiet_evidence':quiet,'started_monotonic':start,
                'ended_monotonic':self.monotonic(),'used':False}
        self.prepared[label]=record;return record

    def write_stage(self,label):
        check(label in ('sham15','return15'),'No candidate')
        check(self.guard_context and self.short_armed and self.timed_watchdog_verified and self.active_start is not None and self.remaining()>0,'Writer requires active verified watchdog window')
        check(not self.panel_uncertain and not self.pending_read and not self.inflight,'No DSI into uncertainty')
        prep=self.prepared[label];check(not prep['used'],'No writer retry');prep['used']=True
        started=self.monotonic();nonce=prep['nonce'];protected=prep.get('protected_marker',prep['quiet_evidence']['begin_marker'])
        self.panel_uncertain=True;self.pending_read=True
        # Fresh host gap/state check, then remote pre-child guard covers launch gap.
        fresh=self._marker(label.upper()+'_PRE_DISPATCH')
        data=self.envelope(env.hold_end_envelope(uuid.uuid4().hex[:12],self.ops['verify'],fresh),label+'-dispatch-gap')
        s.qualify_quiet(data['KERNEL'],protected,fresh,self.reference)
        env.validate_state(data,3600,self.before['boot_id'])
        check('PWM_P85_WRITE_'+nonce not in data['KERNEL'],'Fresh writer collision')
        begin=self._marker(label.upper()+'_WRITE_BEGIN');end=self._marker(label.upper()+'_WRITE_END')
        plan=guarded_writer_plan(nonce,self.ops['verify'],self.token,label,begin,end,self.tmp,self.before['boot_id'],protected)
        dispatch=self.monotonic();self.report['register85_writes_attempted'].append(label)
        data=self.envelope(plan,label+'-write');validation=self.monotonic()
        p85.validate_write_capture(data['CHILD'],nonce,label)
        p85.validate_write_wire(data['KERNEL'],begin,end,label,self.reference)
        p85.validate_write_wire(data['KERNEL'],protected,end,label,self.reference)
        env.validate_state(data,3600,self.before['boot_id'])
        check(data['ESD'].strip()=='reg_read','Post-write ESD failed')
        guard_match=re.fullmatch(r'GUARD_TIMING ([0-9]+\.[0-9]+) ([0-9]+\.[0-9]+)\n',data['PRE_GUARD'])
        check(guard_match is not None,'Missing device guard timing')
        guard_begin,guard_end=map(float,guard_match.groups())
        check(0<=guard_end-guard_begin<=8,'Device guard exceeded bound')
        self._timing(label,validation,'host_validation');self.pending_read=False
        self.report.setdefault('writes',[]).append({'stage':label,'started_monotonic':started,
            'device_guard_seconds':guard_end-guard_begin,'dispatch_monotonic':dispatch,'validated_monotonic':self.monotonic(),
            'elapsed_seconds':self.monotonic()-started,'standalone_callbacks':3,'native_and_wire_gates':True,
            'quiet_age_to_callback_upper_seconds':self.monotonic()-prep['ended_monotonic'],
            'quiet_age_limit':'Host upper bound through validated return; not synchronized callback time',
            'camera_end_to_dispatch_seconds':dispatch-prep['camera_end_monotonic'] if 'camera_end_monotonic' in prep else None})
        self._persist('after-write-'+label)

    def optical_hold(self,label,record,overlap=False):
        start=self.monotonic();begin=self.mark(label.upper()+'_HOLD_BEGIN')
        record['hold_start_utc']=s.now();record['hold_start_monotonic']=self.monotonic()
        camera_start=self.metadata(label+'-hold-start');camera_start_end=camera_start['host_capture_bounds']['end_monotonic']
        deadline=camera_start_end+base.HOLD
        if overlap:
            prep=self.prepare_writer('return15');ended=prep['ended_monotonic'];began=prep['started_monotonic']
            wait=max(0,deadline-ended)
            record['return_prequiet']={k:prep[k] for k in ('started_monotonic','ended_monotonic','quiet_evidence')}
            record['return_prequiet'].update(wait_seconds=wait,
                overlap_seconds=max(0,min(ended,deadline)-max(began,camera_start_end)),
                overshoot_seconds=max(0,ended-deadline))
        else:wait=max(0,deadline-self.monotonic())
        if wait:
            if self.active_start is not None:check(self.remaining()>wait,'Hold exceeds remaining window')
            self.sleep(wait)
        check(self.monotonic()>=deadline,'Hold shortened')
        camera_end=self.metadata(label+'-hold-end')
        check(camera_end['host_capture_bounds']['begin_monotonic']>=deadline,'Camera hold shortened')
        record['hold_end_utc']=s.now();record['hold_end_monotonic']=self.monotonic()
        end=self._marker(label.upper()+'_HOLD_END')
        data=self.envelope(env.hold_end_envelope(uuid.uuid4().hex[:12],self.ops['verify'],end),label+'-hold-end')
        s.qualify_quiet(data['KERNEL'],begin,end,self.reference);env.validate_state(data,3600,self.before['boot_id'])
        frames=camera_end['frame_count']-camera_start['frame_count'];check(frames>=120,'Insufficient sensor frames')
        if overlap:
            check('PWM_P85_WRITE_'+self.prepared['return15']['nonce'] not in data['KERNEL'],'Hold writer collision')
            self.prepared['return15'].update(protected_marker=begin,camera_end_monotonic=camera_end['host_capture_bounds']['end_monotonic'])
        record.update(hold_seconds=base.HOLD,observed_sensor_frames=frames,stable_encoded_frames=None,
            camera_start=camera_start,camera_end=camera_end,hold_markers={'begin':begin,'end':end},
            hold_verified_monotonic=self.monotonic())
        record['phase_seconds']['hold_and_metadata']=self.monotonic()-start

    def timed_observe(self,label):
        check(label in ('sham15','return15'),'Unexpected timed stage')
        check(not self.pending_read and not self.inflight and not self.observation_failed
              and not self.observation_in_progress and label not in self.timed_observed,
              'No timed observation retry into uncertainty')
        check(self.guard_context and self.short_armed and self.active_start is not None,'Observation requires active watchdog')
        check(self.report.get('writes') and self.report['writes'][-1]['stage']==label,'Observation requires matching qualified writer')
        expected=['baseline'] if label=='sham15' else ['baseline','sham15']
        check([stage['label'] for stage in self.report['stages']]==expected,'Out-of-order timed observation')
        self.timed_observed.add(label);self.observation_in_progress=True
        try:return self._timed_observe(label)
        except BaseException:
            self.observation_failed=True;self.panel_uncertain=True
            raise
        finally:self.observation_in_progress=False

    def _timed_observe(self,label):
        check(label in ('sham15','return15'),'Unexpected timed stage')
        self.panel_uncertain=True;started=self.monotonic()
        quiet_start=self.monotonic();self.quiet(label,3600)
        record={'label':label,'started_at_utc':s.now(),'qualified':False,'phase_seconds':{'quiet':self.monotonic()-quiet_start}}
        record['p85'],record['phase_seconds']['p85']=self._read_one(label,'p85')
        if label=='sham15':record['c1']=dict(OMITTED_C1)
        else:
            record['c1'],record['phase_seconds']['c1']=self._read_one(label,'c1')
            self.explicit_return_verified=True;self.report['explicit15_readback_and_stock_c1_verified']=True
            qualified=self.monotonic();self.report['return_qualified_monotonic']=qualified
            self.disarm_short()
            disarmed=self.monotonic()
            self.report['disarmed_monotonic']=disarmed
            self.report['disarm_seconds']=disarmed-qualified
            self.report['active_G_seconds']=disarmed-self.active_start
        if label=='sham15':self.optical_hold(label,record,overlap=True)
        self.panel_uncertain=False
        if label=='sham15':
            record.update(qualified=True,elapsed_seconds=self.monotonic()-started)
            self.report['stages'].append(record);self._persist('stage-'+label)
        return record,started

    def arm_timed(self):
        check(self.guard_context and self.active_start is not None and not self.short_armed and not self.timed_arm_attempted,'Arm only once inside clock')
        self.timed_arm_attempted=True
        self.short_armed=True;self.short_started=self.active_start
        start=self.monotonic()
        try:
            self.shell(base.short_watchdog(self.tmp,self.token,self.before['boot_id']),root=True,label='timed-watchdog-arm')
            self.shell(self.ops['verify']+f'; test -d {self.tmp}/candidate_armed; kill -0 $(cat {self.tmp}/candidate-watchdog.pid)',root=True,label='timed-watchdog-verify')
        except BaseException:
            self.active_failed=True;self.panel_uncertain=True;raise
        self.timed_watchdog_verified=True
        self.report.update(arm_seconds=self.monotonic()-self.active_start,arm_request_to_verified_seconds=self.monotonic()-start,
                           candidate_watchdog='armed60s_no_renewal')
        self._persist('armed-timed')

    def recover(self):
        check(not self.guard_context and self.active_start is None,'Cancel host alarm before recovery')
        self.active_failed=False
        super().recover()

    def restore(self):
        check(not self.panel_uncertain and not self.pending_read and not self.inflight and not self.recovery_failed,'Recovery required')
        for record in self.envelopes:
            if not record['cleaned']:
                self.shell(cleanup_command(record),label='timed-envelope-remnant');record['cleaned']=True
        super().restore()

    def execute(self):
        error=None
        try:
            self.setup();self.observe_stage('baseline')
            self.panel_uncertain=True
            self.identity();self.camera_identity();self.metadata('pre-timed');self.state(3600)
            self.prepare_writer('sham15')
            self.panel_uncertain=False
            with self.active_window():
                self.arm_timed();self.write_stage('sham15');self.timed_observe('sham15')
                self.write_stage('return15');record,started=self.timed_observe('return15')
            # Full return optical hold remains mandatory after verified disarm.
            self.panel_uncertain=True;self.optical_hold('return15',record)
            record.update(qualified=True,elapsed_seconds=self.monotonic()-started)
            self.report['stages'].append(record);self.panel_uncertain=False
            self.report['explicit15_readback_and_stock_c1_return']=True
            self.report['status']='awaiting_optical_review';self._persist('complete-stages')
        except BaseException as exc:
            error=exc;self.report.update(status='failed',error_type=type(exc).__name__)
            if self.panel_uncertain or self.pending_read or self.inflight or self.short_armed:
                try:self.recover()
                except BaseException:pass
        finally:
            try:self.stop_camera()
            except BaseException as exc:self.report['camera_cleanup_error_type']=type(exc).__name__;error=error or exc
            try:self.cleanup_camera_xml()
            except BaseException as exc:self.report['camera_ui_cleanup_pending']=True;error=error or exc
            if not self.recovery_failed:
                try:
                    if self.short_armed:self.disarm_short()
                    self.restore()
                except BaseException as exc:self.report['cleanup_error_type']=type(exc).__name__;error=error or exc
            if error:self.report['status']='failed; inspect recovery and retained watchdog/owner'
            self.report['finished_at_utc']=s.now();self.save()
        if error:raise RuntimeError('Timed stock failed; no retry') from error
        return self.report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=int);parser.add_argument('camera',type=int)
    parser.add_argument('--stock-only',action='store_true',required=True)
    parser.add_argument('--experiment-id',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();s.plan(args.experiment_id)
    check(args.target>0 and args.camera>0 and args.target!=args.camera,'Distinct transports')
    private=Path.home()/'.cache/legion-y70-p85-timed-stock'/args.experiment_id
    check(not args.output.exists() and not private.exists(),'Fresh output/private required')
    bounds=size_preflight();source=base.source_provenance(paths=SOURCE_FILES,require_clean=args.execute)
    if not args.execute:
        print(json.dumps({**source,'scope':SCOPE,'candidate_enabled':False,'offline_only':True,'envelope_command_size_preflight':bounds},indent=2));return
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.mkdir()
    private.parent.mkdir(parents=True,exist_ok=True,mode=0o700);private.mkdir(mode=0o700)
    from guarded_adb_socket import GuardedADB
    run=TimedStockTrial(GuardedADB(),args.target,args.camera,args.experiment_id,args.output,private)
    run.report.update(source,envelope_command_size_preflight=bounds)
    owner=private/'owner.txt';owner.write_text(run.token+'\n');owner.chmod(0o600)
    def abort(signum,frame):raise KeyboardInterrupt('Termination requested')
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,abort)
    run.save();run.execute();print(json.dumps({'status':run.report['status'],'candidate_enabled':False,'pwm_hz':None}))


if __name__=='__main__':main()
