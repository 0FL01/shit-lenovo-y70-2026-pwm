"""Offline bytes/plan helpers only. No transport, subprocess, SDK or file writes."""
from dataclasses import dataclass
import hashlib
import io
import re
import zipfile

PACKAGE = 'net.sourceforge.opencamera'
CHUNK = 1024 * 1024
MAX_APK = 64 * CHUNK
MAX_TOTAL = 128 * CHUNK
MAX_PATHS = 16
MAX_MANIFEST = 2 * CHUNK
MAX_DEX = 64 * CHUNK

class Rejected(ValueError): pass

def require(condition, reason):
    if not condition: raise Rejected(reason)

def paths(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 8192, 'path output size/type')
    try: lines = raw.decode('ascii').splitlines()
    except UnicodeError: raise Rejected('path encoding') from None
    require(0 < len(lines) <= MAX_PATHS, 'path count')
    result=[]
    for line in lines:
        require(line.startswith('package:'), 'unexpected package response')
        path=line[8:]
        # Deliberately narrow data/app dialect. A different PM path is a blocker,
        # not a reason to guess another path or relax scope automatically.
        require(re.fullmatch(r'/data/app/[A-Za-z0-9_~+=.-]+(?:/[A-Za-z0-9_~+=.-]+){1,3}\.apk',path) is not None,
                'unsupported exact PM path dialect')
        require(all(p not in ('.','..') for p in path.split('/')), 'noncanonical path')
        require(path not in result, 'duplicate path')
        result.append(path)
    return tuple(result)

@dataclass(frozen=True)
class FileObservation:
    path: str
    size: int
    sha256: str

def validate_files(observed_paths, files):
    require(type(observed_paths) is tuple and type(files) is tuple, 'immutable file evidence required')
    require(paths(('\n'.join('package:'+p for p in observed_paths)+'\n').encode())==observed_paths,'paths')
    require(len(files)==len(observed_paths), 'missing file metadata')
    for path,f in zip(observed_paths,files):
        require(type(f) is FileObservation and f.path==path,'file/path order binding')
        require(type(f.size) is int and 0<f.size<=MAX_APK,'file size limit')
        require(type(f.sha256) is str and re.fullmatch('[0-9a-f]{64}',f.sha256) is not None,'digest')
    require(sum(f.size for f in files)<=MAX_TOTAL,'aggregate byte limit')

def proposed_reads(observed_paths, files):
    """Returns inert command strings, never dispatches. Paths validated above."""
    validate_files(observed_paths,files)
    result=[]
    for f in files:
        for index in range((f.size+CHUNK-1)//CHUNK):
            result.append({'path':f.path,'index':index,'expected_bytes':min(CHUNK,f.size-index*CHUNK),
                'command':f"dd if='{f.path}' bs={CHUNK} skip={index} count=1",
                'stdout_cap':CHUNK,'stderr_cap':8192,'timeout_seconds':15})
    return {'physical_admission':False,'dispatch_implemented':False,'reads':result}

@dataclass(frozen=True)
class ChunkResult:
    path: str
    index: int
    rc: int
    stdout: bytes
    stderr: bytes
    complete: bool

def assemble(before, after, chunks, *, boot_before, boot_after, identity_before, identity_after):
    """Consumes supplied evidence only. No retry/continuation state or live reader."""
    require(type(before) is tuple and type(after) is tuple and type(chunks) is tuple,'immutable evidence')
    observed=tuple(f.path for f in before)
    validate_files(observed,before);validate_files(tuple(f.path for f in after),after)
    require(before==after,'package files changed')
    require(type(boot_before) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot_before) is not None,
            'boot missing')
    require(boot_before==boot_after,'boot changed')
    require(identity_before==identity_after==('Galaga','ROW','A001'),'camera identity mismatch')
    plan=proposed_reads(observed,before)['reads']
    require(len(chunks)==len(plan),'missing/extra chunks')
    collected={p:bytearray() for p in observed}
    for want,got in zip(plan,chunks):
        require(type(got) is ChunkResult and got.path==want['path'] and type(got.index) is int and got.index==want['index'],
                'chunk path/order mismatch')
        require(type(got.rc) is int and got.rc==0 and got.complete is True,'failed/denied/incomplete read: terminal')
        require(type(got.stdout) is bytes and len(got.stdout)==want['expected_bytes'],'chunk length')
        require(type(got.stderr) is bytes and len(got.stderr)<=8192,'stderr limit')
        collected[got.path].extend(got.stdout)
    result={}
    for f in before:
        data=bytes(collected[f.path]);require(hashlib.sha256(data).hexdigest()==f.sha256,'APK digest mismatch')
        result[f.path]=data
    return result

def inspect_apk(data):
    """Structural ZIP inventory only. Never APK/DEX execution or arbitrary extraction."""
    require(type(data) is bytes and 0<len(data)<=MAX_APK,'APK bound')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries=z.infolist();require(len(entries)<=4096,'ZIP entry count')
            names=[e.filename for e in entries];require(len(set(names))==len(names),'duplicate ZIP members')
            require('AndroidManifest.xml' in names,'manifest absent')
            selected=[e for e in entries if e.filename=='AndroidManifest.xml' or re.fullmatch(r'classes(?:[2-9]|[1-9][0-9]+)?\.dex',e.filename)]
            require(sum(e.file_size for e in selected)<=MAX_TOTAL,'uncompressed selected limit')
            inventory={}
            for e in selected:
                cap=MAX_MANIFEST if e.filename=='AndroidManifest.xml' else MAX_DEX
                require(0<e.file_size<=cap and not e.flag_bits&1,'encrypted/oversized selected member')
                with z.open(e) as stream: content=stream.read(cap+1)
                require(len(content)==e.file_size<=cap,'member size/CRC')
                inventory[e.filename]={'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    except (zipfile.BadZipFile,RuntimeError,NotImplementedError,EOFError) as e:
        raise Rejected('unreadable APK ZIP') from e
    return {'apk_sha256':hashlib.sha256(data).hexdigest(),'members':inventory,
        'merged_manifest_decoded':False,'code_semantics_verified':False,'source_equivalent':False,
        'physical_admission':False}
