"""Retrospective, read-only R12b replay. Supply public R12b artifact directory;
optional --private FROZEN_METHOD_DIR CAMERA_ONLY_ORDINAL_DIR OPERATOR_ARCHIVE.
Print only shareable checks; temporary scorer output is never published."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

FREEZE = '5285639f7dccff76abab209a2c5280d5c4c42a1a6c8aabde2225a3098c88b35f'
GEOM = '952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631'
PORTABLE = '33c590a96ce0185e184f23661761b0dc69bb6c2b3383f350ec4527b2ee00f4cf'
PRED = 'c3c353e34585c4e4b4bc60d16586d813219bc1372a9a2714f23f09e3b1a56079'
KEY = '6684bf87f9ef6de8c6d33a9b6118aabb988d6926facf4accd7616f2ea176d747'
SCORE = 'e634b72e37f8361c80b31c9c3d052631de61997011f33eeed03214e8fe8a2364'
SLOTS = [(f'p{i+1:02}_{j+1}.png', f'P{i:02}_{j}') for i in range(6) for j in range(3)]


def need(condition, what):
    if not condition:
        raise ValueError(what)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path):
    return json.loads(path.read_bytes())


def match_logs(rows):
    pattern = re.compile(r'P\d+_\d+_bracket|P\d+_complete|acquisition_complete')
    found = [(r[1], r[2]) for r in rows if pattern.fullmatch(r[1])]
    want = []
    for _, tag in SLOTS:
        want.append(tag + '_bracket')
        if tag.endswith('_2'):
            want.append(tag[:3] + '_complete')
    want.append('acquisition_complete')
    need([n for n, _ in found] == want, 'operator slot order/count')
    need(all(v is True for n, v in found if n.endswith('complete')), 'completion markers')


def inventory(aliases, originals, expected, public, aggregated):
    names, tags = zip(*SLOTS)
    need(set(aliases) == set(names) == set(expected) == set(aggregated), 'ordinal inventory')
    need(set(originals) == {t+'.png' for t in tags}, 'original slot inventory')
    need([v['ordinal'] for v in public] == list(tags), 'operator export slot order/count')
    need(len(set(expected.values())) == len(names), 'duplicate committed PNG bytes')
    for (n, t), frame in zip(SLOTS, public):
        b = aliases[n].read_bytes()
        need(b == originals[t+'.png'].read_bytes(), 'alias/original bytes: '+n)
        need(hashlib.sha256(b).hexdigest() == expected[n] == aggregated[n]['hash']
             == frame['image']['sha256'], 'bound PNG identity: '+n)
        need(len(b) == frame['image']['bytes'], 'length mismatch: '+n)


def diff_method(a, b):
    aa, bb = a.read_text().splitlines(), b.read_text().splitlines()
    need(len(aa) == len(bb), 'predictor line count')
    changed = [i for i, (x,y) in enumerate(zip(aa,bb)) if x != y]
    need(changed == [6] and aa[6].startswith('T=Path(') and bb[6].startswith('T=(Path(')
         and aa[6].endswith(';z=T.read_bytes()') and bb[6].endswith(';z=T.read_bytes()'),
         'non-location predictor diff')
    return 7


def run(script, args):
    proc = subprocess.run([sys.executable,'-E','-P','-B',str(script), *map(str,args)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    need(proc.returncode == 0, script.name + ' failed')


def audit(root, private):
    a = root/'analysis'
    man = a/'original_freeze.sha256'
    need(sha(man) == FREEZE, 'method manifest commitment')
    frozen = {n:h for h,n in (s.split() for s in man.read_text().splitlines())}
    need(set(frozen) == {'SPEC.txt','operator.py','predict.py','score.py'}, 'method manifest content')
    for n, m in [('SPEC.txt','SPEC.txt'),('operator.py','operator_plan.py'),('score.py','score.py')]:
        need(sha(a/m) == frozen[n], 'public method: '+m)
    need(sha(a/'predict.py') == PORTABLE != frozen['predict.py'], 'portable predictor identity')
    need(sha(root/'geometry'/'locked_transform.json') == GEOM, 'geometry')
    need(sha(a/'outcome.json') == SCORE, 'public score commitment')
    binding = obj(root/'binding.json')
    need(binding['operator_key_commitment'] == KEY and binding['blind_prediction_commitment'] == PRED,
         'handoff commitments')
    out = {'R013': {'public_predictor':PORTABLE,'frozen_predictor':frozen['predict.py'],
                    'freeze_manifest':FREEZE,'public_companions_exact':3,
                    'historical_chronology':'reported; no independent trusted timestamp'},
           'R014': {'planned_r12b':18,'new_acquisitions':0},
           'R015': {'private_replay':'SKIP: provide all three private archive inputs',
                    'retrospective':True}}
    if private:
        method, aliases, operator = private
        need((method/'FREEZE.sha256').read_bytes() == man.read_bytes(), 'original manifest copy')
        for name,h in frozen.items():
            need(sha(method/name) == h, 'frozen source: '+name)
        line = diff_method(method/'predict.py', a/'predict.py')
        out['R013'].update(originals_exact=4,portable_only_line_changed=line)
        inventory({p.name:p for p in aliases.iterdir()},
                  {p.name:p for p in operator.iterdir() if re.fullmatch(r'P\d+_\d+\.png',p.name)},
                  binding['sha256'],obj(root/'source'/'outcome_r12b.json')['frames'],
                  obj(a/'preview_aggregates.json'))
        match_logs([json.loads(l) for l in (operator/'log.jsonl').read_text().splitlines()])
        out['R014'].update(ordered_brackets=18,complete_phase_markers=6,
                           present=18,absent=0,extra_slot_files=0,duplicate_slot_events=0,
                           byte_identical_aliases=18,distinct_png_digests=18)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for name, script in [('frozen',method/'predict.py'),('portable',a/'predict.py')]:
                pred=d/(name+'.json')
                run(script,[aliases,pred])
                need(sha(pred)==PRED,'ordinal prediction commitment: '+name)
            # First key read by this replay is AFTER both full predictions are sealed and checked.
            key=operator/'private_pages'/'key.json'
            need(sha(key)==KEY, 'private key commitment')
            scored=d/'score.json'
            run(a/'score.py',[d/'frozen.json',key,PRED,KEY,scored])
            need(sha(scored)==SCORE and scored.read_bytes()==(a/'outcome.json').read_bytes(),
                 'scorer output mismatch')
            out['R015'].update(private_replay='MATCH',predictors_matching_seal=2,
                               predictions_digest=PRED,salted_key_digest=KEY,full_score_digest=SCORE)
    # Public assertions are deliberately separate from label-withheld replay.
    outcome=obj(a/'outcome.json')
    frames=list(outcome['frames'].values())
    coded=[f for f in frames if 'accuracy' in f]
    null=[f for f in frames if 'null_abs_ncc' in f]
    out['R015']['published_score']={
        'correct_cells':sum(f['accuracy'] for f in coded),'coded_cells':64*len(coded),
        'coded_pixel_pass':sum(f['ok'] for f in coded),'coded_frames':len(coded),
        'negative_pass':sum(f['ok'] for f in null),'negative_frames':len(null),
        'inversions_pass':sum(f['ok'] for f in outcome['inversions'].values()),
        'decoder_pixel_pass':outcome['decoder_pixel_pass']}
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--private', nargs=3,type=Path)
    args=p.parse_args()
    print(json.dumps(audit(args.root,args.private),indent=2))
