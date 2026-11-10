#!/usr/bin/env python3
"""Fixed full-table AA11/10 trial. Offline unless verified host inputs are supplied.

Stock surrogate measures this exact composition, not the old factory15 run.
37s includes arm through qualified return/disarm. Return optical hold remains
under the nonrenewed overall600s watchdog. Markers are not optical recovery.
"""
import argparse
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import signal
import uuid
import xml.etree.ElementTree as ET

import run_p85_timed_stock_trial as timed
import aa_threshold_trial as aa
import a9_reproduction as a9
import aa_acquisition_validation as acquisition

s=timed.s;env=timed.env;base=timed.base;check=s.check;q=s.q
SOURCE_FILES=timed.SOURCE_FILES+('06-tools/aa_threshold_trial.py','06-tools/run_aa_timed_stock_trial.py','06-tools/aa_acquisition_validation.py')
def absent_probes():
    return "if grep -Fq pwm_mode/ /sys/kernel/tracing/kprobe_events; then exit 81; else rc=$?; test \"$rc\" = 1; fi"


STOCK_SCOPE='aa-threshold-stock-surrogate-v1'
CANDIDATE_SCOPE='aa-threshold-candidate-v1'
REDRAW_SCENE_CONTRACT=acquisition.REDRAW_SCENE_CONTRACT
REDRAW_SETTLE_SECONDS=1.0


class SettingsOpeningPending(ValueError):
    """Complete observed opening scene, but not proof of a settled scene."""
    def __init__(self,scene):
        super().__init__('Observed Settings opening is not settled')
        self.scene=scene


def settings_scene(text,*,opening=False):
    """Narrow observed Android16 activity dump, not a generic UI/text decoder.

    The top dump also includes stopped launcher/parent activities. Select by
    each activity's own native lifecycle, then bind the focused Settings view
    tree AND its resumed AndroidX fragment. Never global-match a fragment name.
    Text/checked values are NOT exposed here: same-trial XML calibration and
    the independent timeout/native checks remain required.
    """
    check(isinstance(text,str) and 0<len(text)<4*1024*1024 and '\ufffd' not in text,
          'Malformed activity scene dump')
    starts=list(re.finditer(r'^  ACTIVITY ([^\n]+)$',text,re.M))
    check(starts,'Missing activity sections')
    resumed=[]
    for i,start in enumerate(starts):
        body=text[start.end():starts[i+1].start() if i+1<len(starts) else len(text)].split('\nTASK ',1)[0]
        local_header=re.search(r'^    Local Activity [0-9a-f]+ State:\n',body,re.M)
        check(local_header is not None,'Missing native activity state')
        local=body[local_header.end():].split('\n    ViewRoot:',1)[0]
        states=re.findall(r'^      mResumed=(true|false) mStopped=(true|false) mFinished=(true|false)$',local,re.M)
        check(len(states)==1,'Ambiguous native activity lifecycle')
        if states[0][0]=='true':resumed.append((start[1],body,local,states[0]))
    check(len(resumed)==1,'Missing/ambiguous resumed activity')
    header,body,local,state=resumed[0]
    identity=re.fullmatch(r'(com\.android\.settings/[^ ]+) [0-9a-f]+ pid=(\d+) userId=0 uid=1000 displayId=0\(type=INTERNAL\)',header)
    check(identity is not None and state==('true','false','false'),'Unexpected resumed Settings identity')
    check('\n      mIsInMultiWindowMode=false mIsInPictureInPictureMode=false\n' in local and
          '\n      mChangingConfigurations=false\n' in local,'Settings configuration transition')
    configs=re.findall(r'^      mCurrentConfig=(.+)$',local,re.M)
    check(len(configs)==1 and 'mDisplayRotation=ROTATION_0' in configs[0] and
          'mWindowingMode=fullscreen' in configs[0],'Unknown Settings display configuration')
    roots=re.findall(r'^    ViewRoot:\n(.*?)^    View Hierarchy:\n',body,re.M|re.S)
    check(len(roots)==1,'Missing/ambiguous Settings ViewRoot')
    for key,value in (('mAdded','true'),('mRemoved','false'),('mStopped','false'),
                      ('mPausedForTransition','false'),('mPendingInputEventCount','0'),
                      ('mProcessInputEventsScheduled','false')):
        check(re.findall(r'^      '+key+r'=(\S+)$',roots[0],re.M)==[value],'Unsettled Settings ViewRoot: '+key)
    traversal=re.findall(r'^      mTraversalScheduled=(\S+)$',roots[0],re.M)
    focus=re.findall(r'^        mHasWindowFocus=(\S+)$',roots[0],re.M)
    check(re.findall(r'^        mWindowVisibility=(\S+)$',roots[0],re.M)==['0'],'Settings window not visible')
    pending=not (traversal==['false'] and focus==['true'])
    if pending:
        check(opening and traversal==['true'] and focus==['false'],'Unqualified Settings traversal/focus state')
        choreographer=re.findall(r'^    Choreographer:\n(.*?)(?=^    [^ ]|\Z)',roots[0],re.M|re.S)
        check(len(choreographer)==1 and
              re.findall(r'^      mFrameScheduled=(\S+)$',choreographer[0],re.M)==['true'],
              'Unqualified Settings opening frame state')
    trees=re.findall(r'^    View Hierarchy:\n(.*?)^    Looper \(main,',body,re.M|re.S)
    check(len(trees)==1,'Incomplete Settings hierarchy boundary')
    hierarchy=[];depths=[];ancestors=[];generated_ids=0
    for line in trees[0].splitlines():
        match=re.fullmatch(r'( +)([A-Za-z_$][\w.$]*)\{[0-9a-f]+ ([VIG.][F.][E.][D.][H.][V.][C.][L.][X.]) ([R.][F.][S.][pP.][H.][A.][I.][D.]) (-?\d+,-?\d+--?\d+,-?\d+)( #[0-9a-f]+(?: [\w.$]+:id/[\w.$]+)?)?(?: aid=\d+)?\}(\[[^\]\n]+\])?',line)
        check(match is not None,'Unknown/truncated Settings view line')
        indent,klass,flags,private,bounds,resource,title=match.groups()
        depth=(len(indent)-6)//2
        check(len(indent)>=6 and len(indent)%2==0 and
              ((not depths and depth==0) or (depth>0 and depth<=depths[-1]+1)),
              'Broken Settings view hierarchy')
        ancestors=ancestors[:depth]
        # AndroidX ViewPager2 creates this internal child with generateViewId().
        # Same-run observed #5 -> #6 is normalized ONLY in the hidden, zero-size
        # tab subtree. Named/static IDs and every other node field remain exact.
        if (klass=='androidx.viewpager2.widget.ViewPager2$RecyclerViewImpl' and
                bounds=='0,0-0,0' and resource is not None and
                re.fullmatch(r' #[0-9a-f]+',resource) and 0<int(resource[2:],16)<0x01000000 and
                len(ancestors)>=2):
            parent,grandparent=ancestors[-1],ancestors[-2]
            if (parent[1]=='androidx.viewpager2.widget.ViewPager2' and parent[4]=='0,0-0,0' and
                    re.fullmatch(r' #[0-9a-f]+ app:id/view_pager',parent[5]) and
                    grandparent[1]=='android.widget.LinearLayout' and grandparent[2][0]=='G' and
                    grandparent[4]=='0,0-0,0' and
                    re.fullmatch(r' #[0-9a-f]+ app:id/tab_container',grandparent[5])):
                generated_ids+=1;check(generated_ids==1,'Ambiguous generated ViewPager2 ID')
                resource=' #<generated-view-id>'
        # Object/autofill IDs and invalidated/dirty frame bits are transient.
        node=[depth,klass,flags,private[:6],bounds,resource or '',title or '']
        hierarchy.append(node);ancestors.append(node)
        depths.append(depth)
    check(5<=len(hierarchy)<=4096 and hierarchy[0][1]=='com.android.internal.policy.DecorView',
          'Incomplete Settings decor tree')
    support=re.findall(r'^    Local FragmentActivity [0-9a-f]+ State:\n(.*)',body,re.M|re.S)
    check(len(support)==1,'Missing/ambiguous support fragment state')
    active=re.fullmatch(r'      mCreated=true mResumed=true mStopped=false    Active Fragments:\n(.*?)^    Added Fragments:\n(.*)',support[0],re.M|re.S)
    check(active is not None,'Unsettled support fragment manager')
    fragments=re.findall(r'^    ([A-Za-z_$][\w.$]*\{[0-9a-f]+\} \([0-9a-f-]+ id=0x[0-9a-f]+\))$',active[1],re.M)
    check(len(fragments)==1,'Ambiguous current Settings fragment')
    fragment=fragments[0];fragment_class=fragment.split('{',1)[0]
    check(re.findall(r'^        mState=(\d+) mWho=[^ ]+ mBackStackNesting=\d+$',active[1],re.M)==['7'] and
          '\n        mAdded=true mRemoving=false mFromLayout=false mInLayout=false\n' in active[1] and
          '\n        mHidden=false mDetached=false mMenuVisible=true mHasMenu=' in active[1],
          'Settings fragment not resumed/visible')
    added=active[2].split('\n    ',1)[0]
    check(added.strip()=='#0: '+fragment,'Current/added fragment mismatch')
    check(active[2].rstrip().endswith('mCurState=7 mStateSaved=false mStopped=false mDestroyed=false'),
          'Incomplete support fragment tail')
    scene={'component':identity[1],'pid':int(identity[2]),'fragment':fragment_class,
           'configuration':configs[0],'hierarchy':hierarchy}
    if pending:
        check(scene['component']=='com.android.settings/.SubSettings' and scene['fragment']=='ScreenTimeoutSettings',
              'Pending state is not the observed timeout opening')
        raise SettingsOpeningPending(scene)
    return scene


