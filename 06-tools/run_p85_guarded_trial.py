#!/usr/bin/env python3
"""Staged coordinator-only runner. DEFAULT offline; --execute is explicit.

--stock-only: baseline, same-value85=15 sham, explicit15 return, one video.
--candidate: requires reviewed successful stock-only run and a fresh lead review
of this run's baseline. Unknown14 may damage the panel before watchdog/reboot.
No frequency claim; optical return remains unverified until offline video review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

import p85_guarded_trial as p85
import stock_c1_sweep as s
from camera_capture_metadata import validate_capture
from run_dsi_mode_trial import new_camera_video

check=s.check
q=shlex.quote
HOLD=4.5
PROFILE={'exposure_ns':100000,'iso':6400,'focus_diopters':2.03874850,
         'crop':(0,0,4080,3072),'zoom':1.0,'camera_id':'0','expected_fps':30.0}


SOURCE_FILES=tuple('06-tools/'+name+'.py' for name in (
    'run_p85_guarded_trial','p85_guarded_trial','stock_c1_sweep','capture_ddic_c1',
    'p85_single_bit_plan','dsi_trial_transaction','a9_reproduction',
    'camera_capture_metadata','run_dsi_mode_trial','guarded_adb_socket'))


def source_provenance(root=None, paths=SOURCE_FILES, *, require_clean=False):
    """Pin only the ten used executable sources, never unrelated artifacts/logs."""
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    commit=git('rev-parse','--verify','HEAD')
    check(re.fullmatch(r'[0-9a-f]{40,64}',commit),'Invalid source commit')
    rows=git('ls-tree',commit,'--',*paths).splitlines();blobs={}
    for row in rows:
        match=re.fullmatch(r'[0-7]+ blob ([0-9a-f]{40,64})\t(.+)',row)
        check(match is not None and match[2] in paths,'Unexpected source tree entry')
        blobs[match[2]]=match[1]
    actual=git('hash-object','--',*paths).splitlines()
    check(len(actual)==len(paths),'Incomplete source content identities')
    diff=subprocess.run(['git','-C',str(root),'diff','--quiet',commit,'--',*paths],capture_output=True,timeout=10)
    check(diff.returncode in (0,1),'Source diff failed')
    clean=(set(blobs)==set(paths) and dict(zip(paths,actual))==blobs and diff.returncode==0)
    check(not require_clean or clean,'Relevant runner/helpers differ from recorded commit; commit reviewed sources before live I/O')
    return {'source_commit':commit,'source_blob_ids':blobs,
            'source_worktree_clean_for_runner':clean,'source_tracked_paths':list(paths)}


def validate_video_probe(probe, minimum_duration):
    streams=probe.get('streams',[])
    check(len(streams)==1,'Require one video stream and no audio/extra streams')
    video=streams[0]
    check(video.get('codec_type')=='video' and video.get('codec_name')=='h264' and
          (video.get('width'),video.get('height'))==(1280,720),'Encoded video profile changed')
    rate=video.get('avg_frame_rate','').split('/')
    check(len(rate)==2 and all(x.isdigit() for x in rate) and int(rate[1])>0,'Missing encoded frame rate')
    fps=int(rate[0])/int(rate[1]);duration=float(probe.get('format',{}).get('duration','0'))
    check(29<=fps<=31 and minimum_duration<=duration<600,'Encoded duration/frame rate unqualified')
    return {'codec':'h264','size':[1280,720],'audio_streams':0,'encoded_average_fps':fps,
            'duration_seconds':duration,'pwm_hz':None}


def qualification(path):
    """Lead-authored optical review must identify exact unmodified stock report."""
    review=json.loads(Path(path).read_text())
    check(review.get('schema')=='p85-stock-review-v1' and review.get('stock_optics_restored') is True
          and review.get('sham_optics_unchanged') is True and review.get('lead_approved') is True
          and review.get('central_stable_encoded_frames',0)>=60 and review.get('timestamp_margins_reviewed') is True,
          'Missing stock/sham optical qualification')
    raw=Path(review['run_report']).read_bytes()
    check(hashlib.sha256(raw).hexdigest()==review.get('run_sha256'),'Stock report changed')
    run=json.loads(raw)
    check(run.get('scope')=='p85-stock-only' and run.get('status')=='awaiting_optical_review'
          and run.get('module_sha256')==s.MODULE_SHA and run.get('camera_stopped_verified') is True
          and run.get('original_settings_dbv_logger_restored') is True
          and run.get('watchdog_disarmed') is True and run.get('mutex_released') is True,
          'Stock-only restoration/identity incomplete')
    check(run.get('video_profile',{}).get('codec')=='h264' and
          run.get('video_profile',{}).get('audio_streams')==0,'Encoded video not qualified')
    check(run.get('source_worktree_clean_for_runner') is True and
          set(run.get('source_blob_ids',{}))==set(SOURCE_FILES),'Stock source provenance missing')
    stages=run.get('stages',[])
    check([x.get('label') for x in stages]==['baseline','sham15','return15'], 'Wrong stock sequence')
    for stage in stages:
        check(stage.get('p85',{}).get('data')==[21,0,0] and stage.get('c1',{}).get('data')==[0,0,96]
              and stage.get('observed_sensor_frames',0)>=120 and stage.get('qualified') is True,
              'Unqualified stock stage')
    latency=max(x['elapsed_seconds'] for x in stages)
    check(2*latency+10<45,'Stock measurement latency cannot fit candidate/return budget')
    return {'report_sha256':review['run_sha256'],'max_stage_seconds':latency,
            'reviewed_optics':True,'source_blob_ids':run['source_blob_ids']}


def short_watchdog(tmp,token,boot):
    # Fixed60s, separate immutable arm. No renewal/extend interface.
    check(re.fullmatch(r'/data/local/tmp/[a-z][a-z0-9_]{7,63}',tmp), 'Bad watchdog path')
    check(re.fullmatch(r'[A-Za-z0-9_.-]{8,128}',token), 'Bad owner')
    check(re.fullmatch(r'[0-9a-f-]{36}',boot),'Bad boot')
    body=(f'sleep 60; if test -d {tmp}/candidate_armed && '
          f'test "$(cat {s.c1.LOCK}/owner)" = {q(token)} && '
          f'test "$(cat /proc/sys/kernel/random/boot_id)" = {q(boot)}; then /system/bin/reboot; fi')
    return (f'set -eu; umask 077; mkdir {tmp}/candidate_armed; '
            f'nohup /system/bin/sh -c {q(body)} >{tmp}/candidate-watchdog.log 2>&1 </dev/null & '
            f'pid=$!; printf "%s\\n" "$pid" >{tmp}/candidate-watchdog.pid; kill -0 "$pid"')


class Trial(s.Sweep):
    def __init__(self,adb,target,camera,experiment_id,out,private,*,candidate=False,
                 qualification_record=None,review_file=None,**kwargs):
        super().__init__(adb,target,experiment_id,out,private,**kwargs)
        check(camera>0 and camera!=target,'Distinct camera transport required')
        self.camera=camera;self.candidate=candidate;self.review_file=Path(review_file) if review_file else None
        self.marker='PWM_P85_'+experiment_id
        self.report={**self.report,'scope':'p85-candidate14' if candidate else 'p85-stock-only',
                     'marker':self.marker,'stages':[],'qualification':qualification_record,
                     'unknown_register_writes':False,'unknown_value_write_attempted':False,
                     'candidate_attempts':0,'register85_writes_attempted':[],'camera_touched':True,
                     'limit':'No physical Hz or optical recovery conclusion from this runner.'}
        self.report.pop('points',None)
        self.child_records=[]
        self.camera_serial=None;self.recording=False;self.last_camera=None
        self.short_armed=False;self.short_started=None;self.candidate_started=None
        self.candidate_attempts=0;self.explicit_return_verified=False;self.files_before=None
        self.cam_xml_owned=False
        self.panel_uncertain=False
        self.observation_failed=False;self.observation_in_progress=False

    def child_nonce(self,kind):
        check(kind in ('p85','c1','writer'),'Unsupported child kind')
        nonce=uuid.uuid4().hex[:12]
        # ALL three builders intentionally retain the audited C1 namespace.
        record={'kind':kind,'nonce':nonce,'work':'/data/local/tmp/pwm-c1-'+nonce,
                'group':'pwm_c1_'+nonce}
        self.child_records.append(record);self.nonces.append(nonce)
        return nonce

    def restore(self):
        check(not self.panel_uncertain,'No ordinary restoration into unqualified panel state')
        check([x['nonce'] for x in self.child_records]==self.nonces,'Untracked child cleanup')
        for child in self.child_records:
            nonce=child['nonce']
            check(child['kind'] in ('p85','c1','writer') and re.fullmatch(r'[a-f0-9]{12}',nonce)
                  and child['work']=='/data/local/tmp/pwm-c1-'+nonce
                  and child['group']=='pwm_c1_'+nonce,'Unexpected child cleanup namespace')
        check(not self.pending_read and not self.inflight and not self.recovery_failed,
              'No file cleanup before verified transaction/recovery')
        for child in self.child_records:
            if child['kind']=='writer':
                paths=' '.join(q(child['work']+'/'+name) for name in p85.WRITER_GATE_FILES)
                verify='; '.join('test ! -e '+q(child['work']+'/'+name) for name in p85.WRITER_GATE_FILES)
                self.shell(self.ops['verify']+'; rm -f '+paths+'; '+verify,root=True,label='remove-owned-writer-snapshots')
        # Sweep.restore checks/removes exactly these known C1 work/probe paths,
        # including remnants after a verified reboot. Never guess alternate paths.
        super().restore()

    def shell(self,command,**kwargs):
        if self.candidate_started is not None and not self.explicit_return_verified:
            remaining=45-(self.monotonic()-self.candidate_started)
            check(remaining>8,'Candidate deadline: reboot only')
            kwargs['timeout']=min(kwargs.get('timeout',25),remaining-8)
        return super().shell(command,**kwargs)

    def cam(self,command,label,timeout=15):
        if self.candidate_started is not None and not self.explicit_return_verified:
            remaining=45-(self.monotonic()-self.candidate_started)
            check(remaining>8,'Candidate deadline: reboot only')
            timeout=min(timeout,remaining-8)
        self.event+=1;stem=f'{self.event:04d}-camera-{label}'
        rc,out,err=self.g.shell(self.camera,command,timeout)
        for suffix,data in (('stdout',out),('stderr',err)):
            path=self.private/(stem+'.'+suffix)
            with path.open('xb') as f:f.write(data)
            path.chmod(0o600)
        check(rc==0,'Camera command failed; no retry')
        return out.decode(errors='replace').strip()

    def camera_ui(self):
        path='/data/local/tmp/'+self.plan['experiment_id']+'-camera.xml'
        if not self.cam_xml_owned:
            self.cam('test ! -e '+q(path),'fresh-ui-path')
            self.cam_xml_owned=True
        return ET.fromstring(self.cam('uiautomator dump '+q(path)+' >/dev/null && cat '+q(path),'ui'))

    def cleanup_camera_xml(self):
        if not self.cam_xml_owned:return
        check(not self.recording,'Camera stop uncertain: retain owned UI XML')
        path='/data/local/tmp/'+self.plan['experiment_id']+'-camera.xml'
        self.cam('rm -f '+q(path)+'; test ! -e '+q(path),'remove-owned-ui')
        self.cam_xml_owned=False
        self.report['camera_ui_temp_removed']=True

    def camera_tap(self,label):
        nodes=[n for n in self.camera_ui().iter('node') if n.get('content-desc')==label]
        check(len(nodes)==1,'Camera control missing/ambiguous')
        bounds=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',nodes[0].get('bounds',''))
        check(bounds is not None,'Bad camera control bounds')
        a,b,c,d=map(int,bounds.groups());check(c>a and d>b,'Empty control')
        self.cam(f'input tap {(a+c)//2} {(b+d)//2}','tap')

    def metadata(self,label):
        begin=self.monotonic();begin_utc=s.now()
        raw=self.cam('dumpsys media.camera',label)
        end=self.monotonic();end_utc=s.now()
        result=validate_capture(raw,
            previous=self.last_camera if self.recording else None,**PROFILE,
            expected_size=(1280,720) if self.recording else None,require_recording=self.recording)
        result.update(host_call_start_utc=begin_utc,host_call_end_utc=end_utc,host_call_elapsed_seconds=end-begin)
        result['host_capture_bounds']={'begin_monotonic':begin,'end_monotonic':end,
            'begin_utc':begin_utc,'end_utc':end_utc,
            'limit':'Call bounds only, not synchronized sensor/encoded PTS or per-frame metadata.'}
        if self.recording:
            check(result['rolling_shutter_skew_ns']==15047630,'Recording skew changed')
            self.last_camera=result
        return result

    def camera_identity(self):
        check(self.cam('getprop ro.product.device; getprop ro.boot.hardware.sku; getprop ro.product.model','identity').splitlines()==['Galaga','ROW','A001'],'Wrong camera')
        check(re.search(r'\bversionName=1\.56\.2(?:\s|$)',self.cam('dumpsys package net.sourceforge.opencamera','package')),'Wrong camera version')

    def setup(self):
        self.g.preflight();self.serial=self.g.bind(self.target);self.camera_serial=self.g.bind(self.camera)
        check(self.serial!=self.camera_serial,'Devices are not distinct')
        self.report['physical_operation_attempted']=True
        self.identity();self.camera_identity();self.metadata('preflight')
        ui=list(self.camera_ui().iter('node'))
        check(any(n.get('content-desc')=='Switch to front camera' for n in ui),'Rear camera required')
        check(any(n.get('content-desc')=='Start recording video' for n in ui),'Camera must not already record')
        log=self.shell('dmesg',root=True,label='prior-kernel')
        check(self.marker not in log,'Marker already used')
        self.shell(self.ops['acquire'],root=True,label='acquire-owner');self.locked=True
        self.before={key:self.shell('settings get system '+key,label='before-setting') for key in s.KEYS}
        check(self.before['screen_brightness_mode']=='0','Require manual brightness')
        self.before['native_dbv']=int(self.shell('cat '+s.BL+'brightness',root=True,label='before-dbv'))
        check(460<=self.before['native_dbv']<=16180,'Unexpected original DBV')
        self.before['logger']=s.logger_value(self.shell('cat '+s.CON+'mipi_cmd_log_en',root=True,label='before-logger'))
        self.before['boot_id']=self.shell('cat /proc/sys/kernel/random/boot_id',label='before-boot')
        self.state(self.before['native_dbv'])
        self.report['before']={k:v for k,v in self.before.items() if k!='boot_id'}
        self.shell(f'test ! -e {self.tmp}',root=True,label='fresh-temp')
        self.temp=True
        self.shell(f'set -eu; umask 077; mkdir -m 700 {self.tmp}; mkdir -m 700 {self.tmp}/debugfs',root=True,label='create-temp')
        check(self.shell(s.esd_read_script(self.tmp),root=True,label='initial-esd')=='reg_read','ESD not stock')
        self.armed=True
        self.shell(s.watchdog_command(self.tmp,self.token,self.before['boot_id']),root=True,label='overall-watchdog')
        self.report['watchdog_state']='armed_verified'
        self.changed=True
        self.shell("printf '1\\n' > "+s.CON+'mipi_cmd_log_en',root=True,label='enable-logger',mutation=True)
        self.shell('settings put system screen_off_timeout '+str(s.setup_timeout(self.before['screen_off_timeout'])),label='extend-timeout',mutation=True)
        self.shell('input keyevent 3',label='home',mutation=True)
        self.shell('am start -W --activity-clear-top -n '+q('com.android.settings/.Settings$DisplaySettingsActivity'),label='display-settings',mutation=True)
        policy=self.shell('dumpsys window policy',label='awake')
        check(all(x in policy for x in ('screenState=SCREEN_STATE_ON','interactiveState=INTERACTIVE_STATE_AWAKE','mIsShowing=false')),'Display not awake/unlocked')
        self.anchor(3600)
        check(self.reference['native_actual_hz']==120 and self.reference['native_group']==3,'Actual120 required')
        self.files_before=self.cam("find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'",'files-before')
        self.recording=True  # An uncertain tap requires camera cleanup, not another start.
        self.report['recording_start_host_bounds']={'begin_monotonic':self.monotonic(),'begin_utc':s.now()}
        self.camera_tap('Start recording video')
        self.report['recording_start_host_bounds'].update(end_monotonic=self.monotonic(),end_utc=s.now())
        first=self.metadata('recording-first');self.sleep(.25);second=self.metadata('recording-second')
        self.report['recording_preflight']=[first,second];self.save()

    def observe_stage(self,label):
        check(not self.pending_read and not self.inflight and not self.observation_failed
              and not self.observation_in_progress,'No observation retry into uncertainty')
        self.observation_in_progress=True
        try:return self._observe_stage(label)
        except BaseException:
            self.observation_failed=True;self.panel_uncertain=True
            raise
        finally:self.observation_in_progress=False

    def _observe_stage(self,label):
        self.panel_uncertain=True
        started=self.monotonic()
        self.quiet(label,3600)
        record={'label':label,'started_at_utc':s.now(),'qualified':False,'phase_seconds':{}}
        for kind,builder,validator in (
            ('p85',lambda n:p85.long3_reader(n,self.token),lambda raw,n:p85.validate_long3(raw,n)),
            ('c1',lambda n:p85.bounded_c1_reader(n,self.token),lambda raw,n:s.validate_adapter_capture(raw,n,3600))):
            phase_started=self.monotonic()
            nonce=self.child_nonce(kind)
            self.pending_read=True
            begin=self.mark(label.upper()+'_'+kind.upper()+'_BEGIN')
            raw=self.shell(builder(nonce),root=True,label=label+'-'+kind,timeout=40)
            record[kind]=validator(raw+'\n',nonce)
            end=self.mark(label.upper()+'_'+kind.upper()+'_END')
            s.verify_read_interval(self.shell('dmesg',root=True,label='read-wire'),begin,end,self.reference)
            self.state(3600)
            check(self.shell(s.esd_read_script(self.tmp),root=True,label='read-esd')=='reg_read','ESD not restored')
            self.pending_read=False
            record['phase_seconds'][kind]=self.monotonic()-phase_started
        expected=[20,0,0] if label=='candidate14' else [21,0,0]
        check(record['p85']['data']==expected,'P85 read plane not expected; no retry/latch')
        if label!='candidate14':check(record['c1']['data']==[0,0,96],'Stock C1 not reproduced')
        if label=='return15':
            # Exact15 TX + qualified15 AND stock C1, native/DBV/ESD precede disarm.
            # Full optical hold/return review is still mandatory afterward.
            self.explicit_return_verified=True
            self.report['explicit15_readback_and_stock_c1_verified']=True
            if self.short_armed:self.disarm_short()
        hold_started=self.monotonic()
        begin=self.mark(label.upper()+'_HOLD_BEGIN')
        record['hold_start_utc']=s.now();record['hold_start_monotonic']=self.monotonic()
        camera_start=self.metadata(label+'-hold-start')
        self.sleep(HOLD)
        camera_end=self.metadata(label+'-hold-end')
        record['hold_end_utc']=s.now();record['hold_end_monotonic']=self.monotonic()
        end=self.mark(label.upper()+'_HOLD_END')
        s.qualify_quiet(self.shell('dmesg',root=True,label='hold-kernel'),begin,end,self.reference)
        self.state(3600)
        frames=camera_end['frame_count']-camera_start['frame_count']
        check(frames>=120,'Insufficient advancing sensor frames for central-window review')
        record['phase_seconds']['hold_and_metadata']=self.monotonic()-hold_started
        record.update(qualified=True,hold_seconds=HOLD,observed_sensor_frames=frames,
                      stable_encoded_frames=None,
                      camera_start=camera_start,camera_end=camera_end,
                      hold_markers={'begin':begin,'end':end},
                      elapsed_seconds=self.monotonic()-started)
        self.panel_uncertain=False
        self.report['stages'].append(record);self.save()
        if label=='baseline':
            rc,image,err=self.g.shell(self.camera,'screencap -p',15)
            check(rc==0 and image.startswith(b'\x89PNG\r\n\x1a\n'),'Camera review screenshot unavailable')
            with (self.private/'baseline-camera-review.png').open('xb') as f:f.write(image)
            (self.private/'baseline-camera-review.png').chmod(0o600)
            self.report['baseline_review_image_sha256']=hashlib.sha256(image).hexdigest()
            self.report['baseline_review_image_private_label']='baseline-camera-review.png';self.save()
        return record

    def write_stage(self,label):
        check(not self.panel_uncertain and not self.pending_read and not self.inflight,
              'No DSI into uncertainty')
        check(label in ('sham15','candidate14','return15'),'Wrong stage')
        started=self.monotonic()
        if label=='candidate14':
            check(self.candidate and self.short_armed and self.candidate_attempts==0,'Candidate not armed')
        nonce=self.child_nonce('writer')
        self.quiet(label+'_PRE',3600)
        log=self.shell('dmesg',root=True,label='write-marker-preflight')
        check('PWM_P85_WRITE_'+nonce not in log,'Write marker collision')
        self.pending_read=True;self.panel_uncertain=True;self.save()
        begin=self.mark(label.upper()+'_WRITE_BEGIN')
        self.report['register85_writes_attempted'].append(label)
        if label=='candidate14':
            self.candidate_attempts+=1
            self.report.update(candidate_attempts=self.candidate_attempts,candidate_may_be_active=True,
                               unknown_value_write_attempted=True,unknown_register_writes=True)
        self.save()
        raw=self.shell(p85.write_script(nonce,self.token,label),root=True,label=label+'-write',timeout=40)
        p85.validate_write_capture(raw+'\n',nonce,label)
        end=self.mark(label.upper()+'_WRITE_END')
        log=self.shell('dmesg',root=True,label='write-final-kernel')
        p85.validate_write_wire(log,begin,end,label,self.reference)
        self.state(3600)
        check(self.shell(s.esd_read_script(self.tmp),root=True,label='write-esd')=='reg_read','Write ESD not restored')
        self.pending_read=False
        self.report.setdefault('writes',[]).append({'stage':label,'standalone_callbacks':3,'native_and_wire_gates':True,'elapsed_seconds':self.monotonic()-started})
        self.save()

    def lead_review(self):
        check(self.review_file is not None and self.review_file.is_file(),'Fresh baseline lead review required; no candidate')
        review=json.loads(self.review_file.read_text())
        base=self.report['stages'][0]
        check(review.get('schema')=='p85-baseline-review-v1' and
              review.get('experiment_id')==self.plan['experiment_id'] and
              review.get('camera_session')==base['camera_end']['session_token'] and
              review.get('frame_count')==base['camera_end']['frame_count'] and
              review.get('review_image_sha256')==self.report.get('baseline_review_image_sha256') and
              review.get('roi_acceptable') is True and review.get('lead_approved') is True,
              'Lead review does not identify this baseline')

    def arm_candidate(self):
        self.lead_review();self.identity();self.camera_identity();self.state(3600)
        self.metadata('pre-candidate');self.quiet('CANDIDATE_ARM',3600)
        check(all(x['qualified'] for x in self.report['stages']) and
              [x['label'] for x in self.report['stages']]==['baseline','sham15'],'Pre-candidate sequence incomplete')
        check(2*max(x['elapsed_seconds'] for x in self.report['stages'])+10<45,'This run cannot fit45s budget')
        self.short_armed=True;self.short_started=self.monotonic()
        self.shell(short_watchdog(self.tmp,self.token,self.before['boot_id']),root=True,label='candidate-watchdog')
        self.candidate_started=self.short_started
        self.report['candidate_watchdog']='armed60s_no_renewal';self.save()

    def disarm_short(self):
        check(self.explicit_return_verified or self.report.get('recovery_reboot_verified'),
              'Never disarm candidate watchdog without verified15 return or changed boot')
        command=(self.ops['verify']+f'; if test -d {self.tmp}/candidate_armed; then rmdir {self.tmp}/candidate_armed; fi; '
                 f'test ! -e {self.tmp}/candidate_armed; pid=$(cat {self.tmp}/candidate-watchdog.pid); '
                 f'if test -r /proc/$pid/cmdline && tr "\\000" " " </proc/$pid/cmdline | grep -Fq {q(self.token)}; then kill "$pid"; fi; '
                 f'rm -f {self.tmp}/candidate-watchdog.pid {self.tmp}/candidate-watchdog.log')
        self.shell(command,root=True,label='disarm-candidate')
        self.short_armed=False;self.report['candidate_watchdog']='disarmed_after_verified_return_or_boot';self.save()

    def recover(self):
        # Deadline cannot inhibit recovery transport or read-only identity checks.
        self.candidate_started=None
        super().recover()
        self.panel_uncertain=False;self.observation_failed=False
        self.report['candidate_may_be_active']=(
            'unknown_after_reboot; DDIC recovery not guaranteed' if self.candidate_attempts else False)
        self.report['physical_ddic_recovery_unverified']=True

    def stop_camera(self):
        if not self.recording:return
        ui=list(self.camera_ui().iter('node'))
        if any(n.get('content-desc')=='Stop recording video' for n in ui):
            self.camera_tap('Stop recording video')
        check(any(n.get('content-desc')=='Start recording video' for n in self.camera_ui().iter('node')),'Camera stop not verified')
        self.recording=False;self.report['camera_stopped_verified']=True
        after=self.cam("find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'",'files-after')
        source=new_camera_video(self.files_before,after)
        size=int(self.cam('stat -c %s '+q(source),'video-size'))
        self.g.run(['adb','-t',str(self.camera),'pull',source,str(self.private/'capture.mp4')],timeout=90,check=True)
        check((self.private/'capture.mp4').stat().st_size==size and size>0,'Video transfer mismatch')
        result=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',
                               str(self.private/'capture.mp4')],capture_output=True,timeout=20,check=True)
        with (self.private/'video-probe.json').open('xb') as f:f.write(result.stdout)
        (self.private/'video-probe.json').chmod(0o600)
        self.report['video_profile']=validate_video_probe(json.loads(result.stdout),len(self.report['stages'])*HOLD)
        self.report['video_private_label']='capture.mp4';self.report['video_bytes']=size;self.save()

    def execute(self):
        error=None
        try:
            self.setup();self.observe_stage('baseline');self.write_stage('sham15');self.observe_stage('sham15')
            if self.candidate:
                self.report['awaiting_fresh_lead_review']=True;self.save()
                deadline=self.monotonic()+90
                while self.review_file is not None and not self.review_file.exists() and self.monotonic()<deadline:
                    self.sleep(.5)
                self.arm_candidate();self.write_stage('candidate14');self.observe_stage('candidate14')
            self.write_stage('return15');self.observe_stage('return15')
            self.explicit_return_verified=True
            self.report['explicit15_readback_and_stock_c1_return']=True
            if self.short_armed:self.disarm_short()
            self.report['status']='awaiting_optical_review'
        except BaseException as exc:
            error=exc;self.report.update(status='failed',error_type=type(exc).__name__)
            if self.panel_uncertain or self.pending_read or self.inflight or self.short_armed or self.report.get('candidate_may_be_active'):
                try:self.recover()
                except BaseException:pass
        finally:
            try:self.stop_camera()
            except BaseException as exc:
                self.report['camera_cleanup_error_type']=type(exc).__name__;error=error or exc
            try:self.cleanup_camera_xml()
            except BaseException as exc:
                self.report['camera_ui_cleanup_pending']=True;error=error or exc
            if not self.recovery_failed:
                try:
                    if self.short_armed:self.disarm_short()
                    self.restore()
                except BaseException as exc:
                    self.report['cleanup_error_type']=type(exc).__name__;error=error or exc
            if error:self.report['status']='failed; inspect recovery and retained watchdog/owner'
            self.report['finished_at_utc']=s.now();self.save()
        if error:raise RuntimeError('P85 trial incomplete; no automatic retry') from error
        return self.report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=int);parser.add_argument('camera',type=int)
    parser.add_argument('--experiment-id',required=True);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--stock-only',action='store_true');mode.add_argument('--candidate',action='store_true')
    parser.add_argument('--qualification',type=Path);parser.add_argument('--baseline-review',type=Path)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();s.plan(args.experiment_id)
    check(args.target>0 and args.camera>0 and args.target!=args.camera,'Bad transports')
    private=Path.home()/'.cache/legion-y70-p85-trial'/args.experiment_id
    check(not args.output.exists() and not private.exists(),'Fresh output/private directories required')
    provenance=source_provenance(require_clean=args.execute)
    reviewed=None
    if args.candidate:
        check(args.qualification is not None and args.baseline_review is not None,'Candidate qualification and fresh review path required')
        check(not args.baseline_review.exists(),'Fresh baseline review must be created after baseline')
        reviewed=qualification(args.qualification)
        check(reviewed['source_blob_ids']==provenance['source_blob_ids'],
              'Runner/helper source changed since qualified stock trial')
    p85.long3_reader('aabbccddeeff','offline_token')
    for stage in ('sham15','candidate14','return15'):p85.write_script('aabbccddeeff','offline_token',stage)
    if not args.execute:
        print(json.dumps({**provenance,'offline_only':True,'mode':'candidate14' if args.candidate else 'stock-only',
                          'hold_seconds':HOLD,'minimum_observed_sensor_frames':120,'central_encoded_frames_require_review':60,'candidate_watchdog_seconds':60,
                          'live_qualification':'not performed','pwm_hz':None},indent=2));return
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.mkdir()
    private.parent.mkdir(parents=True,exist_ok=True,mode=0o700);private.mkdir(mode=0o700);os.chmod(private,0o700)
    from guarded_adb_socket import GuardedADB
    run=Trial(GuardedADB(),args.target,args.camera,args.experiment_id,args.output,private,
              candidate=args.candidate,qualification_record=reviewed,review_file=args.baseline_review)
    run.report.update(provenance)
    (private/'owner.txt').write_text(run.token+'\n');(private/'owner.txt').chmod(0o600)
    def abort(signum,frame):raise KeyboardInterrupt('Termination requested')
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,abort)
    run.save();run.execute()
    print(json.dumps({'status':run.report['status'],'report':str(args.output/'run.json'),'pwm_hz':None},indent=2))


if __name__=='__main__':main()
