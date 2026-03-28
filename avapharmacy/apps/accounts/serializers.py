"""
Serializers for the accounts app.

Covers user registration/login, profile read/update, admin user management,
address management, password change, user notes, and audit log output.
"""
import json

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from django.utils import timezone
from .models import AdminAuditLog, Address, Customer, PaymentMethod, Pharmacist, User, UserNote
from apps.consultations.serializers import (
    DoctorOnboardingSerializer, DoctorProfileSerializer,
    PediatricianOnboardingSerializer, PediatricianProfileSerializer,
)
from apps.lab.models import LabPartner
from apps.lab.serializers import (
    LabPartnerRegistrationSerializer, LabPartnerSerializer,
)
from .utils import (
    consume_pharmacist_activation,
    get_valid_pharmacist_activation,
    issue_pharmacist_activation_token,
    send_pharmacist_activation_email,
    split_full_name,
)


def validate_unique_phone(phone, instance=None):
    """Validate that a non-empty phone number is unique across users."""
    phone = (phone or '').strip()
    if not phone:
        return phone

    queryset = User.objects.filter(phone=phone)
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        raise serializers.ValidationError('A user with this phone number already exists.')
    return phone


def validate_unique_email(email, instance=None):
    """Validate that an email address remains unique across users."""
    email = (email or '').strip().lower()
    if not email:
        raise serializers.ValidationError('Email is required.')

    queryset = User.objects.filter(email__iexact=email)
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        raise serializers.ValidationError('A user with this email address already exists.')
    return email


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for public self-registration.

    Validates passwords, restricts allowed roles, and creates a Pharmacist
    automatically when the role is 'pharmacist'.
    """

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'password', 'password_confirm', 'role')

    def validate_role(self, value):
        """Reject roles that are not allowed during self-registration."""
        allowed = [User.CUSTOMER, User.DOCTOR, User.PEDIATRICIAN, User.PHARMACIST, User.LAB_TECHNICIAN]
        if value not in allowed:
            raise serializers.ValidationError('Invalid role for self-registration.')
        return value

    def validate_phone(self, value):
        """Ensure registration phone numbers are unique."""
        return validate_unique_phone(value)

    def validate(self, attrs):
        """Ensure the two password fields match."""
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        """Create the user and, if pharmacist, an associated Pharmacist."""
        user = User.objects.create_user(**validated_data)
        request = self.context.get('request')
        actor = request.user if request and getattr(request.user, 'is_authenticated', False) else None
        if user.role == User.PHARMACIST:
            Pharmacist.objects.create(user=user, created_by=actor, updated_by=actor)
        elif user.role == User.CUSTOMER:
            Customer.objects.create(user=user, created_by=actor, updated_by=actor)
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for validating login credentials (email + password)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """Read serializer for the authenticated user's own profile."""

    full_name = serializers.ReadOnlyField()
    total_orders = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'date_of_birth', 'role', 'status', 'address', 'total_orders',
            'date_joined', 'updated_at'
        )
        read_only_fields = ('id', 'date_joined', 'updated_at')


class UserUpdateSerializer(serializers.ModelSerializer):
    """Write serializer allowing users to update their own basic profile fields."""

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'date_of_birth', 'address')

    def validate_email(self, value):
        """Ensure updated email addresses remain unique."""
        return validate_unique_email(value, instance=self.instance)

    def validate_phone(self, value):
        """Ensure updated phone numbers remain unique."""
        return validate_unique_phone(value, instance=self.instance)


