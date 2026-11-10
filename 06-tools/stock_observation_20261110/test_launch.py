"""Offline source-bound visual intake and default CLI no-device tests."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import zlib
import construction as c
import launch

ROOT=Path(__file__).resolve().parents[2]

def png():
    def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')

class Tests(unittest.TestCase):
    def restore_module_namespace(self):
        # Test-only isolation: keep production preload rejection unchanged.
        for name in c.SOURCES:
            sys.modules.pop(name,None)
        sys.modules.update(self.saved_modules)

    def setUp(self):
        self.saved_modules={n:sys.modules[n] for n in c.SOURCES if n in sys.modules}
        self.addCleanup(self.restore_module_namespace)
        for name in c.SOURCES:
            sys.modules.pop(name,None)
        raw={n:(ROOT/p).read_bytes() for n,p in c.SOURCES.items()}
        hashes={n:hashlib.sha256(v).hexdigest() for n,v in raw.items()}
        bootstrap={f'06-tools/stock_observation_20261110/{n}.py':hashlib.sha256((ROOT/f'06-tools/stock_observation_20261110/{n}.py').read_bytes()).hexdigest() for n in ('construction','launch')}
        self.s=c.load_sources(raw,hashes,commit='a'*40,bootstrap_sha256=bootstrap)
    def tearDown(self):
        for n,m in self.s.modules.items():
            if sys.modules.get(n) is m:del sys.modules[n]
    def fixture(self):
        image=png();digest=hashlib.sha256(image).hexdigest()
        boots={'target':'00000000-0000-0000-0000-000000000001','camera':'00000000-0000-0000-0000-000000000002'}
        provenance={'helper_sha256':self.s.hashes['prestart_inspection'],
          'probe_sha256':self.s.hashes['stock_readonly_probe'],'launch_sha256':self.s.hashes['readonly_launch'],
          'dependency_commit':self.s.modules['prestart_inspection'].COMMIT,
          'parser_source_sha256':{p:h for p,h in self.s.modules['prestart_inspection'].PARSER_SOURCES.values()},
          'dependency_sha256':{k:self.s.hashes[n] for k,n in [('probe','stock_readonly_probe'),
             ('offline_baseline_adb','offline_baseline_adb'),('linux_adb_probe_dependencies','linux_adb_probe_dependencies'),
             ('camera_capture_metadata','camera_capture_metadata')]}}
        receipt={'schema':1,'receipt_phase':'before_descriptor_close','inspection_boot_before':boots,
          'inspection_boot_after':boots,'roles':{r:{'serial':r} for r in boots},'source_provenance':provenance,
          'summary':{'status':'prestart_inspected','boot_stable':True,'target':{'settings_foreground':True,
             'unlocked':True,'native_mode':{'native_actual_hz':120,'native_group':3},'software_hz':120},
             'screenshots':{r:{'sha256':digest} for r in boots}},
          'screenshot_custody':{r:{'sha256':digest,'size':len(image)} for r in boots}}
        raw=json.dumps(receipt).encode()
        cfg={'inspection_path':'/private/inspection.json','inspection_sha256':hashlib.sha256(raw).hexdigest(),
          'camera_png_path':'/private/camera.png','camera_png_sha256':digest,
          'target_png_path':'/private/target.png','target_png_sha256':digest,
          'roi':{k:list(v) for k,v in self.s.modules['protocol_v2'].ROI.items()},
          'scene_component':'com.android.settings/.Settings$DisplaySettingsActivity',
          'decision':'geometry_layout_approved_for_observation_only'}
        files={cfg['inspection_path']:raw,cfg['camera_png_path']:image,cfg['target_png_path']:image}
        reader=lambda path,cap,private:files[path]
        return cfg,receipt,files,reader
    def test_real_parser_receipt_byte_binding(self):
        cfg,receipt,files,reader=self.fixture()
        prior=launch.prior_review(cfg,self.s,('target','camera'),reader)
        record=prior.validate(receipt['inspection_boot_after'],dict(self.s.provenance))
        self.assertFalse(record['fresh_visual_review']);self.assertTrue(record['actual_media_review_required'])
    def test_forged_fresh_flag_rejected(self):
        cfg,receipt,files,reader=self.fixture();cfg['fresh_visual_review']=True
        with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)
    def test_changed_png_bytes_rejected(self):
        cfg,receipt,files,reader=self.fixture();files[cfg['camera_png_path']]=b'bad'
        with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)
    def test_changed_role_receipt_rejected(self):
        cfg,receipt,files,reader=self.fixture();receipt['roles']['camera']['serial']='other'
        raw=json.dumps(receipt).encode();files[cfg['inspection_path']]=raw;cfg['inspection_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)
    def test_changed_source_receipt_rejected(self):
        cfg,receipt,files,reader=self.fixture();receipt['source_provenance']['helper_sha256']='0'*64
        raw=json.dumps(receipt).encode();files[cfg['inspection_path']]=raw;cfg['inspection_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)
    def test_v1_old_unknown_producer_receipts_rejected(self):
        for digest in ('5af512cf02640e0813e627d9967439bcc1ed5ef334485f1d53cb73000158c723','69af'+'0'*60,'0'*64):
            cfg,receipt,files,reader=self.fixture();receipt['source_provenance']['helper_sha256']=digest
            raw=json.dumps(receipt).encode();files[cfg['inspection_path']]=raw;cfg['inspection_sha256']=hashlib.sha256(raw).hexdigest()
            with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)

    def test_v2_failure_receipt_is_not_geometry_review(self):
        cfg,receipt,files,reader=self.fixture()
        raw=json.dumps({'schema':1,'status':'prestart_inspection_failed','diagnostic_revision':2,
                        'receipt_phase':'before_descriptor_close'}).encode()
        files[cfg['inspection_path']]=raw;cfg['inspection_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):launch.prior_review(cfg,self.s,('target','camera'),reader)

    def test_read_file_rejects_symlink(self):
        with tempfile.TemporaryDirectory(prefix='stock-observation-launch-') as d:
            os.chmod(d,0o700);p=Path(d,'file');p.write_bytes(b'x');p.chmod(0o600)
            self.assertEqual(launch.read_file(str(p),10,private=True),b'x')
            link=Path(d,'link');link.symlink_to(p)
            with self.assertRaises(OSError):launch.read_file(str(link),10,private=True)
    def test_default_cli_never_constructs_or_selects_devices(self):
        construct=Mock();source=SimpleNamespace();inputs=object();review=object()
        with patch.object(launch,'prepare',return_value=(construct,source,inputs,review)),patch('sys.stdout',new_callable=io.StringIO) as out:
            result=launch.main(['--source-root','/source','--process-config','/p','--capture-config','/c'])
        self.assertEqual(result,0);construct.prepare.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())['device_services_sent'],0)

if __name__=='__main__':unittest.main()
