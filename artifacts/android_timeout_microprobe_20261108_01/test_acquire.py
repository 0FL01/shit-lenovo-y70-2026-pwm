"""Offline shell-v2 framing/deadline regressions. No transport or device access."""
import struct
import unittest
from unittest.mock import patch
import acquire

class Clock:
    value = 0.0
    def now(self):
        return self.value

class Socket:
    def __init__(self, clock, pieces):
        self.clock, self.pieces, self.reads = clock, list(pieces), []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def settimeout(self, value):
        if value <= 0:
            raise RuntimeError('Nonpositive timeout')
    def recv(self, count):
        self.reads.append(count)
        if not self.pieces:
            return b''
        data, stamp = self.pieces.pop(0)
        self.clock.value = stamp
        if len(data) > count:
            self.pieces.insert(0, (data[count:],stamp))
            data = data[:count]
        return data

class G:
    def __init__(self, sock):
        self.sock = sock
    def selected(self, transport, service, timeout):
        if transport != 1 or service != 'shell,v2,raw:fixed' or timeout != 8:
            raise RuntimeError('Unexpected synthetic invocation')
        return self.sock

def frame(channel, data, stamp):
    return [(struct.pack('<BI',channel,len(data)),stamp),(data,stamp)]

class Tests(unittest.TestCase):
    def run_case(self, pieces, expect_error=False, cap=4096):
        clock = Clock(); sock = Socket(clock,pieces); partial = []
        with patch.object(acquire.time,'monotonic',clock.now):
            if expect_error:
                with self.assertRaises(RuntimeError):
                    acquire.bounded_shell(G(sock),1,'fixed',cap=cap,partial=lambda a,b:partial.append((a,b)))
                result = None
            else:
                result = acquire.bounded_shell(G(sock),1,'fixed',cap=cap,partial=lambda a,b:partial.append((a,b)))
        return result,sock,partial

    def test_complete(self):
        result,_,partial = self.run_case(frame(1,b'ab',1)+frame(2,b'e',2)+frame(3,b'\x00',3))
        self.assertEqual(result,(0,b'ab',b'e'))
        self.assertEqual(partial,[(b'ab',b'e')])

    def test_late_header(self):
        _,sock,_ = self.run_case(frame(3,b'\x00',9),True)
        self.assertEqual(sock.reads,[5])

    def test_late_exit(self):
        self.run_case([(struct.pack('<BI',3,1),7),(b'\x00',9)],True)

    def test_fragmented_header_deadline(self):
        header=struct.pack('<BI',3,1)
        self.run_case([(header[:1],1),(header[1:3],7),(header[3:],9),(b'\x00',9)],True)

    def test_late_payload_partial_audit(self):
        _,_,partial=self.run_case(frame(1,b'ok',1)+[(struct.pack('<BI',1,2),7),(b'x',7.5),(b'y',9)],True)
        self.assertEqual(partial,[(b'ok',b'')])

    def test_aggregate_cap_precedes_payload(self):
        _,sock,partial=self.run_case(frame(1,b'ab',1)+[(struct.pack('<BI',2,2),2),(b'cd',2)],True,cap=3)
        self.assertEqual(sock.reads,[5,2,5])
        self.assertEqual(partial,[(b'ab',b'')])

    def test_frame_boundaries(self):
        for pieces in ([(struct.pack('<BI',3,2),1)],[(struct.pack('<BI',4,0),1)],[(b'\x01',1)]):
            with self.subTest(pieces=pieces):
                self.run_case(pieces,True)

    def test_exact_deadline_reject(self):
        self.run_case(frame(3,b'\x00',8),True)

if __name__ == '__main__':
    unittest.main()
