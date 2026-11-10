"""Separate finite observation coordinator, OFFLINE-reviewed API only.

No CLI/import side effects, no Trial inheritance. Construction/source binding,
native-mode/scene/geometry receipt producer and real UI matching remain unadmitted.
Use only byte-bound dependencies and existing-server OfflineBaselineADB supplied
by the reviewed launcher. Tests supply synthetic transport, never devices.
"""
import hashlib
from dataclasses import asdict
import json
import os
import re
import shlex
import stat
import xml.etree.ElementTree as ET
from protocol_v2 import SCHEMA, WINDOWS, PriorGeometryReview, need

PROFILE = dict(exposure_ns=100000, iso=6400, focus_diopters=2.0387485,
               crop=(0,0,4080,3072), zoom=1.0, camera_id='0', expected_fps=30.0)
BL='/sys/class/backlight/panel0-backlight/brightness'
FILES="find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'"
UUID=r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
DURATION='Maximum duration of video'
RESTART='Restart video after max duration'
FILE_RESTART='Restart on maximum file size'
VIDEO_SETTINGS='Video settings…'


def normal_camera_launch(text):
    """Narrow current ActivityRecord intent check; unknown dump layouts reject.

    Main-launch requirement prevents ACTION_VIDEO_CAPTURE duration extras from
    silently overriding the finite UI preference. No activity launch/reset here.
    """
    need(type(text) is str and len(text)<=8*1024*1024,'camera activity dump')
    resumed=re.findall(r'^\s*mResumedActivity:\s*ActivityRecord\{([a-f0-9]+)\s+u[0-9]+\s+(net\.sourceforge\.opencamera/(?:\.MainActivity|net\.sourceforge\.opencamera\.MainActivity))\s+t[0-9]+[^}]*\}',text,re.M)
    need(len(resumed)==1,'current Open Camera activity missing')
    markers=list(re.finditer(r'^\s*\* Hist #[0-9]+: ActivityRecord\{([a-f0-9]+)\s+u[0-9]+\s+([^\s}]+)\s+t[0-9]+[^}]*\}[^\n]*$',text,re.M))
    selected=[i for i,m in enumerate(markers) if (m[1],m[2])==resumed[0]]
    need(len(selected)==1,'current camera activity block ambiguous')
    i=selected[0];block=text[markers[i].end():markers[i+1].start() if i+1<len(markers) else None]
    intents=re.findall(r'^\s*Intent \{([^\n}]*)\}\s*$',block,re.M)
    need(len(intents)==1,'current camera Intent unavailable')
    intent=intents[0]
    actions=re.findall(r'(?:^|\s)act=([^\s]+)',intent)
    components=re.findall(r'(?:^|\s)cmp=([^\s]+)',intent)
    need(actions==['android.intent.action.MAIN'] and components==[resumed[0][1]] and
         'cat=[android.intent.category.LAUNCHER]' in intent and
         '(has extras)' not in intent and 'extras=' not in intent,
         'camera launch override or nonstandard intent')
    pending=re.findall(r'^\s*(?:mPendingNewIntents|pendingNewIntents|mNewIntents|newIntents)=(.*)$',block,re.M)
    need(all(x.strip() in ('null','[]') for x in pending),'pending new camera Intent')
    return {'component':resumed[0][1],'action':'android.intent.action.MAIN',
            'pending_intents_field_observed':bool(pending),
            'no_pending_new_intents_observed':True,'pending_intent_absence_proven':False,
            'activity_dump_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'duration_intent_override_absent':True}


def classify_camera_ui(tree):
    """Only explicitly recognized Open Camera levels; unknown never gets Back."""
    state={'level':'unknown','dialog':None,'filesize_switch':None}
    if tree.tag!='hierarchy':return state
    nodes=list(tree.iter('node'))
    def found(key,value):return [n for n in nodes if n.get(key)==value]
    alerts=found('resource-id','android:id/alertTitle')
    choices=[n for n in nodes if n.get('class')=='android.widget.CheckedTextView' and n.get('checkable')=='true']
    if alerts or choices:
        selected=[n for n in choices if n.get('checked')=='true']
        if len(alerts)==1 and alerts[0].get('text') in (DURATION,RESTART) and len(selected)==1:
            return dict(state,level='option_dialog',dialog=alerts[0].get('text'))
        return state
    starts=found('content-desc','Start recording video');stops=found('content-desc','Stop recording video')
    settings=found('content-desc','Settings')
    if len(starts)==len(settings)==1 and not stops and all(n.get('enabled')=='true' for n in starts+settings):
        return dict(state,level='preview')
    if starts or stops:return state
    durations=found('text',DURATION);restarts=found('text',RESTART)
    if len(durations)==len(restarts)==1 and all(n.get('enabled')=='true' for n in durations+restarts):
        state['level']='video_settings'
        labels=found('text',FILE_RESTART)
        if len(labels)==1:
            parents={c:p for p in tree.iter() for c in p};row=labels[0]
            while row.get('clickable')!='true' and row in parents:row=parents[row]
            switches=[n for n in row.iter('node') if n.get('checkable')=='true']
            if len(switches)==1 and switches[0].get('checked') in ('true','false'):
                state['filesize_switch']=switches[0].get('checked')=='true'
        return state
    video=found('text',VIDEO_SETTINGS)
    if len(video)==1 and video[0].get('enabled')=='true' and not durations and not restarts:
        return dict(state,level='main_settings')
    return state


class PreviewEncoderPending(ValueError):
    def __init__(self):super().__init__('not verified preview: residual encoder stream')


class Coordinator:
    def __init__(self, *, transport, target, camera, serials, parser, readonly,
                 lock_commands, new_camera_video, native_state, inspection, owned_directory, retained_sink,
                 source, token, clock, sleep, byte_cap):
        need(type(target) is str and type(camera) is str and
             re.fullmatch('[1-9][0-9]*', target) and re.fullmatch('[1-9][0-9]*',camera)
             and target != camera, 'distinct role aliases required')
        need(type(serials) is tuple and len(set(serials))==2 and all(type(s) is bytes for s in serials),
             'immutable roles required')
        need(type(byte_cap) is int and 0<byte_cap<=256*1024*1024,'explicit finite media cap')
        need(type(source) is dict and set(source)=={'commit','closure_sha256'} and
             re.fullmatch('[a-f0-9]{40}',str(source['commit'])) and
             re.fullmatch('[a-f0-9]{64}',str(source['closure_sha256'])),'source closure required')
        need(re.fullmatch('[a-z][a-z0-9_]{7,63}',token),'owned namespace required')
        self.g,self.ids,self.serials=transport,{'target':target,'camera':camera},serials
        self.parser,self.ro,self.ops,self.video=parser,readonly,lock_commands(token),new_camera_video
        self.parse_native=native_state;self.mode_lines=None;self.inspection=inspection
        self.dispatch_evidence=None;self.prior_review=None;self.acquisition_attempted=False
        self.owned,self.retained,self.source=owned_directory,retained_sink,source
        self.clock,self.sleep,self.cap,self.token=clock,sleep,byte_cap,token
        self.spent=False; self.locked=False; self.changed=False; self.start=None
        self.stopped=False; self.before=None; self.boots=None; self.counter=0
        self.preferences=[]; self.xml_paths=[]; self.switch_original=None; self.records={}
        self.ui_restore_pending=False;self.ui_transition=None;self.ui_transition_uncertain=False
        self.original_preview_verified=False;self.original_preview_signature=None
        self.report={'schema':SCHEMA,'source':source,'status':'not_started','windows':WINDOWS,
                     'candidate_attempts':0,'custom_dsi_writes':0,'pwm_hz':None}

    def persist(self, label, data):
        need(re.fullmatch('[a-z0-9_-]+',label),'private label')
        self.counter+=1
        self.owned.deadline=self.clock()+5; self.owned.verify()
        raw=json.dumps(data,sort_keys=True).encode()
        name=f'{self.counter:04d}-{label}.json'
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.owned.fd)
        try:
            st=os.fstat(fd)
            need(st.st_mode==stat.S_IFREG|0o600 and st.st_nlink==1 and
                 st.st_uid==self.owned.identity[2],'private evidence inode')
            view=memoryview(raw)
            while view:
                n=os.write(fd,view);need(n>0,'private evidence short write');view=view[n:]
        finally: os.close(fd)
        self.records[label]={'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        return self.records[label]

    def shell(self, role, command, *, timeout=5, root=False):
        if root: command='su -c '+shlex.quote(command)
        rc,out,err=self.g.shell(self.ids[role],command,timeout)
        need(rc==0 and type(out) is bytes and not err and len(out)<=8*1024*1024,
             'operation failed; no retry')
        return out.decode('utf-8','strict').strip()

    def query(self, role, operation):
        need(operation in self.ro.COMMANDS and role in self.ro.ROLES[operation], 'readonly allowlist')
        return self.shell(role,self.ro.COMMANDS[operation])

    def read_boots(self):
        result={r:self.query(r,'boot') for r in self.ids}
        need(all(re.fullmatch(UUID,x) for x in result.values()),'boot identity')
        return result

    def target_state(self):
        need(self.read_boots()==self.boots,'role boot changed')
        values=self.query('target','settings').splitlines()
        need(len(values)==5 and all(re.fullmatch(r'null|[0-9]{1,8}(?:\.[0-9]{1,6})?',x)
                                  for x in values),'original settings format')
        n=self.query('target','native').splitlines()
        need(len(n)==4 and all(re.fullmatch('[0-9]{1,8}',x) for x in n[:3]),'native shape')
        log=re.fullmatch(r'[^\n]*:\s*([01])',n[3]);need(log is not None,'logger shape')
        result={'settings':dict(zip(self.ro.KEYS,values)),'native_dbv':int(n[0]),
                'bl_power':int(n[1]),'panel_dc':int(n[2]),'logger':int(log[1])}
        need(result['bl_power']==result['panel_dc']==result['logger']==0,'stock state mismatch')
        need(result['settings']['screen_brightness_mode']=='0','manual mode required')
        need(460<=result['native_dbv']<=16180,'native DBV range')
        need(tuple(self.query('target','target_identity').splitlines())==self.ro.TARGET,'target identity')
        log=self.shell('target','dmesg',root=True)
        mode=self.parse_native(log)
        need(mode['native_actual_hz']==120 and mode['native_group']==3,'native120 required')
        lines=tuple(x for x in log.splitlines() if 'dsi_display_set_mode' in x and 'fps=' in x)
        if self.mode_lines is None:self.mode_lines=lines
        else:need(lines==self.mode_lines,'mode event changed or log retention lost')
        display=self.shell('target','dumpsys display')
        rates=re.findall(r'mActiveSfDisplayMode=[^\n]*peakRefreshRate=([0-9.]+)',display)
        need(len(rates)==1 and abs(float(rates[0])-120)<.03,'software120 required')
        return result

    def ui(self):
        # Unique, exclusively created owner sentinel for every dump. Never read
        # a pre-existing/stale XML; do not remove unrelated files.
        self.counter+=1
        p=f'/data/local/tmp/{self.token}_{self.counter}.xml'
        q=shlex.quote(p)
        self.shell('camera',f'set -eu; set -C; umask 077; printf pending > {q}')
        self.xml_paths.append(p)
        raw=self.shell('camera',f'set -eu; uiautomator dump {q} >/dev/null; cat {q}',timeout=3)
        tree=ET.fromstring(raw)
        need(tree.tag=='hierarchy' and all(n.get('package') in ('net.sourceforge.opencamera','android','')
             for n in tree.iter('node')),'camera UI package changed')
        return tree

    def observe_ui(self):
        tree=self.ui(); state=classify_camera_ui(tree)
        self.report['camera_ui_observed_level']=state['level']
        if self.ui_transition is not None and not self.ui_transition_uncertain:
            expected=self.ui_transition['expected']
            matched=(state['level']==expected if type(expected) is str else
                     state['level']=='option_dialog' and state['dialog']==expected[1]
                     if expected[0]=='option_dialog' else
                     state['level']=='video_settings' and state['filesize_switch'] is expected[1])
            if matched:self.ui_transition=None
        return state,tree

    def expect_ui(self, level, title=None):
        state,tree=self.observe_ui()
        need(not self.ui_transition_uncertain and self.ui_transition is None,
             'UI transition pending; read-only observation only')
        need(state['level']==level and (title is None or state['dialog']==title),'unexpected camera UI level')
        return tree

    def ui_action(self, command, expected):
        need(self.start is None or self.stopped,'no navigation while recording outcome unresolved')
        need(self.ui_transition is None and not self.ui_transition_uncertain,'no uncertain UI input retry')
        self.ui_restore_pending=True;self.original_preview_verified=False
        self.report['camera_ui_restore_pending']=True
        self.report['camera_ui_original_preview_verified']=False
        self.ui_transition={'expected':expected,'command_returned':False}
        self.ui_transition_uncertain=True  # latch BEFORE any input dispatch
        self.persist('ui-transition-intent',self.ui_transition)
        self.shell('camera',command,timeout=1)
        self.ui_transition['command_returned']=True
        self.ui_transition_uncertain=False
        self.observe_ui()
        need(self.ui_transition is None,'UI transition not yet observed')

    def click(self,node,*,transition_to=None):
        need(node.get('enabled')=='true','disabled control')
        m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.get('bounds',''))
        need(m is not None,'control bounds');a,b,c,d=map(int,m.groups())
        need(0<=a<c<=4096 and 0<=b<d<=4096,'control bounds range')
        command=f'input tap {(a+c)//2} {(b+d)//2}'
        if transition_to is not None:self.ui_action(command,transition_to)
        else:self.shell('camera',command,timeout=1)  # only the separately guarded recording Start

    def unique_node(self,tree,key,value):
        ns=[n for n in tree.iter('node') if n.get(key)==value]
        need(len(ns)==1,'control missing/ambiguous')
        return ns[0]

    def row(self,tree,title):
        n=self.unique_node(tree,'text',title)
        parents={c:p for p in tree.iter() for c in p}
        while n.get('clickable')!='true':
            need(n in parents,'preference row missing');n=parents[n]
        return n

    def verify_original_preview(self, *, initial=False):
        tree=self.expect_ui('preview')
        self.metadata(recording=False,timeout=2)
        signature={label:{k:self.unique_node(tree,'content-desc',label).get(k,'')
                          for k in ('package','resource-id','class','bounds','enabled')}
                   for label in ('Start recording video','Settings')}
        if initial:
            need(self.original_preview_signature is None and not self.ui_restore_pending,'initial UI already consumed')
            self.original_preview_signature=signature
            self.persist('original-camera-preview',signature)
        else:need(self.original_preview_signature==signature,'original preview controls/layout not restored')
        self.original_preview_verified=True;self.ui_restore_pending=False
        self.report.update(camera_ui_original_preview_verified=True,camera_ui_restore_pending=False)

    def open_video_from_main(self):
        tree=self.expect_ui('main_settings')
        self.click(self.row(tree,VIDEO_SETTINGS),transition_to='video_settings')

    def enter_video_settings(self):
        need(self.read_boots()==self.boots,'no preferences across boot change')
        self.verify_original_preview()
        tree=self.expect_ui('preview')
        self.click(self.unique_node(tree,'content-desc','Settings'),transition_to='main_settings')
        self.open_video_from_main()

    def leave_video_settings(self):
        self.expect_ui('video_settings')
        self.ui_action('input keyevent 4','main_settings')
        self.expect_ui('main_settings')
        self.ui_action('input keyevent 4','preview')
        self.verify_original_preview()

    def close_option_dialog(self,title):
        self.expect_ui('option_dialog',title)
        self.ui_action('input keyevent 4','video_settings')

    def open_preference(self,title):
        need(title in (DURATION,RESTART),'unsupported preference')
        tree=self.expect_ui('video_settings')
        self.click(self.row(tree,title),transition_to=('option_dialog',title))
        tree=self.expect_ui('option_dialog',title)
        selected=[n for n in tree.iter('node') if n.get('class')=='android.widget.CheckedTextView'
                  and n.get('checkable')=='true' and n.get('checked')=='true']
        need(len(selected)==1 and selected[0].get('text'),'selected value missing')
        return tree,selected[0].get('text')

    def filesize_switch(self, wanted=None):
        tree=self.expect_ui('video_settings');n=self.row(tree,FILE_RESTART)
        switches=[s for s in n.iter('node') if s.get('checkable')=='true']
        need(len(switches)==1 and switches[0].get('checked') in ('true','false'),'filesize switch')
        old=switches[0].get('checked')=='true'
        if wanted is not None and old!=wanted:self.click(n,transition_to=('video_switch',wanted))
        return old

    def preference(self,title,value):
        tree,old=self.open_preference(title)
        if old!=value:
            self.preferences.append((title,old));self.persist('preferences',self.preferences)
            self.click(self.unique_node(tree,'text',value),transition_to='video_settings')
        else:self.close_option_dialog(title)
        tree,current=self.open_preference(title)
        self.close_option_dialog(title)
        need(current==value,'preference readback mismatch')

    def cleanup_camera_ui(self):
        need(self.start is None or self.stopped,'no camera UI cleanup before verified stop')
        self.ui_restore_pending=True;self.original_preview_verified=False
        self.report.update(camera_ui_restore_pending=True,camera_ui_original_preview_verified=False)
        need(self.read_boots()==self.boots,'no UI cleanup across boot change')
        state,_=self.observe_ui()
        need(not self.ui_transition_uncertain and self.ui_transition is None,
             'uncertain UI transition; retain cleanup and owner')
        need(state['level']!='unknown','unknown UI; no blind Back or Settings')
        if state['level']=='option_dialog':
            self.close_option_dialog(state['dialog']);state,_=self.observe_ui()
        changed=bool(self.preferences) or self.switch_original is not None
        if state['level']=='preview':
            if not changed:self.verify_original_preview();return
            self.enter_video_settings();state,_=self.observe_ui()
        elif state['level']=='main_settings':
            if not changed:
                self.ui_action('input keyevent 4','preview');self.verify_original_preview();return
            self.open_video_from_main();state,_=self.observe_ui()
        need(state['level']=='video_settings','no known cleanup navigation edge')
        self.finish_preferences()
        self.leave_video_settings()

    def metadata(self, *, recording, previous=None, timeout=1):
        begin=self.clock()
        raw=self.shell('camera','dumpsys media.camera',timeout=timeout)
        snap=self.parser.validate_capture(raw,previous=previous,**PROFILE,
             expected_size=(1280,720) if recording else None,require_recording=recording)
        if not recording:
            need(not snap['recording_verified'] and snap['request']['capture_intent']=='PREVIEW'
                 and snap['result']['capture_intent']=='PREVIEW','not verified preview')
            if any(stream['consumer_kind'] in self.parser.ENCODER_CONSUMERS for stream in snap['streams']):
                raise PreviewEncoderPending()
        else:need(snap['rolling_shutter_skew_ns']==15047630,'recording skew')
        snap['host_capture_bounds']={'begin_monotonic':begin,'end_monotonic':self.clock(),
            'limit':'Host call bounds only; no sensor-to-file timestamp calibration.'}
        return snap

    def unchanged(self,dbv):
        state=self.target_state()
        need(state==dict(self.before,native_dbv=dbv),'target changed')
        self.shell('target',self.ops['verify'],root=True)

    def native_dbv(self,value):
        need(type(value) is int and 460<=value<=16180,'brightness range')
        need(self.start is None or self.stopped,'no target mutation during recording')
        self.shell('target',self.ops['verify'],root=True)
        self.shell('target',f"printf '%s\\n' {value} > {BL}",root=True)

    def private_png(self, role):
        rc,raw,err=self.g.shell(self.ids[role],'screencap -p',5)
        need(rc==0 and type(raw) is bytes and not err,'PNG capture failed')
        info=self.inspection.validate_png(raw)
        self.owned.deadline=self.clock()+5;self.owned.verify()
        name='dispatch-'+role+'.png'
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                   0o600,dir_fd=self.owned.fd)
        try:
            st=os.fstat(fd)
            need(st.st_mode==stat.S_IFREG|0o600 and st.st_uid==self.owned.identity[2] and st.st_nlink==1,
                 'private PNG custody')
            view=memoryview(raw)
            while view:
                need(self.clock()<self.owned.deadline,'PNG write deadline')
                n=os.write(fd,view);need(n>0,'PNG short write');view=view[n:]
            need(os.fstat(fd).st_size==len(raw),'PNG size mismatch')
            return dict(info,file=name,device=st.st_dev,inode=st.st_ino,uid=st.st_uid,mode=st.st_mode)
        finally:os.close(fd)

    def current_scene(self):
        activity=self.shell('target','dumpsys activity activities')
        focus=self.shell('target','dumpsys window windows')
        lock=self.shell('target','dumpsys window policy')
        classification=self.inspection.scene(activity,focus,lock)
        need(classification=={'settings_foreground':True,'unlocked':True},'scene/focus/lock changed')
        components=re.findall(r'^.*mResumedActivity:.*\s(com\.android\.settings/[^\s}]+).*$',activity,re.M)
        need(len(components)==1 and components[0]==self.prior_review['scene']['component'],'Settings component changed')
        return {'component':components[0],'settings_foreground':True,'unlocked':True}

    def dispatch_guard(self):
        need(self.start is None and self.dispatch_evidence is None,'dispatch inspection already spent')
        need(self.prior_review is not None,'prior visual review missing')
        begin=self.clock()
        self.unchanged(3600)
        scene=self.current_scene()
        launch_before=normal_camera_launch(self.shell('camera','dumpsys activity activities'))
        first=self.metadata(recording=False,timeout=2)
        images={role:self.private_png(role) for role in ('target','camera')}
        last=self.metadata(recording=False,previous=first,timeout=2)
        need(last.get('progress_verified') is True,'preview progress missing')
        launch_after=normal_camera_launch(self.shell('camera','dumpsys activity activities'))
        need(launch_before['component']==launch_after['component'],'camera activity changed')
        need(self.current_scene()==scene,'scene changed across dispatch images')
        self.unchanged(3600)
        end=self.clock()
        need(0<=end-begin<=30,'dispatch inspection exhausted30s budget')
        gate={'begin_monotonic':begin,'end_monotonic':end,'source':self.source,
              'boots':self.boots,'scene':scene,'camera_before':first,'camera_after':last,
              'camera_launch_before':launch_before,'camera_launch_after':launch_after,
              'screenshots':images,'new_png_visual_review':False,
              'geometry_status':'actual_media_review_required'}
        self.persist('dispatch-machine-evidence',gate)
        self.dispatch_evidence=gate
        return gate

    def record(self):
        need(self.start is None,'start attempt already spent')
        need(self.original_preview_verified and not self.ui_restore_pending and self.ui_transition is None
             and not self.ui_transition_uncertain,'camera UI setup not verified')
        need(self.report.get('camera_limit_readback')=={'duration_seconds':10,'restart_count':0,
             'filesize_restart':False},'finite camera preferences not read back')
        gate=self.dispatch_guard()
        tree=self.ui()
        need(not any(n.get('content-desc')=='Stop recording video' for n in tree.iter('node')),
             'already recording')
        start=self.unique_node(tree,'content-desc','Start recording video')
        self.files_before=self.shell('camera',FILES)
        need(self.clock()-gate['begin_monotonic']<=30,'stale machine invariants at dispatch')
        need(gate is self.dispatch_evidence,'unbound machine gate')
        self.ui_restore_pending=True;self.original_preview_verified=False
        self.report.update(camera_ui_restore_pending=True,camera_ui_original_preview_verified=False)
        self.start=self.clock()  # Includes tap, startup and settling.
        self.report['start_attempt_monotonic']=self.start
        self.click(start)        # Exactly one start; NEVER a Stop tap.
        previous=None; snapshots=[]; early=False; preview=None; unsettled=[]
        while self.clock()-self.start<15:
            remaining=15-(self.clock()-self.start)
            call_begin=self.clock()
            try:
                snap=self.metadata(recording=True,previous=previous,timeout=min(1,remaining))
            except self.parser.RequestResultNotSettled as exc:
                need(len(unsettled)<5,'startup request/result rejection cap')
                previous=exc.continuity_snapshot
                unsettled.append({'elapsed':self.clock()-self.start,
                    'host_call_begin_monotonic':call_begin,'continuity_snapshot':previous})
                self.report['request_result_startup_rejections']=len(unsettled)
                self.persist('request-result-unsettled',unsettled)
                self.sleep(min(.25,max(0,15-(self.clock()-self.start))))
                continue
            except self.parser.CaptureMetadataError:
                # Inspect current PREVIEW, never convert a failed profile check
                # into another start/stop. Transport failures propagate directly.
                try:
                    preview=self.metadata(recording=False,timeout=min(1,max(.001,15-(self.clock()-self.start))))
                except PreviewEncoderPending:
                    self.report['preview_encoder_pending_observed']=True
                    self.sleep(min(.25,max(0,15-(self.clock()-self.start))))
                    continue
                if len(snapshots)>=2 and snapshots[-1]['snapshot'].get('progress_verified') is True:
                    self.stopped=True;break
                # A queued start may execute after this PREVIEW. It is NOT stop
                # evidence until advancing recording has been observed.
                self.report['startup_preview_pending']=True
                self.sleep(min(.25,max(0,15-(self.clock()-self.start))))
                continue
            previous=snap
            snapshots.append({'elapsed':self.clock()-self.start,'snapshot':snap})
            if len(snapshots)>=2 and snap.get('progress_verified') is True:
                self.report['advancing_recording_observed']=True
                self.report.setdefault('first_advancing_recording_elapsed',snapshots[-1]['elapsed'])
            if len(snapshots)>=2 and snapshots[-1]['elapsed']<=1:
                early=True
            self.sleep(min(.25,max(0,15-(self.clock()-self.start))))
        elapsed=self.clock()-self.start
        self.report.update(stop_observed_elapsed=elapsed,early_controls_bound=early,
                           camera_stopped_verified=self.stopped)
        self.persist('recording-snapshots',snapshots)
        need(self.stopped,'native stop unverified; no toggle contingency')
        need(elapsed<=15,'late stop observation')
        self.unchanged(3600)
        self.report['recording_observation_complete']=True
        if not (len(snapshots)>=2 and early):
            self.report['capture_validity_failure']='early_controls_unbound'
            self.report['failure_reason']='frame30 controls unbound'
            self.report['control_coverage_status']='unknown_first_window'
            raise ValueError('frame30 controls unbound')

    def restore(self):
        need(self.start is None or self.stopped,'retain cleanup until verified stop')
        need(self.read_boots()==self.boots,'no restoration across boot change')
        # Camera preference rollback requires known navigation level. This is
        # handled explicitly by finish_preferences(), never blind Back loops.
        need(not self.preferences and self.switch_original is None,'camera preference restoration pending')
        need(self.original_preview_verified and not self.ui_restore_pending and self.ui_transition is None
             and not self.ui_transition_uncertain,'original camera UI restoration pending')
        if self.changed:
            state=self.target_state()
            need(state['settings']==self.before['settings'],'unexpected framework change')
            self.native_dbv(self.before['native_dbv']);self.sleep(1)
        self.unchanged(self.before['native_dbv'])
        self.report['originals_restored']=True

    def finish_preferences(self):
        # Caller has explicitly reached the verified Video settings page.
        need(self.start is None or self.stopped,'no settings while recording')
        need(self.read_boots()==self.boots,'no preference restore across boot change')
        if self.switch_original is not None:
            self.filesize_switch(self.switch_original)
            need(self.filesize_switch()==self.switch_original,'filesize restart restore mismatch')
            self.switch_original=None
        while self.preferences:
            title,old=self.preferences[-1]
            tree,current=self.open_preference(title)
            if current!=old:self.click(self.unique_node(tree,'text',old),transition_to='video_settings')
            else:self.close_option_dialog(title)
            tree,actual=self.open_preference(title)
            self.close_option_dialog(title)
            need(actual==old,'preference restore mismatch')
            self.preferences.pop();self.persist('preferences-restored',self.preferences)

    def pull(self):
        need(self.stopped,'pull only after verified stop')
        path=self.video(self.files_before,self.shell('camera',FILES))
        q=shlex.quote(path)
        def identity():
            raw=self.shell('camera',f'stat -c %s {q}; sha256sum {q}',timeout=10).splitlines()
            need(len(raw)==2 and re.fullmatch('[1-9][0-9]*',raw[0]),'media identity')
            need(re.fullmatch('[a-f0-9]{64}  '+re.escape(path),raw[1]),'media digest')
            return int(raw[0]),raw[1][:64]
        size,digest=identity();need(size<=self.cap,'media byte cap')
        dest=str(self.owned.path/'capture.mp4')
        self.g.sync(self.ids['camera'],dest,path,pull=True,timeout=45,expected_size=size,byte_cap=self.cap)
        facts=self.retained.facts()
        need(facts.created is True and facts.confirmed_written==size and
             facts.write_outcome_uncertain is False and facts.close_outcome=='closed',
             'private sink lifecycle incomplete')
        need(identity()==(size,digest),'source changed during transfer')
        self.owned.deadline=self.clock()+10;self.owned.verify()
        fd=os.open('capture.mp4',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.owned.fd)
        try:
            st=os.fstat(fd)
            need((st.st_dev,st.st_ino,st.st_uid,st.st_mode)==self.retained.created_identity,
                 'created-inode custody mismatch')
            h=hashlib.sha256()
            while True:
                need(self.clock()<self.owned.deadline,'private hash deadline')
                chunk=os.read(fd,65536)
                if not chunk:break
                h.update(chunk)
            need(st.st_size==size and h.hexdigest()==digest,'private media mismatch')
            after=os.fstat(fd)
            need((after.st_dev,after.st_ino,after.st_uid,after.st_mode,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==
                 (st.st_dev,st.st_ino,st.st_uid,st.st_mode,st.st_size,st.st_mtime_ns,st.st_ctime_ns),
                 'private media changed during hash')
        finally:os.close(fd)
        self.report['media']={'bytes':size,'sha256':digest,'created_inode_verified':True}

    def begin(self, receipt):
        need(not self.spent,'single attempt');self.spent=True
        self.g.preflight()
        for role,serial in zip(('target','camera'),self.serials):
            need(self.g.bind(self.ids[role])==serial,'role identity')
        self.boots=self.read_boots()
        # Initial visual review is provenance, not a claim of current pixels.
        need(type(receipt) is PriorGeometryReview,'concrete prior review required')
        self.prior_review=receipt.validate(self.boots,self.source)
        self.report['geometry_review_status']='actual_media_review_required'
        self.persist('prior-geometry-review',self.prior_review)
        need(tuple(self.query('camera','camera_identity').splitlines())==self.ro.CAMERA,'camera identity')
        package=self.query('camera','package')
        need(re.search(r'\bversionName=1\.56\.2(?:\s|$)',package) and
             re.search(r'\bversionCode=96(?:\s|$)',package),'camera version')
        need(self.query('target','root')=='0' and self.query('target','panel')==self.ro.PANEL,
             'target root/panel')
        need(self.query('target','module')==self.ro.MODULE+'  /vendor/lib/modules/msm_drm.ko','target module')
        self.metadata(recording=False,timeout=2)
        normal_camera_launch(self.shell('camera','dumpsys activity activities'))
        self.verify_original_preview(initial=True)
        self.acquisition_attempted=True
        self.report['mutex_acquire_outcome']='uncertain'
        self.persist('mutex-acquire-intent',{'token':self.token,'boots':self.boots})
        self.shell('target',self.ops['acquire'],root=True);self.locked=True
        self.report['mutex_acquire_outcome']='verified'
        self.before=self.target_state()
        self.persist('before',{'boot_id':self.boots['target'],'camera_boot_id':self.boots['camera'],
                               **self.before,'source':self.source})
        if self.before['native_dbv']!=3600:
            self.changed=True;self.native_dbv(3600)
        self.sleep(1);self.unchanged(3600)

    def release(self):
        need(self.report.get('originals_restored') is True and not self.preferences and self.switch_original is None
             and self.original_preview_verified and not self.ui_restore_pending and self.ui_transition is None
             and not self.ui_transition_uncertain,
             'cleanup pending; retain mutex')
        for p in self.xml_paths:
            self.shell('camera','rm -- '+shlex.quote(p))
        self.xml_paths.clear()
        self.shell('target',self.ops['release'],root=True);self.locked=False
        self.report['mutex_released']=True

    def observe_late_stop(self):
        """One bounded read-only cleanup probe, never repairs failed cap evidence."""
        need(self.start is not None and not self.stopped,'late probe not needed')
        need(self.report.get('advancing_recording_observed') is True,
             'pending start cannot be closed by preview')
        need(not self.report.get('late_probe_attempted'),'late probe already spent')
        self.report['late_probe_attempted']=True
        need(self.read_boots()==self.boots,'boot changed; no late cleanup')
        self.metadata(recording=False,timeout=2)
        self.stopped=True
        self.report['late_preview_elapsed']=self.clock()-self.start
        self.report['status']='inconclusive_late_stop'
        self.persist('late-stop',self.report)

    def run(self, receipt):
        """One-shot API; live source/receipt binding has NOT been admitted.

        Pending cleanup leaves own mutex/media intact. No second recording.
        """
        error=None
        try:
            self.begin(receipt)
            self.enter_video_settings()
            self.preference(DURATION,'10 seconds')
            self.preference(RESTART,"Don't restart")
            original=self.filesize_switch()
            if original:
                self.switch_original=original
                self.persist('filesize-original',{'restart':original})
                self.filesize_switch(False)
            need(self.filesize_switch() is False,'filesize auto-restart must be disabled')
            self.report['camera_limit_readback']={'duration_seconds':10,'restart_count':0,'filesize_restart':False}
            self.leave_video_settings()
            self.record()
            self.report['status']='geometry_review_pending'
        except BaseException as exc:
            error=exc;self.report['status']='inconclusive';self.report['error_type']=type(exc).__name__
        finally:
            if self.before is not None and (self.start is None or self.stopped):
                try:
                    self.cleanup_camera_ui()
                    self.restore();self.release()
                except BaseException as exc:
                    error=error or exc;self.report['cleanup_pending']=True
                    self.report['cleanup_error_type']=type(exc).__name__
            elif self.locked or self.acquisition_attempted or self.xml_paths or self.ui_restore_pending:
                self.report['cleanup_pending']=True
            if self.stopped and hasattr(self,'files_before'):
                try:self.pull()
                except BaseException as exc:
                    error=error or exc;self.report['transfer_error_type']=type(exc).__name__
            if error and self.report['status']=='geometry_review_pending':
                self.report['status']='inconclusive'
            self.persist('outcome',self.report)
            if self.report.get('media') and all(k in self.records for k in ('before','recording-snapshots','outcome','source-closure')):
                try:self.capsule()
                except BaseException as exc:
                    self.report['capsule_error_type']=type(exc).__name__
                    self.report['status']='inconclusive'
                    self.persist('outcome',self.report)
        return self.report

    def capsule(self):
        need(self.stopped and self.report.get('originals_restored') is True and
             self.report.get('mutex_released') is True and self.original_preview_verified and
             not self.ui_restore_pending and self.ui_transition is None and not self.ui_transition_uncertain,
             'capsule requires verified cleanup and original camera UI')
        boots=self.read_boots();need(boots==self.boots,'final capsule boot drift')
        records={k:self.records[k] for k in ('before','recording-snapshots','outcome','source-closure')}
        facts=asdict(self.retained.facts())
        evidence={'schema':'stock-observation-analysis-evidence-v1',
          'records':records,'records_sha256':{k:v['sha256'] for k,v in records.items()},
          'source':self.source,'final_boots':boots,
          'media':{'bytes':self.report['media']['bytes'],'sha256':self.report['media']['sha256'],
                   'created_identity':list(self.retained.created_identity),'sink_facts':facts},
          'control_binding':{'first_window_start_index':30,'last_window_end_exclusive':270,
                   'method':'camera_snapshots_progress_with_pts_validation_pending',
                   'evidence_sha256':records['recording-snapshots']['sha256'],
                   'per_frame_controls_proven':False,'sensor_to_file_calibrated':False},
          'geometry_review_status':'actual_media_review_required'}
        self.persist('analysis-evidence',evidence)
        return evidence
