#!/usr/bin/env python3
"""Быстрые stdlib tests; known-answer: GHIDRA_TOOLKIT_KNOWN_ANSWER=1 в PyGhidra venv.

Тяжёлый прогон пишет временное evidence только во внешнем approved cache.
Каждый запуск .ko ограничен 480 s; projects/temp всегда во внешнем cache.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location('ghidra_decompile', HERE / 'ghidra_decompile.py')
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class UnitTests(unittest.TestCase):
    def setUp(self):
        tool.CACHE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=tool.CACHE, prefix='unit-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def test_elf_validation(self):
        binary = self.path / 'fixture'
        header = bytearray(b'\x7fELF\x02\x01' + b'\x00' * 14)
        for kind, expected in ((1, 'ET_REL'), (3, 'ET_DYN')):
            struct.pack_into('<HH', header, 16, kind, 183)
            binary.write_bytes(header)
            self.assertEqual(tool.elf_type(binary), expected)
        struct.pack_into('<HH', header, 16, 3, 62)
        binary.write_bytes(header)
        with self.assertRaises(ValueError):
            tool.elf_type(binary)
        binary.write_bytes(b'not ELF')
        with self.assertRaises(ValueError):
            tool.elf_type(binary)

    def test_pe32_plus_arm64_validation(self):
        binary = self.path / 'firmware.efi'
        image = bytearray(0x200)
        image[:2] = b'MZ'
        struct.pack_into('<I', image, 0x3c, 0x80)
        image[0x80:0x84] = b'PE\x00\x00'
        struct.pack_into('<HH', image, 0x84, 0xaa64, 1)
        struct.pack_into('<H', image, 0x94, 0xf0)
        struct.pack_into('<H', image, 0x98, 0x20b)
        binary.write_bytes(image)
        self.assertEqual(tool.elf_type(binary), 'PE32+')
        struct.pack_into('<H', image, 0x84, 0x8664)
        binary.write_bytes(image)
        with self.assertRaises(ValueError):
            tool.elf_type(binary)
        struct.pack_into('<H', image, 0x84, 0xaa64)
        struct.pack_into('<I', image, 0x3c, len(image))
        binary.write_bytes(image)
        with self.assertRaises(ValueError):
            tool.elf_type(binary)

    def test_provenance_hash_and_stable_json(self):
        binary = self.path / 'a'
        binary.write_bytes(b'abc')
        self.assertEqual(tool.sha256(binary),
                         'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
        tool.write_json(self.path / 'first.json', {'z': 1, 'a': 2})
        tool.write_json(self.path / 'second.json', {'a': 2, 'z': 1})
        self.assertEqual((self.path / 'first.json').read_bytes(),
                         (self.path / 'second.json').read_bytes())

    def test_project_default_and_escape_rejected(self):
        parsed = tool.parser().parse_args(['symbols', 'x', '--output', 'out'])
        self.assertEqual(parsed.project_location, tool.CACHE)
        for path in (ROOT, tool.CACHE / '..'):
            with self.assertRaises(tool.argparse.ArgumentTypeError):
                tool.external_location(str(path))
        link = self.path / 'escape'
        link.symlink_to(ROOT, target_is_directory=True)
        with self.assertRaises(tool.argparse.ArgumentTypeError):
            tool.external_location(str(link))

    def test_selector_and_timebox_validation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for args in (['decompile', 'x', '--output', 'out'],
                         ['xrefs', 'x', '--output', 'out', '--function', 'f', '--address', '10'],
                         ['symbols', 'x', '--output', 'out', '--timebox', 'nan']):
                with self.assertRaises(SystemExit):
                    tool.parser().parse_args(args)

    def test_brief_selector(self):
        for selector in (['--function', 'f'], ['--address', '10']):
            parsed = tool.parser().parse_args(['brief', 'x', '--output', 'out', *selector])
            self.assertEqual(parsed.command, 'brief')
        with contextlib.redirect_stderr(io.StringIO()):
            for selector in ([], ['--filter', 'f'],
                             ['--function', 'f', '--address', '10']):
                with self.assertRaises(SystemExit):
                    tool.parser().parse_args(['brief', 'x', '--output', 'out', *selector])

    def test_lines_parser(self):
        args = ['decompile', 'x', '--function', 'f', '--output', 'out']
        self.assertEqual(tool.parser().parse_args(args + ['--lines', '2:4']).lines, (2, 4))
        with contextlib.redirect_stderr(io.StringIO()):
            for value in ('0:2', '3:2', '-1:2', '1', '1:', ':2', '1:2:3', 'a:2', '1.5:2'):
                with self.assertRaises(SystemExit):
                    tool.parser().parse_args(args + ['--lines', value])
            with self.assertRaises(SystemExit):
                tool.parser().parse_args(['brief', 'x', '--function', 'f', '--output', 'out', '--lines', '1:2'])

    def test_excerpt_inclusive_and_bounds(self):
        text = '/* provenance */\none\ntwo\nthree'
        self.assertEqual(tool.excerpt_lines(text, (2, 3)), 'one\ntwo\n')
        self.assertEqual(tool.excerpt_lines(text, (4, 4)), 'three')
        self.assertEqual(tool.excerpt_lines(text, (1, 4)), text)
        for bounds in ((0, 1), (2, 1), (1, 5)):
            with self.assertRaises(ValueError):
                tool.excerpt_lines(text, bounds)

    def test_lines_export_and_out_of_file_refusal(self):
        binary = self.path / 'fixture'
        header = bytearray(b'\x7fELF\x02\x01' + b'\x00' * 14)
        struct.pack_into('<HH', header, 16, 1, 183)
        binary.write_bytes(header)
        output = self.path / 'output'

        def fake_worker(command, timeout, log, env):
            request = json.loads(Path(command[-1]).read_text())
            tool.write_json(request['result'], {'ghidra_version': '12.1.4', 'c': 'one\ntwo'})
            return 0

        args = ['decompile', str(binary), '--function', 'f', '--output', str(output)]
        with mock.patch.object(tool, 'run_bounded', side_effect=fake_worker):
            self.assertEqual(tool.main(args + ['--lines', '2:3']), 0)
            full = (output / 'decompiled.c').read_text()
            excerpt = (output / 'excerpt.c').read_text()
            self.assertEqual(excerpt.split('\n', 1)[1], 'one\ntwo\n')
            provenance = json.loads(excerpt.split('\n', 1)[0].removeprefix('/* provenance: ').removesuffix(' */'))
            self.assertEqual(provenance['sha256'], tool.sha256(binary))
            self.assertEqual(provenance['lines'], [2, 3])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main(args + ['--lines', '2:4']), 1)
            self.assertEqual((output / 'decompiled.c').read_text(), full)
            self.assertFalse((output / 'excerpt.c').exists())
            self.assertEqual(json.loads((output / 'manifest.json').read_text())['status'], 'error')

    def test_timebox_reaps_worker(self):
        pidfile = self.path / 'pid'
        code = f'import os,time; open({str(pidfile)!r}, "w").write(str(os.getpid())); time.sleep(30)'
        with (self.path / 'log').open('w') as log:
            with self.assertRaises(subprocess.TimeoutExpired):
                tool.run_bounded([sys.executable, '-c', code], 0.5, log, os.environ.copy())
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)


@unittest.skipUnless(os.environ.get('GHIDRA_TOOLKIT_KNOWN_ANSWER') == '1',
                     'set GHIDRA_TOOLKIT_KNOWN_ANSWER=1 in PyGhidra venv')
class KnownAnswerTests(unittest.TestCase):
    module = ROOT / 'artifacts/kernel/gki_r59/target_vendor/msm_drm.ko'
    als = ROOT / 'artifacts/current_display_path/als/motorola.hardware.sensorext-service'

    @classmethod
    def setUpClass(cls):
        tool.CACHE.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=tool.CACHE, prefix='known-answer-')
        cls.addClassCleanup(temp.cleanup)
        cls.output = Path(temp.name)

    def run_tool(self, command, binary, name, *selector, timebox=120):
        output = self.output / name
        args = [sys.executable, str(HERE / 'ghidra_decompile.py'), command, str(binary),
                '--output', str(output), '--timebox', str(timebox), *selector]
        print('\n$ ' + shlex.join(args), flush=True)
        subprocess.run(args, check=True, timeout=timebox + 20)
        result = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['ghidra_version'], '12.1.4')
        self.assertEqual(result['sha256'], tool.sha256(binary))
        return result

    def test_a_module(self):
        data = self.run_tool('decompile', self.module, 'module_backlight',
                             '--function', 'dsi_display_set_backlight', '--lines', '10:16', timebox=480)
        self.assertEqual(data['instruction_count'], 153)
        self.assertEqual(data['function']['name'], 'dsi_display_set_backlight')
        self.assertIn('dsi_panel_set_backlight',
                      (self.output / 'module_backlight/decompiled.c').read_text())
        full = (self.output / 'module_backlight/decompiled.c').read_text()
        excerpt = (self.output / 'module_backlight/excerpt.c').read_text()
        header, fragment = excerpt.split('\n', 1)
        self.assertIn('provenance:', header)
        self.assertIn('"lines": [10, 16]', header)
        self.assertEqual(fragment, tool.excerpt_lines(full, (10, 16)))
        self.assertEqual(data['excerpt']['lines'], [10, 16])
        brief = self.run_tool('brief', self.module, 'module_brief',
                              '--function', 'dsi_display_set_backlight', timebox=480)
        self.assertEqual(brief['function'], data['function'])
        self.assertEqual(brief['instruction_count'], 153)
        self.assertEqual(brief['size_bytes'], 153 * 4)
        self.assertTrue(brief['callers'])
        self.assertIn('dsi_panel_set_backlight', [f['name'] for f in brief['callees']])
        self.assertTrue(brief['referenced_strings'])
        self.assertTrue(brief['constants'])
        self.assertGreater(brief['branch_count'], 0)
        self.assertNotIn('instructions', brief)
        self.assertFalse((self.output / 'module_brief/decompiled.c').exists())
        # Семантика LUT/clamp сверяется вручную с прежним evidence, не по имени callee.

    def test_b_als_and_debugdata(self):
        symbols = self.run_tool('symbols', self.als, 'als_symbols')
        command = ['readelf', '--wide', '--dyn-syms', str(self.als)]
        print('\n$ ' + shlex.join(command), flush=True)
        raw = subprocess.check_output(command, text=True, env=os.environ | {'LC_ALL': 'C'})
        (self.output / 'als_dynsym.txt').write_text(raw)
        match = re.search(r"Symbol table '\.dynsym' contains (\d+) entries", raw)
        self.assertIsNotNone(match)
        count = int(match.group(1))
        recovered_name = '_ZN15AlsCompensation9calculateEfj'
        self.assertNotIn(recovered_name, raw)
        self.assertTrue(any(s['name'] == recovered_name and s['source'] == 'IMPORTED'
                            for s in symbols['symbols']))
        tool.write_json(self.output / 'debugdata_comparison.json',
                        {key: symbols[key] for key in ('binary', 'sha256', 'ghidra_version')} |
                        {'dynsym_entries_including_null': count,
                         'recovered_imported_symbol_absent_from_dynsym': recovered_name,
                         'ghidra_import_symbol_count': symbols['symbol_count']})
        self.assertGreater(symbols['symbol_count'], count)
        self.assertTrue(any('AlsCompensation' in s['name'] and s['source'] == 'IMPORTED'
                            for s in symbols['symbols']))
        functions = self.run_tool('functions', self.als, 'als_functions', '--filter', 'AlsCompensation')
        self.assertTrue(any(f['name'] == recovered_name for f in functions['functions']))
        # functions → decompile: импортированное mangled имя переживает demangler.
        data = self.run_tool('decompile', self.als, 'als_threshold', '--function', recovered_name)
        self.assertTrue(any(i['address']['block'] == '.text' and i['address']['offset'] == '0xc8e4'
                            for i in data['instructions']))
        # Повтор того же малого fixture доказывает детерминированность JSON и C.
        repeat = self.run_tool('decompile', self.als, 'als_threshold_repeat', '--function', recovered_name)
        self.assertEqual(data, repeat)
        self.assertEqual((self.output / 'als_threshold/decompiled.c').read_bytes(),
                         (self.output / 'als_threshold_repeat/decompiled.c').read_bytes())
        refs = self.run_tool('xrefs', self.als, 'als_xrefs',
                             '--address', data['function']['entry']['ghidra'])
        self.assertTrue(refs['incoming'])
        brief = self.run_tool('brief', self.als, 'als_brief', '--function', recovered_name)
        repeat = self.run_tool('brief', self.als, 'als_brief_repeat',
                               '--address', data['function']['entry']['ghidra'])
        self.assertEqual(brief['function'], data['function'])
        self.assertEqual(brief | {'selector': repeat['selector']}, repeat)


if __name__ == '__main__':
    unittest.main(verbosity=2)
