from django.core.files.images import get_image_dimensions
from rest_framework import serializers


IMAGE_UPLOAD_LABELS = {
    'category': 'Category image',
    'brand': 'Brand logo',
    'product': 'Product image',
    'promotion': 'Offer image',
}


def validate_uploaded_image(file_obj, spec_key):
    """Ensure the uploaded file is a readable image without rejecting low-resolution assets."""
    if not file_obj:
        return

    label = IMAGE_UPLOAD_LABELS.get(spec_key, 'image')

    try:
        width, height = get_image_dimensions(file_obj)
    except Exception as exc:
        raise serializers.ValidationError(f'Upload a valid {label.lower()}.') from exc
    finally:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

    if not width or not height:
        raise serializers.ValidationError(f'Upload a valid {label.lower()}.')
