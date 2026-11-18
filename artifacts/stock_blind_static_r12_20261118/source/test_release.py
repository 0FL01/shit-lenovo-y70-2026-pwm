import tempfile,unittest
from pathlib import Path
import state_qa as s
from operator_core import Reject
GOOD='mActualBacklight=0.40987244\n mCurrentScreenBrightness=0.40987244\n mHbmMode=off\nResult: Bundle[{value=0}]\nmCurrentFocus=ZRamSettingsActivity\n'
class Tests(unittest.TestCase):
 def run_release(self,text):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   if text is not None:(p/'release_target_extra.txt').write_text(text)
   return s.release(p)
 def test_present(self):self.assertTrue(self.run_release(GOOD)['verified'])
 def test_absent(self):self.assertFalse(self.run_release(None)['verified'])
 def test_wrong_float(self):
  with self.assertRaises(Reject):self.run_release(GOOD.replace('0.40987244','0.4',1))
 def test_hbm(self):
  with self.assertRaises(Reject):self.run_release(GOOD.replace('mHbmMode=off','mHbmMode=on'))
 def test_dc(self):
  with self.assertRaises(Reject):self.run_release(GOOD.replace('value=0','value=1'))
if __name__=='__main__':unittest.main()
