import csv, hashlib, os, tempfile, unittest
from pathlib import Path
import numpy as np
from PIL import Image
from audit import D, roles, save_mask, relative, verify_legends
class Tests(unittest.TestCase):
    def test_mask_exact_and_exclusion(self):
        m=roles()
        yy,xx=np.nonzero(m==1)
        self.assertEqual(len(xx),1280)
        np.testing.assert_array_equal(np.column_stack((yy,xx-800)),np.column_stack(np.nonzero(m==2)))
        self.assertEqual((int(xx.min()),int(xx.max()),int(yy.min()),int(yy.max())),(914,1010,1085,1181))
        self.assertFalse(m[:,280:900].any()) # entire central instrument and its margins
        self.assertFalse(m[:900].any());self.assertFalse(m[1340:].any())
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'m.png';save_mask(m,p)
            with Image.open(p) as im:np.testing.assert_array_equal(np.array(im),m)
    def test_ratio_equal_and_opposed(self):
        def data(d,b):return {'direct':{'mean_y':d},'background':{'mean_y':b}}
        self.assertTrue(relative(data(40,10),data(20,5))['within_10_percent'])
        self.assertFalse(relative(data(40,5),data(20,10))['within_10_percent'])
    def test_mixed_unknown_missing_and_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            with (D/'legend_reads.csv').open() as f:rows=list(csv.DictReader(f))
            for r in rows:
                if r['original_qc']!='missing':
                    b=r['slot'].encode();(d/(r['slot']+'.png')).write_bytes(b);r['source_sha256']=hashlib.sha256(b).hexdigest()
            rows[0]['time_label']='1mS';rows[1]['coupling']='unknown'
            p=d/'input.csv'
            with p.open('w') as f:
                w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
            q=verify_legends(d,p)
            self.assertEqual({k:len(v) for k,v in q['groups'].items()},{'X1 / 1mS / AC':1,'X1 / 5mS / AC':41})
            self.assertEqual(q['unreadable'],['P00_s1']);self.assertEqual(len(q['missing']),8)
            (d/'P14_s0.png').write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'source mismatch'):verify_legends(d,p)
if __name__=='__main__':unittest.main()
