# R42: что подтверждает длинный ответ на `23:C1` и `23:85`

**45 отдельных кадров прошли офлайн-проверку DCS long/WC=3: 28 для C1 и 17 для P85.** На той же странице `23`, при DBV 3600 и 120 Гц, в 13 архивных этапах прочитаны оба адреса: P85 дал `15 00 00`, затем C1 — `00 00 60`, 13/13 раз. Оба отличаются от `23 00 00` и друг от друга. Это положительный контроль ответа, зависящего от запроса, при неизменном селекторе. Контрпример — R40 `02:FE`: **тот же заголовок и те же счётчики**, но данные `02 00 00` совместимы с эхом селектора. Формат пакета сам по себе не отличает эхо от данных.

`confirmed-on-target` здесь означает повторный разбор записей XT2611-1 (`BOE cmd_v4`, модуль `msm_drm` из [квитанции C1](../c1_live_20261108/stock120_qualified.json)). Дата положительных наблюдений — 8 ноября, R40 — 21 ноября 2026 г. Счётная единица — отдельная исходная трасса RX с уникальным nonce, а не файл JSON, прогон камеры или успешное завершение всего опыта.

### Откуда взялись числа

Слева — подкаталоги `~/.cache/legion-y70-…`; в `p85-{batched,timed-stock}` считалась только секция `CHILD` соответствующего `stdout`. Справа — файлы из `artifacts/`. `P0…P5`, `baseline`, `sham15`, `return15` — метки архивных наблюдений.

| Семейство исходных файлов | C1 | P85 | Квитанция / охват |
|---|---:|---:|---|
| `c1/<nonce>/capture.txt` | 5 | — | [c1_live](../c1_live_20261108/): `stock{120,90,144}_qualified.json`, `stock120_{return,highdbv}_qualified.json`; шестой файл, nonce `14aaef2774b5`, без RX, исключён |
| `stock-c1/stock_c1_20261108_01/*-P*-capture.stdout` | 6 | — | [P0_828.json … P5_828.json](../stock_c1_20261108_01/); повторы в `run.json` не прибавлены |
| `trials/a9_c1_a001_20261108_{02,06}/*-c1-capture.txt` | 1 + 3 | — | В [02](../a9_c1_a001_20261108_02/run.json) есть `baseline-c1-capture.txt`, но нет публичной квитанции `c1_capture`: **только кадр**, не успешный этап. В [06](../a9_c1_a001_20261108_06/run.json) — `baseline`, `a9_only`, `return_a9_only` |
| `p85/05f192fe7990/capture.txt` | — | 1 | DBV 828. [Отказ short1](../p85_live_20261108/stock828_qualified.json) и [разбор long3](../p85_live_20261108/stock828_long3_reanalysis.json) относятся к **одной** записи |
| `p85-trial/p85_stock_a001_20261108_{01,04}/*-{p85,c1}.stdout` | 1 + 3 | 1 + 3 | [01](../p85_stock_a001_20261108_01/run.json): только baseline, весь прогон завершился ошибкой; [04](../p85_stock_a001_20261108_04/run.json): все три этапа. В 02 и 03 нет этапов с этими кадрами |
| `p85-batched/p85_batch_stock_a001_20261108_01/*-envelope-*-{p85,c1}.stdout` | 3 | 3 | [run.json](../p85_batch_stock_a001_20261108_01/run.json), все три этапа |
| `p85-timed-stock/p85_timed_stock_a001_20261108_{01,02,03}/*-envelope-*-{p85,c1}.stdout` | 6 | 9 | [01](../p85_timed_stock_a001_20261108_01/run.json), [02](../p85_timed_stock_a001_20261108_02/run.json), [03](../p85_timed_stock_a001_20261108_03/run.json): на `sham15` нет C1; отсутствие чтения не равно нулевому ответу |
| **Итого по двум адресам** | **28** | **17** | **44** кадра сверены с отдельной или вложенной JSON-квитанцией; **1** дополнительный C1 установлен непосредственно по raw. Ещё **1** попытка C1 не дала кадра |