class AdminUserSerializer(serializers.ModelSerializer):
    """Detailed read serializer used by admins to view a user with extra context.

    Includes pharmacist permissions, last order date, default address, recent orders,
    and total spend derived from paid orders.
    """

    full_name = serializers.ReadOnlyField()
    total_orders = serializers.ReadOnlyField()
    pharmacist_permissions = serializers.SerializerMethodField()
    last_order_date = serializers.SerializerMethodField()
    default_address = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()
    total_spend = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'status', 'address', 'total_orders',
            'last_order_date', 'default_address', 'recent_orders', 'total_spend',
            'date_joined', 'pharmacist_permissions'
        )

    def get_pharmacist_permissions(self, obj):
        """Return the pharmacist's custom permissions list, or an empty list."""
        if hasattr(obj, 'pharmacist'):
            return obj.pharmacist.permissions
        return []

    def get_last_order_date(self, obj):
        """Return the created_at timestamp of the user's most recent order."""
        prefetched_orders = getattr(obj, '_prefetched_objects_cache', {}).get('orders')
        if prefetched_orders is not None:
            last = max(prefetched_orders, key=lambda order: order.created_at, default=None)
        else:
            last = obj.orders.order_by('-created_at').first()
        return last.created_at if last else None

    def get_default_address(self, obj):
        """Return the user's default address (or first address) as serialized data."""
        prefetched_addresses = getattr(obj, '_prefetched_objects_cache', {}).get('addresses')
        if prefetched_addresses is not None:
            ordered_addresses = sorted(prefetched_addresses, key=lambda address: (not address.is_default, -address.created_at.timestamp()))
            address = ordered_addresses[0] if ordered_addresses else None
        else:
            address = obj.addresses.filter(is_default=True).first() or obj.addresses.first()
        return AddressSerializer(address).data if address else None

    def get_recent_orders(self, obj):
        """Return the five most recent orders as lightweight dicts."""
        prefetched_orders = getattr(obj, '_prefetched_objects_cache', {}).get('orders')
        if prefetched_orders is not None:
            recent_orders = sorted(prefetched_orders, key=lambda order: order.created_at, reverse=True)[:5]
            return [
                {
                    'id': order.id,
                    'order_number': order.order_number,
                    'status': order.status,
                    'payment_status': order.payment_status,
                    'total': order.total,
                    'created_at': order.created_at,
                }
                for order in recent_orders
            ]
        return list(
            obj.orders.order_by('-created_at')
            .values('id', 'order_number', 'status', 'payment_status', 'total', 'created_at')[:5]
        )

    def get_total_spend(self, obj):
        """Return the sum of all paid order totals for this user."""
        prefetched_orders = getattr(obj, '_prefetched_objects_cache', {}).get('orders')
        if prefetched_orders is not None:
            total = sum(order.total for order in prefetched_orders if order.payment_status == 'paid')
            return total or 0
        total = obj.orders.filter(payment_status='paid').aggregate(total=Sum('total'))['total']
        return total or 0


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Write serializer for admins to create or fully update a user.

    Handles optional password hashing and Pharmacist creation/update.
    """

    password = serializers.CharField(write_only=True, validators=[validate_password], required=False)
    pharmacist_permissions = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'role', 'address', 'password', 'pharmacist_permissions')

    def validate_phone(self, value):
        """Ensure admin-created or updated users have a unique phone number."""
        return validate_unique_phone(value, instance=self.instance)

    def validate(self, attrs):
        """Require password for non-pharmacist users created by admins."""
        if self.instance is None:
            role = attrs.get('role')
            password = attrs.get('password')
            if role != User.PHARMACIST and not password:
                raise serializers.ValidationError({'password': 'Password is required for this role.'})
        return attrs

    def create(self, validated_data):
        """Create user and optional Pharmacist with the given permissions."""
        permissions = validated_data.pop('pharmacist_permissions', [])
        password = validated_data.pop('password', None)
        request = self.context.get('request')
        actor = getattr(request, 'user', None)

        user = User.objects.create_user(password=password, **validated_data)
        if user.role == User.PHARMACIST:
            user.is_active = False
            user.save(update_fields=['is_active', 'updated_at'])
            Pharmacist.objects.create(
                user=user,
                permissions=permissions,
                created_by=actor if getattr(actor, 'is_authenticated', False) else None,
                updated_by=actor if getattr(actor, 'is_authenticated', False) else None,
            )
            token, raw_token = issue_pharmacist_activation_token(user, created_by=actor)
            send_pharmacist_activation_email(
                user=user,
                raw_token=raw_token,
                request=request,
                invited_by=actor,
            )
            self.activation_email_meta = {
                'sent_to': user.email,
                'expires_at': token.expires_at,
            }
        elif user.role == User.CUSTOMER:
            Customer.objects.create(
                user=user,
                created_by=actor if getattr(actor, 'is_authenticated', False) else None,
                updated_by=actor if getattr(actor, 'is_authenticated', False) else None,
            )
        return user

    def update(self, instance, validated_data):
        """Update user fields, optionally reset password, and sync pharmacist permissions."""
        permissions = validated_data.pop('pharmacist_permissions', None)
        password = validated_data.pop('password', None)
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        actor = actor if getattr(actor, 'is_authenticated', False) else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        instance.save()

        if instance.role == User.PHARMACIST:
            profile, created = Pharmacist.objects.get_or_create(
                user=instance,
                defaults={'created_by': actor, 'updated_by': actor},
            )
            if permissions is not None:
                profile.permissions = permissions
            profile.updated_by = actor
            if created and not profile.created_by:
                profile.created_by = actor
            profile.save(update_fields=['permissions', 'updated_by', 'created_by', 'updated_at'])
        else:
            Pharmacist.objects.filter(user=instance).delete()

        if instance.role == User.CUSTOMER:
            customer_profile, created = Customer.objects.get_or_create(
                user=instance,
                defaults={'created_by': actor, 'updated_by': actor},
            )
            customer_profile.updated_by = actor
            if created and not customer_profile.created_by:
                customer_profile.created_by = actor
            customer_profile.save(update_fields=['updated_by', 'created_by', 'updated_at'])
        else:
            Customer.objects.filter(user=instance).delete()

        return instance


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for a user's delivery address."""

    class Meta:
        model = Address
        fields = ('id', 'label', 'phone', 'street', 'city', 'county', 'is_default', 'created_at')
        read_only_fields = ('id', 'created_at')


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            'id', 'brand', 'last4', 'expiry_month', 'expiry_year',
            'cardholder_name', 'is_default', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_last4(self, value):
        value = ''.join(ch for ch in str(value or '') if ch.isdigit())
        if len(value) != 4:
            raise serializers.ValidationError('Last four digits are required.')
        return value

    def validate_expiry_month(self, value):
        if not 1 <= int(value) <= 12:
            raise serializers.ValidationError('Expiry month must be between 1 and 12.')
        return value

    def validate_expiry_year(self, value):
        if int(value) < timezone.now().year:
            raise serializers.ValidationError('Expiry year cannot be in the past.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        month = attrs.get('expiry_month', getattr(self.instance, 'expiry_month', None))
        year = attrs.get('expiry_year', getattr(self.instance, 'expiry_year', None))
        if month is None or year is None:
            return attrs

        now = timezone.now()
        if int(year) == now.year and int(month) < now.month:
            raise serializers.ValidationError({'expiry_month': ['Expiry date cannot be in the past.']})
        return attrs


class UserNoteSerializer(serializers.ModelSerializer):
    """Serializer for admin-written notes attached to a user."""

    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')

    class Meta:
        model = UserNote
        fields = ('id', 'content', 'created_by', 'created_by_name', 'created_at')
        read_only_fields = ('id', 'created_by', 'created_at')


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for the authenticated user's password change request."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Ensure new_password and new_password_confirm match."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match.'})
        return attrs