def scene_digest(scene):
    return hashlib.sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_replay(log,begin,end,reference):
    section=aa.tx.marker_interval(log,begin,end)
    check(aa.tx.native_state(log)==reference,'Replay changed native timing')
    check(not any(x in section for x in ('dsi_display_set_mode','Command transfer failed','LOST')),'Replay native failure')
    rows=re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9a-fA-F ]+)',section)
    actual=[(int(n),int(k,16),mode,bytes.fromhex(payload)) for n,k,mode,payload in rows]
    check(section.count('dsi_ctrl_cmd_transfer len=')==1 and actual==[(3,57,'hs',b'\x51\x0e\x10')], 'Replay must be exactly one3600 packet, never a hidden table')
    return {'dbv':3600,'observed_writes':[{'length':3,'type':57,'mode':'hs','payload':'51 0e 10'}],'exact_wire_verified':True}


def validate_replay_trace(before,after,entry_count):
    """Account only for the observed replay return-event shape.

    A known status-read return may precede the brightness return inside this
    observation interval. Return order does not establish dispatch order,
    absence of overlap, or general safety of concurrent ESD activity.
    Exact replay wire/native validation remains a separate mandatory check.
    """
    aa.tx.check_snapshot(before,entry_count);aa.tx.check_snapshot(after,entry_count)
    old,new=aa.tx._events(before),aa.tx._events(after)
    for text,events in ((before,old),(after,new)):
        check([line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]==events,
              'Unknown replay trace event')
    check(new[:len(old)]==old,'Replay trace prefix changed')
    suffix=new[len(old):]
    check(len(suffix) in (1,2),'Unexpected replay trace event count')
    prefix=r'^\s*{task}-\d+\s+(?:\([^)]*\)\s+)?\[\d+\]\s+\S+\s+(\d+\.\d+):\s+mode_ctrl_return:\s+'
    replay=prefix.format(task='printf')+re.escape('(dsi_host_transfer_sub+0x2f4/0x558 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=0')
    replay_match=re.fullmatch(replay,suffix[-1])
    check(replay_match is not None,'Unqualified replay controller return')
    esd=[]
    if len(suffix)==2:
        poll=prefix.format(task=r'kworker/\d+:\d+')+re.escape('(dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1')
        poll_match=re.fullmatch(poll,suffix[0])
        check(poll_match is not None,'Unqualified status-read return in replay observation')
        check(Decimal(poll_match[1])<=Decimal(replay_match[1]),'Reversed replay return timestamps')
        esd=[{'caller':'dsi_display_validate_status+0x154/0x308','return_code':1}]
    result={'page_callbacks_verified':0,'controller_returns':([1] if esd else [])+[0],
            'entry_count_after':entry_count}
    if esd:
        result.update(background_esd_in_replay_observation=esd,
            limitation='Return-event order only; dispatch order and absence of overlap are not established')
    return result


