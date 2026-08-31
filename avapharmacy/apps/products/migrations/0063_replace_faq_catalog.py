from django.db import migrations, models


FAQS = (
    (
        'Ordering & Prescriptions',
        'Do I need a prescription to buy medicines online?',
        'Yes. Prescription medicines require a valid prescription uploaded during checkout. Over-the-counter (OTC) products can be purchased without one.',
    ),
    (
        'Ordering & Prescriptions',
        'How do I place an order?',
        'Browse products, add items to your cart, and proceed to checkout. For prescription medicines, upload your prescription for pharmacist approval.',
    ),
    (
        'Ordering & Prescriptions',
        'Can I track my order?',
        'Absolutely. Once your order is confirmed, you’ll receive a tracking link via SMS/WhatsApp and email.',
    ),
    (
        'Delivery & Collection',
        'Where do you deliver?',
        'We deliver across Nairobi and selected counties in Kenya. Delivery timelines vary by location.',
    ),
    (
        'Delivery & Collection',
        'Do you offer same-day delivery?',
        'Yes, for orders placed before 2 PM within Nairobi. Outside Nairobi, delivery takes 1–3 working days.',
    ),
    (
        'Delivery & Collection',
        'Can I collect my order in person?',
        'Yes. You can choose “Pick-Up” at checkout and collect from our pharmacy shopfront.',
    ),
    (
        'Payments & Pricing',
        'What payment methods do you accept?',
        'We accept M-Pesa, debit/credit cards, and bank transfers. Cash payments are available for in-store pick-up.',
    ),
    (
        'Payments & Pricing',
        'Are prices the same online and in-store?',
        'Yes, though online promotions may occasionally differ.',
    ),
    (
        'Quality & Safety',
        'Are your medicines genuine?',
        'Yes. All products are sourced from licensed suppliers and comply with Pharmacy and Poisons Board (PPB) regulations.',
    ),
    (
        'Quality & Safety',
        'Do you provide pharmacist consultation?',
        'Yes. Our licensed pharmacists are available via phone, WhatsApp, or in-store for guidance.',
    ),
    (
        'Support',
        'How can I contact you?',
        'You can reach us via WhatsApp, email, or call us on the following lines:\n\n'
        'The Hub Karen branch, Nairobi: 0715737330, 0733737330\n'
        'GTC Westlands branch, Nairobi: 0713444999, 0101444999\n'
        'The Promenade Mall branch, Mombasa: 0723888835, 0717122022',
    ),
)


def replace_faq_catalog(apps, schema_editor):
    FAQ = apps.get_model('products', 'FAQ')
    FAQ.objects.all().delete()
    FAQ.objects.bulk_create(
        [
            FAQ(
                category=category,
                question=question,
                answer=answer,
                is_published=True,
                sort_order=position * 10,
            )
            for position, (category, question, answer) in enumerate(FAQS, start=1)
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0062_alter_faq_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='faq',
            options={'ordering': ['sort_order', 'pk']},
        ),
        migrations.RemoveIndex(
            model_name='faq',
            name='products_fa_is_publ_f47208_idx',
        ),
        migrations.AlterField(
            model_name='faq',
            name='category',
            field=models.CharField(
                choices=[
                    ('Ordering & Prescriptions', 'Ordering & Prescriptions'),
                    ('Delivery & Collection', 'Delivery & Collection'),
                    ('Payments & Pricing', 'Payments & Pricing'),
                    ('Quality & Safety', 'Quality & Safety'),
                    ('Support', 'Support'),
                ],
                db_index=True,
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='faq',
            name='sort_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name='faq',
            index=models.Index(
                fields=['is_published', 'sort_order'],
                name='products_fa_is_publ_d06ab1_idx',
            ),
        ),
        migrations.RunPython(replace_faq_catalog, migrations.RunPython.noop),
    ]
