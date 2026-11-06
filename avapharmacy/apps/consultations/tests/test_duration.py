from django.test import SimpleTestCase
from apps.consultations.duration import normalize_duration
from apps.consultations.serializers import validate_clinician_prescription_items


class PrescriptionDurationTests(SimpleTestCase):
    def test_notation_and_readable_values(self):
        for notation, value, unit, label in [('3/7', 3, 'days', '3 days (3/7)'), ('5/7', 5, 'days', '5 days (5/7)'), ('1/52', 1, 'weeks', '1 week (1/52)'), ('2/52', 2, 'weeks', '2 weeks (2/52)'), ('1/12', 1, 'months', '1 month (1/12)')]:
            result = normalize_duration({'duration': notation})
            self.assertEqual(result['duration'], label)
            self.assertEqual((result['duration_value'], result['duration_unit']), (value, unit))
            self.assertEqual(normalize_duration({'duration': label}), result)

    def test_structured_duration_and_frequency_remain_separate(self):
        item = {'drug_name': 'Medication', 'catalog_fallback': True, 'duration_value': 5, 'duration_unit': 'days', 'frequency': 'BD'}
        result = validate_clinician_prescription_items([item])[0]
        self.assertEqual(result['frequency'], 'BD')
        self.assertEqual(result['duration'], '5 days (5/7)')

    def test_invalid_structured_values_are_rejected(self):
        for value, unit in [(0, 'days'), (-1, 'weeks'), (1.5, 'months'), (True, 'days'), (1, 'years'), (1000, 'days')]:
            with self.assertRaises(ValueError):
                normalize_duration({'duration_value': value, 'duration_unit': unit})

    def test_legacy_free_text_is_preserved(self):
        self.assertEqual(normalize_duration({'duration': 'until reviewed'}), {'duration': 'until reviewed'})

    def test_invalid_notation_is_rejected(self):
        for text in ['0/7', '-1/7', '1.5/52', '1/30']:
            with self.assertRaises(ValueError):
                normalize_duration({'duration': text})
