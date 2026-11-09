import unittest
from types import SimpleNamespace
from inert_source_loader import *

class FakeInputs:
    def __init__(self):
        self.files={p:b'value=1\n' for p in PATHS}
        self.files['06-tools/stock_c1_sweep.py']=b'import capture_ddic_c1\nvalue=capture_ddic_c1.value\n'
        self.algorithm='sha1';self.calls=[];self.reads=[];self.missing=False
        self.dirty=False;self.hash_dirty=False;self.raw_dirty=False;self.diff_error=False
        self.registry={};self.late_preload=False
    def git(self,*args):
        self.calls.append(args);cmd=args[0];rc=0
        ids={p:blob_id(raw,self.algorithm) for p,raw in self.files.items()}
        if cmd=='rev-parse':out=self.algorithm if args[1]=='--show-object-format' else 'a'*(64 if self.algorithm=='sha256' else 40)
        elif cmd=='ls-tree':
            out='\n'.join('100644 blob '+ids[p]+'\t'+p for p in PATHS if not(self.missing and p==SELF_PATH))
        elif cmd=='hash-object':out='\n'.join(('b'*40 if self.hash_dirty else ids[p]) for p in PATHS)
        elif cmd=='diff':out='';rc=128 if self.diff_error else int(self.dirty)
        else:raise RuntimeError('Unexpected Git operation')
        return SimpleNamespace(stdout=out,returncode=rc)
    def read(self,path):
        self.reads.append(path);relative=path.removeprefix('/fixture/')
        if self.late_preload:self.registry['stock_c1_sweep']=object()
        return b'changed=1\n' if self.raw_dirty else self.files[relative]
    def loader(self):
        return FixedSourceLoader(root='/fixture',git=self.git,read_bytes=self.read,
                                 registry=self.registry)

class LoaderTests(unittest.TestCase):
    def test_fixed_bytes_loaded_without_pyc(self):
        f=FakeInputs();r=f.loader().load()
        self.assertEqual(len(r['modules']),len(DAG))
        self.assertEqual(r['modules']['stock_c1_sweep'].value,1)
        self.assertFalse(r['live_admitted'])
        self.assertEqual(len(f.reads),len(PATHS))
        self.assertTrue(all(p.endswith('.py') for p in f.reads))
    def test_sha256_git_repository(self):
        f=FakeInputs();f.algorithm='sha256'
        self.assertEqual(len(f.loader().load()['source_commit']),64)
    def test_original_13_preserved_and_only_exact_additions(self):
        self.assertEqual(len(BASELINE),13);self.assertEqual(len(PATHS),22)
        self.assertTrue(set(BASELINE).issubset(PATHS))
    def test_untracked_rejected_before_reads(self):
        f=FakeInputs();f.missing=True
        with self.assertRaises(RuntimeError):f.loader().load()
        self.assertFalse(f.reads);self.assertFalse(f.registry)
    def test_worktree_dirty_rejected_before_exec(self):
        for name in ('dirty','hash_dirty','diff_error','raw_dirty'):
            f=FakeInputs();setattr(f,name,True)
            with self.subTest(name=name),self.assertRaises(RuntimeError):f.loader().load()
            self.assertFalse(f.registry)
    def test_preloaded_shadow_rejected_before_git(self):
        f=FakeInputs();f.registry['stock_c1_sweep']=object()
        with self.assertRaises(RuntimeError):f.loader().load()
        self.assertFalse(f.calls)
    def test_late_preloaded_rejected(self):
        f=FakeInputs();f.late_preload=True
        with self.assertRaises(RuntimeError):f.loader().load()
        self.assertEqual(set(f.registry),{'stock_c1_sweep'})
    def test_wrong_origin_rejected(self):
        f=FakeInputs();f.files[DAG[0][1]]=b'__file__="/wrong/origin.py"\n'
        with self.assertRaises(RuntimeError):f.loader().load()
    def test_wrong_registry_rejected(self):
        f=FakeInputs()
        class Registry(dict):
            def __setitem__(self,key,value):super().__setitem__(key,object())
        f.registry=Registry()
        with self.assertRaises(RuntimeError):f.loader().load()
    def test_dag_forward_import_rejected(self):
        f=FakeInputs();f.files[DAG[0][1]]=b'import run_p85_timed_stock_trial\n'
        with self.assertRaises(RuntimeError):f.loader().load()
    def test_unlisted_dependency_rejected(self):
        f=FakeInputs();f.files[DAG[0][1]]=b'import unlisted_project_helper\n'
        with self.assertRaises(RuntimeError):f.loader().load()
    def test_loader_one_attempt_after_failure(self):
        f=FakeInputs();f.dirty=True;loader=f.loader()
        with self.assertRaises(RuntimeError):loader.load()
        f.dirty=False
        with self.assertRaises(RuntimeError):loader.load()
    def test_bound_snapshot_not_later_read(self):
        f=FakeInputs();loader=f.loader();original=loader.prepare
        def prepare():
            result=original();f.files[DAG[0][1]]=b'value=999\n';return result
        loader.prepare=prepare
        self.assertEqual(loader.load()['modules'][DAG[0][0]].value,1)
    def test_default_construction_no_io(self):
        f=FakeInputs();f.loader()
        self.assertFalse(f.calls);self.assertFalse(f.reads);self.assertFalse(f.registry)
    def test_no_execute_main(self):
        f=FakeInputs();f.files[DAG[0][1]]=b'if __name__=="__main__": raise RuntimeError("main executed")\n'
        f.loader().load()

if __name__=='__main__':unittest.main()
