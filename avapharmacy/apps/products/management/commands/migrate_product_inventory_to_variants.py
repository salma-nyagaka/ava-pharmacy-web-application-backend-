from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Product, Variant


class Command(BaseCommand):
    help = 'Create default variants for legacy products and copy product images onto their representative variants.'

    def _default_variant_name(self, product):
        strength = (product.strength or '').strip()
        return strength or 'Standard'

    @transaction.atomic
    def handle(self, *args, **options):
        created_variants = 0
        copied_images = 0
        touched_products = 0

        products = Product.objects.prefetch_related('variants').order_by('id')
        for product in products:
            variants = list(product.variants.all())
            if variants:
                variant = product.get_representative_variant() or variants[0]
            else:
                variant = Variant.objects.create(
                    product=product,
                    sku=product.sku,
                    barcode=product.barcode,
                    pos_product_id=product.pos_product_id,
                    name=self._default_variant_name(product),
                    strength=product.strength,
                    dosage_instructions='',
                    directions=product.directions,
                    warnings=product.warnings,
                    price=product.price,
                    cost_price=product.cost_price,
                    image=product.image,
                    is_active=product.is_active,
                )
                created_variants += 1
                touched_products += 1

            if product.image and not variant.image:
                variant.image = product.image
                variant.save(update_fields=['image', 'updated_at'])
                copied_images += 1

            variant._clear_inventory_cache()
            variant.save()

        self.stdout.write(self.style.SUCCESS(
            f'Created variants: {created_variants}, copied images: {copied_images}, touched products: {touched_products}'
        ))