class PharmacistActivationSetPasswordSerializer(serializers.Serializer):
    """Set password using one-time staff activation token."""

    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match.'})
        token_obj = get_valid_pharmacist_activation(attrs['token'])
        if token_obj is None:
            raise serializers.ValidationError({'token': 'Activation link is invalid or expired.'})
        if token_obj.user.status == User.STATUS_SUSPENDED:
            raise serializers.ValidationError({'token': 'This account is suspended. Contact support.'})
        attrs['token_obj'] = token_obj
        return attrs

    def save(self, **kwargs):
        token = self.validated_data['token']
        user = self.validated_data['token_obj'].user
        user.set_password(self.validated_data['new_password'])
        user.is_active = True
        user.status = User.STATUS_ACTIVE
        user.save(update_fields=['password', 'is_active', 'status', 'updated_at'])
        consume_pharmacist_activation(token)
        return user


class AdminAuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for AdminAuditLog entries."""

    actor_name = serializers.ReadOnlyField(source='actor.full_name')

    class Meta:
        model = AdminAuditLog
        fields = (
            'id', 'action', 'entity_type', 'entity_id',
            'message', 'metadata', 'actor_name', 'created_at'
        )


def _parse_list_input(value, default=None):
    if value in (None, ''):
        return [] if default is None else default
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return [] if default is None else default
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed, list):
            return parsed
        return [] if default is None else default
    return [] if default is None else default


def _professional_type_label(value):
    labels = {
        'doctor': 'Doctor',
        'pediatrician': 'Pediatrician',
        'lab_partner': 'Lab Partner',
    }
    return labels[value]


class ProfessionalRegistrationSerializer(serializers.Serializer):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('pediatrician', 'Pediatrician'),
        ('lab_partner', 'Lab Partner'),
    )
    ROLE_ALIASES = {
        'doctor': 'doctor',
        'pediatrician': 'pediatrician',
        'paediatrician': 'pediatrician',
        'lab_partner': 'lab_partner',
        'lab partner': 'lab_partner',
        'lab-partner': 'lab_partner',
    }

    type = serializers.CharField()
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    license = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    licenseBoard = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    licenseCountry = serializers.CharField(max_length=100, required=False, allow_blank=True, default='Kenya')
    licenseExpiry = serializers.DateField(required=False, allow_null=True)
    idNumber = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    specialty = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    facility = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    labName = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    labLocation = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    labAccreditation = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    experience = serializers.IntegerField(required=False, allow_null=True)
    availability = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    address = serializers.CharField(required=False, allow_blank=True, default='')
    bio = serializers.CharField(required=False, allow_blank=True, default='')
    languages = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    consultModes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    payoutMethod = serializers.CharField(required=False, allow_blank=True, default='M-Pesa')
    payoutAccount = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    ref1Name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    ref1Email = serializers.EmailField(required=False, allow_blank=True, default='')
    ref1Phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    ref2Name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    ref2Email = serializers.EmailField(required=False, allow_blank=True, default='')
    ref2Phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    backgroundConsent = serializers.BooleanField()
    complianceDeclaration = serializers.BooleanField()
    docChecklist = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    agreedToTerms = serializers.BooleanField()
    documentNames = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    cvNames = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)
        for field in ('languages', 'consultModes', 'docChecklist', 'documentNames', 'cvNames'):
            raw = mutable.get(field)
            if hasattr(data, 'getlist'):
                values = data.getlist(field)
                if len(values) > 1:
                    mutable.setlist(field, values)
                    continue
                if len(values) == 1:
                    raw = values[0]
            mutable[field] = _parse_list_input(raw)
        return super().to_internal_value(mutable)

    def validate_type(self, value):
        normalized = self.ROLE_ALIASES.get(str(value).strip().lower())
        if not normalized:
            raise serializers.ValidationError('Select a valid professional type.')
        return normalized

    def validate_payoutMethod(self, value):
        normalized = str(value or '').strip().lower()
        if normalized in ('mpesa', 'm-pesa'):
            return 'mpesa'
        if normalized in ('bank', 'bank transfer', 'bank_transfer'):
            return 'bank_transfer'
        raise serializers.ValidationError('Select a valid payout method.')

    def validate(self, attrs):
        professional_type = attrs['type']
        errors = {}

        if professional_type == 'lab_partner':
            if not attrs['labName'].strip():
                errors['labName'] = 'Lab name is required.'
            if not attrs['labLocation'].strip():
                errors['labLocation'] = 'Lab location is required.'
            if not attrs['labAccreditation'].strip():
                errors['labAccreditation'] = 'Accreditation number is required.'
            if not attrs['license'].strip():
                errors['license'] = 'Facility licence number is required.'
        else:
            if not attrs['license'].strip():
                errors['license'] = 'License number is required.'
            if not attrs['licenseBoard'].strip():
                errors['licenseBoard'] = 'Licensing board is required.'
            if not attrs['licenseExpiry']:
                errors['licenseExpiry'] = 'License expiry date is required.'
            if not attrs['idNumber'].strip():
                errors['idNumber'] = 'ID / Passport number is required.'
            if not attrs['specialty'].strip():
                errors['specialty'] = 'Select a specialty.'
        if not attrs['payoutAccount'].strip():
            errors['payoutAccount'] = 'Payout account is required.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _build_references(self, attrs):
        refs = []
        for prefix in ('ref1', 'ref2'):
            item = {
                'name': attrs.get(f'{prefix}Name', '').strip(),
                'email': attrs.get(f'{prefix}Email', '').strip(),
                'phone': attrs.get(f'{prefix}Phone', '').strip(),
            }
            if any(item.values()):
                refs.append(item)
        return refs

    def _document_names(self, request, attrs):
        explicit = attrs.get('documentNames') or []
        uploaded = [file.name for file in request.FILES.getlist('documents')]
        return list(dict.fromkeys([*attrs.get('docChecklist', []), *explicit, *uploaded]))

    def _cv_names(self, request, attrs):
        explicit = attrs.get('cvNames') or []
        uploaded = [file.name for file in request.FILES.getlist('cv_files')]
        return list(dict.fromkeys([*explicit, *uploaded]))

    def _doctor_payload(self, attrs):
        consult_fee = attrs.get('fee')
        if consult_fee is None:
            consult_fee = 1500 if attrs['type'] == 'doctor' else 1200
        return {
            'name': attrs['name'].strip(),
            'type': attrs['type'],
            'specialty': attrs['specialty'].strip(),
            'email': attrs['email'],
            'phone': attrs['phone'].strip(),
            'license_number': attrs['license'].strip(),
            'license_board': attrs['licenseBoard'].strip(),
            'license_country': attrs['licenseCountry'].strip(),
            'license_expiry': attrs['licenseExpiry'],
            'id_number': attrs['idNumber'].strip(),
            'facility': attrs['facility'].strip() or 'Independent Practice',
            'availability': attrs['availability'].strip(),
            'bio': attrs['bio'].strip(),
            'languages': attrs.get('languages') or ['English'],
            'consult_modes': attrs.get('consultModes') or [],
            'consult_fee': consult_fee,
            'years_experience': attrs.get('experience'),
            'county': attrs['county'].strip(),
            'address': attrs['address'].strip(),
            'references': self._build_references(attrs),
            'document_checklist': attrs.get('docChecklist', []),
            'payout_method': attrs['payoutMethod'],
            'payout_account': attrs['payoutAccount'].strip(),
            'background_consent': attrs['backgroundConsent'],
            'compliance_declaration': attrs['complianceDeclaration'],
            'agreed_to_terms': attrs['agreedToTerms'],
        }

    def _lab_partner_payload(self, attrs):
        return {
            'name': attrs['labName'].strip(),
            'email': attrs['email'],
            'phone': attrs['phone'].strip(),
            'location': attrs['labLocation'].strip(),
            'contact_name': attrs['name'].strip(),
            'accreditation': attrs['labAccreditation'].strip(),
            'license_number': attrs['license'].strip(),
            'county': attrs['county'].strip(),
            'address': attrs['address'].strip(),
            'years_in_operation': attrs.get('experience'),
            'references': self._build_references(attrs),
            'document_checklist': attrs.get('docChecklist', []),
            'payout_method': attrs['payoutMethod'],
            'payout_account': attrs['payoutAccount'].strip(),
            'background_consent': attrs['backgroundConsent'],
            'compliance_declaration': attrs['complianceDeclaration'],
            'agreed_to_terms': attrs['agreedToTerms'],
            'notes': attrs['bio'].strip(),
        }

    def create(self, validated_data):
        request = self.context['request']
        documents = request.FILES.getlist('documents')
        cv_files = request.FILES.getlist('cv_files')
        document_names = self._document_names(request, validated_data)

        professional_type = validated_data['type']
        if professional_type in ('doctor', 'pediatrician'):
            payload = self._doctor_payload(validated_data)
            serializer_class = DoctorOnboardingSerializer if professional_type == 'doctor' else PediatricianOnboardingSerializer
            response_serializer = DoctorProfileSerializer if professional_type == 'doctor' else PediatricianProfileSerializer
            if professional_type == 'pediatrician':
                payload.pop('type', None)
            serializer = serializer_class(data={
                **payload,
                'documents': documents,
                'document_names': document_names,
                'cv_files': cv_files,
            }, context={'request': request})
            serializer.is_valid(raise_exception=True)
            application = serializer.save()
            self._response_serializer = response_serializer
            return application

        if professional_type == 'lab_partner':
            payload = self._lab_partner_payload(validated_data)
            serializer = LabPartnerRegistrationSerializer(data={
                **payload,
                'documents': documents,
                'document_names': document_names,
            }, context={'request': request})
            serializer.is_valid(raise_exception=True)
            application = serializer.save()
            self._response_serializer = LabPartnerSerializer
            return application

        raise serializers.ValidationError({'type': 'Select a valid professional type.'})

    def build_response(self, instance):
        serializer_class = getattr(self, '_response_serializer')
        registration_type = self.validated_data['type']
        return {
            'detail': 'Professional application submitted successfully.',
            'registration_type': registration_type,
            'registration_type_display': _professional_type_label(registration_type),
            'application': serializer_class(instance).data,
            'next_steps': [
                'Application received',
                'Document review within 24 to 48 hours',
                'Background and credentials check',
                'Onboarding call scheduling',
                'Profile activation on AVA Health',
            ],
        }


class PublicLabPartnerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = ('id', 'reference', 'name', 'location', 'accreditation')


class ProvisionProfessionalAccountSerializer(serializers.Serializer):
    # Kept optional for backward compatibility with older clients.
    # Provisioning now always uses activation-email password setup.
    password = serializers.CharField(write_only=True, required=False, allow_blank=False, validators=[validate_password])

    def _get_actor(self):
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        return actor if getattr(actor, 'is_authenticated', False) else None

    def _create_user(self, *, email, phone, full_name, role, address=''):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({'phone': 'A user with this phone number already exists.'})

        first_name, last_name = split_full_name(full_name)
        user = User.objects.create_user(
            email=email,
            password=None,
            first_name=first_name,
            last_name=last_name,
            phone=phone or '',
            role=role,
            address=address or '',
            status=User.STATUS_ACTIVE,
        )
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        return user

    def _issue_activation(self, user):
        actor = self._get_actor()
        request = self.context.get('request')
        token, raw_token = issue_pharmacist_activation_token(user, created_by=actor)
        send_pharmacist_activation_email(
            user=user,
            raw_token=raw_token,
            request=request,
            invited_by=actor,
        )
        self.activation_email_meta = {
            'sent_to': user.email,
            'expires_at': token.expires_at,
        }


class ProvisionDoctorAccountSerializer(ProvisionProfessionalAccountSerializer):
    def validate(self, attrs):
        doctor = self.context['doctor']
        if doctor.user_id:
            raise serializers.ValidationError({'detail': 'This application already has a linked user account.'})
        if doctor.status != 'active':
            raise serializers.ValidationError({'detail': 'Only approved doctor or pediatrician applications can be provisioned.'})
        return attrs

    def save(self, **kwargs):
        doctor = self.context['doctor']
        actor = self._get_actor()
        user = self._create_user(
            email=doctor.email,
            phone=doctor.phone,
            full_name=doctor.name,
            role=User.DOCTOR,
            address=doctor.address or doctor.county or '',
        )
        doctor.user = user
        doctor.updated_by = actor
        doctor.save(update_fields=['user', 'updated_by', 'updated_at'])
        self._issue_activation(user)
        return doctor, user, None


class ProvisionPediatricianAccountSerializer(ProvisionProfessionalAccountSerializer):
    def validate(self, attrs):
        pediatrician = self.context['pediatrician']
        if pediatrician.user_id:
            raise serializers.ValidationError({'detail': 'This application already has a linked user account.'})
        if pediatrician.status != 'active':
            raise serializers.ValidationError({'detail': 'Only approved pediatrician applications can be provisioned.'})
        return attrs

    def save(self, **kwargs):
        pediatrician = self.context['pediatrician']
        actor = self._get_actor()
        user = self._create_user(
            email=pediatrician.email,
            phone=pediatrician.phone,
            full_name=pediatrician.name,
            role=User.PEDIATRICIAN,
            address=pediatrician.address or pediatrician.county or '',
        )
        pediatrician.user = user
        pediatrician.updated_by = actor
        pediatrician.save(update_fields=['user', 'updated_by', 'updated_at'])
        self._issue_activation(user)
        return pediatrician, user, None


class ProvisionLabPartnerAccountSerializer(ProvisionProfessionalAccountSerializer):
    def validate(self, attrs):
        partner = self.context['partner']
        if partner.user_id:
            raise serializers.ValidationError({'detail': 'This lab partner already has a linked user account.'})
        if partner.status != 'verified':
            raise serializers.ValidationError({'detail': 'Only verified lab partner applications can be provisioned.'})
        return attrs

    def save(self, **kwargs):
        partner = self.context['partner']
        actor = self._get_actor()
        full_name = partner.contact_name or partner.name
        user = self._create_user(
            email=partner.email,
            phone=partner.phone,
            full_name=full_name,
            role=User.LAB_PARTNER,
            address=partner.address or partner.location,
        )
        partner.user = user
        partner.updated_by = actor
        partner.save(update_fields=['user', 'updated_by', 'updated_at'])
        self._issue_activation(user)
        return partner, user, None


class ProvisionLabTechnicianAccountSerializer(ProvisionProfessionalAccountSerializer):
    def validate(self, attrs):
        tech = self.context['tech']
        if tech.user_id:
            raise serializers.ValidationError({'detail': 'This lab technician application already has a linked user account.'})
        if tech.status != 'active':
            raise serializers.ValidationError({'detail': 'Only approved lab technician applications can be provisioned.'})
        if not tech.partner or tech.partner.status != 'verified':
            raise serializers.ValidationError({'detail': 'The linked lab partner must be verified before provisioning this account.'})
        return attrs

    def save(self, **kwargs):
        tech = self.context['tech']
        actor = self._get_actor()
        user = self._create_user(
            email=tech.email,
            phone=tech.phone,
            full_name=tech.name,
            role=User.LAB_TECHNICIAN,
            address=tech.address or tech.county,
        )
        tech.user = user
        tech.updated_by = actor
        tech.save(update_fields=['user', 'updated_by', 'updated_at'])
        self._issue_activation(user)
        return tech, user, None
