#!/usr/bin/env python3
"""Offline differential harness. Never print raw evidence or exception details."""
import collections, hashlib, json, os, pathlib, random, statistics, subprocess, sys, tempfile, time
sys.dont_write_bytecode=True
os.umask(0o077)
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(HERE.parent))
import p85_batched_envelope as oracle
def require(ok, message):
 if not ok: raise RuntimeError(message)
FROZEN={'06-tools/p85_batched_envelope.py':'ac3d55f5f7928ad8e55b9090615e23f9f35d5e0e','06-tools/run_p85_timed_stock_trial.py':'9c804b7f12c5a77768d2487c31703b66c540f62c'}
def blobs():
 for name,expected in FROZEN.items():
  b=(ROOT/name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  require(actual==expected, 'frozen_source_changed')
def plan(nonce='012345abcdef',parts=(('A',256),('B',32))):
 return oracle.Envelope(nonce,tuple(oracle.Part(k,'offline-no-execution',False,c) for k,c in parts),20)
def encode(p,payloads):
 pre=('@P85E:'+p.nonce+':').encode();raw=pre+b'START\n'
 for part,body in zip(p.parts,payloads):raw+=pre+b'SECTION '+part.label.encode()+b' 0 '+str(len(body)).encode()+b' 0\n'+body+b'\n'+pre+b'END '+part.label.encode()+b'\n'
 return raw+pre+b'DONE\n'
counts=collections.Counter(); timings=[]; corpus_sizes=[]
with tempfile.TemporaryDirectory(prefix='pwm-envelope-test-',dir='/tmp') as directory:
 work=pathlib.Path(directory);rawpath=work/'input';pp=work/'plan';ep=work/'stderr';out=work/'result'
 def run(raw,p,rc=0,err=b'',category='synthetic',env=None,expected=None,uncertain=False):
  rawpath.write_bytes(raw);ep.write_bytes(err)
  pp.write_text(''.join(f'{x.label} {x.limit}\n' for x in p.parts))
  try:gold=oracle.parse(raw,p,returncode=rc,stderr=err)
  except Exception:gold=None
  start=time.perf_counter()
  result=subprocess.run(['sh',str(HERE/'decode.sh'),str(rawpath),str(pp),p.nonce,str(rc),str(ep),str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=30)
  elapsed=time.perf_counter()-start
  good=result.returncode==0
  if category=='private_complete': timings.append(elapsed); corpus_sizes.append(len(raw))
  require(not result.stdout, 'unexpected_decoder_stdout')
  if good:
   require(gold is not None, 'accepted_oracle_reject')
   require(set(x.name for x in out.iterdir())=={'SUCCESS'}|{f'section{i:02d}' for i in range(1,len(p.parts)+1)}, 'output_names')
   for i,part in enumerate(p.parts,1):require((out/f'section{i:02d}').read_bytes()==gold[part.label].encode('utf-8'), 'byte_mismatch')
   for x in out.iterdir():x.unlink()
   out.rmdir();counts[category+'_accepted']+=1
  else:
   if uncertain:
    require(out.is_dir() and not (out/'SUCCESS').exists(), 'expected_uncertain_publication')
    # This fresh test owns the destination; production caller must quarantine uncertainty.
    for f in out.iterdir():f.unlink()
    out.rmdir();counts['uncertain_publication_rejected']+=1
   require(not out.exists(), 'failure_published_output')
   require(not pathlib.Path(str(out)+'.stage').exists(), 'failure_left_stage')
   counts[category+('_stricter' if gold is not None else '_agreed_reject')]+=1
  if expected is not None:require(good==expected, 'unexpected_acceptance')
  counts['cases']+=1
  return good
 blobs()
 p=plan();base=encode(p,[b'a\n\t\r\x01z',b''])
 run(base,p,expected=True)
 # Every byte truncation of representative framing and payload, including all boundaries.
 for i in range(len(base)):run(base[:i],p,category='truncation',expected=False)
 mutations=[base+b'\n',base+b'junk',base+base,base.replace(b'START',b'DONE',1),base.replace(b'abcdef',b'abcdee',1),base.replace(b'END A',b'END B'),base.replace(b'SECTION A',b'SECTION B'),base.replace(b'SECTION A',b'SECTION ../../x'),base.replace(b' 0 6 0',b' 1 6 0'),base.replace(b' 0 6 0',b' 0 6 1')]
 for n in (b'0',b'1',b'5',b'7',b'-6',b'06',b'000000006',b'999999999',b'1000000000',b'16777217',b'+6'):
  mutations.append(base.replace(b' 0 6 0',b' 0 '+n+b' 0'))
 for rc in (b'00',b'000',b'0000',b'-1',b'256'):mutations.append(base.replace(b' 0 6 0',b' '+rc+b' 6 0'))
 for body in (b'\0',b'\xff',b'\xc3\xa9',b'\x7f',b'\n',b'@P85E:012345abcdef:',b'x@P85E:012345abcdef:DONE\ny',b'@P85E:000000000000:DONE',b'@P85E:012345abcdef:START@P85E:012345abcdef:DONE',bytes(range(1,128))):
  mutations.append(encode(p,[body,b'']))
 # Deterministic insertion, deletion and bit replacement fuzz; check EVERY acceptance.
 rng=random.Random(8705)
 for _ in range(350):
  j=rng.randrange(len(base));v=bytes([rng.randrange(256)])
  mutations.extend((base[:j]+v+base[j+1:],base[:j]+v+base[j:],base[:j]+base[j+1:]))
 # Explicit structural ambiguity, not dependent on random mutations.
 pre=('@P85E:'+p.nonce+':').encode()
 first=base.index(pre+b'SECTION A');second=base.index(pre+b'SECTION B');done=base.index(pre+b'DONE')
 sa=base[first:second];sb=base[second:done];start=base[:first];end=base[done:]
 mutations.extend((start+sb+sa+end,start+sa+sa+sb+end,start+sb+end,start+sa+end,
                   start+start+sa+sb+end,start+sa+end+sb+end,
                   base.replace(b'END A\n',b'END A'),base.replace(b'START\n',b'START '),
                   base.replace(b'DONE\n',b'DONE\r\n')))
 for raw in mutations:run(raw,p,category='mutation')
 for rc,err in ((1,b''),(124,b''),(0,b'warning'),(0,b'\0')):run(base,p,rc,err,category='producer',expected=False)
 # Fake external producers first produce normal output, then fail or emit stderr.
 fake=work/'bin';fake.mkdir()
 for tool in ('wc','od','awk'):
  real=subprocess.run(['which',tool],capture_output=True,text=True,check=True).stdout.strip()
  for fault in ('exit 9','printf fault >&2'):
   f=fake/tool;f.write_text('#!/bin/sh\n'+real+' "$@"\n'+fault+'\n');f.chmod(0o700)
   env=dict(os.environ,PATH=str(fake)+':'+os.environ['PATH'])
   run(base,p,category='tool_fault',env=env,expected=False);f.unlink()
 # Valid od output silently truncated at a token boundary must not hide raw trailing data.
 realod=subprocess.run(['which','od'],capture_output=True,text=True,check=True).stdout.strip()
 f=fake/'od'
 f.write_text('#!/usr/bin/env python3\nimport subprocess,sys\nr=subprocess.run(['+repr(realod)+',"-An","-v","-tu1"],input=sys.stdin.buffer.read(),capture_output=True)\nsys.stdout.buffer.write(b" ".join(r.stdout.split()[:-1])+b"\\n")\nsys.exit(r.returncode)\n')
 f.chmod(0o700);env=dict(os.environ,PATH=str(fake)+':'+os.environ['PATH'])
 run(base+b'X',p,category='truncated_od',env=env,expected=False);f.unlink()
 # A rename may complete before a tool reports failure: rc remains nonzero, quarantine.
 realmv=subprocess.run(['which','mv'],capture_output=True,text=True,check=True).stdout.strip()
 f=fake/'mv';f.write_text('#!/bin/sh\n'+realmv+' "$@"\nexit 7\n');f.chmod(0o700)
 run(base,p,category='publication_fault',env=env,expected=False,uncertain=True);f.unlink()
 # Empty and malformed arguments terminate before reading evidence.
 for nonce in ('','g'*12,'0'*11,'0'*13,'a\\nbbbbbbbbb'):
  result=subprocess.run(['sh',str(HERE/'decode.sh'),str(rawpath),str(pp),nonce,'0',str(ep),str(out)],capture_output=True,timeout=2)
  require(result.returncode and not out.exists(), 'offline_validation_failed');counts['argument_reject']+=1
 # Trusted plan rejects arbitrary labels, empty plan, duplicates, too many parts/caps.
 for badplan in ('','../X 10\n','A/../../X 10\n','A 10\nA 10\n','A -1\n','A 16777217\n','A 00\n', ''.join(f'A{i} 1\n' for i in range(17))):
  rawpath.write_bytes(base);ep.write_bytes(b'');pp.write_text(badplan)
  result=subprocess.run(['sh',str(HERE/'decode.sh'),str(rawpath),str(pp),p.nonce,'0',str(ep),str(out)],capture_output=True,timeout=2)
  require(result.returncode and not out.exists() and not pathlib.Path(str(out)+'.stage').exists(), 'offline_validation_failed');counts['plan_reject']+=1
 # Size cap before od, and exact section cap.
 rawpath.write_bytes(b'');
 with rawpath.open('wb') as f:f.truncate(oracle.MAX_TOTAL+1)
 pp.write_text('A 1\n');ep.write_bytes(b'')
 result=subprocess.run(['sh',str(HERE/'decode.sh'),str(rawpath),str(pp),p.nonce,'0',str(ep),str(out)],capture_output=True,timeout=2)
 require(result.returncode and not out.exists(), 'offline_validation_failed');counts['oversize_reject']+=1
 for n in (255,256,257):run(encode(p,[b'x'*n,b'']),p,category='cap',expected=n<=256)
 if '--private' in sys.argv:
  state=(('FIELDS',1024),('DISPLAY',4*1024*1024),('BOOT',128),('OWNER',0))
  for suffix in ('01','02','03'):
   name='p85_timed_stock_a001_20261108_'+suffix
   private=pathlib.Path.home()/'.cache/legion-y70-p85-timed-stock'/name
   manifest=json.loads((private/'envelope-manifest.json').read_text())
   report=json.loads((ROOT/'artifacts'/name/'run.json').read_text())
   events=report['envelope_timings'];require(len(manifest)==len(events)==28, 'offline_validation_failed')
   for record,event in zip(manifest,events):
    label=record['label'];require(label==event['label'], 'offline_validation_failed')
    if label=='state':parts=state
    elif label.startswith('quiet-'):parts=(('BEGIN',0),('WAIT',0),('END',0),('KERNEL',16*1024*1024))+state
    elif label.endswith('-hold-end') or label.endswith('-dispatch-gap'):parts=(('END',0),('KERNEL',16*1024*1024))+state
    elif label in ('baseline-c1','baseline-p85','sham15-p85','return15-c1','return15-p85','sham15-write','return15-write'):
     parts=(('BEGIN',0),)+((('PRE_GUARD',128),) if label.endswith('-write') else ())+ (('CHILD',1024*1024),('END',0),('KERNEL',16*1024*1024))+state+(('ESD',128),)
    else:raise AssertionError('unmapped_trusted_plan')
    # CHILD metadata validation only; no builder/command executed.
    q=plan(record['nonce'],parts)
    if any(x.label=='CHILD' for x in q.parts):
     from dataclasses import replace
     q=replace(q,parts=tuple(replace(x,root=True) if x.label=='CHILD' else x for x in q.parts),child_command='offline-no-execution')
    stem=event['raw_record'];require('/' not in stem and stem.endswith(label), 'offline_validation_failed')
    raw=(private/(stem+'.stdout')).read_bytes();err=(private/(stem+'.stderr')).read_bytes()
    run(raw,q,event['return_code'],err,category='private_complete',expected=True)
    # Mutated private inputs retain trusted metadata, never parse nonce/plan from them.
    for cut in (0,1,len(raw)//2,len(raw)-1):run(raw[:cut],q,category='private_truncation',expected=False)
    run(raw+b'X',q,category='private_trailing',expected=False)
 blobs()
summary=lambda xs: {'min':min(xs),'median':statistics.median(xs),'max':max(xs)} if xs else None
print(json.dumps({'host_decode_seconds':summary(timings),'corpus_bytes':summary(corpus_sizes),'android_performance_claim':False,'status':'PASS','counts':dict(counts),'frozen_sources':FROZEN,'universal_subset_proven':False},sort_keys=True))
