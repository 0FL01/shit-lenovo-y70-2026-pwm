"""R36: emit the R35 fixed-reader with only the expected brightness allowlist changed.

Same on-device path/owner/locks and exact DSI reads, no new address or write. Do
not install simultaneously with another reader. No HBM or thermal-policy changes.
"""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct_camera_r35_20261120'))
from build_reader import build

text=build();old='1024|3600|3601|4096'
if text.count(old)!=3:raise ValueError('R35 CLI or guards changed')
print(text.replace(old,'512|6692|14078'),end='')
