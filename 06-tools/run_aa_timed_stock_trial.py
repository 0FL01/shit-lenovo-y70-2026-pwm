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


class SettingsTransitionPending(ValueError):
    """Complete live scene with unready lifecycle; grants read-only waiting."""
    def __init__(self,scene,*,finished):
        super().__init__('Settings transition is not settled')
        self.scene=scene;self.finished=finished


def _scene_hierarchy(lines,*,complete=True):
    hierarchy=[];depths=[];ancestors=[];generated_ids=0
    for line in lines:
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
    check(len(hierarchy)<=4096 and (not complete or len(hierarchy)>=5) and
          (not hierarchy or hierarchy[0][1]=='com.android.internal.policy.DecorView'),
          'Incomplete Settings decor tree')
    return hierarchy


def _complete_settings_scene(text,*,transition=False):
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
    activities=[];resumed=[]
    for i,start in enumerate(starts):
        body=text[start.end():starts[i+1].start() if i+1<len(starts) else len(text)].split('\nTASK ',1)[0]
        local_headers=list(re.finditer(r'^    Local Activity\b[^\n]*',body,re.M))
        check(len(local_headers)==1,'Missing/duplicate native activity state')
        local_header=local_headers[0]
        check(re.fullmatch(r'    Local Activity [0-9a-f]+ State:',local_header[0]),'Malformed native activity header')
        local=body[local_header.end():].split('\n    ViewRoot:',1)[0]
        states=re.findall(r'^      mResumed\b([^\n]*)$',local,re.M)
        check(len(states)==1,'Missing/duplicate native activity lifecycle')
        parsed_state=re.fullmatch(r'=(true|false) mStopped=(true|false) mFinished=(true|false)',states[0])
        check(parsed_state is not None,'Malformed native activity lifecycle')
        state=parsed_state.groups()
        check(state[:2]!=('true','true'),'Contradictory native activity lifecycle')
        activity=(start[1],body,local,state);activities.append(activity)
        if state[0]=='true':resumed.append(activity)
    check(len(resumed)<=1,'Ambiguous resumed activities')
    if resumed:
        selected=resumed[0]
    else:
        # A top dump taken after Back can contain only the finishing source.
        # Absence of a resumed activity is not success or a generic retry:
        # require one complete Settings context, then bind it in settle_scene.
        check(transition,'Missing resumed activity')
        candidates=[a for a in activities if a[0].startswith('com.android.settings/')]
        check(len(candidates)==1 and all(a is candidates[0] or a[3][1]=='true' for a in activities),
              'Missing/ambiguous live Settings transition context')
        selected=candidates[0]
    header,body,local,state=selected
    identity=re.fullmatch(r'(com\.android\.settings/[^ ]+) [0-9a-f]+ pid=(\d+) userId=0 uid=1000 displayId=0\(type=INTERNAL\)',header)
    check(identity is not None,'Unexpected Settings identity')
    # Count the consumed header prefix before validating its spelling. A
    # malformed duplicate must not disappear behind one valid header.
    for prefix,pattern in ((r'ViewRoot\b',r'ViewRoot:'),(r'View Hierarchy\b',r'View Hierarchy:'),
                           (r'Choreographer\b',r'Choreographer:'),
                           (r'Looper\b',r'Looper \(main,[^\n]+'),
                           (r'Local FragmentActivity\b',r'Local FragmentActivity [0-9a-f]+ State:'),
                           (r'Added Fragments\b',r'Added Fragments:')):
        headers=re.findall(r'^    ('+prefix+r'[^\n]*)$',body,re.M)
        check(len(headers)==1 and re.fullmatch(pattern,headers[0]),'Missing/malformed/duplicate Settings header: '+prefix)
    check(re.findall(r'^      mIsInMultiWindowMode=([^\n]+)$',local,re.M)==['false mIsInPictureInPictureMode=false'] and
          len(re.findall(r'^      mIsInMultiWindowMode\b',local,re.M))==1 and
          re.findall(r'^      mChangingConfigurations=([^\n]*)$',local,re.M)==['false'] and
          len(re.findall(r'^      mChangingConfigurations\b',local,re.M))==1,'Settings configuration transition')
    configs=re.findall(r'^      mCurrentConfig=(.+)$',local,re.M)
    check(len(configs)==1 and len(re.findall(r'^      mCurrentConfig\b',local,re.M))==1 and 'mDisplayRotation=ROTATION_0' in configs[0] and
          'mWindowingMode=fullscreen' in configs[0],'Unknown Settings display configuration')
    roots=re.findall(r'^    ViewRoot:\n(.*?)^    View Hierarchy:\n',body,re.M|re.S)
    check(len(roots)==1,'Missing/ambiguous Settings ViewRoot')
    def field(section,key,pattern,indent=6):
        values=re.findall(r'^'+' '*indent+re.escape(key)+r'\b([^\n]*)$',section,re.M)
        check(len(values)==1 and re.fullmatch('=(?:'+pattern+')',values[0]),'Missing/invalid/duplicate Settings field: '+key)
        return values[0][1:]
    root={key:field(roots[0],key,r'true|false') for key in
          ('mAdded','mRemoved','mStopped','mPausedForTransition','mProcessInputEventsScheduled','mTraversalScheduled')}
    check(root['mAdded']=='true' and root['mRemoved']=='false','Settings ViewRoot removed/not added')
    count=field(roots[0],'mPendingInputEventCount',r'0|[1-9]\d*')
    focus=field(roots[0],'mHasWindowFocus',r'true|false',8)
    visibility=field(roots[0],'mWindowVisibility',r'0|4|8',8)
    choreographer=re.findall(r'^    Choreographer:\n(.*?)(?=^    [^ ]|\Z)',roots[0],re.M|re.S)
    check(len(choreographer)==1,'Missing/ambiguous Settings Choreographer')
    field(choreographer[0],'mFrameScheduled',r'true|false')
    trees=re.findall(r'^    View Hierarchy:\n(.*?)^    Looper \(main,',body,re.M|re.S)
    check(len(trees)==1,'Incomplete Settings hierarchy boundary')
    hierarchy=_scene_hierarchy(trees[0].splitlines())
    support=re.findall(r'^    Local FragmentActivity [0-9a-f]+ State:\n(.*)',body,re.M|re.S)
    check(len(support)==1,'Missing/ambiguous support fragment state')
    active=re.fullmatch(r'      mCreated=(true|false) mResumed=(true|false) mStopped=(true|false)    Active Fragments:\n(.*?)^    Added Fragments:\n(.*)',support[0],re.M|re.S)
    check(active is not None and len(re.findall(r'^      mCreated\b',support[0],re.M))==1,
          'Malformed/duplicate support fragment manager')
    created,support_resumed,support_stopped,active_body,added_body=active.groups()
    check(created=='true' and (support_resumed,support_stopped)!=('true','true'),
          'Uncreated/contradictory support fragment manager')
    fragments=re.findall(r'^    ([A-Za-z_$][\w.$]*\{[0-9a-f]+\} \([0-9a-f-]+ id=0x[0-9a-f]+\))$',active_body,re.M)
    check(len(fragments)==1 and len(re.findall(r'^    [A-Za-z_$][\w.$]*\{',active_body,re.M))==1,
          'Malformed/ambiguous current Settings fragment')
    fragment=fragments[0];fragment_class=fragment.split('{',1)[0]
    fragment_lines=re.findall(r'^        mState\b([^\n]*)$',active_body,re.M)
    check(len(fragment_lines)==1,'Missing/duplicate Settings fragment state')
    fragment_state=re.fullmatch(r'=(\S+) mWho=[^ ]+ mBackStackNesting=\d+',fragment_lines[0])
    check(fragment_state is not None,'Malformed Settings fragment state')
    fragment_states=[fragment_state[1]]
    # AndroidX VIEW_CREATED=2 through RESUMED=7 retain a view, including
    # AWAITING_EXIT_EFFECTS=3. destroyFragmentView runs on descent to CREATED=1.
    check(len(fragment_states)==1 and fragment_states[0] in ('2','3','4','5','6','7'),
          'Missing/invalid/duplicate live Settings fragment state')
    check(re.findall(r'^        mAdded=([^\n]+)$',active_body,re.M)==
          ['true mRemoving=false mFromLayout=false mInLayout=false'] and
          len(re.findall(r'^        mAdded\b',active_body,re.M))==1 and
          len(re.findall(r'^        mHidden=false mDetached=false mMenuVisible=true mHasMenu=(?:true|false)$',active_body,re.M))==1 and
          len(re.findall(r'^        mHidden\b',active_body,re.M))==1,
          'Settings fragment removed/detached/hidden')
    added=added_body.split('\n    ',1)[0]
    check(added.strip()=='#0: '+fragment,'Current/added fragment mismatch')
    tail_lines=re.findall(r'^      mCurState\b([^\n]*)$',added_body,re.M)
    check(len(tail_lines)==1,'Missing/duplicate support fragment tail')
    tail=re.fullmatch(r'=(\S+) mStateSaved=(true|false) mStopped=(true|false) mDestroyed=(true|false)',tail_lines[0])
    check(tail is not None,'Malformed support fragment tail')
    tails=[tail.groups()]
    check(tails[0][0] in ('2','3','4','5','6','7') and tails[0][3]=='false' and
          re.search(r'\n      mCurState=\S+ mStateSaved=(?:true|false) mStopped=(?:true|false) mDestroyed=false\s*\Z',added_body),
          'Incomplete/invalid/destroyed support fragment tail')
    scene={'component':identity[1],'pid':int(identity[2]),'fragment':fragment_class,
           'configuration':configs[0],'hierarchy':hierarchy}
    # Keep the previous stable-success predicate. FrameScheduled is parsed,
    # but was never itself a stable-success gate. All ordinary readiness
    # changes can only request another read, never grant action authority.
    stable=(state==('true','false','false') and root['mStopped']=='false' and
            root['mPausedForTransition']=='false' and count=='0' and
            root['mProcessInputEventsScheduled']=='false' and root['mTraversalScheduled']=='false' and
            focus=='true' and visibility=='0' and support_resumed=='true' and support_stopped=='false' and
            fragment_states==['7'] and tails==[('7','false','false','false')])
    if not stable:
        check(transition,'Unsettled Settings scene')
        raise SettingsTransitionPending(scene,finished=state[2]=='true')
    return scene