**Пересчитанные данные.** C1: `00 00 60` ×19, `00 00 10` ×2, `00 00 50` ×1, `00 00 80` ×1, `00 02 b3` ×2, `00 02 c0` ×1, `00 02 26` ×1, `00 01 30` ×1. На stock при 120 Гц последовательность DBV `828 → 460 → 2048 → 3000 → 3600 → 828` даёт `0002b3 → 0002c0 → 000226 → 000130 → 000060 → 0002b3`. В серии A9 при том же DBV 3600 и 120 Гц: `000060 → 000010 → 000060`. Это проверяемый возврат значения, не декодирование поля C1. P85: `15 00 00` **17/17** (1 при DBV 828, 16 при 3600); при 3600 это 6 baseline, 5 sham15, 5 return15. Совпадение со штатным `15` не различает содержимое ячейки, константу или возврат ранее установленного значения. Два конечных нуля находятся *внутри WC*, но их смысл неизвестен.

### Две разные проверки

1. **Кадр.** Во всех 45 raw: один FIFO helper и один заголовок на том же PID, что и возврат из RX. Порядок событий и места вызова согласованы; `requested=MRPS=3`, `allocation=read_bytes=16`, `disp_op=0`. Заголовок little-endian `1c 03 00 16`: DCS long, WC=3, пересчитанный ECC `16`. Аппаратный `hw_status >> 16` и нормализованный count оба 9 (=4+3+2); фактический RX `rc=3`, напечатано 3 байта. Контроллер `[0,3,0,0]`, page TX `[0,0,0]`; на каждую пробу число попаданий равно числу событий, пропусков нет. В короткой исторической обвязке 9 записей, с тремя дополнительными входами page TX — 12. Для 21/21 файлов batched/timed в kernel-интервале **конкретного** опыта отдельно найдены записи селектора `23 → 00 → 00`; это журнал записей селектора, не анализатор пакетов на шине. У попытки `14aaef2774b5` только 2/2 события, 0 header и 0 hardware, нет C1 и есть `RECOVERY_REQUIRED`: возвращённого нулевого значения нет.
2. **Содержимое.** Разные воспроизводимые ответы на два не-FE запроса при одном селекторе исключают простое правило «вернуть ID текущей страницы с двумя нулями» для этих контролей. В R40 [квитанция](../ddic_r40_page02_20261121/receipt.json) и приватный `fe.step/raw` согласуются: один `02:FE`, те же `1c 03 00 16`, ECC и 9/9, возврат `[0,3,0]`, TX `[0,0]` (другая обвязка), три байта `02 00 00`. Известный контроль до/после дал `FE/80/82/BA=23/50/00/00`, DBV `0400` в обеих точках. На `02` **0 не-FE ответов**, повторов FE тоже нет. Статус R40 остаётся `not_dcs_short1`, `value=null`; совпадение с селектором допускает эхо, но не доказывает механизм эха.

**Граница применения.** На этих записях откалиброван только случай MRPS3, long/WC3 и исходного/нормализованного счёта 9/9. Одни `rc=3` и три байта stdout недостаточны: [драйвер копирует запрошенную длину](../../06-tools/C1_CAPTURE.md), и при меньшем WC в вывод может попасть CRC. Для будущего анализа сначала проверяется транспорт целиком, затем — воспроизводимость **всех трёх** байтов не-FE ответа при одном состоянии после разных известных предшествующих значений и отличие от селектора/предшественника; нужна сверка с известной страницей до и после и проверка возможного зеркала. Совпадение только формы `xx 00 00` не критерий отказа (P85 — контрпример), а один корректный заголовок или один `FE` не критерий независимого банка (R40 — контрпример). Архивные 13 пар не являются экспериментом со случайной перестановкой предшественников. `unknown`: CRC полезной нагрузки не захвачен, native ширина/автоинкремент/записываемость и независимость страницы `02` не установлены; этот опыт не измеряет свет, PWM или режим эмиссии. Нового допуска на DSI из него не следует.

