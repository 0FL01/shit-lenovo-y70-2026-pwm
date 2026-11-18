"""Offline negative tests. Usage: python test_prospective.py PRIVATE_RUN_DIR."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import replay as base
import replay_prospective as prospective

SOURCE=Path(sys.argv.pop(1))


class ProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for p in SOURCE.iterdir():
            if p.is_file():shutil.copyfile(p,self.root/p.name)

    def tearDown(self):self.temp.cleanup()

    def json(self,name,fn):
        p=self.root/(name+'.json');obj=json.loads(p.read_text());fn(obj);p.write_text(json.dumps(obj))

    def logs(self,fn):
        p=self.root/'oc.log';rows=[json.loads(s) for s in p.read_text().splitlines()];fn(rows)
        p.write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def reject(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):
            prospective.replay(self.root,True)

    def test_verified_partial(self):
        v=prospective.replay(self.root,True)
        self.assertEqual((v['completed_phases'],v['completed_samples']),(1,4))
        self.assertEqual(v['status'],'aborted_same_dbv_sham_only')

    def test_no_default_completion(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            prospective.replay(self.root)

    def test_fake_complete_marker(self):
        (self.root/'manifest_complete.json').write_text('[]');self.reject()

    def test_frozen_source_changed(self):
        with (self.root/'analysis_geometry.py').open('a') as f:f.write('\n# altered\n')
        self.reject()

    def test_copy_metadata_frame(self):
        shutil.copyfile(self.root/'P00_s0_pre_read0.json',self.root/'P00_s1_pre_read0.json');self.reject()

    def test_copy_image(self):
        shutil.copyfile(self.root/'P00_s0.png',self.root/'P00_s1.png');self.reject()

    def test_erase_failed_image(self):
        shutil.copyfile(self.root/'P01_s0.png',self.root/'P01_s1.png');self.reject()

    def test_wrong_plateau_dbv(self):
        p=self.root/'P00_end_display.txt';p.write_text(p.read_text().replace('\n2632\n0\n','\n2633\n0\n'));self.reject()

    def test_wrong_plateau_refresh(self):
        p=self.root/'P00_end_display.txt';p.write_text(p.read_text().replace('vsyncRate=120.00 Hz','vsyncRate=60.00 Hz'));self.reject()

    def test_provider_dc(self):
        p=self.root/'P01_early_provider.txt';p.write_text(p.read_text().replace('value=0','value=1'));self.reject()

    def test_false_cross_dbv_command(self):
        def change(rows):
            r=next(r for r in rows if r[1]=='P01_command');r[2][1:]=[base.ARGS[2633],2633]
        self.logs(change);self.reject()

    def test_transplant_plateau_log(self):
        def change(rows):
            a=next(r for r in rows if r[1]=='P00_pre');b=next(r for r in rows if r[1]=='P01_pre');b[0]=a[0];b[2]=a[2]
        self.logs(change);self.reject()

    def test_duplicate_event(self):
        def change(rows):
            i=next(i for i,r in enumerate(rows) if r[1]=='P00_s0_manifest');rows.insert(i,rows[i])
        self.logs(change);self.reject()

    def test_missing_post_bracket(self):
        (self.root/'P01_s0_post_read0.json').unlink();self.reject()

    def test_wrong_restore_camera(self):
        self.json('oc_return_b_read0',lambda m:m.update(camera='other'));self.reject()

    def test_duplicate_oc_restore(self):
        shutil.copyfile(self.root/'oc_return_a_read0.json',self.root/'oc_return_b_read0.json');self.reject()

    def test_stock_frame_only_stale(self):
        a=base.read(self.root,'stock_final_a0')
        self.json('stock_final_b0',lambda m:m.update({'request.frameCount':a['request.frameCount']}));self.reject()

    def test_wrong_anchor_reference(self):
        self.json('new_ref',lambda m:m['top-left'].update(height=10));self.reject()


if __name__=='__main__':unittest.main()
