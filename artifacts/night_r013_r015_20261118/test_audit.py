import hashlib
import tempfile
import unittest
from pathlib import Path
from audit import SLOTS, diff_method, inventory, match_logs


def good_logs():
    rows = []
    for _, tag in SLOTS:
        rows.append([None, tag+'_bracket', []])
        if tag.endswith('_2'):
            rows.append([None, tag[:3]+'_complete', True])
    return rows+[[None, 'acquisition_complete', True]]


class Tests(unittest.TestCase):
    def test_good_event_sequence(self):
        match_logs(good_logs())

    def test_bad_event_sequences(self):
        events = good_logs()
        for bad in [events[1:], [events[0]]+events, events[:-1], events[::-1],
                    events[:-1]+[[None,'acquisition_complete',False]]]:
            with self.subTest(bad=bad[0][1]), self.assertRaises(ValueError):
                match_logs(bad)

    def test_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            files, raw, hashes, frames, agg = {}, {}, {}, [], {}
            for n,t in SLOTS:
                p=Path(td)/n
                p.write_bytes(n.encode())
                q=Path(td)/(t+'.png')
                q.write_bytes(p.read_bytes())
                h=hashlib.sha256(p.read_bytes()).hexdigest()
                files[n],raw[q.name],hashes[n],agg[n]=p,q,h,{'hash':h}
                frames.append({'ordinal':t, 'image':{'sha256':h,'bytes':len(n)}})
            inventory(files,raw,hashes,frames,agg)
            for x in [(dict(list(files.items())[1:]),raw,hashes,frames,agg),
                      (files,{**raw,'P05_3.png':q},hashes,frames,agg),
                      (files,raw,hashes,frames[::-1],agg),
                      (files,raw,{**hashes,n:hashes[SLOTS[0][0]]},frames,agg)]:
                with self.assertRaises(ValueError):
                    inventory(*x)
            q.write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                inventory(files,raw,hashes,frames,agg)

    def test_validator_rejects_extra_predictor_edit(self):
        before='\n'*6+"T=Path('abc');z=T.read_bytes()\npass\n"
        after='\n'*6+"T=(Path('def'));z=T.read_bytes()\npass\n"
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a', Path(td)/'b'
            a.write_text(before); b.write_text(after)
            self.assertEqual(diff_method(a,b), 7)
            b.write_text(after.replace('pass','pass; pass'))
            with self.assertRaises(ValueError):
                diff_method(a,b)


if __name__ == '__main__':
    unittest.main()
