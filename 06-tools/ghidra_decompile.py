#!/usr/bin/env python3
"""Офлайн ARM64 ELF/PE RE через PyGhidra 3.1 / Ghidra 12.1.4, без GUI.

Запуск: ~/tools/ghidra-12.1.4-pyvenv/bin/python 06-tools/ghidra_decompile.py
  decompile BINARY --function NAME --output DIR --timebox 600
functions/symbols: необязательный --filter; decompile/xrefs/brief: обязательный
--function либо --address (hex Ghidra address). functions/symbols показывают
результат импорта; decompile/xrefs/brief запускают auto-analysis.
brief пишет компактный manifest.json без листинга. decompile --lines A:B пишет
также excerpt.c: строки полного decompiled.c (1-based, включительно, с учётом
provenance в строке 1) с отдельным provenance-заголовком.
brief: callers = все xrefs на entry; callees = разрешённые call-ссылки;
strings = прямые ссылки на defined strings; constants = уникальные scalar
операнды кроме 0/1 (включая смещения/маски, без dataflow); branches = jump-инструкции.
Каждый запуск — новый внешний проект.
ET_REL: block+offset, не live kernel VA; ET_DYN/PE32+: import VA, не live VA.
Декомпилят — гипотеза для независимой проверки, не семантика DDIC.
"""

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile


CACHE = Path('/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107')
GHIDRA = Path.home() / 'tools/ghidra-12.1.4'
JAVA = Path('/home/stfu/.sdkman/candidates/java/current')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    indent=2) + '\n', encoding='utf-8')


def elf_type(path):
    with Path(path).open('rb') as stream:
        header = stream.read(20)
        if len(header) == 20 and header[:6] == b'\x7fELF\x02\x01':
            kind, machine = struct.unpack_from('<HH', header, 16)
            if machine != 183 or kind not in (1, 3):
                raise ValueError('Требуется ARM64 ET_REL или ET_DYN')
            return {1: 'ET_REL', 3: 'ET_DYN'}[kind]
        if header[:2] == b'MZ':
            stream.seek(0x3c)
            offset_bytes = stream.read(4)
            if len(offset_bytes) != 4:
                raise ValueError('Усечённый PE header')
            offset = struct.unpack('<I', offset_bytes)[0]
            if offset < 0x40 or offset + 26 > Path(path).stat().st_size:
                raise ValueError('Некорректный PE offset')
            stream.seek(offset)
            pe = stream.read(26)
            if pe[:4] != b'PE\x00\x00' or len(pe) != 26:
                raise ValueError('Некорректный PE header')
            machine, sections = struct.unpack_from('<HH', pe, 4)
            optional_size = struct.unpack_from('<H', pe, 20)[0]
            if machine != 0xaa64 or not sections or optional_size < 2 or pe[24:26] != b'\x0b\x02':
                raise ValueError('Требуется ARM64 PE32+')
            return 'PE32+'
    raise ValueError('Требуется ARM64 ELF64 little-endian или PE32+')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def external_location(value):
    path = Path(value).expanduser().resolve()
    if not path.is_relative_to(CACHE.resolve()):
        raise argparse.ArgumentTypeError(f'Проекты разрешены только внутри {CACHE}')
    return path


def seconds(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('timebox должен быть конечным и > 0')
    return number


def line_range(value):
    parts = value.split(':')
    if len(parts) != 2 or not all(p.isdecimal() for p in parts):
        raise argparse.ArgumentTypeError('lines: требуется A:B (целые номера строк)')
    first, last = map(int, parts)
    if first < 1 or last < first:
        raise argparse.ArgumentTypeError('lines: требуется 1 <= A <= B')
    return first, last


def excerpt_lines(text, bounds):
    lines = text.splitlines(keepends=True)
    first, last = bounds
    if not 1 <= first <= last <= len(lines):
        raise ValueError(f'lines: диапазон {first}:{last} вне файла ({len(lines)} строк)')
    return ''.join(lines[first - 1:last])


def parser():
    result = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = result.add_subparsers(dest='command', required=True)
    for name in ('functions', 'decompile', 'xrefs', 'symbols', 'brief'):
        command = commands.add_parser(name)
        command.add_argument('binary', type=Path)
        command.add_argument('--output', type=Path, required=True)
        command.add_argument('--project-location', type=external_location, default=CACHE)
        command.add_argument('--timebox', type=seconds, default=300,
                             help='секунды на JVM+import+analysis+export+закрытие')
        if name in ('decompile', 'xrefs', 'brief'):
            target = command.add_mutually_exclusive_group(required=True)
            target.add_argument('--function', help='точное имя, qualified или короткое')
            target.add_argument('--address', help='hex Ghidra import address')
        else:
            command.add_argument('--filter', default='', help='подстрока имени')
        if name == 'decompile':
            command.add_argument('--lines', type=line_range, metavar='A:B',
                                 help='excerpt.c: строки A..B полного decompiled.c, 1-based, включая provenance')
    return result


def run_bounded(command, timeout, log, env):
    """Отдельная process group ограничивает также JVM/native decompiler и cleanup."""
    with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                          env=env, cwd=CACHE, start_new_session=True) as process:
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # TERM позволяет JVM закрыться; KILL ограничивает зависший shutdown.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            # Лидер мог завершиться раньше своего native decompiler.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise


