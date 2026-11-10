import hashlib
import sys
import unittest
import numpy as np
import analyze as a

class FiniteDiagnosticTests(unittest.TestCase):
    def test_primary_matches_pinned_all_nine(self):
        p=a.PRIVATE/'pinned_tools/optical_spectrum.py'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'414497032b763f815d1ec48eb0d00af48a0526a1f0e31012384ddd537886db7b')
        sys.path.insert(0,str(p.parent))
        from optical_spectrum import analyze_profiles
        with np.load(a.PRIVATE/'final_profiles.npz',allow_pickle=False) as src:
            for roi in a.ROIS:
                for values in src['profiles_'+roi]:
                    ref=analyze_profiles(values,frequencies=[a.Q])
                    self.assertAlmostEqual(a.metric(values),ref['total_rms_amplitude'][0]/(values.mean()-16),places=13)
    def test_phase_rotating_not_cancelled(self):
        y=np.arange(330);phase=np.linspace(0,2*np.pi,60,endpoint=False)
        p=100+5*np.cos(2*np.pi*a.Q*y[None,:]+phase[:,None])
        c=a.coeff(p)
        self.assertLess(abs(c.mean()),1e-12)
        self.assertGreater(np.sqrt(np.mean(abs(c)**2)),4.99)
        self.assertLess(np.ptp(abs(c))/5,.001)
    def test_joint_exact_polynomial_plus_sine(self):
        y=np.arange(330);x=np.linspace(-1,1,330)
        p=np.array([100+2*x+x*x+4*np.cos(2*np.pi*a.Q*y+.7)])
        amp,phase,res,_=a.joint(p)
        np.testing.assert_allclose(amp,4,atol=1e-12)
        np.testing.assert_allclose(phase,.7,atol=1e-12)
        self.assertLess(abs(res).max(),1e-10)
    def test_envelope_recovers_known_shape(self):
        y=np.arange(330);x=np.linspace(-1,1,330)
        p=np.array([100+x+(4+2*x+x*x)*np.cos(2*np.pi*a.Q*y)+(1-x)*np.sin(2*np.pi*a.Q*y)])
        fit,res,_=a.envelope_model(p)
        np.testing.assert_allclose(fit,p,atol=1e-10)
        self.assertLess(res,1e-10)
    def test_peak_grid_is_spatial_not_hertz(self):
        y=np.arange(330);p=np.array([100+5*np.cos(2*np.pi*a.Q*y)])
        q,amp,edge=a.peak(p)
        self.assertLessEqual(abs(q[0]-a.Q),1/8192)
        self.assertEqual(edge,0)
        self.assertGreater(amp[0],4.99)
    def test_nonmutating(self):
        p=np.random.default_rng(314).normal(100,3,(4,330));orig=p.copy()
        a.metric(p);a.joint(p, broad=True);a.envelope_model(p);a.peak(p);a.broad_leakage(p)
        np.testing.assert_array_equal(p,orig)
    def test_subranges_inside_reviewed_pixels(self):
        for start,stop in a.SUBRANGES.values(): self.assertTrue(0<=start<stop<=330)
    def test_constant_correlations_undefined(self):
        self.assertIsNone(a.corr(np.ones(60),np.arange(60)))
    def test_primary_failure_is_preserved(self):
        with np.load(a.PRIVATE/'final_profiles.npz',allow_pickle=False) as src: p=src['profiles_right']
        self.assertGreater((a.metric(p[1])/a.metric(p[0])-1)*100,5)
    def test_broad_model_is_not_an_exact_fit_to_real_profiles(self):
        with np.load(a.PRIVATE/'final_profiles.npz',allow_pickle=False) as src: p=src['profiles_main'][1]
        _,_,res,_=a.joint(p,broad=True)
        self.assertGreater(np.sqrt(np.mean(res**2)),6)

if __name__=='__main__': unittest.main()