class IncompleteSettingsObservation(ValueError):
    """Missing observation data only; contains no scene or success digest."""
    def __init__(self,missing):
        super().__init__('Incomplete Settings observation: '+', '.join(missing))
        self.missing=tuple(missing)


def _available_settings_context(text,expected,previous):
    """Validate every present field before classifying missing observation data.

    Android's asynchronous activity dump can lose its client activity after the
    system prints its header. Missing data grants only another bounded read;
    present contradictions must not hide behind an earlier missing section.
    """
    known={scene['component']:scene for scene in (expected,previous)}
    starts=list(re.finditer(r'^  ACTIVITY ([^\n]+)$',text,re.M))
    check(starts,'Missing activity identity, not a bound Settings observation')
    check(len({start[1] for start in starts})==len(starts),'Duplicate activity observation identity')
    missing=[];known_headers=0;resumed=[];foreign_states=[]
    for index,start in enumerate(starts):
        missing_before=len(missing)
        body=text[start.end():starts[index+1].start() if index+1<len(starts) else len(text)].split('\nTASK ',1)[0]
        header=re.fullmatch(r'([^ ]+) [0-9a-f]+ pid=(\d+) userId=(\d+) uid=(\d+) displayId=(\d+)\(type=([A-Z]+)\)',start[1])
        check(header is not None,'Malformed activity observation identity')
        component=header[1];scene=known.get(component)
        if scene is not None:
            known_headers+=1
            check((int(header[2]),header[3],header[4],header[5],header[6])==
                  (scene['pid'],'0','1000','0','INTERNAL'),'Settings observation identity changed')

        def take(prefix,pattern,name,*,section=body):
            lines=[line for line in section.splitlines() if re.match(prefix,line)]
            if not lines:
                missing.append(name);return None
            check(len(lines)==1,'Duplicate Settings observation field: '+name)
            match=re.fullmatch(pattern,lines[0])
            check(match is not None,'Malformed Settings observation field: '+name)
            return match

        take(r'^    Local Activity\b',r'    Local Activity [0-9a-f]+ State:','native header')
        native=take(r'^      mResumed\b',r'      mResumed=(true|false) mStopped=(true|false) mFinished=(true|false)','native lifecycle')
        if native is not None:
            check(native.groups()[:2]!=('true','true'),'Contradictory native observation lifecycle')
            if native[1]=='true':
                resumed.append(component);check(scene is not None,'Foreign resumed activity observation')
            if scene is None:foreign_states.append(native.groups())
            elif native[3]=='true':check(component==previous['component'],'Expected destination is finished')
        if scene is None and component.startswith('com.android.settings/'):
            # A historical Settings home activity may coexist with the live
            # calibrated chooser. It is not a scene candidate. Require complete
            # independent evidence of a stopped, hidden instance in the same
            # Settings process before ignoring its unrelated fragment/tree data.
            # Missing evidence here is terminal, never a generic retry permit.
            check(all((int(header[2]),header[3],header[4],header[5],header[6])==
                      (item['pid'],'0','1000','0','INTERNAL') for item in (expected,previous)),
                  'Foreign Settings observation identity')
            def stopped(prefix,pattern,name,*,section=body):
                # Keep whole-block duplicate/contradiction rejection as well as
                # requiring the field inside its actual owning section.
                if section is not body:take(prefix,pattern,name)
                value=take(prefix,pattern,name,section=section)
                check(value is not None,'Incomplete historical Settings evidence: '+name)
                return value
            check(native is not None and native.groups()==('false','true','false'),
                  'Foreign live Settings observation')
            stopped(r'^    ViewRoot\b',r'    ViewRoot:','historical root header')
            stopped(r'^    View Hierarchy\b',r'    View Hierarchy:','historical hierarchy boundary')
            stopped(r'^    Local FragmentActivity\b',r'    Local FragmentActivity [0-9a-f]+ State:',
                    'historical support header')
            stopped(r'^    Added Fragments\b',r'    Added Fragments:','historical added boundary')
            stopped(r'^    FragmentManager misc state\b',r'    FragmentManager misc state:',
                    'historical manager boundary')
            native_start=re.search(r'^    Local Activity [0-9a-f]+ State:\n',body,re.M)
            root_start=re.search(r'^    ViewRoot:\n',body,re.M)
            tree_start=re.search(r'^    View Hierarchy:\n',body,re.M)
            support_start=re.search(r'^    Local FragmentActivity [0-9a-f]+ State:\n',body,re.M)
            added_start=re.search(r'^    Added Fragments:\n',body,re.M)
            manager_start=re.search(r'^    FragmentManager misc state:\n',body,re.M)
            check(all(item is not None for item in (native_start,root_start,tree_start,support_start,added_start,manager_start)) and
                  native_start.end()<=root_start.start() and root_start.end()<=tree_start.start()<support_start.start()<added_start.start()<manager_start.start(),
                  'Invalid historical Settings section order')
            native_section=body[native_start.end():root_start.start()]
            root_section=re.split(r'^    \S',body[root_start.end():tree_start.start()],maxsplit=1,flags=re.M)[0]
            support_section=re.split(r'^    \S',body[support_start.end():added_start.start()],maxsplit=1,flags=re.M)[0]
            stopped(r'^      mResumed\b',r'      mResumed=false mStopped=true mFinished=false',
                    'historical native lifecycle',section=native_section)
            manager_section=re.split(r'^    \S',body[manager_start.end():],maxsplit=1,flags=re.M)[0]
            for key,value in (('mAdded','true'),('mRemoved','false'),('mStopped','true')):
                stopped(r'^      '+key+r'\b',r'      '+key+'='+value,'historical '+key,section=root_section)
            stopped(r'^        mHasWindowFocus\b',r'        mHasWindowFocus=false','historical focus',section=root_section)
            stopped(r'^        mWindowVisibility\b',r'        mWindowVisibility=8','historical visibility',section=root_section)
            stopped(r'^      mCreated\b',
                    r'      mCreated=true mResumed=false mStopped=true    Active Fragments:',
                    'historical support lifecycle',section=support_section)
            stopped(r'^      mCurState\b',
                    r'      mCurState=4 mStateSaved=(true|false) mStopped=true mDestroyed=false',
                    'historical support tail',section=manager_section)
            check(len(missing)==missing_before,'Incomplete historical Settings observation')
        if scene is None:continue

        modes=take(r'^      mIsInMultiWindowMode\b',r'      mIsInMultiWindowMode=(true|false) mIsInPictureInPictureMode=(true|false)','window modes')
        if modes is not None:check(modes.groups()==('false','false'),'Settings observation window mode changed')
        changing=take(r'^      mChangingConfigurations\b',r'      mChangingConfigurations=(true|false)','changing configuration')
        if changing is not None:check(changing[1]=='false','Settings observation configuration transition')
        config=take(r'^      mCurrentConfig\b',r'      mCurrentConfig=(.+)','configuration')
        if config is not None:check(config[1]==scene['configuration'],'Settings observation configuration changed')

        take(r'^    ViewRoot\b',r'    ViewRoot:','ViewRoot header')
        root_values={}
        for key in ('mAdded','mRemoved','mStopped','mPausedForTransition','mProcessInputEventsScheduled','mTraversalScheduled'):
            value=take(r'^      '+key+r'\b',r'      '+key+r'=(true|false)',key)
            root_values[key]=value[1] if value is not None else None
            if value is not None and key in ('mAdded','mRemoved'):
                check(value[1]==('true' if key=='mAdded' else 'false'),'Settings observation root removed/not added')
        take(r'^      mPendingInputEventCount\b',r'      mPendingInputEventCount=(0|[1-9]\d*)','pending input count')
        focus=take(r'^        mHasWindowFocus\b',r'        mHasWindowFocus=(true|false)','window focus')
        visibility=take(r'^        mWindowVisibility\b',r'        mWindowVisibility=(0|4|8)','window visibility')
        take(r'^    Choreographer\b',r'    Choreographer:','Choreographer header')
        take(r'^      mFrameScheduled\b',r'      mFrameScheduled=(true|false)','frame scheduled')

        tree_header=take(r'^    View Hierarchy\b',r'    View Hierarchy:','hierarchy header')
        looper=take(r'^    Looper\b',r'    Looper \(main,[^\n]+','hierarchy tail')
        hierarchy=None;complete=False
        if tree_header is not None:
            tree_start=re.search(r'^    View Hierarchy:(?:\n|\Z)',body,re.M)
            check(tree_start is not None,'Malformed hierarchy header boundary')
            tail=body[tree_start.end():]
            boundary=re.search(r'^    \S',tail,re.M)
            lines=tail[:boundary.start() if boundary else len(tail)].splitlines()
            complete=boundary is not None and tail[boundary.start():].startswith('    Looper (main,')
            hierarchy=_scene_hierarchy(lines,complete=complete)
            if not complete:missing.append('complete hierarchy')

        take(r'^    Local FragmentActivity\b',r'    Local FragmentActivity [0-9a-f]+ State:','support header')
        support=take(r'^      mCreated\b',r'      mCreated=(true|false) mResumed=(true|false) mStopped=(true|false)    Active Fragments:','support lifecycle')
        if support is not None:
            check(support[1]=='true' and support.groups()[1:]!=('true','true'),
                  'Uncreated/contradictory Settings observation fragment manager')
        # Looper messages can contain transaction items with the same class{
        # prefix. Only the support manager's Active Fragments section owns
        # fragment identities, matching the complete-scene parser's boundary.
        support_start=re.search(r'^    Local FragmentActivity [0-9a-f]+ State:(?:\n|\Z)',body,re.M)
        fragment_section=body[support_start.end():].split('\n    Added Fragments:',1)[0] if support_start else body
        fragments=[line for line in fragment_section.splitlines() if re.match(r'^    [A-Za-z_$][\w.$]*\{',line)]
        fragment=None
        if not fragments:missing.append('active fragment identity')
        else:
            check(len(fragments)==1,'Duplicate active Settings observation fragment')
            fragment=re.fullmatch(r'    ([A-Za-z_$][\w.$]*)\{[0-9a-f]+\} \([0-9a-f-]+ id=0x[0-9a-f]+\)',fragments[0])
            check(fragment is not None,'Malformed active Settings observation fragment')
        fragment_state=take(r'^        mState\b',r'        mState=([2-7]) mWho=[^ ]+ mBackStackNesting=\d+','live fragment state')
        added=take(r'^        mAdded\b',r'        mAdded=(true|false) mRemoving=(true|false) mFromLayout=(true|false) mInLayout=(true|false)','fragment membership')
        if added is not None:check(added.groups()==('true','false','false','false'),'Settings observation fragment removed')
        visible=take(r'^        mHidden\b',r'        mHidden=(true|false) mDetached=(true|false) mMenuVisible=(true|false) mHasMenu=(true|false)','fragment visibility')
        if visible is not None:check(visible.groups()[:3]==('false','false','true'),'Settings observation fragment detached/hidden')
        take(r'^    Added Fragments\b',r'    Added Fragments:','added fragment header')
        support_start=re.search(r'^    Local FragmentActivity [0-9a-f]+ State:(?:\n|\Z)',body,re.M)
        added_start=re.search(r'^    Added Fragments:(?:\n|\Z)',body,re.M)
        added_section=(body[added_start.end():].split('\n    ',1)[0] if added_start else
                       body[support_start.end():] if support_start else body)
        added_identity=take(r'^      #\d+\b',r'      #0: (.+)','added fragment identity',section=added_section)
        added_match=None
        if added_identity is not None:
            added_match=re.fullmatch(r'([A-Za-z_$][\w.$]*)\{[0-9a-f]+\} \([0-9a-f-]+ id=0x[0-9a-f]+\)',added_identity[1])
            check(added_match is not None,'Malformed Settings observation added fragment')
            if fragment is not None:check(added_identity[1]==fragments[0].strip(),'Settings observation active/added mismatch')
        manager=take(r'^      mCurState\b',r'      mCurState=([2-7]) mStateSaved=(true|false) mStopped=(true|false) mDestroyed=(true|false)','fragment manager tail')
        if manager is not None:check(manager[4]=='false','Destroyed Settings observation fragment manager')
        # A component is not an activity-instance identity: dumpsys can retain
        # an older stopped SubSettings hosting DisplaySettings alongside the
        # resumed SubSettings hosting ScreenTimeoutSettings. Validate the whole
        # background block first; only its calibrated scene comparisons differ.
        # Missing or contradictory evidence cannot grant this exclusion.
        background=(len(missing)==missing_before and complete and native is not None and
                    native.groups()==('false','true','false') and root_values['mStopped']=='true' and
                    focus is not None and focus[1]=='false' and visibility is not None and visibility[1]=='8' and
                    support is not None and support.groups()==('true','false','true') and
                    fragment_state is not None and fragment_state[1]=='4' and
                    manager is not None and manager[1]=='4' and manager[3]=='true')
        if not background:
            if hierarchy is not None:
                check(hierarchy==(scene['hierarchy'] if complete else scene['hierarchy'][:len(hierarchy)]),
                      'Settings observation hierarchy changed')
            if fragment is not None:check(fragment[1]==scene['fragment'],'Settings observation fragment changed')
            if added_match is not None:check(added_match[1]==scene['fragment'],'Settings observation added fragment changed')
    check(known_headers>0,'Missing calibrated Settings identity')
    check(len(resumed)<=1,'Ambiguous resumed activity observations')
    if not resumed:check(all(state[1]=='true' for state in foreign_states),'Foreign live activity during Settings observation')
    if missing:raise IncompleteSettingsObservation(missing)


