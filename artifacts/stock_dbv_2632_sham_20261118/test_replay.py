"""Offline tests on temporary copies, never the private originals.

python test_replay.py PRIVATE_RUN PUBLIC_PREVIOUS_PACKAGE
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import replay

SOURCE=Path(sys.argv.pop(1));DEPENDENCY=Path(sys.argv.pop(1))


class ShamTests(unittest.TestCase):
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
            replay.replay(self.root,DEPENDENCY,True)

    def test_verified_commissioning_abort(self):
        out=replay.replay(self.root,DEPENDENCY,True)
        self.assertEqual((out['status'],out['samples']),('commissioning_rejected',0))
        self.assertEqual(out['reference_scores'][0]['score']['failures'],['right-upper/b:absolute'])

    def test_default_rejects_incomplete(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            replay.replay(self.root,DEPENDENCY)

    def test_false_complete(self):
        (self.root/'sham_validity_series.json').write_text('[]');self.reject()

    def test_false_native_reference(self):
        (self.root/'sham_ref.json').write_text('{}');self.reject()

    def test_false_sample_file(self):
        (self.root/'S00_fixture.json').write_text('{}');self.reject()

    def test_false_sample_receipt(self):
        self.logs(lambda rows:rows.append([rows[-1][0],'S00_receipt',{}]));self.reject()

    def test_erase_blocker_image(self):
        shutil.copyfile(self.root/'R01.png',self.root/'R00.png');self.reject()

    def test_duplicate_reference_frame(self):
        shutil.copyfile(self.root/'R00_pre_read0.json',self.root/'R01_pre_read0.json');self.reject()

    def test_missing_post(self):
        (self.root/'R02_post_read0.json').unlink();self.reject()

    def test_wrong_focus(self):
        self.edit('R01_post_read0',lambda m:m['res'].update({'lens.focusDistance':'2.0'}));self.reject()

    def test_wrong_camera(self):
        self.edit('R00_pre_read0',lambda m:m.update(camera='other'));self.reject()

    def test_bad_restore_camera(self):
        self.edit('oc_return_b_read0',lambda m:m.update(camera='other'));self.reject()

    def test_duplicate_oc_restore(self):
        shutil.copyfile(self.root/'oc_return_a_read0.json',self.root/'oc_return_b_read0.json');self.reject()

    def test_stale_stock_frame(self):
        a=json.loads((self.root/'stock_final_a0.json').read_text())
        self.edit('stock_final_b0',lambda m:m.update({'request.frameCount':a['request.frameCount']}));self.reject()

    def test_stale_stock_timestamp(self):
        a=json.loads((self.root/'stock_final_a0.json').read_text())
        self.edit('stock_final_b0',lambda m:m.update({'sensor.timestamp':a['sensor.timestamp']}));self.reject()

    def test_reference_too_early(self):
        def change(rows):
            entry=next(r for r in rows if r[1]=='single_entry_command')
            r=next(r for r in rows if r[1]=='native_reference');r[2][1]=entry[0]
        self.logs(change);self.reject()

    def test_duplicate_reference_log(self):
        def change(rows):
            i=next(i for i,r in enumerate(rows) if r[1]=='native_reference');rows.insert(i,rows[i])
        self.logs(change);self.reject()

    def test_wrong_entry_dbv(self):
        p=self.root/'sham_enter_display.txt';p.write_text(p.read_text().replace('\n2632\n0\n','\n2633\n0\n'));self.reject()

    def test_wrong_entry_refresh(self):
        p=self.root/'sham_enter_display.txt';p.write_text(p.read_text().replace('vsyncRate=120.00 Hz','vsyncRate=60.00 Hz'));self.reject()

    def test_wrong_return_brightness(self):
        p=self.root/'return_sham_display.txt';p.write_text(p.read_text().replace('\n6879\n0\n','\n2632\n0\n'));self.reject()

    def test_wrong_provider(self):
        p=self.root/'sham_enter_provider.txt';p.write_text(p.read_text().replace('value=0','value=1'));self.reject()

    def test_frozen_scorer_changed(self):
        with (self.root/'analysis_geometry.py').open('a') as f:f.write('\n# mutation\n')
        self.reject()


if __name__=='__main__':unittest.main()
