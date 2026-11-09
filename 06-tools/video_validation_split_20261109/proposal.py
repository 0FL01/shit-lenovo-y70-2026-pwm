"""Inactive source transformation. No runtime imports or device I/O."""
import difflib
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PINS={'run_p85_guarded_trial.py':'b651f185c0691d72de050415ad76886439f700e0e8d0a34e404de012014662d0','run_p85_timed_stock_trial.py':'69d6a563ba313c2c2ba304f4d1abc77f2186326c4c27fd0f09ed85adc54eb4f1'}
def sources():
    old={n:(HERE.parent/n).read_text() for n in PINS}
    for n,text in old.items():
        if hashlib.sha256(text.encode()).hexdigest()!=PINS[n]:raise RuntimeError('Source binding changed')
    new=dict(old)
    n='run_p85_guarded_trial.py';t=new[n]
    t=t.replace('    def stop_camera(self):','    def stop_camera(self, *, defer_video_validation=False):',1)
    anchor="        result=subprocess.run(['ffprobe'"
    pos=t.index(anchor,t.index('    def stop_camera('))
    t=t[:pos]+'''        if defer_video_validation:
            self.report.update(video_private_label='capture.mp4',video_bytes=size,
                               video_transfer_verified=True,video_validation_status='pending_offline')
            self.save()
            return
'''+t[pos:]
    new[n]=t
    n='run_p85_timed_stock_trial.py';t=new[n]
    t=t.replace('            try:self.stop_camera()','            try:self.stop_camera(defer_video_validation=True)',1)
    anchor="        return self.report\n\n\ndef main():"
    replacement="""        self.report.update(video_acquisition_schema='p85-deferred-acquisition-v1',
                           video_acquisition_origin='timed_stock_caller',evidence_kind='acquisition')
        self.report['video_lifecycle_complete']=True
        self.report['status']='awaiting_offline_video_validation'
        self.save()
        return self.report


def main():"""
    if t.count(anchor)!=1:raise RuntimeError('Execute anchor changed')
    new[n]=t.replace(anchor,replacement)
    return old,new

def write_artifacts():
    old,new=sources()
    patch=''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/06-tools/'+n,tofile='b/06-tools/'+n)) for n in old)
    (HERE/'lifecycle.proposed.patch').write_text(patch)
    (HERE/'source_binding.json').write_text(json.dumps({'applied_to_runtime':False,'original_sha256':PINS,'proposed_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in new.items()},'patch_sha256':hashlib.sha256(patch.encode()).hexdigest()},indent=2)+'\n')
if __name__=='__main__':write_artifacts()