### Проверка по исходным файлам

Из корня указанного worktree, локальным `python3 -B` без `-O`. Код ниже читает только перечисленные захваты и квитанции, выводит счётчики и останавливается при несовпадении. Заголовки, длины и содержимое не берутся из сводных отчётов.

```sh
awk '/^```python$/{p=1;next} p&&/^```$/{exit} p' artifacts/direct_camera_r42_20261121/framing.md | python3 -B
```

```python
import json, re, sys
from collections import Counter
from pathlib import Path
sys.path[:0] = ['06-tools', 'artifacts/ddic_r40_page02_20261121']
import capture_ddic_c1 as c1
import framing as r40

A, H = Path('artifacts'), Path.home()/'.cache'
def load(p): return json.loads(p.read_bytes())
hist, seen, pairs, wire = Counter(), set(), {}, 0
matched = missing = 0
patterns = {'c1': '*/capture.txt', 'p85': '*/capture.txt',
    'stock-c1': 'stock_c1_20261108_01/*-P*-capture.stdout',
    'trials': 'a9_c1_a001_20261108_*/*-c1-capture.txt'}
for k in ('p85-trial', 'p85-batched', 'p85-timed-stock'):
    patterns[k] = 'p85_*_20261108_*/*-*.stdout'
for k, pattern in patterns.items():
    for p in sorted((H/('legion-y70-'+k)).glob(pattern)):
        run, name = p.parent.name, p.name
        stage = re.search(r'(baseline|sham15|return15)-(c1|p85)\.stdout$', name)
        if k in ('p85-trial','p85-batched','p85-timed-stock') and not stage: continue
        if '-envelope-' in name:
            # Read only CHILD; scan the exact marker interval for selector packets.
            marker = 'PWM_P85_'+run+'_'+'_'.join(stage.groups()).upper()
            raw, child, active, bounds, packets = '', False, False, [], []
            with p.open() as f:
                for line in f:
                    if re.match(r'^@P85E:\w+:END CHILD$', line): child = False
                    if child: raw += line
                    if re.match(r'^@P85E:\w+:SECTION CHILD 0 \d+ 0$', line): child = True
                    if line.rstrip().endswith(marker+'_BEGIN'): active=True; bounds.append('B')
                    if line.rstrip().endswith(marker+'_END'): active=False; bounds.append('E')
                    if active and 'dsi_ctrl_cmd_transfer len=' in line:
                        packets.append(line.split(' cmds= ')[-1].strip())
            assert bounds == ['B','E'] and packets == ['FF 5A A5 '+x for x in ('23','00','00')]
            wire += 1
        else: raw = p.read_text()
        if k=='c1' and run=='14aaef2774b5':
            assert 'RECOVERY_REQUIRED' in raw and not re.search(r'^C1 |\b(?:hardware|header)_\w+:', raw, re.M)
            assert 'entries-in-buffer/entries-written: 2/2' in raw
            missing += 1; continue
        label, = re.findall(r'^(C1|P85|P85_LONG3) ', raw, re.M)
        op = 'C1' if label=='C1' else '85'
        nonce, = re.findall(r'\bheader_([0-9a-f]{12}):', raw)
        assert nonce not in seen; seen.add(nonce)
        (dbv,hz), = re.findall(r'^STATE (\d+) ([\d.]+)$', raw, re.M)
        d = c1.validate_capture(re.sub('^'+label+' ', 'C1 ', raw, flags=re.M), nonce, int(dbv), round(float(hz)))
        trace = raw.split('TRACE_BEGIN\n')[1].split('TRACE_END')[0].splitlines()
        profile = raw.split('PROFILE_BEGIN\n')[1].split('PROFILE_END')[0].splitlines()
        _, specs = c1.probe_specs(nonce)
        entry = any('entry_'+nonce+':' in s for s in trace)
        if entry: specs['entry_'+nonce] = ('p', 'entry pending=%x:u32 length=%x:u32 flags=%x:u32')
        rows = r40.parse_trace(trace, specs); counts = Counter(r[0] for r in rows)
        assert r40.parse_profile(profile, specs) == {key:dict(hits=v,misses=0) for key,v in counts.items()}
        expected = (['entry'] if entry else []) + ['ctrl','tx']
        assert [r[0] for r in rows] == expected + ['hardware','header','ctrl'] + expected*2
        assert all(r[2]=='dsi_display_cmd_transfer+0x0/0x34c [msm_drm]' and
                   r[3]==dict(pending=0,length=11,flags=0) for r in rows if r[0]=='entry')
        core = [r for r in rows if r[0]!='entry']
        assert tuple(r[2] for r in core) == r40.SITES + (r40.WRITE,r40.TX)
        assert all(core[i][1]==core[j][1] for i,j in ((0,1),(2,3),(3,4),(5,6),(7,8)))
        assert d['raw_hardware_count']==9
        payload = bytes(d['data']).hex(); hist[op,payload] += 1
        if k=='c1': j, = [x for f in (A/'c1_live_20261108').glob('*qualified.json') if (x:=load(f))['nonce']==nonce]
        elif k=='p85': j=load(A/'p85_live_20261108/stock828_long3_reanalysis.json'); assert j['source_nonce']==nonce
        elif k=='stock-c1': j=load(A/run/(name.split('-')[1]+'.json')); assert j['nonce']==nonce
        elif k=='trials':
            if run.endswith('_02'):
                assert name=='baseline-c1-capture.txt' and 'c1_capture' not in load(A/run/'run.json')['stages'][0]
                continue
            j, = [s['c1_capture'] for s in load(A/run/'run.json')['stages'] if s['label']==name.split('-c1-')[0]]
        else:
            key, addr = stage.groups(); assert op=={'c1':'C1','p85':'85'}[addr]
            j, = [s[addr] for s in load(A/run/'run.json')['stages'] if s['label']==key]
            pairs.setdefault((run,key),[]).append((int(name[:4]),op,payload))
        assert (j['page'],j['opcode'])==('23',op)
        assert all(j[x]==d[x] for x in ('requested','data','header_hex','raw_hardware_count','normalized_count',
                   'scratch_allocation','native_dbv','software_refresh','single_receive','framing_qualified'))
        matched += 1
both = [[(op,v) for _,op,v in sorted(xs)] for xs in pairs.values() if len(xs)==2]
assert len(both)==13 and all(x==[('85','150000'),('C1','000060')] for x in both)
print(dict(sorted(hist.items())), 'JSON',matched,'без RX',missing,'пары',len(both),'селектор',wire)
assert (len(seen),matched,missing,wire)==(45,44,1,21)

R = Path('../../private-bench-evidence/ddic-r40-page02-20261121')
b = (R/'fe.step/raw').read_bytes(); n=(R/'nonce').read_text().strip()
f = r40.validate(b,n); assert f==load(A/'ddic_r40_page02_20261121/receipt.json')['framing']
assert (f['reason'],f['transport_verified'],f['value'])==('not_dcs_short1',True,None)
h = bytes.fromhex(f['header_hex']); assert h[:3]==bytes.fromhex('1c0300') and h[3]==c1.ecc(int.from_bytes(h[:3],'little'))
assert (f['raw_hardware_count'],f['normalized_count'],f['returned'])==(9,9,3)
assert r40.sections(b.decode(),n)[0]==bytes.fromhex('020000')
for side in ('initial','final'):
    assert 'CTRL FE=23 80=50 82=00 BA=00 DBV=0400' in (R/(side+'.step/raw')).read_text().splitlines()
print('02:FE',f['header_hex'], '02 00 00', f['reason'])
```
