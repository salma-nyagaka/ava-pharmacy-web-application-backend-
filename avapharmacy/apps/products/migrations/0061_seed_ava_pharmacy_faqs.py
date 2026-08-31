from django.db import migrations


FAQS = (
    (
        'Ordering & Prescriptions',
        'Do I need a prescription to buy medicines online?',
        'Yes. Prescription medicines require a valid prescription uploaded during checkout. Over-the-counter (OTC) products can be purchased without one.',
        10,
        (),
    ),
    (
        'Ordering & Prescriptions',
        'How do I place an order?',
        'Browse products, add items to your cart, and proceed to checkout. For prescription medicines, upload your prescription for pharmacist approval.',
        20,
        (),
    ),
    (
        'Ordering & Prescriptions',
        'Can I track my order?',
        'Absolutely. Once your order is confirmed, you’ll receive a tracking link via SMS/WhatsApp and email.',
        30,
        ('How can I track my order?',),
    ),
    (
        'Delivery & Collection',
        'Where do you deliver?',
        'We deliver across Nairobi and selected counties in Kenya. Delivery timelines vary by location.',
        10,
        (),
    ),
    (
        'Delivery & Collection',
        'Do you offer same-day delivery?',
        'Yes, for orders placed before 2 PM within Nairobi. Outside Nairobi, delivery takes 1–3 working days.',
        20,
        (),
    ),
    (
        'Delivery & Collection',
        'Can I collect my order in person?',
        'Yes. You can choose “Pick-Up” at checkout and collect from our pharmacy shopfront.',
        30,
        (),
    ),
    (
        'Payments & Pricing',
        'What payment methods do you accept?',
        'We accept M-Pesa, debit/credit cards, and bank transfers. Cash payments are available for in-store pick-up.',
        10,
        ('Which payment methods are available?',),
    ),
    (
        'Payments & Pricing',
        'Are prices the same online and in-store?',
        'Yes, though online promotions may occasionally differ.',
        20,
        (),
    ),
    (
        'Quality & Safety',
        'Are your medicines genuine?',
        'Yes. All products are sourced from licensed suppliers and comply with Pharmacy and Poisons Board (PPB) regulations.',
        10,
        (),
    ),
    (
        'Quality & Safety',
        'Do you provide pharmacist consultation?',
        'Yes. Our licensed pharmacists are available via phone, WhatsApp, or in-store for guidance.',
        20,
        (),
    ),
    (
        'Support',
        'How can I contact you?',
        'You can reach us via WhatsApp, email, or call us on the following lines:\n\n'
        'The Hub Karen branch, Nairobi: 0715737330, 0733737330\n'
        'GTC Westlands branch, Nairobi: 0713444999, 0101444999\n'
        'The Promenade Mall branch, Mombasa: 0723888835, 0717122022',
        10,
        (),
    ),
)


def seed_faqs(apps, schema_editor):
    FAQ = apps.get_model('products', 'FAQ')

    for category, question, answer, sort_order, aliases in FAQS:
        faq = FAQ.objects.filter(question=question).first()
        if faq is None and aliases:
            faq = FAQ.objects.filter(question__in=aliases).order_by('pk').first()

        if faq is None:
            FAQ.objects.create(
                category=category,
                question=question,
                answer=answer,
                is_published=True,
                sort_order=sort_order,
            )
            continue

        faq.category = category
        faq.question = question
        faq.answer = answer
        faq.is_published = True
        faq.sort_order = sort_order
        faq.save(update_fields=('category', 'question', 'answer', 'is_published', 'sort_order', 'updated_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0060_faq'),
    ]

    operations = [
        migrations.RunPython(seed_faqs, migrations.RunPython.noop),
    ]
