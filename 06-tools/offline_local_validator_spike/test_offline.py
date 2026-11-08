"""Offline tests only. Read saved private files, never import a live runner."""
import os
import shlex
import shutil
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import p85_guarded_trial as p85
import stock_c1_sweep as stock
import p85_batched_envelope as envelope

def saved_sections(raw):
    # Test corpus extraction only, not a proposed device parser.
    first,raw=raw.split(b'\n',1)
    prefix=first.removesuffix(b'START')
    parts={}
    while raw!=prefix+b'DONE\n':
        header,raw=raw.split(b'\n',1)
        m=re.fullmatch(re.escape(prefix)+rb'SECTION ([A-Z_]+) 0 ([0-9]+) 0',header)
        if not m:raise ValueError('bad saved envelope')
        label=m[1].decode();n=int(m[2]);payload,raw=raw[:n],raw[n:]
        ending=b'\n'+prefix+b'END '+m[1]+b'\n'
        if not raw.startswith(ending) or label in parts:raise ValueError('bad saved boundary')
        raw=raw[len(ending):];parts[label]=payload
    return prefix.split(b':')[1].decode(),parts

def oracle(data,nonce,kind):
    try:
        text=data.decode('utf8','strict')
        if kind=='write':return p85.validate_write_capture(text,nonce,'sham15')
        if kind=='85':return p85.validate_long3(text,nonce)
        return stock.validate_adapter_capture(text,nonce,3600)
    except (ValueError,OverflowError):return None

def port(data,nonce,kind,stderr=b'',mode=0o600,rc=0):
    with tempfile.TemporaryDirectory() as d:
        f=Path(d)/'out';e=Path(d)/'err';f.write_bytes(data);e.write_bytes(stderr)
        f.chmod(mode);e.chmod(0o600)
        r=subprocess.run(['sh',str(HERE/'validate_capture.sh'),str(f),str(e),nonce,kind,str(rc)],capture_output=True)
        if r.returncode:return None
        if r.stderr:raise ValueError('validator emitted stderr')
        return dict(x.split('=',1) for x in r.stdout.decode().splitlines())