def validate_safe_gap(before,after,entry_count):
    """Only exact already-qualified native ESD polls outside a DSI operation."""
    aa.tx.check_snapshot(before,entry_count);aa.tx.check_snapshot(after,entry_count)
    old,new=aa.tx._events(before),aa.tx._events(after)
    check(new[:len(old)]==old,'Main trace prefix changed')
    pattern=re.compile(r'^\s*(.+)-(\d+)\s+(?:\([^)]*\)\s+)?\[\d+\]\s+\S+\s+(\d+\.\d+):\s+(mode_entry|mode_return|mode_ctrl_return):\s+(.*)$')
    caller='(dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1'
    accepted=[]
    for line in new[len(old):]:
        match=pattern.fullmatch(line)
        check(match is not None,'Unqualified safe-gap trace event')
        task,pid,stamp,event,payload=match.groups()
        check(re.fullmatch(r'kworker/\d+:\d+',task) and event=='mode_ctrl_return' and payload==caller,
              'Unaccounted main trace activity, not exact native ESD')
        accepted.append({'kind':'native_esd_in_safe_gap','caller':'dsi_display_validate_status+0x154/0x308',
                         'return_code':1,'timestamp':float(stamp)})
    return accepted


def trace_guard(tmp,owner,before):
    """Remote pre-child prefix binding; only qualified ESD in the new suffix."""
    aa._path(tmp)
    events=aa.tx._events(before);prefix=''.join(line+'\n' for line in events)
    digest=hashlib.sha256(prefix.encode()).hexdigest()
    paths=[tmp+'/main-guard-'+name for name in ('snapshot','events','prefix','gap')]
    snap,all_events,old,gap=paths
    pattern=(r'^[[:space:]]*kworker/[0-9]+:[0-9]+-[0-9]+[[:space:]]+'
        r'(\([^)]*\)[[:space:]]+)?\[[0-9]+\][[:space:]]+[^[:space:]]+[[:space:]]+'
        r'[0-9]+\.[0-9]+:[[:space:]]+mode_ctrl_return:[[:space:]]+'
        r'\(dsi_display_validate_status\+0x154/0x308 \[msm_drm\] <- dsi_ctrl_cmd_transfer\) rc=1$')
    body='set -eu; '+owner+'; '
    for path in paths:body+=f'test ! -e {path}; test ! -L {path}; '
    body+=f'umask 077; cat {aa.TRACE}/trace > {snap}; '
    body+=f"awk '/LOST/ {{exit 51}} /rc=-[0-9]/ {{exit 51}}' {snap}; "
    body+=f"if grep -E 'mode_(entry|return|ctrl_return):' {snap} > {all_events}; then :; else rc=$?; test \"$rc\" = 1; test ! -s {all_events}; fi; "
    body+=f'head -n {len(events)} {all_events} > {old}; test \"$(sha256sum {old} | cut -d \" \" -f 1)\" = {digest}; '
    body+=f'tail -n +{len(events)+1} {all_events} > {gap}; awk '+q('!/'+pattern.replace('/',r'\/')+'/ {exit 51}')+f' {gap}; '
    body+='rm '+' '.join(paths)+"; printf 'TRACE_GUARD_OK\\n'"
    return body


def child_plan(nonce,owner,child,begin,end,*,guard=None):
    parts=[env.marker_part('BEGIN',begin),env.Part('TRACE_BEFORE','cat '+aa.TRACE+'/trace',True,4*1024*1024),
           env.Part('CHILD',child,True,4*1024*1024,25),
           env.Part('TRACE_AFTER','cat '+aa.TRACE+'/trace',True,4*1024*1024),env.marker_part('END',end),
           env.Part('KERNEL','dmesg',True,16*1024*1024),*env.state_parts(owner)]
    plan=env.Envelope(nonce,tuple(parts),45,child,env._owner(owner))
    if guard is not None:
        parts.insert(2,env.Part('PRE_GUARD',timed.guard_command(plan,owner,*guard),True,128,8))
    return replace(plan,parts=tuple(parts))


def qualification(record,source):
    check(type(record) is dict and record.get('scope')==STOCK_SCOPE,'Full AA stock surrogate required')
    check(record.get('video_acquisition_schema')==aa.SCHEMA and record.get('status')=='awaiting_offline_video_validation','Completed AA acquisition required')
    check(record.get('candidate_attempts')==0 and record.get('unknown_value_write_attempted') is False,'Surrogate contains unknown write')
    check(record.get('source_commit')==source.get('source_commit') and record.get('source_blob_ids')==source.get('source_blob_ids'),'Same exact runtime sources required')
    check(record.get('explicit_full_stock_return_verified') is True and record.get('return_hold_and_postselectors_verified') is True,'Incomplete stock return')
    for key in ('camera_stopped_verified','original_settings_dbv_logger_restored','watchdog_disarmed','mutex_released','video_transfer_verified','video_lifecycle_complete'):
        check(record.get(key) is True,'Surrogate cleanup missing: '+key)
    check(type(record.get('active_G_seconds')) in (int,float) and 0<record['active_G_seconds']<37,'No measured full composition budget')
    check([x['label'] for x in record.get('stages',[])]==['baseline','sham_stock','return_stock'],'Wrong surrogate stages')
    for stage in record['stages']:
        check(stage.get('qualified') is True and stage.get('program_sha256')==aa.STOCK_SHA,'Unqualified surrogate stage')
        check(stage.get('transaction',{}).get('controller_packets_verified')==75 and stage.get('wire',{}).get('native_packets_matched')==75,'Surrogate not full table')
        check(stage.get('same_dbv_replay',{}).get('exact_wire_verified') is True and stage.get('redraw_audit',{}).get('native_dsi_writes')==0,'Missing surrogate replay/redraw')
        for key in ('selectors_before_hold','selectors_after_hold'):check(stage.get(key,{}).get('values')==aa.SELECTORS,'Missing surrogate selectors')
        check(stage.get('c1',{}).get('data')==[0,0,96] and stage.get('hold_seconds')==base.HOLD,'Missing surrogate C1/hold')
    return {'scope':STOCK_SCOPE,'measured_G_seconds':record['active_G_seconds'],'same_source_verified':True,
            'limit':'One measured run is not a guaranteed latency bound; hard cutoff remains37s'}


