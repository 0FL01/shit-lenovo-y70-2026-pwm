"""Offline tests against a private copy; never writes original evidence."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import replay

SOURCE=Path(sys.argv.pop(1))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        for path in SOURCE.iterdir():
            if path.suffix in ('.json','.jsonl','.log','.png'):
                shutil.copyfile(path,self.root/path.name)

    def tearDown(self):
        self.temp.cleanup()

    def edit_json(self,name,fn):
        p=self.root/(name+'.json');obj=json.loads(p.read_text());fn(obj);p.write_text(json.dumps(obj))

    def edit_log(self,name,fn):
        p=self.root/name;rows=[json.loads(s) for s in p.read_text().splitlines()];fn(rows)
        p.write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def reject(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):
            replay.replay(self.root,True)

    def test_verified_abort(self):
        out=replay.replay(self.root,True)
        self.assertEqual(out['completed_samples'],0)
        self.assertEqual(out['status'],'aborted_not_comparative_evidence')

    def test_default_never_accepts_incomplete(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            replay.replay(self.root)

    def test_false_complete_marker(self):
        (self.root/'manifest_complete.json').write_text('[]');self.reject()

    def test_duplicate_restore(self):
        shutil.copyfile(self.root/'oc_return_a_read0.json',self.root/'oc_return_b_read0.json');self.reject()

    def test_wrong_camera(self):
        self.edit_json('oc_return_b_read0',lambda m:m.update(camera='other'));self.reject()

    def test_stale_stock_frame(self):
        a=replay.read(self.root,'stock_final_a0')
        self.edit_json('stock_final_b0',lambda m:m.update({'request.frameCount':a['request.frameCount']}));self.reject()

    def test_stale_stock_time(self):
        a=replay.read(self.root,'stock_final_a0')
        self.edit_json('stock_final_b0',lambda m:m.update({'sensor.timestamp':a['sensor.timestamp']}));self.reject()

    def test_oc_timestamp_only_stale(self):
        a=replay.read(self.root,'oc_return_a_read0')
        self.edit_json('oc_return_b_read0',lambda m:m['res'].update({'sensor.timestamp':a['res']['sensor.timestamp']}));self.reject()

    def test_wrong_focus(self):
        self.edit_json('P00_s0_pre_read0',lambda m:m['res'].update({'lens.focusDistance':'2.0'}));self.reject()

    def test_duplicate_formed_retry(self):
        shutil.copyfile(self.root/'P00_s0_pre_read0.json',self.root/'P00_s0_pre_read1.json');self.reject()

    def test_duplicate_phase_log(self):
        self.edit_log('oc.log',lambda rows:rows.append(next(r for r in rows if r[1]=='P00_command')));self.reject()

    def test_false_sample_control(self):
        self.edit_log('oc.log',lambda rows:rows.append([rows[-1][0],'P00_s0_manifest',{}]));self.reject()

    def test_wrong_native_plateau(self):
        self.edit_log('oc.log',lambda rows:next(r[2][2] for r in rows if r[1]=='P00_pre').update(DBV='2633'));self.reject()

    def test_transplanted_calibration(self):
        def change(rows):
            refs=[r for r in rows if r[1]=='reach'];refs[3][2]=refs[2][2]
        self.edit_log('log.jsonl',change);self.reject()

    def test_wrong_raw_return_dc(self):
        def change(rows):
            r=next(r for r in rows if r[1]=='final_target_full');r[2]=r[2].replace('panelDC=0','panelDC=1')
        self.edit_log('log.jsonl',change);self.reject()

    def test_wrong_return_scene(self):
        p=self.root/'final_native_target.png'
        with replay.Image.open(p) as im:
            rgb=im.convert('RGB');rgb.putpixel((500,1000),(1,2,3));rgb.save(p)
        self.reject()

    def test_valid_png_substitution_cannot_erase_blocker(self):
        shutil.copyfile(self.root/'new_qual0.png',self.root/'P00_s0.png');self.reject()


if __name__=='__main__':
    unittest.main()
