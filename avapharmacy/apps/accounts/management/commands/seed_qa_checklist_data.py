from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Address, Customer, Pharmacist, User
from apps.consultations.models import (
    ClinicianDocument,
    ClinicianProfile,
    ClinicianPrescription,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)
from apps.notifications.models import Notification
from apps.orders.models import Cart, CartItem, Order, OrderEvent, OrderItem, PaymentIntent, ShippingMethod
from apps.prescriptions.models import (
    Prescription,
    PrescriptionAuditLog,
    PrescriptionClarificationMessage,
    PrescriptionFile,
    PrescriptionItem,
    PrescriptionReviewDecision,
)
from apps.products.models import (
    Brand,
    Category,
    HealthConcern,
    Product,
    Promotion,
    StockMovement,
    Subcategory,
    Variant,
    VariantInventory,
)


class Command(BaseCommand):
    help = 'Seed repeatable QA data for the Ava Pharmacy full QA checklist.'

    PASSWORD = 'AvaQA123!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-qa',
            action='store_true',
            help='Delete records tagged with qa-* identifiers before reseeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset_qa']:
            self._reset_qa_data()

        admin = self._user(
            'qa.admin@avapharmacy.test',
            User.ADMIN,
            'QA',
            'Admin',
            '+254790000001',
            is_staff=True,
            is_superuser=True,
        )
        customer = self._user('qa.customer@avapharmacy.test', User.CUSTOMER, 'QA', 'Customer', '+254790000002')
        guardian = self._user('qa.guardian@avapharmacy.test', User.CUSTOMER, 'QA', 'Guardian', '+254790000003')
        pharmacist_user = self._user('qa.pharmacist@avapharmacy.test', User.PHARMACIST, 'QA', 'Pharmacist', '+254790000004')
        doctor_user = self._user('qa.doctor@avapharmacy.test', User.DOCTOR, 'QA', 'Doctor', '+254790000005')
        pediatrician_user = self._user('qa.pediatrician@avapharmacy.test', User.PEDIATRICIAN, 'QA', 'Pediatrician', '+254790000006')
        pending_doctor_user = self._user('qa.pending.doctor@avapharmacy.test', User.DOCTOR, 'QA', 'Pending Doctor', '+254790000007')
        pending_pediatrician_user = self._user('qa.pending.pediatrician@avapharmacy.test', User.PEDIATRICIAN, 'QA', 'Pending Pediatrician', '+254790000008')

        Customer.objects.get_or_create(user=customer, defaults={'notes': 'QA checklist customer'})
        Customer.objects.get_or_create(user=guardian, defaults={'notes': 'QA checklist guardian'})
        Address.objects.update_or_create(
            user=customer,
            label='QA Home',
            defaults={
                'phone': customer.phone,
                'street': 'QA Towers, Waiyaki Way',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'is_default': True,
            },
        )

        Pharmacist.objects.update_or_create(
            user=pharmacist_user,
            defaults={
                'license_number': 'QA-PHARM-001',
                'branch_location': 'QA Main Branch',
                'position': 'QA Pharmacist',
                'permissions': [
                    Pharmacist.PERMISSION_PRESCRIPTION_REVIEW,
                    Pharmacist.PERMISSION_DISPENSE_ORDERS,
                    Pharmacist.PERMISSION_INVENTORY_ADD,
                ],
                'created_by': admin,
                'updated_by': admin,
            },
        )

        category, subcategory, concern, brand = self._catalog_taxonomy(admin)
        variants = self._catalog_variants(admin, category, subcategory, concern, brand)
        self._promotions(variants['QA-PARA-250-SYRUP'].product)

        doctor = self._clinician(
            ClinicianProfile.TYPE_DOCTOR,
            doctor_user,
            'Dr QA Doctor',
            'General Medicine',
            'QA-DOC-ACTIVE-001',
            ClinicianProfile.STATUS_ACTIVE,
            admin,
        )
        pediatrician = self._clinician(
            ClinicianProfile.TYPE_PEDIATRICIAN,
            pediatrician_user,
            'Dr QA Pediatrician',
            'Paediatrics',
            'QA-PED-ACTIVE-001',
            ClinicianProfile.STATUS_ACTIVE,
            admin,
        )
        pending_doctor = self._clinician(
            ClinicianProfile.TYPE_DOCTOR,
            pending_doctor_user,
            'Dr QA Pending Doctor',
            'Dermatology',
            'QA-DOC-PENDING-001',
            ClinicianProfile.STATUS_PENDING,
            admin,
        )
        pending_pediatrician = self._clinician(
            ClinicianProfile.TYPE_PEDIATRICIAN,
            pending_pediatrician_user,
            'Dr QA Pending Pediatrician',
            'Neonatology',
            'QA-PED-PENDING-001',
            ClinicianProfile.STATUS_PENDING,
            admin,
        )
        for clinician in [doctor, pediatrician, pending_doctor, pending_pediatrician]:
            self._clinician_document(clinician)

        rx_pending, rx_approved, rx_clarification = self._prescriptions(customer, pharmacist_user, variants)
        consultation, pediatric_consultation = self._consultations(customer, guardian, doctor, pediatrician, variants)
        self._cart_from_approved_prescription(customer, rx_approved)
        self._orders(customer, pharmacist_user, variants, rx_approved)
        self._notifications(admin, customer, pharmacist_user, doctor_user, pediatrician_user, pending_doctor, pending_pediatrician)

        self.stdout.write(self.style.SUCCESS('Seeded Ava QA checklist data.'))
        self.stdout.write(f'Password for all QA users: {self.PASSWORD}')
        self.stdout.write(f'Admin: {admin.email}')
        self.stdout.write(f'Customer: {customer.email}')
        self.stdout.write(f'Pharmacist: {pharmacist_user.email}')
        self.stdout.write(f'Doctor: {doctor_user.email}')
        self.stdout.write(f'Pediatrician: {pediatrician_user.email}')
        self.stdout.write(f'Pending doctor reference: {pending_doctor.reference}')
        self.stdout.write(f'Pending pediatrician reference: {pending_pediatrician.reference}')
        self.stdout.write(f'Prescription references: {rx_pending.reference}, {rx_approved.reference}, {rx_clarification.reference}')
        self.stdout.write(f'Consultation references: {consultation.reference}, {pediatric_consultation.reference}')

    def _reset_qa_data(self):
        qa_users = User.objects.filter(email__startswith='qa.')
        qa_user_ids = list(qa_users.values_list('id', flat=True))
        if qa_user_ids:
            Notification.objects.filter(recipient_id__in=qa_user_ids).delete()
            ConsultationPaymentIntent.objects.filter(initiated_by_id__in=qa_user_ids).delete()
            ConsultationPaymentIntent.objects.filter(clinician__user_id__in=qa_user_ids).delete()
            ConsultationPaymentIntent.objects.filter(consultation__patient_id__in=qa_user_ids).delete()
            Consultation.objects.filter(patient_id__in=qa_user_ids).delete()
            Consultation.objects.filter(clinician__user_id__in=qa_user_ids).delete()
            Prescription.objects.filter(patient_id__in=qa_user_ids).delete()
            Order.objects.filter(customer_id__in=qa_user_ids).delete()
            ClinicianProfile.objects.filter(user_id__in=qa_user_ids).delete()
            Pharmacist.objects.filter(user_id__in=qa_user_ids).delete()
            Customer.objects.filter(user_id__in=qa_user_ids).delete()
            Address.objects.filter(user_id__in=qa_user_ids).delete()
            qa_users.delete()
        Product.objects.filter(sku__startswith='QA-').delete()
        Promotion.objects.filter(code__startswith='QA-').delete()
        Brand.objects.filter(slug__startswith='qa-').delete()
        Category.objects.filter(slug__startswith='qa-').delete()
        HealthConcern.objects.filter(slug__startswith='qa-').delete()

    def _user(self, email, role, first_name, last_name, phone, **flags):
        defaults = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'role': role,
            'status': User.STATUS_ACTIVE,
            'is_active': True,
            'is_staff': flags.get('is_staff', False),
            'is_superuser': flags.get('is_superuser', False),
        }
        user, _ = User.objects.update_or_create(email=email, defaults=defaults)
        user.set_password(self.PASSWORD)
        user.save(update_fields=['password', 'updated_at'])
        return user

    def _catalog_taxonomy(self, admin):
        category, _ = Category.objects.update_or_create(
            slug='qa-medicines',
            defaults={'name': 'QA Medicines', 'description': 'QA catalog category', 'is_active': True, 'created_by': admin, 'updated_by': admin},
        )
        subcategory, _ = Subcategory.objects.update_or_create(
            slug='qa-pain-relief',
            defaults={'category': category, 'name': 'QA Pain Relief', 'description': 'QA catalog subcategory', 'is_active': True, 'created_by': admin, 'updated_by': admin},
        )
        concern, _ = HealthConcern.objects.update_or_create(
            slug='qa-fever',
            defaults={'name': 'QA Fever', 'description': 'QA health concern', 'is_active': True, 'created_by': admin, 'updated_by': admin},
        )
        brand, _ = Brand.objects.update_or_create(
            slug='qa-ava-brand',
            defaults={'name': 'QA Ava Brand', 'logo': 'brands/qa-ava-brand.png', 'description': 'QA test brand', 'is_active': True, 'created_by': admin, 'updated_by': admin},
        )
        return category, subcategory, concern, brand

    def _catalog_variants(self, admin, category, subcategory, concern, brand):
        product, _ = Product.objects.update_or_create(
            sku='QA-PARACETAMOL',
            defaults={'name': 'QA Paracetamol', 'slug': 'qa-paracetamol', 'brand': brand, 'is_active': True, 'created_by': admin, 'updated_by': admin},
        )
        product.image = 'products/qa-paracetamol.png'
        product.save(update_fields=['image', 'updated_at'])

        variant_specs = [
            ('QA-PARA-500', '500mg Tablets', Decimal('120.00'), 30, False),
            ('QA-PARA-250-SYRUP', '250mg Syrup', Decimal('180.00'), 4, False),
            ('QA-AMOX-500', 'Amoxicillin 500mg Capsules', Decimal('350.00'), 12, True),
            ('QA-OUT-STOCK', 'Out of Stock Test Variant', Decimal('99.00'), 0, False),
        ]
        variants = {}
        for sku, name, price, stock, requires_prescription in variant_specs:
            variant, _ = Variant.objects.update_or_create(
                sku=sku,
                defaults={
                    'product': product,
                    'name': name,
                    'strength': name.split()[0],
                    'category': category,
                    'subcategory': subcategory,
                    'price': price,
                    'cost_price': price * Decimal('0.65'),
                    'short_description': f'{name} for QA checklist testing.',
                    'description': f'{name} seeded for QA checklist verification.',
                    'features': ['QA searchable', 'Variant-managed stock'],
                    'dosage_quantity': '1',
                    'dosage_unit': 'tablet' if 'Tablets' in name or 'Capsules' in name else 'ml',
                    'dosage_frequency': 'twice_daily',
                    'requires_prescription': requires_prescription,
                    'image': f'products/variants/{sku.lower()}.png',
                    'is_active': True,
                },
            )
            variant.health_concerns.set([concern])
            inventory, _ = VariantInventory.objects.update_or_create(
                variant=variant,
                location=Product.STOCK_BRANCH,
                batch_number=f'{sku}-BATCH-A',
                defaults={
                    'supplier': 'QA Supplier',
                    'stock_quantity': stock,
                    'low_stock_threshold': 5,
                    'reorder_level': 5,
                    'expiry_date': timezone.now().date().replace(year=timezone.now().year + 1),
                    'shelf_location': 'QA-A1',
                },
            )
            StockMovement.objects.update_or_create(
                variant_inventory=inventory,
                reference=f'QA-SEED-{sku}',
                defaults={
                    'movement_type': StockMovement.TYPE_INITIAL,
                    'source': StockMovement.SOURCE_SYSTEM,
                    'batch_number': inventory.batch_number,
                    'quantity_change': stock,
                    'quantity_before': 0,
                    'quantity_after': stock,
                    'reason': 'QA checklist seed stock',
                    'created_by': admin,
                    'updated_by': admin,
                },
            )
            variants[sku] = variant
        return variants

    def _promotions(self, product):
        today = timezone.now().date()
        campaign_window = {
            'start_date': today - timezone.timedelta(days=1),
            'end_date': today + timezone.timedelta(days=30),
            'status': Promotion.STATUS_ACTIVE,
        }
        Promotion.objects.update_or_create(
            code='QA-WELLNESS-10',
            defaults={
                'title': 'QA Wellness Essentials',
                'description': 'Save on selected everyday pharmacy essentials during QA testing.',
                'type': Promotion.TYPE_PERCENTAGE,
                'value': Decimal('10.00'),
                'scope': Promotion.SCOPE_PRODUCT,
                'targets': [str(product.id), product.slug, product.get_display_sku()],
                'priority': 50,
                'is_stackable': False,
                'minimum_order_amount': Decimal('0.00'),
                **campaign_window,
            },
        )
        Promotion.objects.update_or_create(
            code='QA-STOREWIDE-5',
            defaults={
                'title': 'QA Storewide Offer',
                'description': 'A live storewide campaign used to verify homepage and offers-page deals.',
                'type': Promotion.TYPE_PERCENTAGE,
                'value': Decimal('5.00'),
                'scope': Promotion.SCOPE_ALL,
                'targets': [],
                'priority': 10,
                'is_stackable': False,
                'minimum_order_amount': Decimal('0.00'),
                **campaign_window,
            },
        )

    def _clinician(self, provider_type, user, name, specialty, license_number, status, admin):
        clinician, _ = ClinicianProfile.objects.update_or_create(
            provider_type=provider_type,
            license_number=license_number,
            defaults={
                'user': user,
                'name': name,
                'specialty': specialty,
                'email': user.email,
                'phone': user.phone,
                'license_board': 'QA Medical Council',
                'license_country': 'Kenya',
                'facility': 'QA Health Centre',
                'availability': 'Mon-Fri 08:00-17:00',
                'availability_schedule': [{'day': 'Mon', 'start_time': '08:00', 'end_time': '17:00'}],
                'bio': f'{name} seeded for QA checklist testing.',
                'languages': ['English', 'Swahili'],
                'consult_modes': ['chat'],
                'years_experience': 8,
                'county': 'Nairobi',
                'address': 'QA Health Centre, Nairobi',
                'document_checklist': ['License', 'National ID', 'CV / Resume'],
                'status': status,
                'is_verified': status == ClinicianProfile.STATUS_ACTIVE,
                'verified_at': timezone.now() if status == ClinicianProfile.STATUS_ACTIVE else None,
                'consult_fee': Decimal('1.00'),
                'created_by': admin,
                'updated_by': admin,
                'agreed_to_terms': True,
                'background_consent': True,
                'compliance_declaration': True,
            },
        )
        return clinician

    def _clinician_document(self, clinician):
        document, _ = ClinicianDocument.objects.get_or_create(
            clinician=clinician,
            name='QA License Document',
            defaults={'status': ClinicianDocument.STATUS_SUBMITTED, 'note': 'Seeded QA document'},
        )
        if not document.file:
            document.file.save('qa-license.txt', ContentFile(b'QA license document'), save=True)
        return document

    def _prescriptions(self, customer, pharmacist, variants):
        pending = self._prescription(customer, 'QA Pending Prescription', Prescription.STATUS_PENDING, variants['QA-AMOX-500'])
        approved = self._prescription(customer, 'QA Approved Prescription', Prescription.STATUS_APPROVED, variants['QA-AMOX-500'])
        clarification = self._prescription(customer, 'QA Clarification Prescription', Prescription.STATUS_CLARIFICATION, variants['QA-PARA-500'], pharmacist)
        PrescriptionClarificationMessage.objects.get_or_create(
            prescription=clarification,
            sender=pharmacist,
            sender_role=PrescriptionClarificationMessage.SENDER_PHARMACIST,
            message='Please confirm the dosage instructions.',
            defaults={'sender_name': pharmacist.full_name},
        )
        return pending, approved, clarification

    def _prescription(self, customer, notes, status, variant, pharmacist=None):
        prescription, _ = Prescription.objects.update_or_create(
            patient=customer,
            notes=notes,
            defaults={
                'patient_name': customer.full_name,
                'doctor_name': 'Dr QA Doctor',
                'pharmacist': pharmacist,
                'source': Prescription.SOURCE_UPLOAD,
                'status': status,
                'pharmacist_notes': 'QA review notes' if pharmacist else '',
            },
        )
        PrescriptionFile.objects.get_or_create(
            prescription=prescription,
            filename=f'{prescription.reference.lower()}-document.txt',
            defaults={'file': f'prescriptions/{prescription.id}/qa-document.txt'},
        )
        PrescriptionItem.objects.update_or_create(
            prescription=prescription,
            variant=variant,
            defaults={
                'product': variant.product,
                'name': variant.name,
                'dose': '1 tablet',
                'frequency': 'twice daily',
                'quantity': 1,
                'is_controlled_substance': False,
            },
        )
        PrescriptionAuditLog.objects.get_or_create(
            prescription=prescription,
            action='QA prescription seeded',
            defaults={'performed_by': pharmacist, 'notes': 'Seeded for QA checklist'},
        )
        if status in {Prescription.STATUS_APPROVED, Prescription.STATUS_REJECTED, Prescription.STATUS_CLARIFICATION}:
            PrescriptionReviewDecision.objects.get_or_create(
                prescription=prescription,
                action=PrescriptionReviewDecision.ACTION_APPROVE if status == Prescription.STATUS_APPROVED else PrescriptionReviewDecision.ACTION_REQUEST_CLARIFICATION,
                defaults={
                    'pharmacist': pharmacist,
                    'from_status': Prescription.STATUS_PENDING,
                    'to_status': status,
                    'notes': 'QA review decision',
                },
            )
        return prescription

    def _consultations(self, customer, guardian, doctor, pediatrician, variants):
        consultation = self._consultation(customer, doctor, 'QA adult consultation', False)
        pediatric_consultation = self._consultation(guardian, pediatrician, 'QA pediatric consultation', True)
        for item in [
            (consultation, doctor.user, 'Doctor QA message'),
            (consultation, customer, 'Customer QA message'),
            (pediatric_consultation, pediatrician.user, 'Pediatrician QA message'),
        ]:
            ConsultationMessage.objects.get_or_create(
                consultation=item[0],
                sender=item[1],
                message=item[2],
                defaults={'sender_name': item[1].full_name, 'message_type': ConsultationMessage.TYPE_TEXT},
            )
        ClinicianPrescription.objects.update_or_create(
            consultation=consultation,
            clinician=doctor,
            defaults={
                'patient_name': customer.full_name,
                'items': [{'variant_id': variants['QA-AMOX-500'].id, 'drug_name': variants['QA-AMOX-500'].name, 'dose': '500mg', 'frequency': 'twice daily', 'quantity': 10}],
                'status': ClinicianPrescription.STATUS_SENT,
                'notes': 'QA doctor prescription',
                'sent_at': timezone.now(),
            },
        )
        self._dispensing_prescription_from_clinician(
            consultation=consultation,
            clinician=doctor,
            variant=variants['QA-AMOX-500'],
            dose='500mg',
            frequency='twice daily',
            quantity=10,
            notes='QA doctor e-prescription converted for pharmacy dispensing.',
        )
        ClinicianPrescription.objects.update_or_create(
            consultation=pediatric_consultation,
            clinician=pediatrician,
            defaults={
                'patient_name': guardian.full_name,
                'items': [{'variant_id': variants['QA-PARA-250-SYRUP'].id, 'drug_name': variants['QA-PARA-250-SYRUP'].name, 'dose': '5ml', 'frequency': 'twice daily', 'quantity': 1}],
                'status': ClinicianPrescription.STATUS_SENT,
                'notes': 'QA pediatric prescription',
                'sent_at': timezone.now(),
            },
        )
        self._dispensing_prescription_from_clinician(
            consultation=pediatric_consultation,
            clinician=pediatrician,
            variant=variants['QA-PARA-250-SYRUP'],
            dose='5ml',
            frequency='twice daily',
            quantity=1,
            notes='QA pediatric e-prescription converted for pharmacy dispensing.',
        )
        for target in [consultation, pediatric_consultation]:
            ConsultationPaymentIntent.objects.update_or_create(
                consultation=target,
                defaults={
                    'initiated_by': target.patient,
                    'clinician': target.clinician,
                    'provider': ConsultationPaymentIntent.PROVIDER_PAYBILL,
                    'status': ConsultationPaymentIntent.STATUS_SUCCEEDED,
                    'amount': Decimal('1.00'),
                    'currency': 'KES',
                    'processed_at': timezone.now(),
                    'consultation_payload': {'issue': target.issue},
                },
            )
        return consultation, pediatric_consultation

    def _consultation(self, patient, clinician, issue, is_pediatric):
        consultation, _ = Consultation.objects.update_or_create(
            patient=patient,
            clinician=clinician,
            issue=issue,
            defaults={
                'patient_name': patient.full_name,
                'patient_email': patient.email,
                'patient_phone': patient.phone,
                'patient_age': 34 if not is_pediatric else 7,
                'status': Consultation.STATUS_IN_PROGRESS,
                'priority': Consultation.PRIORITY_ROUTINE,
                'is_pediatric': is_pediatric,
                'guardian_name': patient.full_name if is_pediatric else '',
                'child_name': 'QA Child' if is_pediatric else '',
                'child_age': 7 if is_pediatric else None,
                'weight_kg': Decimal('24.50') if is_pediatric else None,
                'consent_status': 'granted' if is_pediatric else 'pending',
                'scheduled_at': timezone.now(),
            },
        )
        return consultation

    def _dispensing_prescription_from_clinician(self, *, consultation, clinician, variant, dose, frequency, quantity, notes):
        clinician_prescription = ClinicianPrescription.objects.filter(
            consultation=consultation,
            clinician=clinician,
        ).order_by('-created_at').first()
        if not clinician_prescription:
            return None
        prescription, _ = Prescription.objects.update_or_create(
            clinician_prescription=clinician_prescription,
            defaults={
                'patient': consultation.patient,
                'patient_name': consultation.patient.full_name,
                'doctor_name': clinician.name,
                'source': Prescription.SOURCE_E_PRESCRIPTION,
                'status': Prescription.STATUS_APPROVED,
                'notes': notes,
            },
        )
        PrescriptionItem.objects.update_or_create(
            prescription=prescription,
            variant=variant,
            defaults={
                'product': variant.product,
                'name': variant.name,
                'dose': dose,
                'frequency': frequency,
                'quantity': quantity,
                'is_controlled_substance': False,
            },
        )
        PrescriptionAuditLog.objects.get_or_create(
            prescription=prescription,
            action='QA e-prescription sent by clinician',
            defaults={'performed_by': clinician.user, 'notes': notes},
        )
        return prescription

    def _cart_from_approved_prescription(self, customer, prescription):
        item = prescription.items.select_related('variant').first()
        if not item or not item.variant_id:
            return None
        cart, _ = Cart.objects.get_or_create(user=customer)
        CartItem.objects.update_or_create(
            cart=cart,
            variant=item.variant,
            prescription=prescription,
            prescription_item=item,
            defaults={
                'quantity': min(item.quantity or 1, item.variant.available_quantity or 1),
                'prescription_reference': prescription.reference,
            },
        )
        return cart

    def _orders(self, customer, pharmacist, variants, prescription):
        shipping, _ = ShippingMethod.objects.update_or_create(
            code='qa-standard',
            defaults={'name': 'QA Standard Delivery', 'fee': Decimal('150.00'), 'is_active': True, 'estimated_delivery_window': '1-2 days'},
        )
        order_specs = [
            ('QA-ORDER-PAID', Order.STATUS_PAID, variants['QA-PARA-500'], 2, None),
            ('QA-ORDER-PROCESSING', Order.STATUS_PROCESSING, variants['QA-AMOX-500'], 1, prescription),
            ('QA-ORDER-DELIVERED', Order.STATUS_DELIVERED, variants['QA-PARA-250-SYRUP'], 1, None),
        ]
        for order_number, order_status, variant, quantity, rx in order_specs:
            subtotal = variant.price * quantity
            order, _ = Order.objects.update_or_create(
                order_number=order_number,
                defaults={
                    'customer': customer,
                    'status': order_status,
                    'payment_method': Order.PAYMENT_MPESA_PAYBILL,
                    'payment_status': Order.PAYMENT_STATUS_PAID,
                    'payment_reference': f'QA-PAY-{order_number}',
                    'delivery_method': 'standard',
                    'shipping_method': shipping,
                    'shipping_first_name': customer.first_name,
                    'shipping_last_name': customer.last_name,
                    'shipping_email': customer.email,
                    'shipping_phone': customer.phone,
                    'shipping_street': 'QA Towers, Waiyaki Way',
                    'shipping_city': 'Nairobi',
                    'shipping_county': 'Nairobi',
                    'subtotal': subtotal,
                    'shipping_fee': shipping.fee,
                    'total': subtotal + shipping.fee,
                    'placed_at': timezone.now(),
                    'inventory_committed': True,
                },
            )
            OrderItem.objects.update_or_create(
                order=order,
                variant=variant,
                defaults={
                    'product_name': variant.product.name,
                    'product_sku': variant.product.sku,
                    'variant_name': variant.name,
                    'variant_sku': variant.sku,
                    'quantity': quantity,
                    'unit_price': variant.price,
                    'prescription_reference': rx.reference if rx else None,
                    'prescription': rx,
                },
            )
            PaymentIntent.objects.update_or_create(
                order=order,
                provider=PaymentIntent.PROVIDER_PAYBILL,
                defaults={
                    'initiated_by': customer,
                    'status': PaymentIntent.STATUS_SUCCEEDED,
                    'amount': order.total,
                    'currency': 'KES',
                    'provider_reference': f'QA-MPESA-{order_number}',
                    'processed_at': timezone.now(),
                },
            )
            OrderEvent.objects.get_or_create(
                order=order,
                event_type='qa_seed',
                defaults={'actor': pharmacist, 'message': f'QA order seeded as {order_status}', 'metadata': {'qa': True}},
            )

    def _notifications(self, admin, customer, pharmacist, doctor_user, pediatrician_user, pending_doctor, pending_pediatrician):
        notifications = [
            (admin, Notification.DOCTOR_VERIFIED, 'New Doctor application', f'{pending_doctor.name} submitted credentials.', {'url': '/admin/doctors?type=Doctor', 'reference': pending_doctor.reference}),
            (admin, Notification.DOCTOR_VERIFIED, 'New Pediatrician application', f'{pending_pediatrician.name} submitted credentials.', {'url': '/admin/doctors?type=Pediatrician', 'reference': pending_pediatrician.reference}),
            (customer, Notification.ORDER_STATUS, 'QA order update', 'Your QA order is processing.', {'reference': 'QA-ORDER-PROCESSING'}),
            (customer, Notification.PRESCRIPTION_STATUS, 'QA prescription update', 'Your QA prescription was approved.', {'sensitive': True}),
            (doctor_user, Notification.NEW_CONSULTATION, 'QA consultation assigned', 'A QA consultation is waiting.', {'sensitive': True}),
            (pediatrician_user, Notification.NEW_CONSULTATION, 'QA pediatric consultation assigned', 'A QA pediatric consultation is waiting.', {'sensitive': True}),
            (pharmacist, Notification.PRESCRIPTION_STATUS, 'QA prescription queue', 'A QA prescription is ready for review.', {'sensitive': True}),
        ]
        for recipient, notification_type, title, message, data in notifications:
            Notification.objects.get_or_create(
                recipient=recipient,
                type=notification_type,
                title=title,
                defaults={'message': message, 'data': data},
            )
