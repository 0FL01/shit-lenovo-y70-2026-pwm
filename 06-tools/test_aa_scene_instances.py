"""Synthetic instance selection and explicitly supplied private 2140 replay.

No later stable physical frame is claimed; caller completion uses a synthetic
readiness projection. Private activity dumps never belong in this repository.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import run_aa_timed_stock_trial as t
import test_run_aa_timed_stock_trial as fixtures


def background_fixture():
    """Historical DisplaySettings hosted by the same SubSettings component."""
    raw=fixtures.scene_fixture().replace('.Settings$DisplaySettingsActivity','.SubSettings')
    for before,after in (
        ('Activity def State:','Activity bef State:'),
        ('SubSettings abc pid=','SubSettings bee pid='),
        ('mResumed=true mStopped=false mFinished=false','mResumed=false mStopped=true mFinished=false'),
        ('      mStopped=false\n','      mStopped=true\n'),
        ('mHasWindowFocus=true','mHasWindowFocus=false'),('mWindowVisibility=0','mWindowVisibility=8'),
        ('mCreated=true mResumed=true mStopped=false','mCreated=true mResumed=false mStopped=true'),
        ('mState=7','mState=4'),
        ('mCurState=7 mStateSaved=false mStopped=false','mCurState=4 mStateSaved=true mStopped=true'),
        ('DecorView{abc V.E......','DecorView{abc I.E......')):
        raw=raw.replace(before,after)
    return raw


class SceneInstanceTests(unittest.TestCase):
    def contexts(self):
        return t.settings_scene(fixtures.scene_fixture(True)),t.settings_scene(fixtures.scene_fixture())

    def observe(self,raw):
        return t.settings_scene(raw,transition=True,known_scenes=self.contexts())

    def assert_terminal(self,raw):
        with self.assertRaises(ValueError) as caught:self.observe(raw)
        self.assertNotIsInstance(caught.exception,(t.SettingsTransitionPending,t.IncompleteSettingsObservation))

    def test_stopped_same_component_is_not_the_live_fragment(self):
        expected,_=self.contexts()
        for pending in (False,True):
            raw=background_fixture()+fixtures.scene_fixture(True,pending=pending)
            if pending:
                with self.assertRaises(t.SettingsTransitionPending) as caught:self.observe(raw)
                self.assertEqual(caught.exception.scene,expected)
            else:self.assertEqual(self.observe(raw),expected)

    def test_classification_requires_all_headers_and_readiness_evidence(self):
        raw=background_fixture();live=fixtures.scene_fixture(True)
        fields=('    Local Activity bef State:\n','      mResumed=false mStopped=true mFinished=false\n',
            '    ViewRoot:\n','      mStopped=true\n','        mHasWindowFocus=false\n',
            '        mWindowVisibility=8\n','    Local FragmentActivity bef State:\n',
            '      mCreated=true mResumed=false mStopped=true    Active Fragments:\n',
            '      mCurState=4 mStateSaved=true mStopped=true mDestroyed=false\n')
        for field in fields:
            self.assertIn(field,raw)
            for replacement in ('',field+field,field.replace('=', '=invalid',1)):
                # Headers without '=' have a separately malformed spelling.
                if replacement==field:replacement=field.rstrip()+' invalid\n'
                with self.subTest(field=field,replacement=replacement):
                    self.assert_terminal(raw.replace(field,replacement)+live)

    def test_uncertain_or_contradictory_background_is_not_excluded(self):
        raw=background_fixture();live=fixtures.scene_fixture(True)
        changes=(('mResumed=false mStopped=true','mResumed=true mStopped=true'),
            ('mResumed=false mStopped=true mFinished=false','mResumed=false mStopped=false mFinished=false'),
            ('mFinished=false','mFinished=true'),('      mStopped=true\n','      mStopped=false\n'),
            ('mHasWindowFocus=false','mHasWindowFocus=true'),('mWindowVisibility=8','mWindowVisibility=0'),
            ('mWindowVisibility=8','mWindowVisibility=4'),
            ('mCreated=true mResumed=false mStopped=true','mCreated=true mResumed=true mStopped=true'),
            ('mCreated=true mResumed=false mStopped=true','mCreated=true mResumed=false mStopped=false'),
            ('mState=4','mState=7'),('mCurState=4','mCurState=7'),
            ('mCurState=4 mStateSaved=true mStopped=true','mCurState=4 mStateSaved=true mStopped=false'))
        for before,after in changes:
            with self.subTest(after=after):self.assert_terminal(raw.replace(before,after)+live)

    def test_background_still_validates_identity_structure_and_fragment_consistency(self):
        raw=background_fixture();live=fixtures.scene_fixture(True)
        changes=(('pid=123','pid=124'),('uid=1000','uid=2000'),('userId=0','userId=1'),
            ('displayId=0','displayId=1'),('type=INTERNAL','type=EXTERNAL'),
            ('mWindowingMode=fullscreen','mWindowingMode=other'),('mChangingConfigurations=false','mChangingConfigurations=true'),
            ('mAdded=true\n','mAdded=false\n'),('mRemoved=false','mRemoved=true'),
            ('android.widget.TextView{bbb','android.widget.TextView{broken'),
            ('mState=4','mState=1'),('mCreated=true','mCreated=false'),('mHidden=false','mHidden=true'),
            ('mDetached=false','mDetached=true'),('mDestroyed=false','mDestroyed=true'),
            ('mRemoving=false','mRemoving=true'),('#0: DisplaySettings','#0: OtherSettings'),
            ('mFrameScheduled=false','mFrameScheduled=unknown'))
        for before,after in changes:
            with self.subTest(after=after):self.assert_terminal(raw.replace(before,after)+live)
        self.assert_terminal(raw+raw+live)
        self.assert_terminal(raw.replace('    Added Fragments:\n','    Added Fragments:\n    Added Fragments:\n')+live)

    def test_background_cannot_hide_bad_or_ambiguous_destination(self):
        background=background_fixture();live=fixtures.scene_fixture(True)
        for before,after in (('android:id/title','android:id/other'),('ScreenTimeoutSettings','OtherSettings'),
            ('pid=123','pid=124'),('mHidden=false','mHidden=true'),('mHasWindowFocus=true','mHasWindowFocus=unknown')):
            with self.subTest(after=after):self.assert_terminal(background+live.replace(before,after))
        self.assert_terminal(background+live+fixtures.scene_fixture())
        self.assert_terminal(background+live.replace('com.android.settings/.SubSettings','com.foreign/.Activity'))

    def test_background_alone_never_grants_stable_success(self):
        with self.assertRaises(ValueError):self.observe(background_fixture())

    def test_synthetic_settle_reads_without_input(self):
        with tempfile.TemporaryDirectory() as root:
            clock=fixtures.Clock();calls=[];expected,previous=self.contexts()
            class FakeADB:
                def shell(self,target,command,budget):
                    calls.append(command);clock.sleep(.01)
                    return 0,(background_fixture()+fixtures.scene_fixture(True,pending=len(calls)==1)).encode(),b''
            run=t.AATimedTrial(FakeADB(),6,1,'aa_instances',root,root,sleep=clock.sleep,monotonic=clock)
            run.target_ui_guard=lambda:'true';run.pending_read=True
            self.assertEqual(run.settle_scene('baseline-scene-opened',expected,previous),t.scene_digest(expected))
            self.assertEqual(len(calls),2);self.assertTrue(all('input ' not in c for c in calls))

    def test_actual_2140_pending_and_synthetic_later_readiness(self):
        path=os.environ.get('AA_INSTANCE_SCENE_PATH')
        if not path:self.skipTest('Explicit private 2140 scene reference not supplied')
        raw=Path(path).read_bytes();self.assertEqual(len(raw),176163)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'58bcc489466c42bc18e42b5cfd8f87619eb96cbc83e2abab9aee7d5672b30741')
        text=raw.decode()
        with self.assertRaises(t.SettingsTransitionPending) as parsed:t._complete_settings_scene(text,transition=True)
        expected=parsed.exception.scene
        self.assertEqual(t.scene_digest(expected),'2fb7ef380b256e190d354692a1088a8aea153648439b34dbc3a806678887d729')
        # Only the available destination is factual; previous context is a
        # synthetic same-process scene and is absent from this saved top dump.
        ready_raw=fixtures.scene_fixture().replace('pid=123','pid='+str(expected['pid']))
        previous=t.settings_scene(ready_raw)
        with self.assertRaises(t.SettingsTransitionPending) as caught:
            t.settings_scene(text,transition=True,known_scenes=(expected,previous))
        self.assertEqual(caught.exception.scene,expected)
        # TEST-ONLY readiness projection, not a later observed target frame.
        head,sep,destination=text.rpartition('  ACTIVITY ')
        stable=head+sep+destination.replace('mTraversalScheduled=true','mTraversalScheduled=false').replace(
            'mHasWindowFocus=false','mHasWindowFocus=true')
        for timeout in (False,True):
            with self.subTest(timeout=timeout),tempfile.TemporaryDirectory() as root:
                clock=fixtures.Clock();calls=[]
                class FakeADB:
                    def shell(self,target,command,budget):
                        calls.append(command);clock.sleep(.01)
                        return 0,(text if timeout or len(calls)==1 else stable).encode(),b''
                run=t.AATimedTrial(FakeADB(),6,1,'aa_actual_instances',root,root,sleep=clock.sleep,monotonic=clock)
                run.target_ui_guard=lambda:'true';run.pending_read=True
                if timeout:
                    with self.assertRaisesRegex(ValueError,'deadline'):run.settle_scene('baseline-scene-opened',expected,previous)
                else:
                    self.assertEqual(run.settle_scene('baseline-scene-opened',expected,previous),t.scene_digest(expected))
                    self.assertEqual(len(calls),2)
                self.assertTrue(run.pending_read);self.assertTrue(all('input ' not in c for c in calls))
        fixtures.Sim.reader=fixtures.execute_reader_fixture()[0].stdout
        for timeout in (False,True):
            with self.subTest(real_redraw=True,timeout=timeout),tempfile.TemporaryDirectory() as root:
                run=fixtures.Sim(root);run.setup();run.setup_aa();original=run.shell;reads=0
                run.redraw_scenes={'ready':previous,'opened':expected};run.redraw_tap=[10,10]
                def shell(command,**kwargs):
                    nonlocal reads
                    value=original(command,**kwargs);label=kwargs.get('label')
                    if label in ('baseline-scene-ready','baseline-scene-returned'):return ready_raw
                    if label=='baseline-scene-opened':
                        reads+=1;return text if timeout or reads==1 else stable
                    return value
                run.shell=shell
                if timeout:
                    with self.assertRaises(ValueError):run.redraw('baseline')
                    self.assertNotIn('baseline-redraw-cancel',run.calls);self.assertTrue(run.pending_read)
                else:
                    result=run.redraw('baseline');self.assertEqual(reads,2)
                    self.assertEqual(result['scene_sha256'][1],t.scene_digest(expected))
                    self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
                    last_read=max(i for i,label in enumerate(run.calls) if label=='baseline-scene-opened')
                    self.assertLess(last_read,run.calls.index('baseline-redraw-cancel'))
                    self.assertFalse(run.pending_read)
                self.assertEqual(run.calls.count('baseline-redraw-open'),1)


if __name__=='__main__':unittest.main()