class AATimedTrial(timed.TimedStockTrial):
    def __init__(self,*args,aa_candidate=False,stock_qualification=None,optical_qualification=None,source_record=None,**kwargs):
        check('candidate' not in kwargs,'Use only fixed AA candidate switch')
        super().__init__(*args,**kwargs)
        self.aa_candidate=aa_candidate;self.programs=aa.fixed_programs();self.entry_count=0
        self.trace_owned=False;self.chunks_owned=False;self.trace_snapshot='';self.redraw_ui_owned=False
        self.target_ui_path='/data/local/tmp/aa-ui-'+uuid.uuid4().hex[:12]
        self.redraw_scenes=None;self.redraw_tap=None
        self.marker='PWM_AA_'+self.plan['experiment_id']
        self.report.update(scope=CANDIDATE_SCOPE if aa_candidate else STOCK_SCOPE,marker=self.marker,
            candidate_enabled=aa_candidate,overall_watchdog_seconds=600,overall_watchdog_renewals=0,native_dbv=3600,full_table_writes_attempted=[],writes=[],
            schema=aa.SCHEMA,video_acquisition_schema=aa.SCHEMA,video_acquisition_origin='aa_timed_caller',
            protocol='full_table_replay_redraw_selectors_c1_hold_postselectors',
            diagnostic_change='C1 mandatory every phase; only known A9/9D/DBV selectors',
            admission='Exact full-stock surrogate measurement required before one AA10 dispatch',
            return_disarm_boundary='full stock75+known selectors+C1+native/ESD before short disarm; mandatory hold/postselectors under overall600',
            residual_risk='Latent AA/latch effects can outlast operational stock markers; optical restoration unproven')
        self.report.pop('register85_writes_attempted',None);self.report.pop('batching_adapter',None)
        self.report.pop('timed_stock_exploratory',None)
        if aa_candidate:
            self.report['qualification']=qualification(stock_qualification,source_record or {})
            acquisition.validate_stock_qualification(stock_qualification,optical_qualification,source_record or {})
            self.report['stock_optical_qualification']=optical_qualification

    def startup_write_attempts(self):
        return self.report['full_table_writes_attempted']

    def trace_check(self,text):
        events=validate_safe_gap(self.trace_snapshot,text,self.entry_count)
        if events:self.report.setdefault('background_esd_safe_gaps',[]).extend(events)
        self.trace_snapshot=text

    def setup_aa(self):
        self.panel_uncertain=True
        path=self.target_ui_path
        self.shell(f'set -eu; test \"$(id -u)\" = 2000; test ! -e {path}; test ! -L {path}',label='target-ui-fresh')
        self.redraw_ui_owned=True
        self.shell(f'set -eu; umask 077; mkdir -m 700 {path}; printf %s {q(self.token)} > {path}/owner; chmod 600 {path}/owner; '+self.target_ui_guard(),label='target-ui-create')
        self.shell(self.ops['verify']+f'; test ! -e {aa.TRACE}; '+absent_probes(),root=True,label='main-trace-fresh')
        self.trace_owned=True
        self.shell(self.ops['verify']+f'; mkdir {aa.TRACE}; printf %s {q(self.token)} > {self.tmp}/main-trace-owner; chmod 600 {self.tmp}/main-trace-owner; printf 0 > {aa.TRACE}/tracing_on; printf mono > {aa.TRACE}/trace_clock',root=True,label='main-trace-create')
        for name,definition in aa.PROBES.items():
            self.shell(self.ops['verify']+f"; printf '%s\\n' {q(definition)} >> /sys/kernel/tracing/kprobe_events; printf 1 > {aa.TRACE}/events/pwm_mode/{name}/enable",root=True,label='main-trace-probe')
        self.shell(self.ops['verify']+f'; printf 1 > {aa.TRACE}/tracing_on; test "$(cat {aa.TRACE}/tracing_on)" = 1',root=True,label='main-trace-start')
        self.trace_snapshot=self.shell('cat '+aa.TRACE+'/trace',root=True,label='main-trace-initial')
        aa.tx.check_snapshot(self.trace_snapshot,0);check(not aa.tx._events(self.trace_snapshot),'Initial trace activity')
        self.chunks_owned=True
        self.shell(self.ops['verify']+f'; umask 077; mkdir -m 700 {self.tmp}/chunks',root=True,label='chunks-create')
        for name,program in self.programs.items():
            for filename,data in aa.chunk_files(program,name).items():
                self.shell(self.ops['verify']+f'; test ! -e {self.tmp}/chunks/{filename}; printf %s {q(data.decode())} > {self.tmp}/chunks/{filename}; chmod 600 {self.tmp}/chunks/{filename}',root=True,label='chunk-prepare')
            self.shell(self.ops['verify']+'; '+aa.file_guards(self.tmp,program,name),root=True,label='chunks-verify')
        self.report['chunks_prepared_before_active_window']=True;self.panel_uncertain=False

    def aa_envelope(self,child,label,*,guard=None):
        begin=self._marker(label.upper().replace('-','_')+'_BEGIN');end=self._marker(label.upper().replace('-','_')+'_END')
        owner=self.ops['verify']+f'; test ! -L {self.tmp}/main-trace-owner; test \"$(cat {self.tmp}/main-trace-owner)\" = {q(self.token)}; test \"$(cat {aa.TRACE}/tracing_on)\" = 1'
        plan=child_plan(uuid.uuid4().hex[:12],owner,child,begin,end,guard=guard)
        # Ownership is checked before any child, not just after the transaction.
        parts=list(plan.parts);index=next(i for i,p in enumerate(parts) if p.label=='CHILD')
        parts.insert(index,env.Part('TRACE_GUARD',trace_guard(self.tmp,owner,self.trace_snapshot),True,64,8))
        plan=replace(plan,parts=(env.Part('TRACE_OWNER',owner,True,0),)+tuple(parts))
        data=self.envelope(plan,label)
        check(data['TRACE_GUARD']=='TRACE_GUARD_OK\n','Missing pre-child trace guard')
        self.trace_check(data['TRACE_BEFORE']);env.validate_state(data,3600,self.before['boot_id'])
        return data,begin,end

    def writer(self,label):
        expected=['baseline',('aa10' if self.aa_candidate else 'sham_stock'),'return_stock']
        index=len(self.report['full_table_writes_attempted']);check(index<3 and label==expected[index],'No repeated/out-of-order writer')
        check(not self.panel_uncertain and not self.pending_read and not self.inflight,'No DSI into uncertainty')
        if label!='baseline':check(self.guard_context and self.short_armed and self.timed_watchdog_verified and self.remaining()>0,'Active watchdog required')
        started = self.monotonic()
        # Sticky before the first mode mutation, including isolation/readback
        # failure. No caught error may open a later DSI child without recovery.
        self.pending_read = self.panel_uncertain = True
        check(self.shell(aa.writer_esd_script(self.tmp, self.token), root=True,
                         label=label+'-writer-isolate', mutation=True) ==
              'WRITER_ESD_ISOLATED esd_sw_sim_success', 'Writer ESD isolation failed')
        isolated = self.monotonic()
        quiet = self.quiet(label+'_PRE', 3600)
        quiet_verified = self.monotonic()
        name='aa10' if label=='aa10' else 'stock';program=self.programs[name]
        self.pending_read=self.panel_uncertain=True
        if name=='aa10':
            check(self.candidate_attempts==0,'No candidate retry');self.candidate_attempts=1
            self.report.update(candidate_attempts=1,unknown_value_write_attempted=True,candidate_may_be_active=True)
        self.report['full_table_writes_attempted'].append(label);self._persist('before-'+label)
        dispatch=self.monotonic()
        child=aa.writer_script(self.tmp,self.token,program,name,self.entry_count)
        # Guard uses unchanged collision parser plus a fresh random nonreusable nonce.
        data,begin,end=self.aa_envelope(child,label+'-write',guard=(self.before['boot_id'],quiet['begin_marker'],uuid.uuid4().hex[:12]))
        check(data['CHILD'].startswith('WRITER_ESD_ISOLATED esd_sw_sim_success\nBLOCK_TRACE_BEGIN -1\n') and
              data['CHILD'].count('WRITER_ESD_ISOLATED esd_sw_sim_success') == 1,
              'Missing writer pre-first-chunk ESD readback')
        initial=re.findall(r'^BLOCK_TRACE_BEGIN -1\n(.*?)^BLOCK_TRACE_END -1$',data['CHILD'],re.M|re.S)
        check(len(initial)==1 and aa.tx._events(initial[0])==aa.tx._events(data['TRACE_BEFORE']),'Activity inside writer before first block')
        transaction=aa.tx.validate_batch_capture(data['CHILD'],self.entry_count)
        capture=re.findall(r'^BLOCK_TRACE_BEGIN 4\n(.*?)^BLOCK_TRACE_END 4$',data['CHILD'],re.M|re.S)
        check(len(capture)==1 and aa.tx._events(capture[0])==aa.tx._events(data['TRACE_AFTER']),'Activity after final writer callback')
        wire=aa.validate_wire(data['KERNEL'],begin,end,program,name,self.reference)
        aa.validate_wire(data['KERNEL'],quiet['begin_marker'],end,program,name,self.reference)
        self.entry_count=transaction['entry_count_after'];self.trace_snapshot=data['TRACE_AFTER']
        table_validated = self.monotonic()
        # Keep mode 5 through CHILD, final trace, END, kernel/state evidence and
        # authoritative host validation. Replace the old independent ESD read.
        check(self.shell(aa.writer_esd_script(self.tmp, self.token, restore=True), root=True,
                         label=label+'-writer-esd', mutation=True) ==
              'WRITER_ESD_RESTORED reg_read', 'Writer ESD restoration failed')
        restored = self.monotonic()
        esd_lifecycle = {
            'contract': acquisition.WRITER_ESD_CONTRACT,
            'isolated_mode': 'esd_sw_sim_success', 'restored_mode': 'reg_read',
            'pre_first_chunk_readback': True, 'inflight_cancellation_proven': False,
            'held_through': 'complete_table_trace_kernel_state_host_validation',
            'isolated_monotonic': isolated, 'quiet_verified_monotonic': quiet_verified,
            'table_validated_monotonic': table_validated, 'restored_monotonic': restored,
        }
        self.pending_read=False;self.panel_uncertain=False
        record={'label':label,'stage':label,'program':name,'program_name':name,'program_sha256':aa.HASHES[name],
                'quiet_evidence':quiet,'esd_lifecycle':esd_lifecycle,'started_at_utc':s.now(),'started_monotonic':started,'dispatch_monotonic':dispatch,
                'validated_monotonic':restored,'transaction':transaction,'wire':wire,
                'qualified':False,'phase_seconds':{'writer_and_quiet':self.monotonic()-started}}
        self.report['writes'].append({k:v for k,v in record.items() if k not in ('phase_seconds','qualified')})
        return record

    def selectors(self,label):
        check(not self.pending_read and not self.inflight,'Selectors forbidden after uncertainty')
        self.pending_read=True
        data,begin,end=self.aa_envelope(aa.selector_script(self.tmp,self.token,self.entry_count),label)
        result=aa.validate_selectors(data['CHILD'],data['TRACE_BEFORE'],data['TRACE_AFTER'],self.entry_count)
        s.verify_read_interval(data['KERNEL'],begin,end,self.reference)
        check(self.shell(s.esd_read_script(self.tmp),root=True,label=label+'-esd')=='reg_read','Selector ESD changed')
        self.entry_count=result['entry_count_after'];self.trace_snapshot=data['TRACE_AFTER'];self.pending_read=False
        return result

    def c1(self,label):
        check(not self.pending_read and not self.inflight,'C1 forbidden after uncertainty');self.pending_read=True
        nonce=self.child_nonce('c1')
        data,begin,end=self.aa_envelope(timed.p85.bounded_c1_reader(nonce,self.token),label+'-c1')
        result=s.validate_adapter_capture(data['CHILD'],nonce,3600)
        delta=a9.validate_c1_trace(data['TRACE_BEFORE'],data['TRACE_AFTER'],self.entry_count)
        check(not delta['background_esd'],'ESD event inside C1 operation envelope')
        s.verify_read_interval(data['KERNEL'],begin,end,self.reference)
        if label!='aa10':check(result['data']==[0,0,96],'Stock C1 changed')
        check(self.shell(s.esd_read_script(self.tmp),root=True,label=label+'-c1-esd')=='reg_read','C1 ESD changed')
        self.entry_count=delta['entry_count_after'];self.trace_snapshot=data['TRACE_AFTER'];self.pending_read=False
        return {**result,'main_trace':delta}

    def replay(self,label):
        check(not self.pending_read and not self.inflight, 'No replay into uncertainty')
        self.pending_read=True
        before=self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-replay-trace-before');self.trace_check(before)
        begin=self.mark(label.upper()+'_REPLAY_BEGIN')
        self.shell(f"printf '%s\\n' 3600 > {s.BL}brightness",root=True,label=label+'-replay',mutation=True)
        self.wait_value('cat '+s.BL+'brightness','3600')
        end=self.mark(label.upper()+'_REPLAY_END')
        result=validate_replay(self.shell('dmesg',root=True,label=label+'-replay-wire'),begin,end,self.reference)
        after=self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-replay-trace-after')
        result['main_trace']=validate_replay_trace(before,after,self.entry_count)
        self.trace_snapshot=after;self.pending_read=False;return result

    def target_ui_guard(self):
        path=self.target_ui_path
        return (f'test \"$(id -u)\" = 2000; test ! -L {path}; test -d {path}; '
                f'test \"$(stat -c %u {path})\" = 2000; test \"$(stat -c %a {path})\" = 700; '
                f'test ! -L {path}/owner; test -f {path}/owner; test \"$(stat -c %u {path}/owner)\" = 2000; '
                f'test \"$(stat -c %a {path}/owner)\" = 600; test \"$(cat {path}/owner)\" = {q(self.token)}')

    def target_ui(self,label):
        path=self.target_ui_path+'/redraw.xml'
        # dump may return zero without rewriting its output. Remove only our
        # guarded owned file, prove absence, and require a newly created file.
        command=('set -eu; '+self.target_ui_guard()+f'; test ! -L {path}; '
            f'if test -e {path}; then test -f {path}; test \"$(stat -c %u {path})\" = 2000; '
            f'test \"$(stat -c %a {path})\" = 600; rm {path}; fi; '
            f'test ! -e {path}; test ! -L {path}; uiautomator dump {path} >/dev/null; '
            f'test ! -L {path}; test -f {path}; test \"$(stat -c %u {path})\" = 2000; '
            f'chmod 600 {path}; test \"$(stat -c %a {path})\" = 600; '
            f'test \"$(wc -c < {path})\" -le 4194304; cat {path}')
        return ET.fromstring(self.shell(command,label=label))

    def target_scene(self,label,timeout=5,*,opening=False):
        text=self.shell('set -eu; '+self.target_ui_guard()+'; dumpsys activity top',label=label,timeout=timeout)
        return settings_scene(text,opening=opening)

    def redraw_audit(self,label,begin):
        end=self.mark('REDRAW_END_'+label)
        log=self.shell('dmesg',root=True,label=label+'-redraw-wire')
        result=a9.verify_redraw_interval(log,self.marker,label);s.qualify_quiet(log,begin,end,self.reference)
        trace=self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-redraw-trace');self.trace_check(trace)
        check(self.shell('settings get system screen_off_timeout',label=label+'-redraw-setting')==str(s.setup_timeout(self.before['screen_off_timeout'])),'Timeout changed')
        self.state(3600)
        return result

    def calibrate_redraw(self):
        """One-time semantic discovery, outside ALL measured stage phases.

        Do not load prior run snapshots or subtract their cost from an estimate.
        Every stage, including measured baseline, uses redraw() below unchanged.
        """
        check(self.redraw_ui_owned,'Owned ordinary target UI scratch required')
        check(self.redraw_scenes is None and self.active_start is None and not self.pending_read,
              'Redraw calibration must precede measured stages')
        self.pending_read=True
        label='calibration'
        begin=self.mark('REDRAW_BEGIN_'+label)
        for attempt in range(3):
            tree=self.target_ui(label+'-redraw-before');parents={c:p for p in tree.iter() for c in p}
            labels=[n for n in tree.iter('node') if n.get('text')=='Screen timeout' and n.get('package')=='com.android.settings']
            check(len(labels)<=1,'Ambiguous timeout row')
            if len(labels)==1:
                row=labels[0]
                while row.get('clickable')!='true':
                    check(row in parents,'No clickable timeout row');row=parents[row]
                check(not any(n.get('checkable')=='true' for n in row.iter('node')),'Unsafe redraw row')
                check(tree.get('rotation')=='0' and row.get('enabled')=='true','Unknown timeout row orientation/state')
                coords=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',row.get('bounds',''))
                check(coords is not None,'Bad redraw bounds');a,b,c,d=map(int,coords.groups())
                check(0<=a<c<=1440 and 0<=b<d<=3168,'Timeout row out of target bounds')
                ready=self.target_scene(label+'-scene-ready')
                check(ready['component']=='com.android.settings/.Settings$DisplaySettingsActivity' and ready['fragment']=='DisplaySettings',
                      'Calibration must start on observed Display settings')
                self.redraw_tap=[(a+c)//2,(b+d)//2]
                self.shell(f'input tap {self.redraw_tap[0]} {self.redraw_tap[1]}',label=label+'-redraw-open',mutation=True)
                opened_xml=self.target_ui(label+'-redraw-opened')
                options=('15 seconds','30 seconds','1 minute','2 minutes','5 minutes','10 minutes','30 minutes')
                titles=[n.get('text') for n in opened_xml.iter('node') if n.get('resource-id')=='android:id/title' and
                        n.get('package')=='com.android.settings' and n.get('text') in options]
                toolbars=[n.get('content-desc') for n in opened_xml.iter('node') if
                          n.get('resource-id')=='com.android.settings:id/collapsing_toolbar' and n.get('package')=='com.android.settings']
                check(opened_xml.get('rotation')=='0' and titles==list(options) and toolbars==['Screen timeout'] and
                      ET.tostring(opened_xml)!=ET.tostring(tree),'Missing fresh exact timeout options page')
                opened=self.target_scene(label+'-scene-opened')
                check(opened['component']=='com.android.settings/.SubSettings' and opened['fragment']=='ScreenTimeoutSettings' and
                      opened['pid']==ready['pid'] and opened['hierarchy']!=ready['hierarchy'],
                      'Opened scene must be distinct in the same Settings process')
                self.shell('input keyevent 4',label=label+'-redraw-cancel',mutation=True)
                returned_xml=self.target_ui(label+'-redraw-returned')
                check(ET.tostring(returned_xml)==ET.tostring(tree),'Did not return to identical Settings scene')
                returned=self.target_scene(label+'-scene-returned')
                check(returned==ready,'Returned framework scene changed')
                break
            check(attempt<2,'Native timeout chooser unavailable')
            self.shell('input swipe 720 2780 720 850 400',label=label+'-redraw-scroll',mutation=True)
        audit=self.redraw_audit(label,begin)
        self.redraw_scenes={'ready':ready,'opened':opened}
        self.report['redraw_ui_calibration']={'contract':REDRAW_SCENE_CONTRACT,
            'source_commit':self.report['source_commit'],'boot_id':self.before['boot_id'],
            'tap_xy':self.redraw_tap,'scene_sha256':{k:scene_digest(v) for k,v in self.redraw_scenes.items()},
            'components':{k:v['component'] for k,v in self.redraw_scenes.items()},
            'fragments':{k:v['fragment'] for k,v in self.redraw_scenes.items()},
            'semantic_xml_verified':True,'returned_xml_equals_ready':True,
            'live_text_or_checked_verification':False,'audit':audit,
            'completed_monotonic':self.monotonic()}
        self.pending_read=False

    def settle_scene(self,label,expected,previous,*,opening=False):
        # A single total acceptance deadline, never a fresh budget per poll.
        # The inherited ADB version handshake has its own timeout, so this is
        # not a new transport wall bound. Reject late results; the unchanged
        # outer37 alarm remains the active-window interruption/recovery guard.
        if opening:
            check(label.endswith('-scene-opened') and
                  expected.get('component')=='com.android.settings/.SubSettings' and
                  expected.get('fragment')=='ScreenTimeoutSettings' and
                  previous.get('component')=='com.android.settings/.Settings$DisplaySettingsActivity' and
                  previous.get('fragment')=='DisplaySettings','Pending reads allowed only while opening timeout page')
        deadline=self.monotonic()+REDRAW_SETTLE_SECONDS
        if self.active_start is not None:deadline=min(deadline,self.monotonic()+self.remaining())
        while True:
            left=deadline-self.monotonic();check(left>0,'Settings transition exceeded acceptance deadline')
            try:
                observed=self.target_scene(label,timeout=left,opening=opening)
            except SettingsOpeningPending as exc:
                # Parsing completed, but this is NEVER settled success. Only
                # the entire same-trial expected opened scene may be reread.
                check(opening and exc.scene==expected,'Unexpected pending Settings scene')
                observed=None
            check(self.monotonic()<=deadline,'Late Settings scene result')
            if observed==expected:return scene_digest(observed)
            # Otherwise permit only the complete known previous stable scene.
            # All other parse/lifecycle/identity/transport failures are terminal.
            check(observed is None or observed==previous,'Unexpected Settings transition scene')
            self.sleep(min(.05,max(0,deadline-self.monotonic())))

    def redraw(self,label):
        check(self.redraw_ui_owned and self.redraw_scenes is not None,'Same-trial Settings calibration required')
        check(not self.pending_read and not self.inflight,'No redraw into uncertainty')
        self.pending_read=True
        begin=self.mark('REDRAW_BEGIN_'+label)
        ready,opened=self.redraw_scenes['ready'],self.redraw_scenes['opened']
        before=self.target_scene(label+'-scene-ready')
        check(before==ready,'Settings scene changed before input')
        self.shell(f'input tap {self.redraw_tap[0]} {self.redraw_tap[1]}',label=label+'-redraw-open',mutation=True)
        opened_digest=self.settle_scene(label+'-scene-opened',opened,ready,opening=True)
        self.shell('input keyevent 4',label=label+'-redraw-cancel',mutation=True)
        returned_digest=self.settle_scene(label+'-scene-returned',ready,opened)
        result=self.redraw_audit(label,begin)
        result.update(scene_contract=REDRAW_SCENE_CONTRACT,
            scene_sha256=[scene_digest(before),opened_digest,returned_digest])
        self.pending_read=False
        return result

    def prehold(self,record):
        check(not self.pending_read and not self.inflight, 'No prehold into uncertainty')
        label=record['label'];self.panel_uncertain=True
        record['prehold_started_monotonic']=self.monotonic()
        for key,operation in (('same_dbv_replay',self.replay),('redraw_audit',self.redraw),('selectors_before_hold',self.selectors),('c1',self.c1)):
            start=self.monotonic();record[key]=operation(label if key not in ('selectors_before_hold',) else label+'-before-hold')
            record['phase_seconds'][key]=self.monotonic()-start
        self.state(3600);self.panel_uncertain=False
        record['prehold_qualified_monotonic']=self.monotonic()

    def finish_hold(self,record):
        check(not self.pending_read and not self.inflight, 'No hold into uncertainty')
        label=record['label'];self.panel_uncertain=True
        self.optical_hold(label,record)
        trace=self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-hold-trace');self.trace_check(trace)
        start=self.monotonic();record['selectors_after_hold']=self.selectors(label+'-after-hold')
        record['phase_seconds']['selectors_after_hold']=self.monotonic()-start
        record['postselectors_verified_monotonic']=self.monotonic()
        record.update(qualified=True,elapsed_seconds=self.monotonic()-record['started_monotonic'])
        self.report['stages'].append(record);self.panel_uncertain=False;self._persist('stage-'+label)
        if label=='baseline':self.baseline_image()

    def baseline_image(self):
        rc,image,err=self.g.shell(self.camera,'screencap -p',15)
        check(rc==0 and not err and image.startswith(b'\x89PNG\r\n\x1a\n'),'Baseline screenshot unavailable')
        path=self.private/'baseline-camera-review.png'
        with path.open('xb') as stream:stream.write(image)
        path.chmod(0o600)
        self.report.update(baseline_review_image_sha256=hashlib.sha256(image).hexdigest(),baseline_review_image_private_label=path.name,
            geometry_limit='Baseline-only scene geometry requires offline review against frozen ROI; metadata is not geometry proof')
        self.save()

    def return_estimate(self):
        return {'status':'unknown_not_a_bound','reason':'Full table replay/redraw/selectors composition; hard37s cutoff unchanged'}

    def restore(self):
        check(not self.panel_uncertain and not self.pending_read and not self.inflight and not self.recovery_failed,'No AA cleanup into uncertainty')
        if self.redraw_ui_owned:
            path=self.target_ui_path
            self.shell('set -eu; '+self.target_ui_guard()+f'; test ! -L {path}/redraw.xml; rm -f {path}/redraw.xml; rm {path}/owner; rmdir {path}; test ! -e {path}',label='target-ui-cleanup')
            self.report['target_ui_temp_removed']=True;self.redraw_ui_owned=False
        if self.trace_owned:
            if self.report.get('recovery_reboot_verified'):
                self.shell(self.ops['verify']+f'; test ! -e {aa.TRACE}; '+absent_probes(),root=True,label='main-trace-reboot-clean')
            else:
                self.trace_check(self.shell('cat '+aa.TRACE+'/trace',root=True,label='main-trace-final'))
                command=self.ops['verify']+f'; test "$(cat {self.tmp}/main-trace-owner)" = {q(self.token)}; printf 0 > {aa.TRACE}/tracing_on; '
                for name in aa.PROBES:command+=f'printf 0 > {aa.TRACE}/events/pwm_mode/{name}/enable; '
                command+=f'rmdir {aa.TRACE}; '
                for name in aa.PROBES:command+=f"printf '%s\\n' '-:pwm_mode/{name}' >> /sys/kernel/tracing/kprobe_events; "
                command+=f'test ! -e {aa.TRACE}; '+absent_probes()
                self.shell(command,root=True,label='main-trace-cleanup')
            self.report['main_trace_removed_verified']=True
        if self.chunks_owned:
            paths=[self.tmp+'/chunks/'+n for name,data in self.programs.items() for n in aa.chunk_files(data,name)]
            self.shell(self.ops['verify']+'; rm -f '+' '.join(paths)+f'; rmdir {self.tmp}/chunks',root=True,label='chunks-cleanup')
            self.report['chunks_removed_verified']=True
        if self.temp:
            paths=['main-guard-snapshot','main-guard-events','main-guard-prefix','main-guard-gap','main-trace-owner','transaction_trace','transaction-previous','transaction-events','transaction-prefix','selector-trace','selector-previous','selector-events','selector-prefix']
            self.shell(self.ops['verify']+'; rm -f '+' '.join(self.tmp+'/'+p for p in paths),root=True,label='aa-scratch-cleanup')
        super().restore()

    def execute(self):
        error=None
        try:
            self.setup();self.setup_aa();self.calibrate_redraw()
            record=self.writer('baseline');self.prehold(record);self.finish_hold(record)
            self.identity();self.camera_identity();self.metadata('pre-aa');self.state(3600)
            phases=record['phase_seconds'];full=sum(phases.values())
            prehold=full-phases['hold_and_metadata']-phases['selectors_after_hold']
            estimate=full+prehold+3.0
            self.report['prearm_planning_estimate']={'observed_baseline_phase_seconds':dict(phases),
                'estimated_active_seconds':estimate,'planning_margin_seconds':3.0,
                'status':'observation_not_a_bound','redraw_scene_contract':REDRAW_SCENE_CONTRACT}
            self.save();check(estimate<37,'Measured baseline composition does not fit37s; stopped before short arm')
            with self.active_window():
                self.arm_timed()
                record=self.writer('aa10' if self.aa_candidate else 'sham_stock');self.prehold(record);self.finish_hold(record)
                record=self.writer('return_stock');self.prehold(record)
                check(not self.pending_read and not self.panel_uncertain and not self.inflight,'Uncertain stock return')
                self.explicit_return_verified=True;self.report['explicit_full_stock_return_verified']=True
                qualified=self.monotonic();self.report['return_qualified_monotonic']=qualified
                self.disarm_short();disarmed=self.monotonic()
                self.report.update(disarmed_monotonic=disarmed,disarm_seconds=disarmed-qualified,active_G_seconds=disarmed-self.active_start)
            self.finish_hold(record);self.report['return_hold_and_postselectors_verified']=True
            self.report['candidate_may_be_active']='latent DDIC state unknown; operational stock markers restored' if self.aa_candidate else False
        except BaseException as exc:
            error=exc;self.report.update(status='failed',error_type=type(exc).__name__)
            if self.panel_uncertain or self.pending_read or self.inflight or self.short_armed:
                try:self.recover()
                except BaseException:pass
        finally:
            try:self.stop_camera(defer_video_validation=True,bounded_pull=True)
            except BaseException as exc:self.report['camera_cleanup_error_type']=type(exc).__name__;error=error or exc
            try:self.cleanup_camera_xml()
            except BaseException as exc:self.report['camera_ui_cleanup_pending']=True;error=error or exc
            if not self.recovery_failed:
                try:
                    if self.short_armed:self.disarm_short()
                    self.restore()
                except BaseException as exc:self.report['cleanup_error_type']=type(exc).__name__;error=error or exc
            self.report['finished_at_utc']=s.now()
            if error:self.report['status']='failed; inspect recovery and retained watchdog/owner'
            self.save()
        if error:raise RuntimeError('AA trial failed; no retry') from error
        self.report.update(evidence_kind='acquisition',video_lifecycle_complete=True,status='awaiting_offline_video_validation')
        self.save();return self.report


def main(*,host_inputs=None,verified_sources=None,host_dependencies=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=int);parser.add_argument('camera',type=int)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--stock-only',action='store_true');group.add_argument('--aa10',action='store_true')
    parser.add_argument('--stock-qualification',type=Path);parser.add_argument('--optical-qualification',type=Path)
    parser.add_argument('--experiment-id',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args();s.plan(args.experiment_id)
    check(args.target>0 and args.camera>0 and args.target!=args.camera,'Distinct transports')
    from host_entrypoint import AA_HARDWARE_PATHS,private_path,source_gate,prepare
    source=base.source_provenance(paths=AA_HARDWARE_PATHS,require_clean=args.execute)
    if not args.execute:
        print(json.dumps({**source,'offline_only':True,'scope':CANDIDATE_SCOPE if args.aa10 else STOCK_SCOPE},indent=2));return
    check(host_inputs is not None and verified_sources is not None and host_dependencies is not None,'Verified host inputs required')
    check(verified_sources.get('profile')=='aa','AA fixed-source profile required');source_gate(verified_sources)
    qualification_record=json.loads(args.stock_qualification.read_text()) if args.stock_qualification else None
    optical_record=json.loads(args.optical_qualification.read_text()) if args.optical_qualification else None
    if args.aa10:
        qualification(qualification_record,source)
        acquisition.validate_stock_qualification(qualification_record,optical_record,source)
    private=Path(str(private_path(host_inputs)));check(not private.exists() and not args.output.exists(),'Fresh output/private directories required')
    args.output.mkdir(parents=True);prepared=prepare(verified_sources,host_inputs,host_dependencies)
    try:
        run=AATimedTrial(prepared.adapter,args.target,args.camera,args.experiment_id,args.output,private,
            aa_candidate=args.aa10,stock_qualification=qualification_record,optical_qualification=optical_record,source_record=source,
            sleep=host_dependencies.sleep,monotonic=host_dependencies.monotonic)
        run.report.update(source);prepared.owned.verify()
        owner=private/'owner.txt';owner.write_text(run.token+'\n');owner.chmod(0o600);prepared.owned.verify()
        def abort(signum,frame):raise KeyboardInterrupt('Termination requested')
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,abort)
        run.save();run.execute();prepared.finalize(run,(args.output/'run.json').read_bytes())
    finally:prepared.close()
    print(json.dumps({'status':run.report['status'],'candidate_attempts':run.report['candidate_attempts'],'pwm_hz':None}))

if __name__=='__main__':main()
