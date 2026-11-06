"""Import labelled scraped brand logos without replacing existing assets."""
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.models import Brand


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def validated_image(data):
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Image exceeds 4 MB')
    if b'<svg' in data[:1500]:
        if b'<!ENTITY' in data.upper() or b'<!DOCTYPE' in data.upper():
            raise ValueError('SVG entities are not supported')
        root = ET.fromstring(data)
        if root.tag.split('}')[-1] != 'svg':
            raise ValueError('Invalid SVG')
        forbidden = {'script', 'foreignObject', 'iframe', 'object', 'embed', 'image', 'a', 'animate', 'animateTransform', 'set'}
        for node in root.iter():
            if node.tag.split('}')[-1] in forbidden:
                raise ValueError('SVG contains active or external content')
            for key, value in node.attrib.items():
                if key.lower().startswith('on') or (key.split('}')[-1] == 'href' and not value.startswith('#')):
                    raise ValueError('SVG contains external references')
                if re.search(r'url\(\s*[\'"]?(?!#)', value, re.I):
                    raise ValueError('SVG contains external resources')
            if node.tag.split('}')[-1] == 'style' and re.search(r'@import|https?:|url\(', node.text or '', re.I):
                raise ValueError('SVG stylesheet uses resources')
        return ET.tostring(root), 'svg'
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 16000000:
            raise ValueError('Image too large')
        image.load()
        image.thumbnail((600, 600))
        image = image.convert('RGBA')
        visible = [pixel for pixel in image.getdata() if pixel[3] > 100]
        # Official reversed logos need a dark backing on the white cards.
        if visible and sum(min(pixel[:3]) > 225 for pixel in visible) / len(visible) > .65:
            background = Image.new('RGBA', image.size, '#17384b')
            background.alpha_composite(image)
            image = background
        output = io.BytesIO(); image.save(output, format='PNG')
        return output.getvalue(), 'png'


class Command(BaseCommand):
    help = 'Validate and import exact-name scraped logos; dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--report-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        directory = Path(options['report_dir']); directory.mkdir(parents=True, exist_ok=True)
        brands = list(Brand.objects.all())
        (directory/'logos-before.json').write_text(json.dumps([{'id':b.pk,'name':b.name,'logo':b.logo.name} for b in brands],indent=2))
        index = {}
        for brand in brands:
            index.setdefault(normalized(brand.name), []).append(brand)
        results = []; seen = set()
        with transaction.atomic():
            for row in json.loads(Path(options['manifest']).read_text()):
                record = {key:value for key,value in row.items() if key != 'path'}
                matches = index.get(normalized(row['brand']), [])
                if len(matches) != 1:
                    record['result'] = 'no unique matching brand'; results.append(record); continue
                brand = matches[0]
                if brand.logo or brand.pk in seen:
                    record['result'] = 'existing logo preserved'; results.append(record); continue
                try:
                    data, extension = validated_image(Path(row['path']).read_bytes())
                    record.update(brand_id=brand.pk,sha256=hashlib.sha256(data).hexdigest())
                    if options['apply']:
                        brand.logo.save(f'researched-{brand.pk}-{record["sha256"][:12]}.{extension}', ContentFile(data), save=True)
                    record['result'] = 'imported' if options['apply'] else 'ready'
                    seen.add(brand.pk)
                except Exception as error:
                    record['result'] = 'rejected'; record['reason'] = str(error)
                results.append(record)
            if options['apply']: invalidate_admin_catalog()
        (directory/'logos.json').write_text(json.dumps(results,indent=2))
        from collections import Counter
        self.stdout.write(json.dumps(dict(Counter(row['result'] for row in results))))