def worker(request_path):
    request = json.loads(Path(request_path).read_text(encoding='utf-8'))
    import pyghidra
    from pyghidra.launcher import HeadlessPyGhidraLauncher

    launcher = HeadlessPyGhidraLauncher(install_dir=GHIDRA)
    launcher.java_home = JAVA
    launcher.add_vmargs(f'-Djava.io.tmpdir={request["jvm_temp"]}',
                        '-Djava.awt.headless=true')
    launcher.start()
    from ghidra.framework import Application
    from ghidra.app.decompiler import DecompInterface
    from ghidra.util.task import TaskMonitor
    from java.lang import System

    # ProjectLocator 12.1.4 отвергает любой компонент с начальной точкой
    # (в том числе утверждённый .cache). FD-alias не переносит проект:
    # он указывает на тот же каталог в approved cache и живёт до close проекта.
    with contextlib.ExitStack() as cleanup:
        Path(request['project']).mkdir()
        project_fd = os.open(request['project'], os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, project_fd)
        project_alias = Path(f'/proc/self/fd/{project_fd}')
        external_location(str(project_alias))
        # Legacy open_program преобразует Path через resolve() и теряет alias.
        # Современный public API принимает явную строку без этой конверсии.
        project = cleanup.enter_context(pyghidra.open_project(
            str(project_alias), 'analysis', create=True))
        with pyghidra.program_loader().project(project).source(request['binary']).name('input').load() as loaded:
            loaded.save(pyghidra.task_monitor())
        program = cleanup.enter_context(pyghidra.program_context(project, '/input'))
        manager = program.getFunctionManager()
        # functions выдаёт импортированные (в т.ч. mangled) имена. Сохраняем
        # соответствующие entry до demangler, чтобы их можно было использовать.
        imported_entries = {str(f.getEntryPoint()) for f in manager.getFunctions(True)
                            if request.get('function') in (str(f.getName()), str(f.getName(True)))}
        if request['command'] in ('decompile', 'xrefs', 'brief'):
            # Public PyGhidra API; импорт сам разворачивает .gnu_debugdata.
            pyghidra.analyze(program)
        memory = program.getMemory()

        def address(addr):
            block = memory.getBlock(addr)
            return {'ghidra': str(addr),
                    'block': str(block.getName()) if block else None,
                    'offset': hex(int(addr.subtract(block.getStart()))) if block else None}

        def function_row(function):
            return {'name': str(function.getName(True)),
                    'entry': address(function.getEntryPoint())}

        def row_key(row):
            return (row['entry']['ghidra'], row['name'])

        command = request['command']
        data = {'ghidra_version': str(Application.getApplicationVersion()),
                'language': str(program.getLanguageID()),
                'image_base': str(program.getImageBase()),
                'jvm_temp': str(System.getProperty('java.io.tmpdir')),
                'analysis': command in ('decompile', 'xrefs', 'brief')}
        if command == 'functions':
            data['functions'] = sorted(
                [function_row(f) for f in manager.getFunctions(True)
                 if request['filter'] in str(f.getName(True))], key=row_key)
        elif command == 'symbols':
            symbols = list(program.getSymbolTable().getAllSymbols(True))
            data['symbol_count'] = len(symbols)
            data['symbols'] = sorted(
                [{'name': str(s.getName(True)), 'entry': address(s.getAddress()),
                  'type': str(s.getSymbolType()), 'source': str(s.getSource())}
                 for s in symbols if request['filter'] in str(s.getName(True))],
                key=lambda row: (*row_key(row), row['type'], row['source']))
        else:
            if request.get('address'):
                target = program.getAddressFactory().getAddress(request['address'].removeprefix('0x'))
                if target is None:
                    raise ValueError('Некорректный Ghidra address')
                function = manager.getFunctionContaining(target)
            else:
                matches = [f for f in manager.getFunctions(True)
                           if request['function'] in (str(f.getName()), str(f.getName(True)))
                           or str(f.getEntryPoint()) in imported_entries]
                if len(matches) != 1:
                    raise ValueError(f'Функция не найдена или неоднозначна: {len(matches)} matches')
                function = matches[0]
                target = function.getEntryPoint()
            if command == 'xrefs':
                refs = program.getReferenceManager()

                def ref_row(ref):
                    return {'from': address(ref.getFromAddress()),
                            'to': address(ref.getToAddress()), 'type': str(ref.getReferenceType())}

                def ref_key(row):
                    return (row['from']['ghidra'], row['to']['ghidra'], row['type'])

                data.update(target=address(target),
                            incoming=sorted([ref_row(r) for r in refs.getReferencesTo(target)], key=ref_key),
                            outgoing=sorted([ref_row(r) for r in refs.getReferencesFrom(target)], key=ref_key))
            else:
                if function is None:
                    raise ValueError('Адрес не принадлежит распознанной функции')
                data['function'] = function_row(function)
                listing = program.getListing()
                if command == 'brief':
                    from ghidra.program.model.data import StringDataInstance
                    from ghidra.program.model.scalar import Scalar

                    refs = program.getReferenceManager()
                    callers, callees, strings, constants = [], {}, {}, set()
                    for ref in refs.getReferencesTo(function.getEntryPoint()):
                        caller = manager.getFunctionContaining(ref.getFromAddress())
                        callers.append({'from': address(ref.getFromAddress()),
                                        'type': str(ref.getReferenceType()),
                                        'function': function_row(caller) if caller else None})
                    instruction_count = branch_count = 0
                    for instruction in listing.getInstructions(function.getBody(), True):
                        instruction_count += 1
                        branch_count += int(instruction.getFlowType().isJump())
                        for operand in range(instruction.getNumOperands()):
                            for obj in instruction.getOpObjects(operand):
                                if isinstance(obj, Scalar):
                                    bits = int(obj.bitLength())
                                    value = int(obj.getUnsignedValue()) & ((1 << bits) - 1)
                                    if value not in (0, 1):
                                        constants.add((value, bits, int(obj.getSignedValue())))
                        for ref in refs.getReferencesFrom(instruction.getAddress()):
                            dest = ref.getToAddress()
                            if ref.getReferenceType().isCall():
                                callee = manager.getFunctionAt(dest)
                                symbol = program.getSymbolTable().getPrimarySymbol(dest)
                                callees[str(dest)] = function_row(callee) if callee else {
                                    'name': str(symbol.getName(True)) if symbol else None,
                                    'entry': address(dest)}
                            datum = listing.getDefinedDataContaining(dest) if dest.isMemoryAddress() else None
                            if datum is not None and StringDataInstance.isString(datum):
                                value = StringDataInstance.getStringDataInstance(datum).getStringValue()
                                if value is not None:
                                    strings[str(dest)] = {'reference': address(dest),
                                                          'entry': address(datum.getAddress()),
                                                          'value': str(value)}
                    data.update(
                        size_bytes=int(function.getBody().getNumAddresses()),
                        instruction_count=instruction_count, branch_count=branch_count,
                        callers=sorted(callers, key=lambda row: (row['from']['ghidra'], row['type'])),
                        callees=sorted(callees.values(), key=lambda row: row['entry']['ghidra']),
                        referenced_strings=[strings[key] for key in sorted(strings)],
                        constants=[{'hex': hex(value), 'bits': bits, 'signed': signed}
                                   for value, bits, signed in sorted(constants)])
                else:
                    data['instructions'] = [
                        {'address': address(i.getAddress()), 'text': str(i)}
                        for i in listing.getInstructions(function.getBody(), True)]
                    data['instruction_count'] = len(data['instructions'])
                    decompiler = DecompInterface()
                    try:
                        if not decompiler.openProgram(program):
                            raise RuntimeError('Не удалось открыть decompiler')
                        result = decompiler.decompileFunction(function, int(request['timebox']), TaskMonitor.DUMMY)
                        if not result.decompileCompleted():
                            raise RuntimeError(str(result.getErrorMessage()))
                        data['c'] = str(result.getDecompiledFunction().getC())
                    finally:
                        decompiler.dispose()
        # Случайный путь JVM temp не входит в детерминированный manifest.
        if Path(data.pop('jvm_temp')).resolve() != Path(request['jvm_temp']).resolve():
            raise RuntimeError('JVM temp вне выделенного внешнего каталога')
        write_json(request['result'], data)


