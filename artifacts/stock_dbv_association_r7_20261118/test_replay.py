"""Offline mutations on temporary copies. Never touches original evidence."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import replay

SOURCE=Path(sys.argv.pop(1));TEMPLATE=Path(sys.argv.pop(1))
SCOPE=replay.ARTIFACTS/'scope_exterior_registration_20261118'
class Audit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for p in SOURCE.iterdir():
            if p.is_file():shutil.copyfile(p,self.root/p.name)
    def tearDown(self):self.temp.cleanup()
    def reject(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):
            replay.replay(self.root,TEMPLATE,SCOPE,True)
    def edit(self,name,fn):
        p=self.root/(name+'.json');m=json.loads(p.read_text());fn(m);p.write_text(json.dumps(m))
    def logs(self,fn):
        p=self.root/'oc.log';rows=[json.loads(s) for s in p.read_text().splitlines()];fn(rows);p.write_text(''.join(json.dumps(v)+'\n' for v in rows))
    def test_original(self):
        m=replay.replay(self.root,TEMPLATE,SCOPE,True);self.assertEqual(m['sample_count'],42);self.assertEqual(m['phases'],14);self.assertFalse(m['full_plan_complete'])
        self.assertEqual(m['status'],'partial_qualitative_association_aborted')
        self.assertEqual(json.loads(replay.render(m)),m)
    def test_incomplete(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):replay.replay(self.root,TEMPLATE,SCOPE)
    def test_missing_sample(self):
        (self.root/'P13_s2.png').unlink();self.reject()
    def test_repeat_image(self):
        shutil.copyfile(self.root/'P00_s0.png',self.root/'P00_s1.png');self.reject()
    def test_repeat_frame(self):
        shutil.copyfile(self.root/'P00_s0_pre_read0.json',self.root/'P00_s1_pre_read0.json');self.reject()
    def test_missing_post(self):
        (self.root/'P00_s0_post_read0.json').unlink();self.reject()
    def test_bad_iso(self):
        self.edit('P00_s0_post_read0',lambda m:m['res'].update({'sensor.sensitivity':'800'}));self.reject()
    def test_bad_focus(self):
        self.edit('P00_s0_pre_read0',lambda m:m['req'].update({'lens.focusDistance':'3.0'}));self.reject()
    def test_wrong_camera(self):
        self.edit('P00_s0_pre_read0',lambda m:m.update(camera='1'));self.reject()
    def test_wrong_float(self):
        def change(rows):
            row=next(v for v in rows if v[1]=='P02_command');row[2][1]='0.140379747'
        self.logs(change);self.reject()
    def test_same_dbv_readback_from_another_phase(self):
        # P00 and P03 early dumps both report DBV 2632 and essentially identical state.
        shutil.copyfile(self.root/'P00_early_display.txt',self.root/'P03_early_display.txt')
        with self.assertRaisesRegex(ValueError,'host phase window'):
            replay.replay(self.root,TEMPLATE,SCOPE,True)
    def test_forged_utc_keeps_stale_uptime(self):
        source=(self.root/'P00_early_display.txt').read_text().splitlines()
        dest=self.root/'P03_early_display.txt';truth=dest.read_text().splitlines()
        dest.write_text('\n'.join([truth[0],*source[1:]])+'\n')
        with self.assertRaisesRegex(ValueError,'nonadvancing readback device clocks'):
            replay.replay(self.root,TEMPLATE,SCOPE,True)
    def test_missing_readback_clock(self):
        dest=self.root/'P03_early_display.txt';dest.write_text(dest.read_text().split('\n',1)[1])
        with self.assertRaisesRegex(ValueError,'missing readback device UTC/uptime'):
            replay.replay(self.root,TEMPLATE,SCOPE,True)
    def test_wrong_dbv(self):
        p=self.root/'P02_end_display.txt';p.write_text(p.read_text().replace('\n2633\n0\n','\n2632\n0\n'));self.reject()
    def test_wrong_mode(self):
        p=self.root/'P02_end_display.txt';p.write_text(p.read_text().replace('vsyncRate=120.00 Hz','vsyncRate=90.00 Hz'));self.reject()
    def test_wrong_dc(self):
        p=self.root/'P02_end_provider.txt';p.write_text(p.read_text().replace('value=0','value=1'));self.reject()
    def test_wrong_scene(self):
        shutil.copyfile(self.root/'P00_s0.png',self.root/'P00_target.png');self.reject()
    def test_fake_qc(self):
        self.edit('P00_s0_qc',lambda m:m.update(corner_supported=not m['corner_supported']));self.reject()
    def test_fake_legend(self):
        self.edit('P00_s0_qc',lambda m:m['legend'].update(pass_modes=False));self.reject()
    def test_freeze(self):
        p=self.root/'corner_geometry.py';p.write_text(p.read_text()+'\n# modified\n');self.reject()
    def test_duplicate_event(self):
        self.logs(lambda rows:rows.append(next(r for r in rows if r[1]=='P00_command')));self.reject()
    def test_duplicate_restore(self):
        shutil.copyfile(self.root/'oc_return_a_read0.json',self.root/'oc_return_b_read0.json');self.reject()
    def test_wrong_restore_id(self):
        self.edit('oc_return_b_read0',lambda m:m.update(camera='bad'));self.reject()
    def test_stock_frame_stale(self):
        a=json.loads((self.root/'stock_final_a0.json').read_text())
        self.edit('stock_final_b0',lambda m:m.update({'request.frameCount':a['request.frameCount']}));self.reject()
    def test_false_stock_zoom(self):
        self.edit('stock_final_b0',lambda m:m.update({'control.zoomRatio':'1.00000000'}));self.reject()
    def test_late_scene_missing(self):
        (self.root/'P13_end_target.png').unlink();self.reject()
    def test_false_label(self):
        def change(rows):
            m=next(r for r in rows if r[1]=='P01_s1_manifest');m[2]['n']=2633
        self.logs(change);self.reject()
    def test_false_completion(self):
        (self.root/'manifest_complete.json').write_text('[]');self.reject()
    def test_fake_failed_pixel(self):
        shutil.copyfile(self.root/'P13_s0.png',self.root/'P14_s0.png');self.reject()
    def test_absent_failed_bracket(self):
        (self.root/'P14_s0_post_read0.json').unlink();self.reject()
    def test_fake_late_readback(self):
        shutil.copyfile(self.root/'P14_early_display.txt',self.root/'P14_end_display.txt');self.reject()
    def test_hide_first_veto(self):
        self.edit('P14_s0_qc',lambda m:m['legend'].update(pass_modes=True));self.reject()
    def test_extra_commissioning_raster(self):
        shutil.copyfile(self.root/'R02.png',self.root/'R03.png');self.reject()
    def test_extra_qc_roster(self):
        def change(rows):
            r=next(v for v in rows if v[1]=='R02_qc')
            extra=json.loads(json.dumps(r));extra[1]='R03_qc';rows.insert(rows.index(r)+1,extra)
        self.logs(change);self.reject()
if __name__=='__main__':unittest.main()
