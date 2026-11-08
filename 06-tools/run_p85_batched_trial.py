#!/usr/bin/env python3
"""Isolated stock-only batching qualification. DEFAULT offline; no candidate mode.

Unchanged qualified children, one per bounded envelope. Every host validator
finishes before the next child. Native snapshots remain non-atomic. Candidate
45/60s budgets are unchanged but no candidate admission is implemented here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import uuid

import p85_batched_envelope as env
import run_p85_guarded_trial as base

s=base.s
p85=base.p85
check=s.check
SOURCE_FILES=base.SOURCE_FILES+('06-tools/p85_batched_envelope.py','06-tools/run_p85_batched_trial.py')


class BatchedTrial(base.Trial):
    def __init__(self,*args,**kwargs):
        check(kwargs.get('candidate',False) is False,'Candidate disabled in unqualified batching adapter')
        super().__init__(*args,**kwargs)
        self.envelopes=[];self._last_quiet_kernel=None
        self.report.update(batching_adapter='p85-batched-stock-v1',candidate_enabled=False,
                           phase_timings=[],envelope_timings=[])

    def _marker(self,suffix):return self.marker+'_'+suffix

    def _timing(self,label,start,kind):
        end=self.monotonic()
        self.report['phase_timings'].append({'label':label,'kind':kind,
            'start_monotonic':start,'end_monotonic':end,'elapsed_seconds':end-start})

    def _persist(self,label):
        start=self.monotonic()
        temporary=self.private/'envelope-manifest.tmp'
        temporary.write_text(json.dumps(self.envelopes,indent=2)+'\n');temporary.chmod(0o600)
        os.replace(temporary,self.private/'envelope-manifest.json')
        self.save();self._timing(label,start,'host_save')
        # Persist this save's timing in the next ordinary report save, not a loop.

    def envelope(self,plan,label):
        check(not self.recovery_failed,'No envelope after unverified recovery')
        self.event+=1;stem=f'{self.event:04d}-envelope-{label}'
        record={'nonce':plan.nonce,'work':plan.work,'owner_digest':plan.owner_digest,'cleaned':False,'label':label}
        self.envelopes.append(record)
        event={'label':label,'at_utc':s.now(),'raw_record':stem,'has_child':plan.child_command is not None,
               'timing_limit':'Host call includes command construction/transport/device work, not pure RTT',
               'start_monotonic':self.monotonic()}
        self.report['envelope_timings'].append(event);self._persist('before-'+label)
        try:
            started=self.monotonic()
            rc,out,err=self.g.shell(self.target,env.script(plan),plan.seconds+5)
            ended=self.monotonic()
            event.update(return_code=rc,transport_start_monotonic=started,
                         transport_end_monotonic=ended,transport_seconds=ended-started)
            for name,data in (('stdout',out),('stderr',err)):
                path=self.private/(stem+'.'+name)
                with path.open('xb') as stream:stream.write(data)
                path.chmod(0o600)
            started=self.monotonic()
            parsed=env.parse(out,plan,returncode=rc,stderr=err)
            self._timing(label,started,'framing_validation')
            record['cleaned']=True  # DONE emitted only after exact owned-dir removal.
            return parsed
        except BaseException as error:
            event['error_type']=type(error).__name__
            raise
        finally:
            event['end_monotonic']=self.monotonic()
            event['elapsed_seconds']=event['end_monotonic']-event['start_monotonic']
            self._persist('after-'+label)

    def state(self,dbv):
        plan=env.state_envelope(uuid.uuid4().hex[:12],self.ops['verify'])
        data=self.envelope(plan,'state')
        started=self.monotonic();env.validate_state(data,dbv,self.before['boot_id'])
        self._timing('state',started,'host_validation')

    def quiet(self,label,dbv,initial=False):
        # Keep the original separately validated pre-state. No DSI in the second
        # envelope; all quiet/post-state evidence is checked before any child.
        self.state(dbv)
        begin=self._marker('QUIET_BEGIN_'+label+'_0');end=self._marker('QUIET_END_'+label+'_0')
        plan=env.quiet_envelope(uuid.uuid4().hex[:12],self.ops['verify'],begin,end)
        data=self.envelope(plan,'quiet-'+label)
        started=self.monotonic()
        current=s.qualify_quiet(data['KERNEL'],begin,end,self.reference)
        env.validate_state(data,dbv,self.before['boot_id'])
        self.reference=current;self._last_quiet_kernel=data['KERNEL']
        self._timing('quiet-'+label,started,'host_validation')
        return {'begin_marker':begin,'end_marker':end,'native_state':current,
                'quiet_seconds':2,'race_limit':'not an atomic compositor lock; no retries in batched qualification'}

    def _read_one(self,label,kind):
        started=self.monotonic();nonce=self.child_nonce(kind)
        self.pending_read=True
        begin=self._marker(label.upper()+'_'+kind.upper()+'_BEGIN')
        end=self._marker(label.upper()+'_'+kind.upper()+'_END')
        plan=env.child_envelope(nonce,self.ops['verify'],self.token,kind,begin,end,self.tmp)
        data=self.envelope(plan,label+'-'+kind)
        validation=self.monotonic()
        if kind=='p85':result=p85.validate_long3(data['CHILD'],nonce)
        else:result=s.validate_adapter_capture(data['CHILD'],nonce,3600)
        s.verify_read_interval(data['KERNEL'],begin,end,self.reference)
        env.validate_state(data,3600,self.before['boot_id'])
        check(data['ESD'].strip()=='reg_read','Independent ESD read not stock')
        check(result['data']==([21,0,0] if kind=='p85' else [0,0,96]),
              'Stock read plane changed; no next child')
        self.pending_read=False
        self._timing(label+'-'+kind,validation,'host_validation')
        self._timing(label+'-'+kind,started,'qualified_read_phase')
        return result,self.monotonic()-started

    def _observe_stage(self,label):
        check(label in ('baseline','sham15','return15'),'Stock-only observation')
        self.panel_uncertain=True;started=self.monotonic()
        quiet_start=self.monotonic();self.quiet(label,3600)
        record={'label':label,'started_at_utc':s.now(),'qualified':False,
                'phase_seconds':{'quiet':self.monotonic()-quiet_start}}
        for kind in ('p85','c1'):
            record[kind],record['phase_seconds'][kind]=self._read_one(label,kind)
        check(record['p85']['data']==[21,0,0],'P85 stock read plane did not reproduce')
        check(record['c1']['data']==[0,0,96],'Stock C1 did not reproduce')
        if label=='return15':
            self.explicit_return_verified=True
            self.report['explicit15_readback_and_stock_c1_verified']=True
        hold_started=self.monotonic()
        begin=self.mark(label.upper()+'_HOLD_BEGIN')
        record['hold_start_utc']=s.now();record['hold_start_monotonic']=self.monotonic()
        camera_start=self.metadata(label+'-hold-start')
        self.sleep(base.HOLD)
        camera_end=self.metadata(label+'-hold-end')
        record['hold_end_utc']=s.now();record['hold_end_monotonic']=self.monotonic()
        end=self._marker(label.upper()+'_HOLD_END')
        plan=env.hold_end_envelope(uuid.uuid4().hex[:12],self.ops['verify'],end)
        data=self.envelope(plan,label+'-hold-end')
        validation=self.monotonic()
        s.qualify_quiet(data['KERNEL'],begin,end,self.reference)
        env.validate_state(data,3600,self.before['boot_id'])
        frames=camera_end['frame_count']-camera_start['frame_count']
        check(frames>=120,'Insufficient advancing sensor frames for central-window review')
        self._timing(label+'-hold-end',validation,'host_validation')
        record['phase_seconds']['hold_and_metadata']=self.monotonic()-hold_started
        record.update(qualified=True,hold_seconds=base.HOLD,observed_sensor_frames=frames,
            stable_encoded_frames=None,camera_start=camera_start,camera_end=camera_end,
            hold_markers={'begin':begin,'end':end},elapsed_seconds=self.monotonic()-started)
        self.panel_uncertain=False;self.report['stages'].append(record);self._persist('stage-'+label)
        record['elapsed_seconds']=self.monotonic()-started  # Includes the completed stage save.
        if label=='baseline':
            rc,image,err=self.g.shell(self.camera,'screencap -p',15)
            check(rc==0 and not err and image.startswith(b'\x89PNG\r\n\x1a\n'),'Camera review screenshot unavailable')
            path=self.private/'baseline-camera-review.png'
            with path.open('xb') as stream:stream.write(image)
            path.chmod(0o600)
            self.report['baseline_review_image_sha256']=hashlib.sha256(image).hexdigest()
            self.report['baseline_review_image_private_label']=path.name;self._persist('baseline-image')
        return record

    def write_stage(self,label):
        check(label in ('sham15','return15'),'Candidate disabled in batching adapter')
        check(not self.panel_uncertain and not self.pending_read and not self.inflight,'No DSI into uncertainty')
        started=self.monotonic();nonce=self.child_nonce('writer')
        self.quiet(label+'_PRE',3600)
        check(self._last_quiet_kernel is not None and 'PWM_P85_WRITE_'+nonce not in self._last_quiet_kernel,
              'Writer marker collision/unqualified quiet')
        self.pending_read=True;self.panel_uncertain=True
        self.report['register85_writes_attempted'].append(label);self._persist('before-write-'+label)
        begin=self._marker(label.upper()+'_WRITE_BEGIN');end=self._marker(label.upper()+'_WRITE_END')
        plan=env.child_envelope(nonce,self.ops['verify'],self.token,label,begin,end,self.tmp)
        data=self.envelope(plan,label+'-write')
        validation=self.monotonic()
        p85.validate_write_capture(data['CHILD'],nonce,label)
        p85.validate_write_wire(data['KERNEL'],begin,end,label,self.reference)
        env.validate_state(data,3600,self.before['boot_id'])
        check(data['ESD'].strip()=='reg_read','Independent ESD read not stock')
        self._timing(label,validation,'host_validation')
        self.pending_read=False
        record={'stage':label,'standalone_callbacks':3,
            'native_and_wire_gates':True,'elapsed_seconds':self.monotonic()-started}
        self.report.setdefault('writes',[]).append(record)
        self._persist('after-write-'+label)
        record['elapsed_seconds']=self.monotonic()-started  # Next ordinary save persists this final bound.

    def arm_candidate(self):raise ValueError('Candidate disabled until same-version batched timing qualification and reviewed admission')

    def restore(self):
        check(not self.panel_uncertain and not self.pending_read and not self.inflight and not self.recovery_failed,
              'No envelope cleanup before verified recovery/state')
        for record in self.envelopes:
            if not record['cleaned']:
                # Exact known shell-owned paths only; no wildcard or unrelated files.
                self.shell(env.remnant_cleanup(record['work'],record['owner_digest']),label='envelope-remnant-cleanup')
                record['cleaned']=True
        super().restore()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=int);parser.add_argument('camera',type=int)
    parser.add_argument('--stock-only',action='store_true',required=True)
    parser.add_argument('--experiment-id',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();s.plan(args.experiment_id)
    check(args.target>0 and args.camera>0 and args.target!=args.camera,'Bad transports')
    private=Path.home()/'.cache/legion-y70-p85-batched'/args.experiment_id
    check(not args.output.exists() and not private.exists(),'Fresh output/private directories required')
    command_bounds=env.size_preflight()
    provenance=base.source_provenance(paths=SOURCE_FILES,require_clean=args.execute)
    provenance['envelope_command_size_preflight']=command_bounds
    if not args.execute:
        print(json.dumps({**provenance,'offline_only':True,'candidate_enabled':False,
            'adapter':'p85-batched-stock-v1','child_scripts':'unchanged','pwm_hz':None},indent=2));return
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.mkdir()
    private.parent.mkdir(parents=True,exist_ok=True,mode=0o700);private.mkdir(mode=0o700);private.chmod(0o700)
    from guarded_adb_socket import GuardedADB
    run=BatchedTrial(GuardedADB(),args.target,args.camera,args.experiment_id,args.output,private)
    run.report.update(provenance)
    owner=private/'owner.txt';owner.write_text(run.token+'\n');owner.chmod(0o600)
    def abort(signum,frame):raise KeyboardInterrupt('Termination requested')
    for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(signum,abort)
    run.save();run.execute()
    print(json.dumps({'status':run.report['status'],'candidate_enabled':False,'pwm_hz':None},indent=2))


if __name__=='__main__':main()
