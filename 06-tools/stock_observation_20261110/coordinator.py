"""Separate finite observation coordinator, OFFLINE-reviewed API only.

No CLI/import side effects, no Trial inheritance. Construction/source binding,
native-mode/scene/geometry receipt producer and real UI matching remain unadmitted.
Use only byte-bound dependencies and existing-server OfflineBaselineADB supplied
by the reviewed launcher. Tests supply synthetic transport, never devices.
"""
import hashlib
import json
import os
import re
import shlex
import stat
import xml.etree.ElementTree as ET
from protocol_v2 import SCHEMA, WINDOWS, admission, need

PROFILE = dict(exposure_ns=100000, iso=6400, focus_diopters=2.0387485,
               crop=(0,0,4080,3072), zoom=1.0, camera_id='0', expected_fps=30.0)
BL='/sys/class/backlight/panel0-backlight/brightness'
FILES="find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'"
UUID=r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
DURATION='Maximum duration of video'
RESTART='Restart video after max duration'
FILE_RESTART='Restart on maximum file size'
VIDEO_SETTINGS='Video settings…'


class Coordinator:
    def __init__(self, *, transport, target, camera, serials, parser, readonly,
                 lock_commands, new_camera_video, native_state, owned_directory, retained_sink,
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
        self.parse_native=native_state;self.mode_lines=None
        self.owned,self.retained,self.source=owned_directory,retained_sink,source
        self.clock,self.sleep,self.cap,self.token=clock,sleep,byte_cap,token
        self.spent=False; self.locked=False; self.changed=False; self.start=None
        self.stopped=False; self.before=None; self.boots=None; self.counter=0
        self.preferences=[]; self.xml_paths=[]; self.switch_original=None
        self.report={'schema':SCHEMA,'source':source,'status':'not_started','windows':WINDOWS,
                     'candidate_attempts':0,'custom_dsi_writes':0,'pwm_hz':None}

    def persist(self, label, data):
        need(re.fullmatch('[a-z0-9_-]+',label),'private label')
        self.counter+=1
        self.owned.deadline=self.clock()+5; self.owned.verify()
        raw=json.dumps(data,sort_keys=True).encode()
        fd=os.open(f'{self.counter:04d}-{label}.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.owned.fd)
        try:
            st=os.fstat(fd)
            need(st.st_mode==stat.S_IFREG|0o600 and st.st_nlink==1 and
                 st.st_uid==self.owned.identity[2],'private evidence inode')
            view=memoryview(raw)
            while view:
                n=os.write(fd,view);need(n>0,'private evidence short write');view=view[n:]
        finally: os.close(fd)

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

    def click(self,node):
        need(node.get('enabled')=='true','disabled control')
        m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.get('bounds',''))
        need(m is not None,'control bounds');a,b,c,d=map(int,m.groups())
        need(0<=a<c<=4096 and 0<=b<d<=4096,'control bounds range')
        self.shell('camera',f'input tap {(a+c)//2} {(b+d)//2}',timeout=1)

    def unique_node(self,tree,key,value):
        ns=[n for n in tree.iter('node') if n.get(key)==value]
        need(len(ns)==1,'control missing/ambiguous')
        return ns[0]

    def button(self,label):
        tree=self.ui(); node=self.unique_node(tree,'content-desc',label)
        need(node.get('package')=='net.sourceforge.opencamera','control package')
        self.click(node)

    def open_preference(self,title):
        tree=self.ui(); n=self.unique_node(tree,'text',title)
        parents={c:p for p in tree.iter() for c in p}
        while n.get('clickable')!='true':
            need(n in parents,'preference row missing');n=parents[n]
        self.click(n)
        tree=self.ui()
        selected=[n for n in tree.iter('node') if n.get('checked')=='true']
        need(len(selected)==1 and selected[0].get('text'),'selected value missing')
        return tree,selected[0].get('text')

    def enter_video_settings(self):
        need(self.read_boots()==self.boots,'no preferences across boot change')
        self.metadata(recording=False,timeout=2)
        self.button('Settings')
        tree=self.ui();n=self.unique_node(tree,'text',VIDEO_SETTINGS)
        parents={c:p for p in tree.iter() for c in p}
        while n.get('clickable')!='true':
            need(n in parents,'video settings row');n=parents[n]
        self.click(n)
        self.unique_node(self.ui(),'text',DURATION)

    def leave_video_settings(self):
        self.unique_node(self.ui(),'text',DURATION)
        self.shell('camera','input keyevent 4',timeout=1)
        self.unique_node(self.ui(),'text',VIDEO_SETTINGS)
        self.shell('camera','input keyevent 4',timeout=1)
        self.metadata(recording=False,timeout=2)

    def filesize_switch(self, wanted=None):
        tree=self.ui();n=self.unique_node(tree,'text',FILE_RESTART)
        parents={c:p for p in tree.iter() for c in p}
        while n.get('clickable')!='true':
            need(n in parents,'filesize row');n=parents[n]
        switches=[s for s in n.iter('node') if s.get('checkable')=='true']
        need(len(switches)==1 and switches[0].get('checked') in ('true','false'),'filesize switch')
        old=switches[0].get('checked')=='true'
        if wanted is not None and old!=wanted:self.click(n)
        return old

    def preference(self,title,value):
        tree,old=self.open_preference(title)
        if old!=value:
            # Persist rollback intent BEFORE a potentially uncertain selection.
            self.preferences.append((title,old));self.persist('preferences',self.preferences)
            self.click(self.unique_node(tree,'text',value))
        else:self.shell('camera','input keyevent 4',timeout=1)
        tree,current=self.open_preference(title)
        self.shell('camera','input keyevent 4',timeout=1)
        need(current==value,'preference readback mismatch')

    def metadata(self, *, recording, previous=None, timeout=1):
        raw=self.shell('camera','dumpsys media.camera',timeout=timeout)
        snap=self.parser.validate_capture(raw,previous=previous,**PROFILE,
             expected_size=(1280,720) if recording else None,require_recording=recording)
        if not recording:
            need(not snap['recording_verified'] and snap['request']['capture_intent']=='PREVIEW'
                 and snap['result']['capture_intent']=='PREVIEW','not verified preview')
        else:need(snap['rolling_shutter_skew_ns']==15047630,'recording skew')
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

    def record(self):
        need(self.start is None,'start attempt already spent')
        need(self.report.get('camera_limit_readback')=={'duration_seconds':10,'restart_count':0,
             'filesize_restart':False},'finite camera preferences not read back')
        self.unchanged(3600); self.metadata(recording=False,timeout=2)
        tree=self.ui()
        need(not any(n.get('content-desc')=='Stop recording video' for n in tree.iter('node')),
             'already recording')
        start=self.unique_node(tree,'content-desc','Start recording video')
        self.files_before=self.shell('camera',FILES)
        self.start=self.clock()  # Includes tap, startup and settling.
        self.report['start_attempt_monotonic']=self.start
        self.click(start)        # Exactly one start; NEVER a Stop tap.
        previous=None; snapshots=[]; early=False; preview=None
        while self.clock()-self.start<15:
            remaining=15-(self.clock()-self.start)
            try:
                snap=self.metadata(recording=True,previous=previous,timeout=min(1,remaining))
            except self.parser.CaptureMetadataError:
                # Inspect current PREVIEW, never convert a failed profile check
                # into another start/stop. Transport failures propagate directly.
                preview=self.metadata(recording=False,timeout=min(1,max(.001,15-(self.clock()-self.start))))
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
            if len(snapshots)>=2 and snapshots[-1]['elapsed']<=1:
                early=True
            self.sleep(min(.25,max(0,15-(self.clock()-self.start))))
        elapsed=self.clock()-self.start
        self.report.update(stop_observed_elapsed=elapsed,early_controls_bound=early,
                           camera_stopped_verified=self.stopped)
        self.persist('recording-snapshots',snapshots)
        need(self.stopped,'native stop unverified; no toggle contingency')
        need(elapsed<=15,'late stop observation')
        need(len(snapshots)>=2 and early,'frame30 controls unbound')
        self.unchanged(3600)

    def restore(self):
        need(self.start is None or self.stopped,'retain cleanup until verified stop')
        need(self.read_boots()==self.boots,'no restoration across boot change')
        # Camera preference rollback requires known navigation level. This is
        # handled explicitly by finish_preferences(), never blind Back loops.
        need(not self.preferences and self.switch_original is None,'camera preference restoration pending')
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
            if current!=old:self.click(self.unique_node(tree,'text',old))
            else:self.shell('camera','input keyevent 4',timeout=1)
            tree,actual=self.open_preference(title)
            self.shell('camera','input keyevent 4',timeout=1)
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
        admission(receipt,boots=self.boots,source=self.source,now=self.clock())
        need(tuple(self.query('camera','camera_identity').splitlines())==self.ro.CAMERA,'camera identity')
        package=self.query('camera','package')
        need(re.search(r'\bversionName=1\.56\.2(?:\s|$)',package) and
             re.search(r'\bversionCode=96(?:\s|$)',package),'camera version')
        need(self.query('target','root')=='0' and self.query('target','panel')==self.ro.PANEL,
             'target root/panel')
        need(self.query('target','module')==self.ro.MODULE+'  /vendor/lib/modules/msm_drm.ko','target module')
        self.metadata(recording=False,timeout=2)
        self.shell('target',self.ops['acquire'],root=True);self.locked=True
        self.before=self.target_state()
        self.persist('before',{'boot_id':self.boots['target'],'camera_boot_id':self.boots['camera'],
                               **self.before,'source':self.source})
        if self.before['native_dbv']!=3600:
            self.changed=True;self.native_dbv(3600)
        self.sleep(1);self.unchanged(3600)

    def release(self):
        need(self.report.get('originals_restored') is True and not self.preferences and self.switch_original is None,
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
            self.report['status']='awaiting_offline_media_validation'
        except BaseException as exc:
            error=exc;self.report['status']='inconclusive';self.report['error_type']=type(exc).__name__
        finally:
            if self.before is not None and (self.start is None or self.stopped):
                try:
                    if self.preferences or self.switch_original is not None:
                        self.enter_video_settings();self.finish_preferences();self.leave_video_settings()
                    self.restore();self.release()
                except BaseException as exc:
                    error=error or exc;self.report['cleanup_pending']=True
                    self.report['cleanup_error_type']=type(exc).__name__
            elif self.locked:self.report['cleanup_pending']=True
            if self.stopped and hasattr(self,'files_before'):
                try:self.pull()
                except BaseException as exc:
                    error=error or exc;self.report['transfer_error_type']=type(exc).__name__
            if error and self.report['status']=='awaiting_offline_media_validation':
                self.report['status']='inconclusive'
            self.persist('outcome',self.report)
        return self.report
