from django.core.files.images import get_image_dimensions
from rest_framework import serializers


IMAGE_UPLOAD_SPECS = {
    'category': {
        'label': 'Category image',
        'min_width': 800,
        'min_height': 800,
    },
    'brand': {
        'label': 'Brand logo',
        'min_width': 400,
        'min_height': 400,
    },
    'product': {
        'label': 'Product image',
        'min_width': 1000,
        'min_height': 1000,
    },
}


def validate_uploaded_image(file_obj, spec_key):
    if not file_obj:
        return

    spec = IMAGE_UPLOAD_SPECS[spec_key]
    label = spec['label']
    min_width = spec['min_width']
    min_height = spec['min_height']

    try:
        width, height = get_image_dimensions(file_obj)
    except Exception as exc:
        raise serializers.ValidationError(f'Upload a valid {label.lower()}.') from exc
    finally:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

    if not width or not height:
        raise serializers.ValidationError(f'Upload a valid {label.lower()}.')

    if width < min_width or height < min_height:
        raise serializers.ValidationError(
            f'{label} is too low resolution and may look blurry. '
            f'Please re-upload an image at least {min_width} x {min_height} pixels.'
        )
