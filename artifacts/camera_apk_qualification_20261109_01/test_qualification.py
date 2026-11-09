import unittest,hashlib,io,zipfile
from dataclasses import replace
from qualification import *
P='/data/app/~~opaque/net.sourceforge.opencamera-opaque/base.apk'
B='00000000-0000-4000-8000-000000000003'
I=('Galaga','ROW','A001')
class Tests(unittest.TestCase):
 def fixture(self,data=b'apk'):
  f=FileObservation(P,len(data),hashlib.sha256(data).hexdigest())
  c=tuple(ChunkResult(P,i,0,data[i*CHUNK:(i+1)*CHUNK],b'',True) for i in range((len(data)+CHUNK-1)//CHUNK))
  return (f,),c
 def run_assembly(self,f,c,**kw):
  args=dict(boot_before=B,boot_after=B,identity_before=I,identity_after=I);args.update(kw)
  return assemble(f,f,c,**args)
 def test_paths(self):self.assertEqual(paths(('package:'+P+'\n').encode()),(P,))
 def test_reject_paths(self):
  for p in [P+';id','/data/user/0/net.sourceforge.opencamera/x.apk','/sdcard/base.apk',P.replace('/base','/../base'),P+'\npackage:'+P]:
   with self.assertRaises(Rejected):paths(('package:'+p).encode())
 def test_size_and_type_bounds(self):
  f,c=self.fixture()
  for n in [True,0,-1,MAX_APK+1,1.5]:
   with self.assertRaises(Rejected):proposed_reads((P,),(replace(f[0],size=n),))
 def test_chunk_plan_and_assembly(self):
  data=b'x'*(CHUNK+9);f,c=self.fixture(data)
  p=proposed_reads((P,),f);self.assertFalse(p['physical_admission']);self.assertFalse(p['dispatch_implemented'])
  self.assertEqual([x['expected_bytes'] for x in p['reads']],[CHUNK,9]);self.assertEqual(self.run_assembly(f,c)[P],data)
 def test_failed_denied_unknown_reads(self):
  f,c=self.fixture()
  for x in [replace(c[0],rc=1),replace(c[0],complete=False),replace(c[0],rc=True),replace(c[0],stderr=b'x'*8193)]:
   with self.assertRaises(Rejected):self.run_assembly(f,(x,))
 def test_short_extra_replay_foreign(self):
  f,c=self.fixture()
  for x in [(),c+c,(replace(c[0],stdout=b'a'),),(replace(c[0],index=1),),(replace(c[0],path=P+'x'),)]:
   with self.assertRaises(Rejected):self.run_assembly(f,x)
 def test_digest_boot_identity(self):
  f,c=self.fixture()
  with self.assertRaises(Rejected):self.run_assembly(f,(replace(c[0],stdout=b'bad'),))
  for kw in [dict(boot_after='changed'),dict(identity_after=('other',)),dict(boot_before='')]:
   with self.assertRaises(Rejected):self.run_assembly(f,c,**kw)
 def test_file_changed(self):
  f,c=self.fixture()
  with self.assertRaises(Rejected):assemble(f,(replace(f[0],size=2),),c,boot_before=B,boot_after=B,identity_before=I,identity_after=I)
 def test_zip_inventory_not_source_equivalence(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('AndroidManifest.xml',b'opaque binary XML');z.writestr('classes.dex',b'opaque DEX')
  r=inspect_apk(b.getvalue());self.assertFalse(r['merged_manifest_decoded']);self.assertFalse(r['source_equivalent'])
  self.assertEqual(set(r['members']),{'AndroidManifest.xml','classes.dex'})
 def test_bad_zip(self):
  with self.assertRaises(Rejected):inspect_apk(b'apk')
 def test_no_manifest(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('classes.dex',b'x')
  with self.assertRaises(Rejected):inspect_apk(b.getvalue())
if __name__=='__main__':unittest.main()
