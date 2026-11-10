"""Read-only replay of the original 03f0ed4 acquisition contract failure.

No media, device APIs, evidence repair, qualification or candidate admission.
The diagnostic collector deliberately continues after failed predicates only
to enumerate downstream violations. Its result is NEVER a validation pass.
"""
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import aa_acquisition_validation as acquisition
import p85_batched_envelope as envelope
from test_aa_saved_esd_failure import bounded_regular_read

SOURCE = Path('/home/opencode/.cache/legion-y70-aa-full-stock-03f0ed4-proposal01/run.json')
SHA = 'a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a'
FAILURE = 'Missing same-trial semantic/structural redraw calibration'
SUPPLEMENT = Path('/home/opencode/.cache/legion-y70-aa-calibration-boot-03f0ed4-01')


class SavedCalibrationFailure(unittest.TestCase):
    def test_separate_raw_boot_corroboration_does_not_repair_original(self):
        if not SOURCE.exists() or not SUPPLEMENT.exists():
            self.skipTest('External original/supplement not available')
        raw = bounded_regular_read(SOURCE, 200000)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SHA)
        report = json.loads(raw)
        linkage = json.loads(bounded_regular_read(SUPPLEMENT / 'event_linkage.json', 20000))
        self.assertEqual(linkage['source_commit'], report['source_commit'])
        self.assertEqual(linkage['acquisition_sha256'], SHA)
        names = ['0019-before-boot.stdout', '0183-envelope-return_stock-write.stdout']
        self.assertEqual([event['name'] for event in linkage['events']], names)
        captures = []
        records = report['events'] + report['envelope_timings']
        for event in linkage['events']:
            data = bounded_regular_read(SUPPLEMENT / event['name'], 1000000)
            self.assertEqual(len(data), event['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), event['sha256'])
            bound = [r for r in records if r.get('raw_record') == event['name'][:-7]]
            self.assertEqual(bound, event['acquisition_records'])
            self.assertEqual(len(bound), 1)
            self.assertEqual(bound[0]['return_code'], 0)
            captures.append(data)
        match = re.match(rb'@P85E:([a-f0-9]{12}):START\n', captures[1])
        self.assertIsNotNone(match)
        labels = ('TRACE_OWNER', 'BEGIN', 'TRACE_BEFORE', 'PRE_GUARD', 'TRACE_GUARD',
                  'CHILD', 'TRACE_AFTER', 'END', 'KERNEL', 'FIELDS', 'DISPLAY', 'BOOT', 'OWNER')
        # Parse saved framing only. These inert commands are never executed;
        # this diagnostic is not a runtime plan or acquisition admission path.
        plan = envelope.Envelope(match[1].decode(), tuple(
            envelope.Part(label, ':', root=label == 'CHILD', limit=1000000)
            for label in labels), 45, child_command=':')
        sections = envelope.parse(captures[1], plan)
        boot = captures[0].decode('ascii').strip()
        self.assertEqual(sections['BOOT'].strip(), boot)
        self.assertEqual(report['redraw_ui_calibration']['boot_id'], boot)
        self.assertNotIn('boot_id', report['before'])
        with self.assertRaisesRegex(ValueError, '^' + FAILURE + '$'):
            acquisition.validate_acquisition(report)
        self.assertEqual(bounded_regular_read(SOURCE, 200000), raw)

    def test_original_stays_rejected_and_all_downstream_predicates_are_audited(self):
        if not SOURCE.exists():
            self.skipTest('External original acquisition not available')
        raw = bounded_regular_read(SOURCE, 200000)
        self.assertEqual(len(raw), 176932)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SHA)
        report = json.loads(raw)
        original = json.dumps(report, sort_keys=True)
        self.assertEqual(report['source_commit'], '03f0ed4774052e843e22e03ff85e2997e9293828')
        self.assertNotIn('boot_id', report['before'])
        self.assertTrue(report['redraw_ui_calibration']['boot_id'])
        with self.assertRaisesRegex(ValueError, '^' + FAILURE + '$'):
            acquisition.validate_acquisition(report)
        violations = []

        def collect_only(ok, message):
            if not ok:
                violations.append(message)

        with patch.object(acquisition, 'require', collect_only):
            # Intentionally discard the return: this is not accepted evidence.
            acquisition.validate_acquisition(report)
        self.assertEqual(violations, [FAILURE])
        with self.assertRaisesRegex(ValueError, '^' + FAILURE + '$'):
            acquisition.validate_acquisition(report)
        self.assertEqual(json.dumps(report, sort_keys=True), original)
        self.assertEqual(bounded_regular_read(SOURCE, 200000), raw)


if __name__ == '__main__':
    unittest.main()
