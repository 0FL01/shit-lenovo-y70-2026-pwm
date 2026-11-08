"""Offline fake-trace and ordinary-temp-file shell tests; no device operations."""
import os
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from dsi_trial_transaction import RANGES, native_state, qualify_quiet, transaction_script, validate_batch_capture, stock_anchor_settings, validate_stock_anchor, refresh_restore_order, experiment_marker, marker_interval, ensure_unused_marker


class TransactionTests(unittest.TestCase):
    def anchor(self,actual=1,group=8):
        return f'[ 1.0] [drm:dsi_display_set_mode [msm_drm]] hactive=1440, vactive=3168, fps=120(actual={actual}, group=0x{group:x}), clk_rate=1234000000\n'

    def test_pinned_native_states_explicit_and_consistent(self):
        idle=native_state(self.anchor())
        active=native_state(self.anchor(120,3))
        self.assertEqual(idle['native_actual_hz'],1)
        self.assertEqual(active['native_actual_hz'],120)
        self.assertEqual(qualify_quiet(self.anchor()+'BEGIN\nquiet\nEND','BEGIN','END'),idle)
        for log in ('software peakRefreshRate120',self.anchor(90,5),self.anchor(1,3),self.anchor().replace('1440','1080')):
            with self.assertRaises(ValueError): native_state(log)
        with self.assertRaises(ValueError): qualify_quiet(self.anchor()+'BEGIN\nEND','BEGIN','END',active)
        for content in ('dsi_ctrl_cmd_transfer len=3','dsi_display_set_mode','Command transfer failed'):
            with self.assertRaises(ValueError): qualify_quiet(self.anchor()+'BEGIN\n'+content+'\nEND','BEGIN','END')

    def test_stock_anchor_freshness_identity_and_settings_order(self):
        anchor90=self.anchor(90,5).replace('fps=120','fps=90')
        valid90='BEGIN90\n'+anchor90+'END90\n'
        self.assertEqual(validate_stock_anchor(valid90,'BEGIN90',90,'END90')['native_actual_hz'],90)
        for log in ('BEGIN90\nEND90',anchor90+'BEGIN90\nEND90',
                    'BEGIN90\n'+self.anchor()+'END90',valid90+'BEGIN90',
                    'END90\nBEGIN90\n'+anchor90,valid90.replace('group=0x5','group=0x3')):
            with self.assertRaises(ValueError):validate_stock_anchor(log,'BEGIN90',90,'END90')
        for actual,group in ((120,3),(1,8)):
            log='BEGIN120\n'+self.anchor(actual,group)+'END120'
            self.assertEqual(validate_stock_anchor(log,'BEGIN120',120,'END120')['native_actual_hz'],actual)
        down=stock_anchor_settings(90);up=stock_anchor_settings(120)
        self.assertLess(down.index('min_refresh_rate'),down.index('peak_refresh_rate'))
        self.assertLess(up.index('peak_refresh_rate'),up.index('min_refresh_rate'))
        with self.assertRaises(ValueError):stock_anchor_settings(144)
        self.assertEqual(refresh_restore_order('120.0','90.0'),('peak_refresh_rate','min_refresh_rate'))
        self.assertEqual(refresh_restore_order('90.0','120.0'),('min_refresh_rate','peak_refresh_rate'))
        self.assertEqual(refresh_restore_order('null','120.0'),('min_refresh_rate','peak_refresh_rate'))

    def test_qualified_stock_anchor_last_mode_with_setup_transients(self):
        evidence=Path(__file__).resolve().parents[1]/'artifacts/native_anchor_qualification_20261108.json'
        if not evidence.exists():self.skipTest('Saved qualification report unavailable')
        # Published actual mode lines inside synthetic test markers, not new live evidence.
        report=json.loads(evidence.read_text())
        for step in report['steps']:
            hz=step['requested_hz']
            fixture='TEST_BEGIN\n'+'\n'.join(step['native_mode_lines'])+'\nTEST_END'
            result=validate_stock_anchor(fixture,'TEST_BEGIN',hz,'TEST_END')
            self.assertEqual(result['native_actual_hz'],hz)
            self.assertEqual(result['fresh_native_events'],len(step['native_mode_lines']))

    def test_run_unique_markers_do_not_alias_prefix_ids_or_old_runs(self):
        short=experiment_marker('test_run_01')
        long=experiment_marker('test_run_01_extra')
        old='PWM_A9_REPRODUCTION'
        for suffix in ('_QUIET_BEGIN_baseline_7','_STOCK_ANCHOR_BEGIN_90',
                       '_BEGIN_baseline','_REDRAW_BEGIN_a9_only','_HOLD_BEGIN_return_a9_only','_READ_BEGIN_baseline'):
            self.assertNotIn(short+suffix,long+suffix)
            self.assertNotIn(short+suffix,old+suffix)
        for invalid in ('short','UPPERCASE_ID','test;unsafe', 'a'*65):
            with self.assertRaises(ValueError):experiment_marker(invalid)
        self.assertEqual(ensure_unused_marker(long+'_HOLD_BEGIN_baseline','test_run_01'),short)
        with self.assertRaises(ValueError):ensure_unused_marker(short+'_READ_BEGIN_baseline','test_run_01')
        begin,end=long+'_HOLD_BEGIN_baseline',long+'_HOLD_END_baseline'
        self.assertEqual(marker_interval('old\n'+begin+'\nvalid\n'+end,begin,end),'\nvalid\n')
        with self.assertRaises(ValueError):marker_interval(begin+begin+end,begin,end)

    def test_saved_trial05_duplicate_markers_reject_and_scoped_replay_separates(self):
        p=Path.home()/'.cache/legion-y70-trials/a9_c1_a001_20261108_05/baseline-quiet-7.txt'
        if not p.exists():self.skipTest('Private trial05 evidence unavailable')
        real=p.read_text()
        old='PWM_A9_REPRODUCTION'
        begin,end=old+'_QUIET_BEGIN_baseline_7',old+'_QUIET_END_baseline_7'
        self.assertEqual(real.count(begin),2)
        with self.assertRaisesRegex(ValueError,'ambiguous quiet'):
            qualify_quiet(real,begin,end)
        # Offline replay only: re-label each retained run's own event lines by
        # known monotonic windows; original evidence is never modified on disk.
        lines=[]
        for line in real.splitlines(keepends=True):
            if old in line:
                stamp=float(re.match(r'\[\s*(\d+\.\d+)\]',line)[1])
                run='a9_c1_a001_20261108_04' if stamp<1800 else 'a9_c1_a001_20261108_05'
                line=line.replace(old,experiment_marker(run),1)
            lines.append(line)
        scoped=''.join(lines)
        current=experiment_marker('a9_c1_a001_20261108_05')
        result=qualify_quiet(scoped,current+'_QUIET_BEGIN_baseline_7',current+'_QUIET_END_baseline_7')
        self.assertEqual(result['native_actual_hz'],120)
        self.assertEqual(result['native_group'],3)
        future=experiment_marker('a9_c1_a001_20261108_06')
        with self.assertRaises(ValueError):
            qualify_quiet(scoped,future+'_QUIET_BEGIN_baseline_7',future+'_QUIET_END_baseline_7')

    def block(self,i):
        start,end=RANGES[i]
        return (f'dd-1 [000] d.... {i+2}.000000: mode_entry: pending={start} length={end-start} flags={64 if i<4 else 0}\n'
                + ('dd-1 [000] d.... 6.000001: mode_ctrl_return: rc=0\n'*75 if i==4 else '')
                +f'dd-1 [000] d.... {i+2}.000002: mode_return: rc=0\n')

    def capture(self,mutate=None):
        # Background ESD in the preexisting prefix is not attributed to the batch.
        trace='kworker-1 [000] d.... 1.000000: mode_ctrl_return: rc=1\n'
        raw='BLOCK_TRACE_BEGIN -1\n'+trace+'BLOCK_TRACE_END -1\n'
        for i in range(5):
            block=self.block(i)
            if mutate: block=mutate(i,block)
            trace+=block
            raw+=f'BLOCK_TRACE_BEGIN {i}\n'+trace+f'BLOCK_TRACE_END {i}\n'
        return raw

    def test_complete_batch_and_fail_closed_deltas(self):
        result=validate_batch_capture(self.capture(),0)
        self.assertEqual((result['chunks_verified'],result['entry_count_after']),(5,5))
        mutations=[lambda i,b:b.replace('pending=500','pending=501'),
                   lambda i,b:b.replace('flags=64','flags=0',1),
                   lambda i,b:b+'mode_ctrl_return: rc=0\n' if i==1 else b,
                   lambda i,b:b+'mode_ctrl_return: rc=1\n' if i==1 else b,
                   lambda i,b:b.replace('rc=0','rc=-1',1),
                   lambda i,b:b.replace('mode_return:','wrong_return:',1)]
        for mutate in mutations:
            with self.assertRaises(ValueError): validate_batch_capture(self.capture(mutate),0)
        with self.assertRaises(ValueError): validate_batch_capture(self.capture().replace('BLOCK_TRACE_END 2','MISSING'),0)

    def simulate_shell(self,root,fail_index=None):
        tmp='/data/local/tmp/synthetic'
        trace='/sys/kernel/tracing/instances/pwm_mode'
        body=shlex.split(transaction_script(tmp,trace,'stock',0))[-1]
        lines=[]
        for line in body.splitlines():
            if line.startswith('mount ') or line.startswith("trap 'umount "): lines.append(':')
            else: lines.append(line)
        body='\n'.join(lines).replace(tmp,str(root)).replace(trace,str(root/'trace_instance'))
        self.assertNotIn('mount ',body)
        c=root/'debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd';c.parent.mkdir(parents=True);c.write_text('')
        t=root/'trace_instance/trace';t.parent.mkdir();t.write_text('kworker: mode_ctrl_return: rc=1\n')
        for i in range(5):
            data=self.block(i)
            if i==fail_index:data=data.replace('pending='+str(RANGES[i][0]),'pending=999')
            (root/f'fixture{i}').write_text(data)
        # Mock only dd, which appends a known trace. No generated panel writes execute.
        prefix='n=0; dd() { command cat "$SIM/fixture$n" >> "$SIM/trace_instance/trace"; command printf "%s\\n" "$n" >> "$SIM/executed"; n=$((n+1)); };\n'
        return subprocess.run(['sh','-c',prefix+body],env={**os.environ,'SIM':str(root)},capture_output=True,text=True)

    def test_device_side_awk_checks_run_before_next_block(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result=self.simulate_shell(root)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(validate_batch_capture(result.stdout,0)['chunks_verified'],5)
            self.assertEqual((root/'executed').read_text().splitlines(),['0','1','2','3','4'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result=self.simulate_shell(root,fail_index=2)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((root/'executed').read_text().splitlines(),['0','1','2'])

    def test_fresh_runner_enables_logger_before_native_ui_setup(self):
        source=(Path(__file__).resolve().parent/'run_dsi_mode_trial.py').read_text()
        early=source.index('enable_logger()  # Observe native HOME/Settings/redraw transitions')
        settings=source.index('        settings_changed = True',early)
        home=source.index("target('input keyevent 3')",settings)
        redraw=source.index("repaint_settings('preflight')",home)
        self.assertLess(early,settings)
        self.assertLess(settings,home)
        self.assertLess(home,redraw)
        self.assertIn('        if not reproduction:\n            enable_logger()',source[redraw:])
        self.assertEqual(source.count('            create_stock_anchor()'),1)
        anchor_call=source.index('            create_stock_anchor()')
        self.assertLess(early,anchor_call)
        self.assertLess(anchor_call,source.index('            recording = True',anchor_call))
        self.assertIn("report.get('stock_native_anchor_attempted') or pending_uncertain or candidate_active",source)

    def test_saved_trial03_is_real_transaction_concurrency(self):
        p=Path.home()/'.cache/legion-y70-trials/a9_c1_a001_20261108_03'
        if not (p/'baseline-kernel.txt').exists():self.skipTest('Private evidence unavailable')
        log=(p/'baseline-kernel.txt').read_text()
        begin,end='PWM_A9_REPRODUCTION_BEGIN_baseline','PWM_A9_REPRODUCTION_END_baseline'
        self.assertEqual(native_state(log)['native_actual_hz'],1)
        with self.assertRaisesRegex(ValueError,'Native writes or mode transition'):
            qualify_quiet(log,begin,end)
        section=log.split(begin,1)[1].split(end,1)[0]
        self.assertEqual(section.count('dsi_ctrl_cmd_transfer len='),101)
        self.assertIn('fps=90(actual=90, group=0x5)',section)
        self.assertIn('fps=120(actual=1, group=0x8)',section)
        # Replay actual per-callback prefixes: writer concurrency must still fail.
        lines=(p/'trace-latest.txt').read_text().splitlines(keepends=True)
        first=next(i for i,l in enumerate(lines) if 'mode_entry:' in l)
        ends=[i for i,l in enumerate(lines) if 'mode_return:' in l]
        self.assertEqual(len(ends),5)
        raw='BLOCK_TRACE_BEGIN -1\n'+''.join(lines[:first])+'BLOCK_TRACE_END -1\n'
        for i,index in enumerate(ends):
            raw+=f'BLOCK_TRACE_BEGIN {i}\n'+''.join(lines[:index+1])+f'BLOCK_TRACE_END {i}\n'
        with self.assertRaisesRegex(ValueError,'Concurrent controller'):
            validate_batch_capture(raw,0)


if __name__=='__main__':unittest.main()
