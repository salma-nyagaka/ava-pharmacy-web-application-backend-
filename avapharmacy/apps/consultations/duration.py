"""Normalize prescription duration without converting calendar months to days."""
import re

UNITS = {'days': ('7', 'day'), 'weeks': ('52', 'week'), 'months': ('12', 'month')}


def normalize_duration(item):
    value, unit = item.get('duration_value'), item.get('duration_unit')
    text = str(item.get('duration') or '').strip()
    if value is None and unit is None:
        match = re.fullmatch(r'([1-9]\d*)/(7|52|12)', text)
        if match:
            value = match[1]
            unit = {'7': 'days', '52': 'weeks', '12': 'months'}[match[2]]
        else:
            match = re.fullmatch(r'([1-9]\d*)\s+(day|week|month)s?(?:\s*\(\d+/(?:7|52|12)\))?', text, re.I)
            if match:
                value, unit = match[1], match[2].lower() + 's'
            else:
                if re.fullmatch(r'[-\d.]+/\d+', text):
                    raise ValueError('Use a positive whole number with /7 for days, /52 for weeks, or /12 for months.')
                return {'duration': text}
    if unit not in UNITS or isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 999:
        raise ValueError('Duration must be a whole number from 1 to 999 with days, weeks, or months.')
    value = int(value)
    denominator, singular = UNITS[unit]
    notation = f'{value}/{denominator}'
    return {'duration_value': value, 'duration_unit': unit, 'duration_notation': notation,
            'duration': f'{value} {singular}{"s" if value != 1 else ""} ({notation})'}