def settings_scene(text,*,transition=False,known_scenes=None):
    check(isinstance(text,str) and 0<len(text)<4*1024*1024 and '\ufffd' not in text,
          'Malformed activity scene dump')
    for line in text.splitlines():
        if re.match(r'^  ACTIVITY\b',line):
            check(re.fullmatch(r'  ACTIVITY [^ ]+ [0-9a-f]+ pid=\d+ userId=\d+ uid=\d+ displayId=\d+\(type=[A-Z]+\)',line),
                  'Malformed activity observation identity')
    # The scene command merges stderr without a pipeline or rc-masking suffix.
    # Reject explicit diagnostics even beside an otherwise complete good dump.
    check(not re.search(r'permission denied|permission denial|access denied|securityexception|'
                        r'deadobjectexception|remoteexception|timeoutexception|'
                        r'(?:error|failure|exception|failed|unable)\s+(?:[^\n]{0,160}?\s+)?dump(?:ing)?\b|'
                        r'(?m:^\s*(?:Error:|Can.t find service:))',text,re.I),
          'Activity dump access/error diagnostic')
    if transition and known_scenes is not None:
        _available_settings_context(text,*known_scenes)
    return _complete_settings_scene(text,transition=transition)


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
    check(record.get('protocol')==acquisition.DIAGNOSTIC_CONTRACT,'Exact middle diagnostic policy required')
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
        check(stage.get('selectors_before_hold',{}).get('values')==aa.SELECTORS,'Missing surrogate prehold selectors')
        acquisition.validate_selector_lifecycle(stage['selectors_before_hold'])
        acquisition.validate_selector_boundary(stage['selectors_before_hold'])
        if stage['label']!='sham_stock':
            acquisition.validate_selector_lifecycle(stage.get('selectors_after_hold',{}))
            acquisition.validate_selector_boundary(stage.get('selectors_after_hold',{}))
        if stage['label']=='sham_stock':
            check(stage.get('c1')==acquisition.OMITTED_C1 and stage.get('selectors_after_hold')==acquisition.OMITTED_POSTSELECTORS,
                  'Mixed middle diagnostic policy')
        else:
            check(stage.get('selectors_after_hold',{}).get('values')==aa.SELECTORS and
                  stage.get('c1',{}).get('data')==[0,0,96],'Missing baseline/return diagnostics')
        check(stage.get('hold_seconds')==base.HOLD,'Missing surrogate hold')
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
            protocol=acquisition.DIAGNOSTIC_CONTRACT,
            diagnostic_change='Middle C1 and posthold selectors not measured; baseline/return measured; middle hold native/state/trace/ESD retained',
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
        initial,_=aa.selector_initial(data['CHILD'])
        gap=validate_safe_gap(data['TRACE_BEFORE'],initial,self.entry_count)
        result=aa.validate_selectors(data['CHILD'],initial,data['TRACE_AFTER'],self.entry_count)
        result['trace_boundary']={
            'contract': acquisition.SELECTOR_TRACE_CONTRACT,
            'outer_source': 'TRACE_BEFORE', 'initial_source': 'CHILD/SELECTOR_INITIAL',
            'capture': 'existing_snapshot_before_isolation_and_dsi',
            'outer_before_sha256': aa.digest(data['TRACE_BEFORE'].encode('utf-8')),
            'initial_sha256': aa.digest(initial.encode('utf-8')),
            'outer_event_count': len(aa.tx._events(data['TRACE_BEFORE'])),
            'initial_event_count': len(aa.tx._events(initial)),
            'entry_count_before': self.entry_count, 'safe_gap_events': gap,
        }
        acquisition.validate_selector_boundary(result)
        s.verify_read_interval(data['KERNEL'],begin,end,self.reference)
        validated = self.monotonic()
        # Keep the exact pre-restore cursor. Resumed polling belongs to the
        # next existing safe-gap guard, not a discarded fresh snapshot.
        self.entry_count=result['entry_count_after'];self.trace_snapshot=data['TRACE_AFTER']
        check(self.shell(aa.writer_esd_script(self.tmp,self.token,restore=True),
                         root=True,label=label+'-selector-esd',mutation=True) ==
              'WRITER_ESD_RESTORED reg_read','Selector ESD restoration failed')
        restored = self.monotonic()
        result['esd_lifecycle'] = {
            'contract': acquisition.SELECTOR_ESD_CONTRACT,
            'isolated_mode': 'esd_sw_sim_success', 'restored_mode': 'reg_read',
            'final_child_readback': True, 'inflight_cancellation_proven': False,
            'held_through': 'selector_trace_kernel_state_host_validation',
            'validated_monotonic': validated, 'restored_monotonic': restored,
        }
        acquisition.validate_selector_lifecycle(result)
        # panel_uncertain belongs to the enclosing stage, not this selector.
        self.pending_read=False
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

    def target_scene(self,label,timeout=5,*,transition=False,known_scenes=None):
        text=self.shell('set -eu; '+self.target_ui_guard()+'; dumpsys activity top 2>&1',label=label,timeout=timeout)
        return settings_scene(text,transition=transition,known_scenes=known_scenes)

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

    def settle_scene(self,label,expected,previous):
        # A single total acceptance deadline, never a fresh budget per poll.
        # The inherited ADB version handshake has its own timeout, so this is
        # not a new transport wall bound. Reject late results; the unchanged
        # outer37 alarm remains the active-window interruption/recovery guard.
        ready_context=('com.android.settings/.Settings$DisplaySettingsActivity','DisplaySettings')
        opened_context=('com.android.settings/.SubSettings','ScreenTimeoutSettings')
        contexts=(opened_context,ready_context) if label.endswith('-scene-opened') else (ready_context,opened_context)
        check(self.pending_read and label.endswith(('-scene-opened','-scene-returned')) and
              ((expected.get('component'),expected.get('fragment')),
               (previous.get('component'),previous.get('fragment')))==contexts and
              expected.get('pid')==previous.get('pid'), 'Pending reads require the known post-input transition')
        deadline=self.monotonic()+REDRAW_SETTLE_SECONDS
        if self.active_start is not None:deadline=min(deadline,self.monotonic()+self.remaining())
        while True:
            left=deadline-self.monotonic();check(left>0,'Settings transition exceeded acceptance deadline')
            try:
                observed=self.target_scene(label,timeout=left,transition=True,known_scenes=(expected,previous))
            except IncompleteSettingsObservation:
                # All present identity/context fields were checked. Missing
                # observation data grants only this bounded read-only wait.
                observed=None
            except SettingsTransitionPending as exc:
                # A complete known context with unfinished readiness has no
                # action authority. Finished is legal only for the source.
                check(exc.scene in (expected,previous) and (not exc.finished or exc.scene==previous),
                      'Unexpected pending Settings scene')
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
        opened_digest=self.settle_scene(label+'-scene-opened',opened,ready)
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
        middle=self.middle_stage(label)
        record['prehold_started_monotonic']=self.monotonic()
        for key,operation in (('same_dbv_replay',self.replay),('redraw_audit',self.redraw),('selectors_before_hold',self.selectors),('c1',self.c1)):
            if key=='c1' and middle:
                record[key]=dict(acquisition.OMITTED_C1)
                continue
            start=self.monotonic();record[key]=operation(label if key not in ('selectors_before_hold',) else label+'-before-hold')
            record['phase_seconds'][key]=self.monotonic()-start
        self.state(3600);self.panel_uncertain=False
        record['prehold_qualified_monotonic']=self.monotonic()

    def middle_stage(self,label):
        middle='aa10' if self.aa_candidate else 'sham_stock'
        check(label in ('baseline',middle,'return_stock'),'Unknown diagnostic stage')
        return label==middle

    def hold_end_guard(self,label):
        check(not self.pending_read and not self.inflight,'No hold guard into uncertainty')
        self.pending_read=True
        check(self.shell(self.ops['verify']+'; '+s.esd_read_script(self.tmp),root=True,
                         label=label+'-hold-end-esd')=='reg_read','Hold ESD changed')
        self.trace_check(self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-hold-trace'))
        self.pending_read=False
        return {'esd_mode':'reg_read','main_trace_prefix_verified':True,'entry_count_after':self.entry_count}

    def finish_hold(self,record):
        check(not self.pending_read and not self.inflight, 'No hold into uncertainty')
        label=record['label'];self.panel_uncertain=True
        middle=self.middle_stage(label)
        self.optical_hold(label,record)
        if label=='baseline' or middle:
            # Measure the identical read-only guard in this run's baseline.
            # It never fabricates a selector measurement.
            start=self.monotonic();record['hold_end_guard']=self.hold_end_guard(label)
            record['phase_seconds']['hold_end_guard']=self.monotonic()-start
            record['hold_guard_verified_monotonic']=self.monotonic()
        else:
            trace=self.shell('cat '+aa.TRACE+'/trace',root=True,label=label+'-hold-trace');self.trace_check(trace)
        if middle:
            record['selectors_after_hold']=dict(acquisition.OMITTED_POSTSELECTORS)
        else:
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
            phases=record['phase_seconds']
            estimate=acquisition.planning_estimate(phases)
            self.report['prearm_planning_estimate']={'observed_baseline_phase_seconds':dict(phases),
                'estimated_active_seconds':estimate,'planning_margin_seconds':3.0,
                'status':'observation_not_a_bound','redraw_scene_contract':REDRAW_SCENE_CONTRACT,
                'protocol':acquisition.DIAGNOSTIC_CONTRACT}
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
