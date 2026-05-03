import argparse
import json
from pathlib import Path


def color_for(percent):
    if percent >= 90:
        return '#16a34a'
    if percent >= 75:
        return '#65a30d'
    if percent >= 60:
        return '#d97706'
    return '#dc2626'


def main():
    parser = argparse.ArgumentParser(description='Generate a simple SVG coverage badge from coverage.py JSON output.')
    parser.add_argument('summary')
    parser.add_argument('output')
    parser.add_argument('label', nargs='?', default='coverage')
    args = parser.parse_args()

    data = json.loads(Path(args.summary).read_text(encoding='utf-8'))
    percent = float(data.get('totals', {}).get('percent_covered', 0))
    value = f'{percent:.1f}%'
    label_width = max(92, len(args.label) * 7 + 18)
    value_width = 58
    width = label_width + value_width

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{args.label}: {value}">
  <title>{args.label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".7"/>
    <stop offset=".1" stop-opacity=".1"/>
    <stop offset=".9" stop-opacity=".3"/>
    <stop offset="1" stop-opacity=".5"/>
  </linearGradient>
  <clipPath id="r"><rect width="{width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color_for(percent)}"/>
    <rect width="{width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{args.label}</text>
    <text x="{label_width / 2}" y="14">{args.label}</text>
    <text x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width / 2}" y="14">{value}</text>
  </g>
</svg>
'''

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding='utf-8')
    print(f'Wrote {output}')


if __name__ == '__main__':
    main()
