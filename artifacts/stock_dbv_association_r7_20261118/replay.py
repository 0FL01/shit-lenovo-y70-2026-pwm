"""Offline association-only replay. No device I/O or imports from private capture."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

import importlib.util
ARTIFACTS=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

badge=module('round7_badge',ARTIFACTS/'stock_dbv_2632_badge_sham_20261118/replay.py')
render=badge.render

def plateau(base,root,tag,expected,n):
    raw=(root/(tag+'_display.txt')).read_text()
    required=('ZRamSettingsActivity','vsyncRate=120.00 Hz','min_refresh_rate=120.0',
              'peak_refresh_rate=120.0','screen_brightness_float=null','screen_brightness_mode=0',
              'mIsRbcActive=false','mIsHdrLayerPresent=false')
    base.need(all(t in raw for t in required),'raw display controls drift')
    patterns={'policy':r'policy=(\w+)','user':r'mCurrentScreenBrightness=([\d.]+)',
              'out':r'mActualBacklight=([\d.]+)','android':r'screen_brightness=(\d+)',
              'DBV':r'\n(\d+)\n0\n','reason':r'mBrightnessReason=([^\n]+)'}
    state={}
    for key,pattern in patterns.items():
        match=re.search(pattern,raw);base.need(match is not None,'missing raw '+key);state[key]=match[1]
    base.need(state==expected,'raw/parsed plateau mismatch');base.target_state(state,n)
    base.need(re.search(r'\bvalue=0\b',(root/(tag+'_provider.txt')).read_text()) is not None,'provider DC mismatch')

def device_readback_timing(base,root,log):
    # UTC is printed at integer-second precision by Android; host stamps
    # surround multiple operations. These are loose phase attribution bounds,
    # not evidence of sub-second clock synchronisation or panel sample times.
    when=lambda k:base.one(log,k)[0]
    checks=[('commission_entry',when('commission_entry'),
             datetime.fromisoformat(base.one(log,'R00_qc')[1]['utc_meta_start'])),
            ('commission_end',when('R02_qc'),when('commission_done'))]
    for i in range(15):
        phase='P%02d'%i
        checks.append((phase+'_early',when(phase+'_command'),when(phase+'_pre')))
        if i<14:checks.append((phase+'_end',when(phase+'_s2_manifest'),when(phase+'_late')))
    previous=None;offsets=[]
    for tag,before,after in checks:
        lines=(root/(tag+'_display.txt')).read_text().splitlines()
        m=re.fullmatch(r'device_utc=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)',lines[0])
        u=re.fullmatch(r'(\d+\.\d{2}) (\d+\.\d{2})',lines[1]) if len(lines)>1 else None
        base.need(m and u,'missing readback device UTC/uptime '+tag)
        utc=datetime.fromisoformat(m[1]).timestamp();up=float(u[1])
        base.need(before.timestamp()-3 <= utc <= after.timestamp()+3,
                  'readback outside host phase window '+tag)
        if previous is not None:
            base.need(utc>previous[0] and up>previous[1],'nonadvancing readback device clocks '+tag)
        previous=(utc,up);offsets.append(utc-up)
    base.need(max(offsets)-min(offsets)<=1.1,'readback UTC/uptime disagreement')
    return dict(commissioning_dumps=2,phase_dumps=len(checks)-2,
                host_window_tolerance_seconds=3,device_clocks_strictly_advancing=True,
                utc_minus_uptime_span_seconds=round(max(offsets)-min(offsets),3))

def replay(root,template,scope_package,allow_partial=False):
    base,_,future,gate=badge.dependencies(scope_package)
    expected=dict(badge.SOURCE_HASHES)
    expected['corner_geometry.py']='f931a8cc847340ef708849625e6253c68df7584904a5c5f915d8b7ebe6b0e54a'
    registry={}
    for line in (root/'sources.sha256').read_text().splitlines():
        digest,name=line.split();base.need(name not in registry,'duplicate source');registry[name]=digest
    base.need(registry==expected,'source registry mismatch')
    for name,digest in expected.items():
        public=(scope_package/name) if name!='corner_geometry.py' else ARTIFACTS/'stock_dbv_2632_20261118/analysis_geometry.py'
        base.need(hashlib.sha256(public.read_bytes()).hexdigest()==digest,'public code drift')
        base.need(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,'private code drift')
    corner=module('round7_corner',ARTIFACTS/'stock_dbv_2632_20261118/analysis_geometry.py')
    ref=future.reference(template)
    log=base.events(root)
    base.need(allow_partial,'incomplete 17-by-3 association series')
    base.need(not (root/'manifest_complete.json').exists() and 'all_phases' not in log,'false completion of observed abort')
    readback_timing=device_readback_timing(base,root,log)
    expected_pngs=['P%02d_s%d'%(i,j) for i in range(14) for j in range(3)]+['P14_s0']
    base.need(sorted(p.stem for p in root.glob('P??_s?.png'))==expected_pngs,'missing/extra captured rasters')
    manifest=None
    restored=base.restoration(root,log,True,'target_full_before')
    last=base.stamp(base.read(root,'oc_first')['res']);fixed=None;seen=set()
    def camera(tag):
        nonlocal last,fixed
        m=base.metadata(root,tag+'_read');sig=base.manual(m);fixed=fixed or sig
        base.need(sig==fixed,'camera controls drift')
        now=base.stamp(m['res']);base.advance(last,now);last=now;return list(now)
    def pixels_unique(tag):
        im=base.pixels(root,tag,(1080,2392));digest=hashlib.sha256(im.tobytes()).hexdigest()
        base.need(digest not in seen,'duplicate raster');seen.add(digest);return im
    def qc(tag,row,enforce=True):
        pair=[camera(tag+'_pre'),camera(tag+'_post')]
        base.need(pair==row['camera'],'QC camera span mismatch')
        im=pixels_unique(tag);g=future.checks(ref,im);m0=gate.checks(ref,im);m=dict(m0,pass_modes=m0['pass_similarity'])
        c=corner.score(im);z=badge.shadows(im);supported=True;displaced=[]
        for a,b,n in [('top-right/a','top-right/b',963),('right-upper/a','right-upper/b',554)]:
            x,y=c['anchors'][a],c['anchors'][b]
            def shape(v):return v['height']>=10 and v['grad']>=5 and 1<=v['width']<=6
            ok=shape(x) and shape(y) and abs(x['pos']-y['pos'])<=1
            if ok and (min(x['pos'],y['pos'])>n+2 or max(x['pos'],y['pos'])<n-2):displaced.append(a+'/'+b)
            supported &= ok and max(abs(x['pos']-n),abs(y['pos']-n))<=2
        base.need((g,m,c,z,bool(supported),displaced)==(row['fixture'],row['legend'],row['blue'],row['shadows'],row['corner_supported'],row['clear_displacement']),'computed QC differs')
        if enforce:base.need(g['geometry']['pass_exterior'] and g['pass_original_upper_headroom'] and m['pass_modes'] and not displaced,'accepted image fails frozen gate')
        return dict(frames=pair,fixture=g,legends=m,shadows=z,blue=c,corner_supported=bool(supported))
    for i in range(3):
        tag='new_qual'+str(i);camera(tag);g=future.checks(ref,pixels_unique(tag))
        base.need(g==base.read(root,tag+'_fixture'),'health fixture mismatch')
        base.need(g['geometry']['pass_exterior'] and g['pass_original_upper_headroom'],'failed health')
    base.need(base.one(log,'starting_bright_badge_health')[1] is True,'missing health qualification')
    ce,cmd=base.one(log,'commission_entry');base.need(cmd[1:]==[base.ARGS[2632],2632],'commission command mismatch')
    original=base.scene(root,'original_app')
    base.need(base.scene(root,'commission_start_target')==original,'commission scene mismatch')
    cstate=base.one(log,'commission_done')[1]
    plateau(base,root,'commission_entry',cstate,2632);plateau(base,root,'commission_end',cstate,2632)
    references=[];prior=ce
    for i in range(3):
        tag='R%02d'%i;et,row=base.one(log,tag+'_qc')
        base.need(row==base.read(root,tag+'_qc'),'reference QC log mismatch')
        t0=datetime.fromisoformat(row['utc_meta_start']);t1=datetime.fromisoformat(row['raster_start']);t2=datetime.fromisoformat(row['raster_end']);t3=datetime.fromisoformat(row['post_utc'])
        base.need(prior<t0<t1<t2<t3<=et and (t0-ce).total_seconds()>=12,'reference timing')
        references.append(qc(tag,row));prior=et
    commission_end,_=base.one(log,'commission_done');base.need(commission_end>prior,'commission chronology')
    phases=['P%02d'%i for i in range(14)]
    expected_qc=['R%02d_qc'%i for i in range(3)]+[p+'_s'+str(j)+'_qc' for p in phases for j in range(3)]+['P14_s0_qc']
    base.need([k for k in log if re.fullmatch(r'(R\d\d|P\d\d_s\d)_qc',k)]==expected_qc,'wrong QC roster')
    base.need(sorted(p.stem for p in root.glob('R??.png'))==['R00','R01','R02'],'wrong commissioning raster roster')
    base.need([k for k in log if re.fullmatch(r'P\d\d_command',k)]==[p+'_command' for p in phases]+['P14_command'],'wrong phase plan')
    base.need([k for k in log if re.fullmatch(r'P\d\d_s\d_manifest',k)]==[p+'_s'+str(j)+'_manifest' for p in phases for j in range(3)],'wrong sample plan')
    rows=[];phase_rows=[];previous=commission_end;png_times=[];first_command=None
    for i,(phase,n) in enumerate(zip(phases,base.STEPS)):
        ct,cmd=base.one(log,phase+'_command');pt,pre=base.one(log,phase+'_pre')
        base.need(cmd[1:]==[base.ARGS[n],n],'phase command mismatch')
        base.need(abs((datetime.fromisoformat(cmd[0])-ct).total_seconds())<.1,'command timestamp mismatch')
        base.need(previous is None or ct>previous,'phase overlap')
        first_command=first_command or ct
        base.need((ct-first_command).total_seconds()>=i*33-.1,'phase before scheduled slot')
        base.need(ct<pt and pre[0]==pre[1]==n,'early native/readback mismatch')
        plateau(base,root,phase+'_early',pre[2],n)
        base.need(base.scene(root,phase+'_target')==pre[3]==original,'scene content mismatch')
        end=pt
        for j in range(3):
            tag=phase+'_s'+str(j);et,row=base.one(log,tag+'_manifest')
            if manifest is not None:base.need(row==manifest[i*3+j],'manifest/log mismatch')
            base.need((row['phase'],row['sample'],row['n'],row['tag'])==(i,j,n,tag),'sample label mismatch')
            t0=datetime.fromisoformat(row['utc_meta_start']);t1=datetime.fromisoformat(row['raster_start']);t2=datetime.fromisoformat(row['raster_end'])
            base.need(end<t0<t1<t2<et,'sample chronology')
            base.need((t0-ct).total_seconds()>=(7,15,23)[j]-.1,'sample before planned delay')
            _,captured=base.one(log,tag+'_qc')
            base.need(captured==base.read(root,tag+'_qc'),'saved capture mismatch')
            base.need(all(row[k]==v for k,v in captured.items()),'manifest capture mismatch')
            qt,_=base.one(log,tag+'_qc')
            t3=datetime.fromisoformat(captured['post_utc'])
            base.need(t2<t3<=qt<=et,'post/QC/manifest timing')
            base.need(abs((et-ct).total_seconds()-row['elapsed_end'])<.15,'elapsed clock mismatch')
            measures=qc(tag,captured)
            rows.append(dict(phase=i,sample=j,dbv=n,**measures,command_to_png_seconds=(t1-ct).total_seconds()))
            png_times.append(t1);end=et
        lt,late=base.one(log,phase+'_late');base.need(lt>end and late[1]==n,'late readback mismatch')
        plateau(base,root,phase+'_end',late[0],n)
        base.need(base.scene(root,phase+'_end_target')==late[2]==original,'late scene mismatch');previous=lt
        phase_rows.append(dict(phase=i,dbv=n,float_command=base.ARGS[n],seconds=(lt-ct).total_seconds()))
    ct,cmd=base.one(log,'P14_command');pt,pre=base.one(log,'P14_pre')
    base.need(previous<ct<pt and cmd[1:]==[base.ARGS[2632],2632] and pre[0]==pre[1]==2632,'failed phase chronology/command')
    base.need((ct-first_command).total_seconds()>=14*33-.1,'failed phase early')
    plateau(base,root,'P14_early',pre[2],2632)
    base.need(base.scene(root,'P14_target')==pre[3]==original,'failed phase scene')
    et,failed=base.one(log,'P14_s0_qc');base.need(failed==base.read(root,'P14_s0_qc'),'failed capture mismatch')
    t0=datetime.fromisoformat(failed['utc_meta_start']);t1=datetime.fromisoformat(failed['raster_start']);t2=datetime.fromisoformat(failed['raster_end']);t3=datetime.fromisoformat(failed['post_utc'])
    base.need(pt<t0<t1<t2<t3<=et and (t0-ct).total_seconds()>=6.9,'failed sample timing')
    failure=qc('P14_s0',failed,False)
    base.need(failure['fixture']['geometry']['pass_exterior'] and failure['fixture']['pass_original_upper_headroom'] and not failed['clear_displacement'],'unexpected failed gate')
    bad=[k for k,v in failure['legends']['glyphs'].items() if not v['ok']]
    base.need(bad==['AUTO','X1'] and not failure['legends']['pass_modes'] and all(v['ok'] for v in failure['legends']['arrows'].values()),'failure not reproduced')
    base.need(all(failure['legends']['glyphs'][k]['ncc']<.80 for k in bad),'wrong legend reason')
    base.need(not any(k in log for k in ('P14_s0_manifest','P14_late','P15_command','P16_command')),'invented later evidence')
    base.need(not (root/'P14_end_display.txt').exists(),'invented late readback')
    base.advance(last,base.stamp(base.metadata(root,'oc_return_a_read')['res']))
    base.need(base.one(log,'target_restored')[0]>et,'restore before failure')
    gaps=[(b-a).total_seconds() for a,b in zip(png_times,png_times[1:])]
    return dict(status='partial_qualitative_association_aborted',phases=14,issued_phases=15,sample_count=42,full_plan_complete=False,failed_sample=failure,
                plan=base.STEPS,phase_summaries=phase_rows,references=references,samples=rows,restoration=restored,
                corner_supported_count=sum(r['corner_supported'] for r in rows),
                timing=dict(readback_clocks=readback_timing,png_span_seconds=(png_times[-1]-png_times[0]).total_seconds(),
                            png_gap_min_seconds=min(gaps),png_gap_max_seconds=max(gaps)),
                limits=['Plan stopped at P14_s0 legend veto. The 43rd raster is rejected; no P14 late readback or P15/P16 exists.',
                        'No certified whole-plot registration; passing badges/legends can miss projective corner motion.',
                        'Only photographed-raster association; not physical PWM, frequency, amplitude or pixel-registered A/B.',
                        '500 us preview, auto WB/ISP, channel floor, unsynchronised capture and unknown optical channel remain.',
                        'Each plateau display dump embeds Android UTC (whole seconds) and /proc/uptime. These are checked for chronology and consistency with host phase windows, not continuous panel telemetry or optical synchronisation.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('template',type=Path)
    p.add_argument('--allow-partial',action='store_true');p.add_argument('--scope-package',type=Path,default=ARTIFACTS/'scope_exterior_registration_20261118');a=p.parse_args()
    print(render(replay(a.root,a.template,a.scope_package,a.allow_partial)))