class Offline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=[]
        cls.wires=[]
        cls.states=[]
        for suffix in ('01','02','03'):
            root=Path.home()/('.cache/legion-y70-p85-timed-stock/p85_timed_stock_a001_20261108_'+suffix)
            for path in sorted(root.glob('*envelope*.stdout')):
                raw=path.read_bytes()
                if b':SECTION CHILD ' not in raw:continue
                nonce,parts=saved_sections(raw);data=parts['CHILD']
                kind='write' if b'WRITE_GATE_OK' in data else ('85' if b'P85_LONG3' in data else 'C1')
                cls.samples.append((data,nonce,kind))
                cls.states.append(parts)
                if kind=='write':
                    log=parts['KERNEL'].decode();markers=re.findall(r'PWM_P85_\S+',log)
                    begin=next(m for m in reversed(markers) if m.endswith('_WRITE_BEGIN'))
                    end=next(m for m in reversed(markers) if m.endswith('_WRITE_END'))
                    suffix='_QUIET_BEGIN_sham15_PRE_0' if '_SHAM15_WRITE_' in begin else '_SHAM15_HOLD_BEGIN'
                    protected=next(m for m in reversed(markers) if m.endswith(suffix))
                    cls.wires.append((log,protected,begin,end))
        if not cls.samples:raise unittest.SkipTest('private corpus absent; synthetic tests remain available')
        if len(cls.samples)!=21:raise ValueError('expected all 21 saved captures')

    def test_all_saved_and_structured(self):
        for data,nonce,kind in self.samples:
            with self.subTest(kind=kind):
                o=oracle(data,nonce,kind);p=port(data,nonce,kind)
                self.assertIsNotNone(o);self.assertIsNotNone(p)
                if kind!='write':
                    self.assertEqual(p['data'],','.join(map(str,o['data'])))
                    self.assertEqual(int(p['raw_count']),o['raw_hardware_count'])
                    self.assertEqual(float(p['refresh']),o['software_refresh'])
                else:self.assertEqual(int(p['callbacks']),o['callbacks'])

    def test_rejections_and_strict_subset(self):
        both=stricter=0
        for data,nonce,kind in self.samples:
            mutations=[data[:len(data)//2],data.rstrip(b'\n'), data+b'junk\n',data+b'\x00',data+b'\xff',data+b'A'*262144,
                data.replace(b'STATE 3600',b'STATE 3599'),data.replace(b'ESD_RESTORED reg_read',b'ESD_RESTORED bad'),
                data.replace(b'TRACE_BEGIN',b'TRACE_BEGIN\nTRACE_BEGIN'),
                data.replace(b'PROFILE_END',b'PROFILE_END\nPROFILE_END'),
                data.replace(b'rc=0',b'rc=-1',1),data.replace(b'pending=0',b'pending=1',1),
                data.replace(b'flags=0',b'flags=0 flags=0',1),
                data.replace(b'CLEANUP_OK',b''),data.replace(b'TRACE_END',b'TRACE_END\nLOST'),
                data.replace(nonce.encode(),b'000000000000',1)]
            mutations.append(data.replace(b'ESD_INITIAL reg_read\nESD_ACTIVE esd_sw_sim_success',b'ESD_ACTIVE esd_sw_sim_success\nESD_INITIAL reg_read'))
            mutations.append(re.sub(rb'(printf-)[0-9]+',rb'\g<1>999999',data,count=1))
            mutations.append(re.sub(rb'(^\s*header_[0-9a-f]+\s+)\d+(\s+)0',rb'\g<1>2\g<2>0',data,flags=re.M))
            mutations.append(re.sub(rb'(^\s*entry_[0-9a-f]+\s+\d+\s+)0',rb'\g<1>1',data,flags=re.M))
            mutations.append(data.replace(b'TRACE_BEGIN\n',b'TRACE_BEGIN\nPROFILE_BEGIN\n',1))
            mutations.append(data.replace(b'pending=0',b'pending=0 extra=0',1))
            event=re.search(rb'^.*entry_'+nonce.encode()+rb':.*\n',data,re.M)[0]
            mutations.extend([data.replace(event,b'',1),data.replace(event,event+event,1)])
            if kind!='write':
                label=b'P85_LONG3' if kind=='85' else b'C1'
                mutations.append(re.sub(rb'^('+label+rb' .*?)$',rb'\1 0xab',data,flags=re.M))
            if kind!='write':
                for a,b in [(b'header=0x1600031c',b'header=0x1700031c'),(b'header=0x1600031c',b'header=0x1600011c'),
                    (b'count=9',b'count=8'),(b'allocation=16',b'allocation=3'),(b'requested=3',b'requested=1'),
                    (b'mrps=3',b'mrps=1'),(b'read_bytes=16',b'read_bytes=8'),(b'hw_status=0x90000',b'hw_status=0x80000'),
                    (b'hw_status=0xd0000',b'hw_status=0x80000')]:
                    if a in data:mutations.append(data.replace(a,b,1))
            for m in mutations:
                self.assertIsNone(port(m,nonce,kind))
                if oracle(m,nonce,kind) is None:both+=1
                else:stricter+=1
            self.assertIsNone(port(data,nonce,kind,stderr=b'warning'))
            self.assertIsNone(port(data,nonce,kind,mode=0o644))
            self.assertIsNone(port(data,nonce,kind,rc=1))
        print('capture mutations: both reject=%d stricter-port=%d'%(both,stricter))

    def test_reviewer_capture_regressions(self):
        cases=0
        for data,nonce,kind in self.samples:
            variants=[data.replace(b'pending=0',b'pending=00',1),
                data.replace(b'flags=0',b'flags=00',1),
                data.replace(b'length=11',b'length=011',1),
                data.replace(b'pending=0',b'pending=0x0',1),
                data.replace(b'pending=0',b'pending=-0',1)]
            for event in ('entry','ctrl','header'):
                forged=('# '+event+'_'+nonce+': (symbol) pending=0 length=11 flags=0\n').encode()
                variants.append(data.replace(b'TRACE_BEGIN\n',b'TRACE_BEGIN\n'+forged,1))
            if kind!='write':
                variants.extend([data.replace(b'requested=3',b'requested=03',1),
                    data.replace(b'allocation=16',b'allocation=016',1),
                    data.replace(b'count=9',b'count=09',1)])
            for mutated in variants:
                if kind!='write':self.assertIsNone(oracle(mutated,nonce,kind))
                self.assertIsNone(port(mutated,nonce,kind));cases+=1
            mutated=data.replace(('entry_'+nonce+':').encode(),('fakeentry_'+nonce+':').encode(),1)
            self.assertIsNone(port(mutated,nonce,kind));cases+=1
            mutated=data.replace(('entry_'+nonce+':').encode(),('entry_'+nonce+': entry_'+nonce+':').encode(),1)
            self.assertIsNone(port(mutated,nonce,kind));cases+=1
            mutated=re.sub(rb'(^\s*entry_[0-9a-f]+\s+)3',rb'\g<1>03',data,flags=re.M)
            self.assertIsNone(port(mutated,nonce,kind));cases+=1
        print('reviewer capture regressions=%d'%cases)

    def test_cartesian_line_grammar(self):
        representatives={kind:(data,nonce) for data,nonce,kind in self.samples}
        cases=accepted=0
        for kind,(data,nonce) in representatives.items():
            # Exercise every nonempty line, including all header/comment lines,
            # all boundary/metadata/profile classes and each event role.
            lines=data.splitlines(keepends=True)
            for index,line in enumerate(lines):
                if not line.strip():continue
                body=line.rstrip(b'\n')
                variants=set()
                for prefix in (b'',b' ',b'\t',b'# ',b'X'):
                    for suffix in (b'',b' ',b'\t',b' CLEANUP_OK',b' TRACE_BEGIN',b' PROFILE_BEGIN',b' extra=0'):
                        variants.add(prefix+body+suffix+b'\n')
                variants.update((body.replace(b' ',b'\t')+b'\n',body.replace(b' ',b'  ')+b'\n',
                    body+b'\n'+body+b'\n',b'# CLEANUP_OK\n'+line,b'# TRACE_BEGIN\n'+line,
                    b'# PROFILE_BEGIN\n'+line,body.replace(b'printf-',b'')+b'\n',
                    body.replace(b'pending=0 length=11 flags=0',b'pending=0 flags=0 length=11')+b'\n',
                    body.replace(b'pending=0 length=11 flags=0',b'flags=0 length=11 pending=0')+b'\n'))
                # Swap every adjacent assignment pair, not just entry fields.
                assignments=list(re.finditer(rb'\b\w+=[^ ]+',body))
                for left,right in zip(assignments,assignments[1:]):
                    variants.add(body[:left.start()]+right[0]+body[left.end():right.start()]+left[0]+body[right.end():]+b'\n')
                for token in (b'TRACE_END',b'PROFILE_END',b'STATE 3600 120.00001',
                        b'ESD_INITIAL reg_read',b'GATE_OK 0',b'WRITE_GATE_OK 0',
                        ('entry_'+nonce+':').encode(),('header_'+nonce+':').encode()):
                    variants.update((b'# '+token+b'\n'+line,token+b' '+line,body+b' '+token+b'\n'))
                for replacement in variants:
                    if replacement==line:continue
                    mutated=b''.join(lines[:index]+[replacement]+lines[index+1:])
                    run=subprocess.run(['awk','-v','nonce='+nonce,'-v','kind='+kind,'-f',str(HERE/'capture.awk')],input=mutated,capture_output=True)
                    cases+=1
                    if run.returncode==0:
                        accepted+=1;expected=oracle(mutated,nonce,kind)
                        self.assertIsNotNone(expected,(kind,index,replacement[:100]))
                        projection=dict(row.split('=',1) for row in run.stdout.decode().splitlines())
                        if kind!='write':self.assertEqual(projection['data'],','.join(map(str,expected['data'])))
            # Exact reviewer cases must reject, not merely agree on positives.
            for bad in [data.replace(b'STATE ',b'STATE\t',1),
                    data.replace(b'GATE_OK ',b'GATE_OK\t',1),
                    data.replace(b'GATE_OK ',b'GATE_OK  ',1),
                    data.replace(b'TRACE_BEGIN\n',b'TRACE_BEGIN\n# CLEANUP_OK\n',1),
                    data.replace(b'pending=0 length=11 flags=0',b'pending=0 flags=0 length=11',1),
                    data.replace(b'pending=0 length=11 flags=0',b'pending=0\tlength=11\tflags=0',1),
                    re.sub(rb'printf-([0-9]+)([^\n]*ctrl_)',rb'\1\2',data,count=1)]:
                self.assertIsNone(port(bad,nonce,kind))
        print('Cartesian whole-line mutations=%d accepted-with-oracle=%d'%(cases,accepted))

    def test_writer_wire_saved_and_mutations(self):
        def run(log,p,b,e):
            r=subprocess.run(['awk','-v','protected='+p,'-v','begin='+b,'-v','end='+e,'-f',str(HERE/'writer_wire.awk')],input=log.encode(),capture_output=True)
            return r.returncode==0
        cases=0
        for log,p,b,e in self.wires:
            reference=stock.native_state(log.split(p)[0])
            self.assertTrue(p85.validate_write_wire(log,b,e,'sham15',reference))
            self.assertTrue(p85.validate_write_wire(log,p,e,'sham15',reference))
            self.assertTrue(run(log,p,b,e))
            addition='[ 9999.0] dsi-ctrl-1: dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= 85 15\n'
            native='[ 9999.0] dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000\n'
            for altered in [log+addition,log+native,log+'LOST\n',log+'Command transfer failed\n',
                log.replace(b,b+'\n'+addition),log.replace(e,e+'\n'+native),log.replace(p,p+' '+p),
                log.replace(e,'MISSING_END'),log.replace('cmds= 85 15','cmds= 85 14'),
                log.replace(b,b+'\n'+native.replace('actual=120','actual=90')+native)]:
                self.assertFalse(run(altered,p,b,e));cases+=1
            # A malformed newer mode must invalidate the older good anchor.
            pos=log.index(p);line_start=log.rfind('\n',0,pos)+1
            for malformed in ('dsi_display_set_mode malformed_no_fps',
                    'dsi_display_set_mode fps=120',
                    'dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=120, group=0x3)',
                    'dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=90, group=0x3), clk_rate=1234000000'):
                altered=log[:line_start]+'[ 9999.0] '+malformed+'\n'+log[line_start:]
                self.assertFalse(run(altered,p,b,e));cases+=1
        print('writer wire: saved=%d malformed=%d'%(len(self.wires),cases))

    def test_writer_cartesian_operation_lines(self):
        def oracle_wire(log,p,b,e,reference):
            try:
                p85.validate_write_wire(log,b,e,'sham15',reference)
                p85.validate_write_wire(log,p,e,'sham15',reference)
                # Exact additional completed-child caller guard in timed.envelope.
                if log.count(e)!=1:return False
                tail=log.split(e,1)[1]
                return not any(x in tail for x in ('dsi_ctrl_cmd_transfer len=','dsi_display_set_mode','Command transfer failed','LOST'))
            except (ValueError,OverflowError):return False
        def run(log,p,b,e):
            result=subprocess.run(['awk','-v','protected='+p,'-v','begin='+b,'-v','end='+e,'-f',str(HERE/'writer_wire.awk')],input=log.encode(),capture_output=True)
            return result.returncode==0
        cases=accepted=0
        wrong='dsi-ctrl-1: dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= 85 14'
        for saved,p,b,e in self.wires:
            reference=stock.native_state(saved.split(p)[0])
            start=saved.rfind('\n',0,saved.index(p))+1
            anchor=[line for line in saved[:start].splitlines() if 'dsi_display_set_mode' in line][-1]
            # Preserve every protected-origin-to-dump line, plus the real latest
            # native anchor. Only unrelated older prefix history is projected out.
            log=anchor+'\n'+saved[start:]
            self.assertTrue(oracle_wire(log,p,b,e,reference));self.assertTrue(run(log,p,b,e))
            good='hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000'
            wrong_tuple=good.replace('fps=120','fps=90').replace('actual=120','actual=90')
            bad_native=log.replace(good,wrong_tuple+' '+good,1)
            bad_packet=log.replace('dsi-ctrl-1: dsi_ctrl_cmd_transfer len=',wrong+' dsi-ctrl-1: dsi_ctrl_cmd_transfer len=',1)
            for bad in (bad_native,bad_packet):
                self.assertFalse(oracle_wire(bad,p,b,e,reference));self.assertFalse(run(bad,p,b,e))
            lines=log.splitlines(keepends=True)
            for index,line in enumerate(lines):
                body=line.rstrip('\n');variants=set()
                for prefix in ('','X ','# ','[ 0.0] '):
                    for suffix in ('',' extra',' '+wrong,' '+p,' '+e):
                        variants.add(prefix+body+suffix+'\n')
                variants.update((body+' '+body+'\n',line+line,body.replace(' ','\t')+'\n',
                    body.replace(' ','  ')+'\n',b+' '+body+'\n',e+' '+body+'\n',
                    body+' '+good+'\n',wrong+' '+body+'\n',body.replace('dsi-ctrl-1:','dsi-ctrl-2:')+'\n',
                    body.replace('0x39','0X39')+'\n',body.replace('hs cmds=','lp cmds=')+'\n'))
                if index+1<len(lines):variants.add(body+' '+lines[index+1])
                for replacement in variants:
                    if replacement==line:continue
                    mutated=''.join(lines[:index]+[replacement]+lines[index+1:]);cases+=1
                    if run(mutated,p,b,e):
                        accepted+=1
                        self.assertTrue(oracle_wire(mutated,p,b,e,reference),(index,replacement[:160]))
            # Explicit boundary order and packet order permutations.
            for first,second in ((p,b),(b,e),(p,e)):
                changed=log.replace(first,'TEMP_MARK').replace(second,first).replace('TEMP_MARK',second)
                self.assertFalse(run(changed,p,b,e));cases+=1
            packet_lines=[line for line in lines if 'dsi_ctrl_cmd_transfer len=' in line]
            for first,second in zip(packet_lines,packet_lines[1:]):
                changed=log.replace(first,'TEMP_PACKET\n').replace(second,first).replace('TEMP_PACKET\n',second)
                self.assertFalse(run(changed,p,b,e));cases+=1
        print('writer Cartesian mutations=%d accepted-with-combined-oracle=%d'%(cases,accepted))

    def test_independent_state_semantics(self):
        def run(parts,boot):
            with tempfile.TemporaryDirectory() as d:
                files=[]
                for key in ('FIELDS','DISPLAY','BOOT','OWNER','ESD'):
                    p=Path(d)/key;p.write_bytes(parts[key]);files.append(str(p))
                r=subprocess.run(['awk','-f',str(HERE/'state.awk'),*files],env=dict(os.environ,LC_ALL='C',P85_OFFLINE_EXPECTED_BOOT=boot),capture_output=True)
                return r.returncode==0
        for parts in self.states:
            boot=parts['BOOT'].decode().strip()
            self.assertTrue(envelope.validate_state({k:v.decode() for k,v in parts.items()},3600,boot))
            self.assertEqual(parts['ESD'].decode().strip(),'reg_read')
            self.assertTrue(run(parts,boot))
            for key,val in [('FIELDS',b'3599\n0\n0\nEnforcing\n'),('FIELDS',b'3600\n0\n0\nPermissive\n'),
                ('FIELDS',b'3600\n1\n0\nEnforcing\n'),('FIELDS',b'3600\n0\n1\nEnforcing\n'),
                ('OWNER',b'owner\n'),('BOOT',b'stale\n'),('ESD',b'esd_sw_sim_success\n'),
                ('DISPLAY',parts['DISPLAY']+parts['DISPLAY']),('BOOT',parts['BOOT']*2),('ESD',b'reg_read\nreg_read\n')]:
                self.assertFalse(run(dict(parts,**{key:val}),boot))
        print('state semantics: saved=%d malformed=%d'%(len(self.states),len(self.states)*10))

class Synthetic(unittest.TestCase):
    @staticmethod
    def wrapper_fixture():
        nonce='012345abcdef'
        lines=['STATE 3600 120.00001','ESD_INITIAL reg_read','ESD_ACTIVE esd_sw_sim_success']
        lines+=['WRITE_GATE_OK '+gate for gate in '01233'];lines+=['TRACE_BEGIN']
        for i,length in enumerate((11,9,11),1):
            for event,fields in (('entry','pending=0 length=%d flags=0'%length),('ctrl','rc=0'),('tx','rc=0')):
                lines.append('printf-%d [000] d.... 1.000000: %s_%s: (symbol) %s'%(i,event,nonce,fields))
        lines+=['TRACE_END','PROFILE_BEGIN']
        lines += [name+'_'+nonce+' '+str(count)+' 0' for name,count in (('header',0),('hardware',0),('ctrl',3),('tx',3),('entry',3))]
        lines+=['PROFILE_END','ESD_RESTORED reg_read','CLEANUP_OK']
        return nonce,('\n'.join(lines)+'\n').encode()

    def test_wrapper_metadata_faults(self):
        nonce,data=self.wrapper_fixture();cases=0
        # All stubs/inputs are synthetic, temporary and never touch a device.
        faults=[('valid-exit9',True,'',9),('absent-success',False,'',0),('absent-failure',False,'',9),
            ('absent-command',False,'',127),('signal-status',False,'',143),
            ('extra-stdout',True,"printf '9\\n'",0),('nul-stdout',True,"printf '\\000'",0)]
        for diagnostic in ("printf 'diagnostic\\n' >&2","printf '\\012' >&2","printf '\\000' >&2"):
            for status in (0,9):faults.append(('diagnostic-'+str(status),True,diagnostic,status))
        for tool in ('stat','id','wc'):
            for label,delegate,extra,status in faults:
                with self.subTest(tool=tool,fault=label),tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);work=root/'scratch';work.mkdir();binpath=root/'bin';binpath.mkdir()
                    out=root/'out';err=root/'err';out.write_bytes(data);err.write_bytes(b'');out.chmod(0o600);err.chmod(0o600)
                    stub=binpath/tool;actual=shutil.which(tool)
                    stub.write_text('#!/bin/sh\n'+(shlex.quote(actual)+' "$@"\n' if delegate else '')+extra+'\nexit '+str(status)+'\n');stub.chmod(0o700)
                    env=dict(os.environ,TMPDIR=str(work),PATH=str(binpath)+os.pathsep+os.environ['PATH'])
                    result=subprocess.run(['sh',str(HERE/'validate_capture.sh'),str(out),str(err),nonce,'write','0'],env=env,capture_output=True)
                    self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'')
                    self.assertEqual(list(work.iterdir()),[]);cases+=1
        print('self-contained metadata faults=%d'%cases)

    def test_final_verdict_is_not_a_receipt(self):
        nonce,data=self.wrapper_fixture()
        for diagnostic in ("printf '\\012' >&2","printf '\\000' >&2"):
            for status in (0,9):
                with tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);work=root/'scratch';work.mkdir();binpath=root/'bin';binpath.mkdir()
                    out=root/'out';err=root/'err';out.write_bytes(data);err.write_bytes(b'');out.chmod(0o600);err.chmod(0o600)
                    stub=binpath/'awk'
                    stub.write_text('#!/bin/sh\nfinal=0\nfor arg in "$@"; do case "$arg" in */capture.awk) final=1;; esac; done\n'+shlex.quote(shutil.which('awk'))+' "$@" || exit $?\nif [ "$final" = 1 ]; then '+diagnostic+'; exit '+str(status)+'; fi\n');stub.chmod(0o700)
                    result=subprocess.run(['sh',str(HERE/'validate_capture.sh'),str(out),str(err),nonce,'write','0'],env=dict(os.environ,TMPDIR=str(work),PATH=str(binpath)+os.pathsep+os.environ['PATH']),capture_output=True)
                    self.assertTrue(result.stdout.startswith(b'kind=write\n'))
                    self.assertNotEqual(result.returncode,0,'verdict must not override failed final status/diagnostics')
                    self.assertEqual(list(work.iterdir()),[])

    def test_wrapper_bootstrap_and_cleanup(self):
        nonce,data=self.wrapper_fixture();cases=0
        def inputs(root):
            work=root/'scratch';work.mkdir();out=root/'out';err=root/'err'
            out.write_bytes(data);err.write_bytes(b'');out.chmod(0o600);err.chmod(0o600)
            return work,['sh',str(HERE/'validate_capture.sh'),str(out),str(err),nonce,'write','0']
        for tool in ('mkdir','rm','rmdir'):
            for delegate,extra,status in ((True,'',9),(False,'',9),(False,'',0),
                    (True,"printf '\\012' >&2",0),(True,"printf '\\000' >&2",0),
                    (True,"printf '\\012'",0),(True,"printf '\\000'",0),
                    (True,"printf '\\000' >&2",9)):
                with self.subTest(tool=tool,delegate=delegate,extra=extra,status=status),tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);work,args=inputs(root);binpath=root/'bin';binpath.mkdir();stub=binpath/tool
                    stub.write_text('#!/bin/sh\n'+(shlex.quote(shutil.which(tool))+' "$@"\n' if delegate else '')+extra+'\nexit '+str(status)+'\n');stub.chmod(0o700)
                    env=dict(os.environ,TMPDIR=str(work),PATH=str(binpath)+os.pathsep+os.environ['PATH'])
                    result=subprocess.run(args,env=env,capture_output=True)
                    self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'');cases+=1
                    if tool=='mkdir' and delegate and status!=0:
                        self.assertEqual(len(list(work.glob('*.work'))),1,'uncertain mkdir must retain its path')
        for suffix in ('audit','stdout','work'):
            for symlink in (False,True):
                with self.subTest(suffix=suffix,symlink=symlink),tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);work,args=inputs(root);foreign=root/'foreign';foreign.write_bytes(b'FOREIGN')
                    target='"$TMPDIR/.p85-validator-$$.'+suffix+'"'
                    if symlink:setup='ln -s '+shlex.quote(str(foreign))+' '+target
                    elif suffix=='work':setup='mkdir '+target+'; printf FOREIGN > '+target+'/sentinel'
                    else:setup='printf FOREIGN > '+target
                    env=dict(os.environ,TMPDIR=str(work))
                    result=subprocess.run(['sh','-c',setup+'; exec sh "$@"','collision-launcher',*args[1:]],env=env,capture_output=True)
                    self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'');self.assertEqual(foreign.read_bytes(),b'FOREIGN')
                    retained=list(work.glob('*.'+suffix));self.assertEqual(len(retained),1)
                    if symlink:self.assertTrue(retained[0].is_symlink())
                    elif suffix=='work':self.assertEqual((retained[0]/'sentinel').read_bytes(),b'FOREIGN')
                    else:self.assertEqual(retained[0].read_bytes(),b'FOREIGN')
                    cases+=1
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work,args=inputs(root)
            result=subprocess.run(args,env=dict(os.environ,TMPDIR=str(work)),capture_output=True)
            self.assertEqual(result.returncode,0);self.assertEqual(result.stderr,b'');self.assertTrue(result.stdout.startswith(b'kind=write\n'))
            self.assertEqual(list(work.iterdir()),[])
            altered=root/'no-proc-wrapper.sh'
            source=(HERE/'validate_capture.sh').read_text();self.assertEqual(source.count('/proc/self/fd/8'),1)
            altered.write_text(source.replace('/proc/self/fd/8',str(root/'absent-fd')))
            result=subprocess.run(['sh',str(altered),*args[2:]],env=dict(os.environ,TMPDIR=str(work)),capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'');cases+=1
        print('self-contained bootstrap/cleanup faults=%d'%cases)

    def test_exact_discrete_state_tokens(self):
        # Self-contained: this regression must not depend on private captures.
        def evaluate(fields,actual,expected,legacy=None):
            parts={'FIELDS':fields,'DISPLAY':'mActiveSfDisplayMode=DisplayMode{peakRefreshRate=120.00001}\n',
                'BOOT':actual+'\n','OWNER':'','ESD':'reg_read\n'}
            try:host=envelope.validate_state(parts,3600,expected)
            except ValueError:host=False
            with tempfile.TemporaryDirectory() as directory:
                files=[]
                for key in ('FIELDS','DISPLAY','BOOT','OWNER','ESD'):
                    path=Path(directory)/key;path.write_text(parts[key]);files.append(str(path))
                env=dict(os.environ,LC_ALL='C');env.pop('P85_OFFLINE_EXPECTED_BOOT',None)
                if expected is not None:env['P85_OFFLINE_EXPECTED_BOOT']=expected
                args=['awk']+(['-v','expected_boot='+legacy] if legacy is not None else [])
                result=subprocess.run([*args,'-f',str(HERE/'state.awk'),*files],env=env,capture_output=True)
                return host,result.returncode==0
        fields='3600\n0\n0\nEnforcing\n'
        identities=('01234567-89ab-4cde-8fab-0123456789ab','ffffffff-ffff-4fff-8fff-ffffffffffff',
            '0','00','1','01','100000','1e5','9007199254740992','9007199254740993',
            '99999999999999999999999999999999999999','99999999999999999999999999999999999998',
            r'\061',r'\x31',r'900719925474099\062',
            r'\0601234567-89ab-4cde-8fab-0123456789ab',r'\x301234567-89ab-4cde-8fab-0123456789ab',
            r'01234567-89ab-4cde-8fab-0123456789a\142')
        for identity in identities:
            self.assertEqual(evaluate(fields,identity,identity),(True,True))
        for expected in identities:
            for actual in identities:
                if actual!=expected:self.assertEqual(evaluate(fields,actual,expected),(False,False))
        # No missing-env fallback or override through the legacy -v argument.
        self.assertFalse(evaluate(fields,'1',None,legacy='1')[1])
        self.assertEqual(evaluate(fields,'1','1',legacy='2'),(True,True))
        self.assertFalse(evaluate(fields,'2','1',legacy='2')[1])
        for invalid in ('',' ','a b','\t','a\nb','é','a'*129):
            self.assertFalse(evaluate(fields,invalid,invalid)[1])
        self.assertEqual(evaluate(fields,'a'*128,'a'*128),(True,True))
        malformed=0
        for index,variants in ((0,('03600','003600','3600.0','3.6e3','36e2','+3600','0xE10')),
                (1,('00','000','+0','-0','0.0','0e0','0x0')),
                (2,('00','000','+0','-0','0.0','0e0','0x0')),
                (3,('enforcing','ENFORCING','0'))):
            for value in variants:
                rows=fields.splitlines();rows[index]=value
                self.assertEqual(evaluate('\n'.join(rows)+'\n',identities[0],identities[0]),(False,False));malformed+=1
        print('synthetic exact-state: identities=%d mismatches=%d malformed-fields=%d'%(len(identities),len(identities)*(len(identities)-1),malformed))

    def test_raw_wrapper_arguments(self):
        nonce,data=self.wrapper_fixture();cases=0
        bad_nonces=(r'012345abcde\146',r'012345abcde\x66',nonce[:-1],nonce+'0',nonce.upper(),
            '012345abcdeg','012345abcde-','',nonce+'\n',' '+nonce,'012345abcdeé')
        bad_kinds=(r'wr\151te',r'\167rite',r'\x77rite',r'C\061',r'\0705','WRITE','c1','write ',' 85','','candidate14','write\n')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'scratch';work.mkdir();out=root/'out';err=root/'err'
            out.write_bytes(data);err.write_bytes(b'');out.chmod(0o600);err.chmod(0o600)
            for candidate_nonce,kind in [(n,'write') for n in bad_nonces]+[(nonce,k) for k in bad_kinds]:
                result=subprocess.run(['sh',str(HERE/'validate_capture.sh'),str(out),str(err),candidate_nonce,kind,'0'],env=dict(os.environ,TMPDIR=str(work)),capture_output=True)
                self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'');self.assertEqual(list(work.iterdir()),[]);cases+=1
        print('raw wrapper argument rejections=%d'%cases)

    def test_file_type_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out';err=Path(d)/'err';out.write_bytes(b'');err.write_bytes(b'');out.chmod(0o600);err.chmod(0o600)
            link=Path(d)/'link';link.symlink_to(out)
            args=['sh',str(HERE/'validate_capture.sh')]
            self.assertNotEqual(subprocess.run(args+[str(link),str(err),'012345abcdef','85','0'],capture_output=True).returncode,0)
            link.unlink();os.link(out,link)
            self.assertNotEqual(subprocess.run(args+[str(out),str(err),'012345abcdef','85','0'],capture_output=True).returncode,0)

    def test_portable_synthetic_captures(self):
        nonce='012345abcdef'
        for kind in ('85','C1','write'):
            rows=[]
            def event(name,pid,fields):
                rows.append('printf-%d [000] d.... 1.000000: %s_%s: (symbol) %s'%(pid,name,nonce,fields))
            for i in range(3):
                event('entry',i+1,'pending=0 length=%d flags=0'%(9 if kind=='write' and i==1 else 11))
                event('ctrl',i+1,'rc=0');event('tx',i+1,'rc=0')
                if i==0 and kind!='write':
                    event('hardware',9,'hw_status=0x90000 read_bytes=16 mrps=3')
                    event('header',9,'header=0x1600031c requested=3 count=9 allocation=16 disp_op=0')
                    event('ctrl',9,'rc=3')
            pre=['STATE 3600 120.00001','ESD_INITIAL reg_read','ESD_ACTIVE esd_sw_sim_success']
            if kind=='write':pre+=['WRITE_GATE_OK '+x for x in '01233']
            else:
                pre+=['GATE_OK '+x for x in '0123']
                pre+=[('P85_LONG3' if kind=='85' else 'C1')+' 0x15 0x00 0x00']
                pre+=['GATE_OK 3','GATE_OK 4']
            if kind=='C1':pre+=['ESD_RESTORED reg_read']
            pre+=['TRACE_BEGIN',*rows,'TRACE_END','PROFILE_BEGIN']
            for name,count in [('header',0 if kind=='write' else 1),('hardware',0 if kind=='write' else 1),('ctrl',3 if kind=='write' else 4),('tx',3),('entry',3)]:
                pre+=['%s_%s %d 0'%(name,nonce,count)]
            pre+=['PROFILE_END']
            if kind!='C1':pre+=['ESD_RESTORED reg_read']
            pre+=['CLEANUP_OK']
            data=('\n'.join(pre)+'\n').encode()
            self.assertIsNotNone(oracle(data,nonce,kind));self.assertIsNotNone(port(data,nonce,kind))
            if kind!='write':
                label=b'P85_LONG3' if kind=='85' else b'C1'
                payloads=((0,10,15),(127,128,170),(255,0,128),(15,255,10))
                for payload in payloads:
                    for raw_count in (9,13):
                        replacement=label+b' '+b' '.join(('0x%02X'%b).encode() for b in payload)
                        valid=re.sub(rb'^'+label+rb' .*$',replacement,data,flags=re.M)
                        valid=valid.replace(b'hw_status=0x90000',('hw_status=0x%x0000'%raw_count).encode())
                        valid=re.sub(rb'printf-([0-9]+)',lambda m:b'printf-'+str(int(m[1])+12000).encode(),valid)
                        valid=valid.replace(b'[000]',b'[007]').replace(b'1.000000:',b'9876.123456:')
                        valid=valid.replace(b'TRACE_BEGIN\n',b'TRACE_BEGIN\n# tracer: nop\n#\n# entries-in-buffer/entries-written: 12/12   #P:8\n# TASK-PID CPU TIMESTAMP FUNCTION\n')
                        expected=oracle(valid,nonce,kind);actual=port(valid,nonce,kind)
                        self.assertIsNotNone(expected);self.assertIsNotNone(actual)
                        self.assertEqual(actual['data'],','.join(map(str,expected['data'])))
                        self.assertEqual(int(actual['raw_count']),expected['raw_hardware_count'])
                        self.assertEqual(float(actual['refresh']),expected['software_refresh'])
            for bad in (data+b'\x00',data+b'\xc0\x80',data.replace(b'rc=0',b'rc=-1',1),data[:-1],data.replace(b'count=9',b'count=0') if kind!='write' else data.replace(b'length=9',b'length=11')):
                self.assertIsNone(port(bad,nonce,kind))

if __name__=='__main__':unittest.main()
