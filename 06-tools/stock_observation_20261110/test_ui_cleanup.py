"""Finite UI cleanup regressions using actual coordinator navigation methods.

Only synthetic XML/state transitions; no transport, ADB or real UI proof.
"""
import re
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET
from test_coordinator import fresh
from coordinator import DURATION,RESTART,FILE_RESTART,VIDEO_SETTINGS,classify_camera_ui

class UI:
    def __init__(self,*,duration='10 seconds',restart="Don't restart",filesize=False):
        self.level='preview';self.duration=duration;self.restart=restart;self.filesize=filesize
        self.dialog=None;self.events=[];self.fail=None;self.fail_ui_once=None
    def node(self,parent,*,text='',bounds='[0,0][20,20]',clickable='false',**extra):
        attrs={'package':'net.sourceforge.opencamera','text':text,'enabled':'true',
               'bounds':bounds,'clickable':clickable,'class':'android.widget.TextView'}
        attrs.update(extra);return ET.SubElement(parent,'node',attrs)
    def tree(self):
        if self.fail_ui_once==self.level:
            self.fail_ui_once=None;raise TimeoutError('synthetic UI read interrupted')
        root=ET.Element('hierarchy')
        if self.level=='preview':
            self.node(root,bounds='[0,0][20,20]',clickable='true',**{'content-desc':'Settings','class':'android.widget.ImageButton'})
            self.node(root,bounds='[100,0][120,20]',clickable='true',**{'content-desc':'Start recording video','class':'android.widget.ImageButton'})
        elif self.level=='main_settings':
            row=self.node(root,bounds='[0,30][200,60]',clickable='true');self.node(row,text=VIDEO_SETTINGS)
        elif self.level=='video_settings':
            for title,y in ((DURATION,100),(RESTART,150),(FILE_RESTART,200)):
                row=self.node(root,bounds=f'[0,{y}][200,{y+40}]',clickable='true');self.node(row,text=title)
                if title==FILE_RESTART:
                    self.node(row,checkable='true',checked=str(self.filesize).lower(),**{'class':'android.widget.Switch'})
        elif self.level=='option_dialog':
            self.node(root,text=self.dialog,**{'resource-id':'android:id/alertTitle'})
            choices=['Unlimited','10 seconds'] if self.dialog==DURATION else ["Don't restart",'Restart once']
            value=self.duration if self.dialog==DURATION else self.restart
            for i,label in enumerate(choices):
                self.node(root,text=label,bounds=f'[0,{300+50*i}][200,{340+50*i}]',clickable='true',
                          checkable='true',checked=str(label==value).lower(),**{'class':'android.widget.CheckedTextView'})
        return root
    def shell(self,role,cmd,**kwargs):
        if role!='camera' or not cmd.startswith('input '):return ''
        old=self.level
        if cmd=='input keyevent 4':
            self.level={'option_dialog':'video_settings','video_settings':'main_settings','main_settings':'preview'}[self.level]
        else:
            match=re.fullmatch(r'input tap ([0-9]+) ([0-9]+)',cmd)
            if not match:raise AssertionError(cmd)
            x,y=map(int,match.groups())
            if self.level=='preview' and (x,y)==(10,10):self.level='main_settings'
            elif self.level=='main_settings' and (x,y)==(100,45):self.level='video_settings'
            elif self.level=='video_settings':
                if y==120:self.level='option_dialog';self.dialog=DURATION
                elif y==170:self.level='option_dialog';self.dialog=RESTART
                elif y==220:self.filesize=not self.filesize
                else:raise AssertionError((self.level,cmd))
            elif self.level=='option_dialog':
                options=['Unlimited','10 seconds'] if self.dialog==DURATION else ["Don't restart",'Restart once']
                value=options[(y-320)//50]
                if self.dialog==DURATION:self.duration=value
                else:self.restart=value
                self.level='video_settings'
            else:raise AssertionError((self.level,cmd))
        event={'command':cmd,'from':old,'to':self.level};self.events.append(event)
        if self.fail and self.fail(event):raise TimeoutError('synthetic input outcome uncertain')
        return ''


def prepared(ui):
    c,clock=fresh();c.ui=ui.tree;c.shell=Mock(side_effect=ui.shell);c.metadata=Mock(return_value={})
    c.original_preview_signature=None;c.original_preview_verified=False
    c.verify_original_preview(initial=True)
    c.begin=Mock();c.locked=True;c.acquisition_attempted=True
    c.restore=Mock(wraps=c.restore);c.release=Mock(wraps=c.release)
    def recording():
        c.start=clock();c.stopped=True;c.ui_restore_pending=True;c.original_preview_verified=False
        c.report.update(camera_stopped_verified=True,camera_ui_restore_pending=True,camera_ui_original_preview_verified=False)
    c.record=Mock(side_effect=recording)
    return c

class Tests(unittest.TestCase):
    def test_enter_after_settings_tap_timeout_retains_owner(self):
        ui=UI();c=prepared(ui);ui.fail=lambda e:e['from']=='preview'
        out=c.run(None)
        self.assertEqual(ui.level,'main_settings');self.assertEqual(len(ui.events),1)
        self.assertTrue(c.ui_restore_pending);self.assertTrue(out['cleanup_pending'])
        self.assertFalse(c.original_preview_verified);c.restore.assert_not_called();c.release.assert_not_called()
        self.assertTrue(c.locked)

    def test_leave_timeout_all_preferences_unchanged_retains_owner(self):
        ui=UI();c=prepared(ui)
        ui.fail=lambda e:e['from']=='video_settings' and e['command']=='input keyevent 4'
        out=c.run(None)
        self.assertEqual(c.preferences,[]);self.assertIsNone(c.switch_original)
        self.assertEqual(ui.level,'main_settings');self.assertTrue(out['cleanup_pending'])
        self.assertTrue(c.ui_restore_pending);c.release.assert_not_called();c.record.assert_not_called()
        self.assertEqual(ui.events[-1]['from'],'video_settings')

    def test_known_dialog_read_interruption_cleanup_uses_known_edge(self):
        ui=UI();c=prepared(ui);ui.fail_ui_once='option_dialog'
        out=c.run(None)
        self.assertEqual(out['status'],'inconclusive')
        self.assertEqual(ui.level,'preview');self.assertFalse(c.ui_restore_pending)
        self.assertTrue(out['originals_restored']);self.assertTrue(out['mutex_released'])
        self.assertFalse(out.get('cleanup_pending',False))
        self.assertTrue(any(e['from']=='option_dialog' and e['command']=='input keyevent 4' for e in ui.events))

    def test_uncertain_back_only_read_classify_no_retry(self):
        ui=UI();c=prepared(ui)
        ui.fail=lambda e:e['from']=='option_dialog' and e['command']=='input keyevent 4'
        out=c.run(None);count=len(ui.events)
        self.assertTrue(out['cleanup_pending']);self.assertTrue(c.ui_transition_uncertain)
        with self.assertRaisesRegex(ValueError,'uncertain UI'):c.cleanup_camera_ui()
        self.assertEqual(len(ui.events),count);c.release.assert_not_called()

    def test_normal_preferences_and_ui_rollback(self):
        ui=UI(duration='Unlimited',restart='Restart once',filesize=True);c=prepared(ui)
        out=c.run(None)
        self.assertEqual((ui.duration,ui.restart,ui.filesize),('Unlimited','Restart once',True))
        self.assertEqual(ui.level,'preview');self.assertFalse(c.ui_restore_pending)
        self.assertTrue(c.original_preview_verified);self.assertIsNone(c.ui_transition)
        self.assertEqual(out['status'],'geometry_review_pending')
        self.assertTrue(out['originals_restored']);self.assertTrue(out['mutex_released'])
        self.assertFalse(out.get('cleanup_pending',False));self.assertEqual(c.record.call_count,1)
        self.assertFalse(any(e['from']=='preview' and e['command']=='input keyevent 4' for e in ui.events))

    def test_unknown_ui_never_receives_back_or_settings(self):
        ui=UI();c=prepared(ui);ui.level='unknown';c.ui_restore_pending=True;c.original_preview_verified=False
        with self.assertRaisesRegex(ValueError,'unknown UI'):c.cleanup_camera_ui()
        self.assertEqual(ui.events,[])
        with self.assertRaises(ValueError):c.restore()
        self.assertTrue(c.locked)

    def test_classifier_rejects_unknown_dialog(self):
        ui=UI();ui.level='option_dialog';ui.dialog='Unknown preference'
        self.assertEqual(classify_camera_ui(ui.tree())['level'],'unknown')

if __name__=='__main__':unittest.main()