def main(argv=None):
    args = parser().parse_args(argv)
    binary = args.binary.expanduser().resolve()
    try:
        kind = elf_type(binary)
        provenance = {'binary': str(binary), 'sha256': sha256(binary),
                      ('pe_type' if kind == 'PE32+' else 'elf_type'): kind,
                      'ghidra_version': '12.1.4', 'command': args.command,
                      'selector': getattr(args, 'function', None) or getattr(args, 'address', None),
                      'filter': getattr(args, 'filter', ''),
                      'address_model': 'import address + memory block offset; NOT live VA'}
        args.project_location.mkdir(parents=True, exist_ok=True)
        args.output.mkdir(parents=True, exist_ok=True)
        # При повторном использовании output ошибка не должна оставлять старый C.
        for filename in ('decompiled.c', 'excerpt.c'):
            (args.output / filename).unlink(missing_ok=True)
        # Request/result/project/JVM temp принадлежат parent: cleanup и при SIGKILL worker.
        with tempfile.TemporaryDirectory(prefix='run-', dir=args.project_location) as temp:
            run = Path(temp)
            jvm_temp = run / 'jvm'
            jvm_temp.mkdir()
            request = vars(args) | {'binary': str(binary), 'project': str(run / 'project'),
                                    'jvm_temp': str(jvm_temp), 'result': str(run / 'result.json')}
            request.pop('output')
            request.pop('project_location')
            write_json(run / 'request.json', request)
            env = os.environ | {'TMPDIR': str(jvm_temp), 'TEMP': str(jvm_temp),
                                'TMP': str(jvm_temp), 'PYTHONDONTWRITEBYTECODE': '1'}
            with (args.output / 'analysis.log').open('w', encoding='utf-8') as log:
                try:
                    code = run_bounded([sys.executable, str(Path(__file__).resolve()),
                                        '--worker', str(run / 'request.json')], args.timebox, log, env)
                except subprocess.TimeoutExpired:
                    write_json(args.output / 'manifest.json',
                               provenance | {'status': 'timeout', 'timebox_seconds': args.timebox})
                    print('Timebox исчерпан; см. manifest.json и analysis.log', file=sys.stderr)
                    return 124
            if code != 0:
                write_json(args.output / 'manifest.json', provenance | {'status': 'error'})
                print('Ошибка PyGhidra; см. analysis.log', file=sys.stderr)
                return 1
            data = json.loads((run / 'result.json').read_text(encoding='utf-8'))
            if data['ghidra_version'] != provenance['ghidra_version']:
                raise ValueError('Версия Ghidra отличается от утверждённой 12.1.4')
            c = data.pop('c', None)
            if c is not None:
                header = json.dumps(provenance, ensure_ascii=False, sort_keys=True)
                # JSON path не может преждевременно закрыть C-comment.
                (args.output / 'decompiled.c').write_text(
                    '/* provenance: ' + header.replace('*/', '* /') + ' */\n' + c + '\n', encoding='utf-8')
                if args.lines is not None:
                    full = (args.output / 'decompiled.c').read_text(encoding='utf-8')
                    try:
                        fragment = excerpt_lines(full, args.lines)
                    except ValueError as error:
                        write_json(args.output / 'manifest.json',
                                   provenance | data | {'status': 'error', 'error': str(error)})
                        raise
                    data['excerpt'] = {'file': 'excerpt.c', 'source_file': 'decompiled.c',
                                       'lines': list(args.lines)}
                    excerpt_header = json.dumps(provenance | data['excerpt'], ensure_ascii=False, sort_keys=True)
                    (args.output / 'excerpt.c').write_text(
                        '/* provenance: ' + excerpt_header.replace('*/', '* /') + ' */\n' + fragment,
                        encoding='utf-8')
            write_json(args.output / 'manifest.json', provenance | data | {'status': 'ok'})
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        sys.exit(main())
