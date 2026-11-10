"""Offline byte mutations and fault-injected generated shell; no Android I/O."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

import aa_threshold_trial as aa
import test_dsi_trial_transaction as fixtures

ROOT=Path(__file__).resolve().parents[1]
TOKEN='aa_offline_test_token'
TMP='/data/local/tmp/aa_offline_test'

# Sanitized native debugfs rendering, including its final ASCII space.
SELECTOR_BODY='ESD_ISOLATED esd_sw_sim_success\nR 23:A9 0x0e \nR 24:9D 0x0e \nR 00:52 0x0e 0x10 \nESD_HELD esd_sw_sim_success\n'

def selector_capture(initial='',body=SELECTOR_BODY):
    return f'SELECTOR_INITIAL_BEGIN {len(initial.encode())}\n'+initial+'\nSELECTOR_INITIAL_END\n'+body

SELECTOR_RAW=selector_capture()

class AATests(unittest.TestCase):
    def test_exact_programs_and_all_byte_mutations(self):
        values=aa.fixed_programs()
        self.assertEqual(values,aa.programs(ROOT))
        self.assertEqual([i for i,(a,b) in enumerate(zip(*values.values())) if a!=b],[77])
        for name,program in values.items():
            for i in range(875):
                changed=bytearray(program);changed[i]^=1
                with self.assertRaises(ValueError):aa.validate_program(bytes(changed),name)
        for name in ('a9_only','p85','AA10',''):
            with self.assertRaises(ValueError):aa.validate_program(values['stock'],name)

    def test_chunk_bytes_and_writer_scope(self):
        for name,data in aa.fixed_programs().items():
            chunks=aa.chunk_files(data,name)
            self.assertEqual([len(v.split()) for v in chunks.values()],[253,247,254,110,11])
            self.assertEqual(bytes(int(v,16) for chunk in chunks.values() for v in chunk.split()),data)
            command=aa.writer_script(TMP,TOKEN,data,name,7)
            body=shlex.split(command)[-1]
            self.assertEqual(body.count('dd if='),5)
            self.assertNotIn('rx_cmd',body)
            self.assertNotIn('P0',body)
            self.assertEqual(body.count('sha256sum'),5)
            self.assertLess(body.index('sha256sum'),body.index('dd if='))
            self.assertEqual(body.count('BLOCK_TRACE_BEGIN'),6)
            self.assertEqual(body.count('/chunks/'+name+'_'),35)
        for tmp in ('/data/local/tmp/a/b','/tmp/test','/data/local/tmp/aa;id'):
            with self.assertRaises(ValueError):aa.writer_script(tmp,TOKEN,data,name,0)

    def test_full_wire_exact(self):
        fixture=fixtures.TransactionTests();anchor=fixture.anchor(120,3);reference=aa.tx.native_state(anchor)
        for name,data in aa.fixed_programs().items():
            lines=[f'dsi-ctrl-1: dsi_ctrl_cmd_transfer len={len(p)}, type=0x{h[0]:02x} hs cmds= {p.hex(" ")}' for _,h,_,p in aa.packets(data)]
            log=anchor+'BEGIN\n'+'\n'.join(lines)+'\nEND\n'
            self.assertEqual(aa.validate_wire(log,'BEGIN','END',data,name,reference)['native_packets_matched'],75)
            for changed in (log.replace('aa 10','aa 11') if name=='aa10' else log.replace('aa 11','aa 10'),log.replace(' hs ',' lp ',1),log.replace('END',lines[0]+'\nEND'),log.replace('END','LOST\nEND'),log.replace('END','dsi_display_set_mode\nEND')):
                with self.assertRaises(ValueError):aa.validate_wire(changed,'BEGIN','END',data,name,reference)

    def test_selectors_trace_and_values(self):
        controls=iter(aa.SELECTOR_CONTROLS);after=''
        for i in range(10):
            rc=next(controls)
            page=i not in (1,4,7)
            if page:after+='mode_entry: pending=0 length=11 flags=0\n'
            after+=f'mode_ctrl_return: rc={rc}\n'
            if page:after+='mode_return: rc=0\n'
        raw=SELECTOR_RAW
        for accepted in (raw,raw.replace(' \n','\n')):
            self.assertEqual(aa.validate_selectors(accepted,'',after,0)['entry_count_after'],7)
        bad=(raw.replace('0x10','0x11'),raw+'R 23:AA 0x10\n',raw+'R 23:A9 0e\n',
             raw.replace('ESD_HELD','BAD'),raw.replace('0x0e \n','0x0e  \n',1),
             raw.replace('0x0e \n','0x0e\t\n',1),raw.replace('R 23:A9',' R 23:A9'),
             raw.replace('0x0e \n','0x0e garbage \n',1),raw.replace('0x0e \n','0x0e 0x0e \n',1),
             raw.replace('0x0e 0x10 ','0x0e '),raw.replace('R 24:9D','R 23:A9'),
             raw.replace('R 23:A9 0x0e \nR 24:9D 0x0e ','R 24:9D 0x0e \nR 23:A9 0x0e '),
             raw.replace('R 24:9D 0x0e \n',''),raw.replace('0x0e 0x10','0x0e  0x10'))
        for broken in bad:
            with self.subTest(raw=broken),self.assertRaises(ValueError):aa.validate_selectors(broken,'',after,0)
        for broken in (after+'mode_ctrl_return: rc=0\n',after.replace('rc=2','rc=1'),after.replace('pending=0','pending=1',1),after+'LOST\n'):
            with self.assertRaises(ValueError):aa.validate_selectors(raw,'',broken,0)

    def simulate_selector(self,fail_at=None,prefix_at=None,head_failure=False,grep_failure=False,nonempty=False):
        """Replace only native operations/mount/owner in generated body.

        All generated awk/count/prefix gates execute against regular-file traces.
        A simulated TX succeeds at the filesystem layer even when native rc fails.
        """
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);trace=root/'trace';trace.write_text('mode_ctrl_return: rc=1\n' if nonempty else '')
            body=shlex.split(aa.selector_script(TMP,TOKEN,0))[-1]
            body=body.replace(aa.lock_commands(TOKEN)['verify'],':')
            body=body.replace(TMP,str(root)).replace(aa.TRACE+'/trace',str(trace))
            body=re.sub(r'(stat -c %u [^\n]+\)\" = )0',lambda m:m[1]+str(os.getuid()),body)
            lines=[];operation=0;expected=[]
            for line in body.splitlines():
                if line.startswith('mount ') or line.startswith("trap 'umount "):lines.append(':');continue
                if '> "$C/tx_cmd"' in line or '> "$C/rx_cmd"' in line:
                    page='tx_cmd' in line
                    rc=0 if page else (2 if operation==7 else 1)
                    data=('mode_entry: pending=0 length=11 flags=0\n' if page else '')+f'mode_ctrl_return: rc={-5 if fail_at==operation else rc}\n'+('mode_return: rc=0\n' if page else '')
                    payload=root/f'op{operation}';payload.write_text(data)
                    prefix='printf CORRUPTED > '+shlex.quote(str(trace))+'; ' if prefix_at==operation else ''
                    lines.append(prefix+'cat '+shlex.quote(str(payload))+' >> '+shlex.quote(str(trace))+'; echo '+str(operation)+' >> '+shlex.quote(str(root/'executed')))
                    if not page:
                        key=('23:A9','24:9D','00:52')[(operation-1)//3]
                        payload=root/f'rx{operation}';payload.write_text(''.join(f'0x{x:02x} ' for x in aa.SELECTORS[key]))
                        lines.append('cat '+shlex.quote(str(payload))+' > \"$C/rx_cmd\"')
                    operation+=1
                else:lines.append(line)
            rx=root/'debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/rx_cmd'
            rx.parent.mkdir(parents=True);rx.write_text('')
            esd=root/'debugfs/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode'
            esd.parent.mkdir(parents=True);(root/'debugfs').chmod(0o700);esd.write_text('reg_read\n')
            result=subprocess.run(['sh','-c',('head() { return 91; };\n' if head_failure else '')+('grep() { return 2; };\n' if grep_failure else '')+'\n'.join(lines)],capture_output=True,text=True,timeout=10)
            executed=(root/'executed').read_text().splitlines() if (root/'executed').exists() else []
            return result,executed,esd.read_text()

    def test_selector_all_ten_native_failure_prefixes_stop_without_cleanup_write(self):
        result,executed,esd=self.simulate_selector()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,SELECTOR_RAW)
        self.assertEqual(executed,list(map(str,range(10))))
        self.assertEqual(esd,'esd_sw_sim_success\n')
        for i in range(10):
            result,executed,esd=self.simulate_selector(fail_at=i)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(executed,list(map(str,range(i+1))))
            self.assertEqual(esd,'esd_sw_sim_success\n')
            self.assertNotIn('ESD_HELD',result.stdout)
        for i in range(1,10):
            result,executed,esd=self.simulate_selector(prefix_at=i)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(executed,list(map(str,range(i+1))))
            self.assertEqual(esd,'esd_sw_sim_success\n')

    def simulate_writer(self,name,fail_at=None,prefix_at=None,corrupt=False,symlink=False,grep_failure=False,empty=False,esd_mode="esd_sw_sim_success\n",controller_at=None,initial_trace=None):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700)
            (root/'debugfs').mkdir(mode=0o700);(root/'chunks').mkdir(mode=0o700)
            data=aa.fixed_programs()[name]
            for filename,contents in aa.chunk_files(data,name).items():
                path=root/'chunks'/filename;path.write_bytes(contents);path.chmod(0o600)
            if corrupt:(root/'chunks'/f'{name}_0.txt').write_bytes(b'wrong')
            if symlink:
                path=root/'chunks'/f'{name}_0.txt';target=root/'elsewhere';path.rename(target);path.symlink_to(target)
            esd = root/'debugfs'/aa.ESD_MODE_PATH
            esd.parent.mkdir(parents=True); esd.write_text(esd_mode)
            c=root/'debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd';c.parent.mkdir(parents=True);c.write_text('')
            trace=root/'trace_instance/trace';trace.parent.mkdir();trace.write_text(initial_trace if initial_trace is not None else ('' if empty else 'kworker: mode_ctrl_return: rc=1\n'))
            fixture=fixtures.TransactionTests()
            for i in range(5):
                block=fixture.block(i)
                if i == controller_at: block += 'mode_ctrl_return: rc=1\n'
                if i==fail_at:block=block.replace('pending='+str(aa.tx.RANGES[i][0]),'pending=999')
                (root/f'fixture{i}').write_text(block)
            body=shlex.split(aa.writer_script(TMP,TOKEN,data,name,0))[-1]
            body=body.replace(aa.lock_commands(TOKEN)['verify'],':').replace(TMP,str(root)).replace(aa.TRACE,str(trace.parent))
            body=re.sub(r'(stat -c %u [^\n]+\)\" = )0',lambda m:m[1]+str(os.getuid()),body)
            body='\n'.join(':' if line.startswith('mount ') or line.startswith("trap 'umount ") else line for line in body.splitlines())
            prefix='n=0; dd() { if [ "$n" = "'+str(prefix_at)+'" ]; then printf CORRUPTED > "$SIM/trace_instance/trace"; fi; command cat "$SIM/fixture$n" >> "$SIM/trace_instance/trace"; command printf "%s\\n" "$n" >> "$SIM/executed"; n=$((n+1)); };\n'
            result=subprocess.run(['sh','-c',('grep() { return 2; };\n' if grep_failure else '')+prefix+body],env={**os.environ,'SIM':str(root)},capture_output=True,text=True,timeout=10)
            executed=(root/'executed').read_text().splitlines() if (root/'executed').exists() else []
            remains=(root/'transaction_trace').exists()
            return result,executed,remains

    def test_both_writer_shells_gate_every_block_and_preserve_failed_evidence(self):
        for name in ('stock','aa10'):
            result,executed,remains=self.simulate_writer(name)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(aa.tx.validate_batch_capture(result.stdout,0)['chunks_verified'],5)
            self.assertEqual(executed,list(map(str,range(5))))
            self.assertFalse(remains)
            for i in range(5):
                result,executed,remains=self.simulate_writer(name,fail_at=i)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(executed,list(map(str,range(i+1))))
                self.assertTrue(remains)
                result,executed,remains=self.simulate_writer(name,prefix_at=i)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(executed,list(map(str,range(i+1))))
            for kwargs in ({'corrupt':True},{'symlink':True}):
                result,executed,_=self.simulate_writer(name,**kwargs)
                self.assertNotEqual(result.returncode,0);self.assertEqual(executed,[])

    def test_shared_transaction_allowlist_preserves_prior_rendering(self):
        import subprocess
        old=subprocess.run(['git','show','HEAD:06-tools/dsi_trial_transaction.py'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
        namespace={};exec(compile(old,'committed_transaction','exec'),namespace)
        for name in ('stock','a9_only'):
            self.assertEqual(aa.tx.transaction_script(TMP,aa.TRACE,name,7),namespace['transaction_script'](TMP,aa.TRACE,name,7))
        self.assertEqual(aa.tx.transaction_script(TMP,aa.TRACE,'aa10',7).count('/chunks/aa10_'),5)
        for name in ('AA10','candidate','aa11','stock; id','../../aa10'):
            with self.assertRaises(ValueError):aa.tx.transaction_script(TMP,aa.TRACE,name,7)

    def test_initial_grep_errors_never_dispatch_with_empty_or_nonempty_prefix(self):
        for nonempty in (False,True):
            result,executed,esd=self.simulate_selector(grep_failure=True,nonempty=nonempty)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(executed,[])
            self.assertEqual(esd,'reg_read\n')
        for name in ('stock','aa10'):
            for empty in (False,True):
                result,executed,remains=self.simulate_writer(name,grep_failure=True,empty=empty)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(executed,[])
                self.assertTrue(remains)
            result,executed,remains=self.simulate_writer(name,empty=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(executed,list(map(str,range(5))))
            self.assertFalse(remains)

    def test_prefix_reader_failure_is_not_masked_by_empty_prefix(self):
        result,executed,esd=self.simulate_selector(head_failure=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(executed,['0'])
        self.assertEqual(esd,'esd_sw_sim_success\n')

    def test_selector_has_no_generic_or_unknown_read(self):
        body=shlex.split(aa.selector_script(TMP,TOKEN,0))[-1]
        self.assertEqual(body.count('> "$C/rx_cmd"'),3)
        self.assertNotIn('0xAA',body)
        self.assertNotIn('restore()',body)
        for count in (-1,True,1.5):
            with self.assertRaises(ValueError):aa.selector_script(TMP,TOKEN,count)

if __name__=='__main__':unittest.main()
