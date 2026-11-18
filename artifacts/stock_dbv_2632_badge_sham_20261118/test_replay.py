"""Offline tests; source evidence is read-only, mutations use temporary copies.

python test_replay.py PRIVATE_RUN PRIVATE_TEMPLATE PUBLIC_SCOPE_PACKAGE
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import replay

SOURCE=Path(sys.argv.pop(1));TEMPLATE=Path(sys.argv.pop(1));SCOPE=Path(sys.argv.pop(1))


class BadgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for p in SOURCE.iterdir():
            if p.is_file():shutil.copyfile(p,self.root/p.name)

    def tearDown(self):self.temp.cleanup()

    def edit(self,name,fn):
        p=self.root/(name+'.json');obj=json.loads(p.read_text());fn(obj);p.write_text(json.dumps(obj))

    def logs(self,fn):
        p=self.root/'oc.log';rows=[json.loads(s) for s in p.read_text().splitlines()];fn(rows)
        p.write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def reject(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):
            replay.replay(self.root,TEMPLATE,SCOPE)

    def test_original_recording(self):
        out=replay.replay(self.root,TEMPLATE,SCOPE)
        self.assertEqual(out['status'],'complete_sham_recording')
        self.assertEqual(out['sample_count'],51)
        self.assertEqual(out['all_51_pass'],out['pass_count']==51)
        rendered=replay.render(out)
        self.assertEqual(json.loads(rendered),out)
        self.assertLess(len(rendered.splitlines()),150)
        self.assertEqual(rendered,replay.render(out))

    def test_missing_completion(self):
        (self.root/'sham_validity_series.json').unlink();self.reject()

    def test_short_manifest(self):
        self.edit('sham_validity_series',lambda m:m.pop());self.reject()

    def test_false_completion_count(self):
        def change(rows):next(r for r in rows if r[1]=='sham_finished')[2]=50
        self.logs(change);self.reject()

    def test_duplicate_receipt(self):
        def change(rows):
            i=next(i for i,r in enumerate(rows) if r[1]=='S00_receipt');rows.insert(i,rows[i])
        self.logs(change);self.reject()

    def test_sample_relabel(self):
        def change(rows):next(r[2] for r in rows if r[1]=='S00_receipt')['index']=1
        self.logs(change);self.reject()

    def test_copy_metadata(self):
        shutil.copyfile(self.root/'S00_pre_read0.json',self.root/'S01_pre_read0.json');self.reject()

    def test_copy_png(self):
        shutil.copyfile(self.root/'S00.png',self.root/'S01.png');self.reject()

    def test_missing_post(self):
        (self.root/'S02_post_read0.json').unlink();self.reject()

    def test_missing_late_plateau(self):
        (self.root/'S02_after_display.txt').unlink();self.reject()

    def test_bad_phase_float(self):
        p=self.root/'S00_before_display.txt';p.write_text(p.read_text().replace('0.14037974','0.15'));self.reject()

    def test_bad_native_dbv(self):
        p=self.root/'S02_after_display.txt';p.write_text(p.read_text().replace('\n2632\n0\n','\n2633\n0\n'));self.reject()

    def test_bad_refresh(self):
        p=self.root/'S02_after_display.txt';p.write_text(p.read_text().replace('vsyncRate=120.00 Hz','vsyncRate=60.00 Hz'));self.reject()

    def test_bad_provider(self):
        p=self.root/'S00_before_provider.txt';p.write_text(p.read_text().replace('value=0','value=1'));self.reject()

    def test_wrong_camera(self):
        self.edit('S00_pre_read0',lambda m:m.update(camera='other'));self.reject()

    def test_wrong_focus(self):
        self.edit('S00_post_read0',lambda m:m['res'].update({'lens.focusDistance':'2.0'}));self.reject()

    def test_semantic_flag_forged(self):
        self.edit('S00_legends',lambda m:m.update(pass_modes=not m['pass_modes']));self.reject()

    def test_fixed_source_changed(self):
        with (self.root/'legends.py').open('a') as f:f.write('\n# mutation\n')
        self.reject()

    def test_wrong_original_template(self):
        with self.assertRaises(ValueError):
            replay.replay(self.root,self.root/'R00.png',SCOPE)

    def test_compressed_schedule(self):
        def change(rows):
            r=next(r[2] for r in rows if r[1]=='S01_receipt');r['elapsed_complete']+=30
            p=self.root/'sham_validity_series.json';v=json.loads(p.read_text());v[1]=r;p.write_text(json.dumps(v))
        self.logs(change);self.reject()

    def test_transplanted_plateau_event(self):
        def change(rows):
            first=next(r for r in rows if r[1]=='S00_target_pre');second=next(r for r in rows if r[1]=='S03_target_pre');second[0]=first[0];second[2]=first[2]
        self.logs(change);self.reject()

    def test_bad_restore_id(self):
        self.edit('oc_return_b_read0',lambda m:m.update(camera='other'));self.reject()

    def test_duplicate_oc_restore(self):
        shutil.copyfile(self.root/'oc_return_a_read0.json',self.root/'oc_return_b_read0.json');self.reject()

    def test_stale_stock_frame(self):
        a=json.loads((self.root/'stock_final_a0.json').read_text())
        self.edit('stock_final_b0',lambda m:m.update({'request.frameCount':a['request.frameCount']}));self.reject()

    def test_stale_stock_timestamp(self):
        a=json.loads((self.root/'stock_final_a0.json').read_text())
        self.edit('stock_final_b0',lambda m:m.update({'sensor.timestamp':a['sensor.timestamp']}));self.reject()


if __name__=='__main__':unittest.main()
