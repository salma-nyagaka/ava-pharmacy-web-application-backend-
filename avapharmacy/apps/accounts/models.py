"""
Database models for the accounts app.

Defines the custom User model (email-based auth), Customer, Pharmacist,
Address, UserNote, and AdminAuditLog.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for the User model using email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password.

        Args:
            email: The user's email address (required, used as USERNAME_FIELD).
            password: Plain-text password; hashed before storage.
            **extra_fields: Additional model field values.

        Returns:
            User: The newly created user instance.

        Raises:
            ValueError: If ``email`` is not provided.
        """
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with admin role and full permissions.

        Args:
            email: The superuser's email address.
            password: Plain-text password.
            **extra_fields: Additional model field values.

        Returns:
            User: The newly created superuser instance.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('status', 'active')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model using email as the login identifier.

    Supports multiple roles (customer, admin, pharmacist, doctor, pediatrician,
    lab_partner, lab_technician, inventory_staff) and an active/suspended status.
    """

    CUSTOMER = 'customer'
    ADMIN = 'admin'
    PHARMACIST = 'pharmacist'
    DOCTOR = 'doctor'
    PEDIATRICIAN = 'pediatrician'
    LAB_PARTNER = 'lab_partner'
    LAB_TECHNICIAN = 'lab_technician'
    INVENTORY_STAFF = 'inventory_staff'

    ROLE_CHOICES = [
        (CUSTOMER, 'Customer'),
        (ADMIN, 'Admin'),
        (PHARMACIST, 'Pharmacist'),
        (DOCTOR, 'Doctor'),
        (PEDIATRICIAN, 'Pediatrician'),
        (LAB_PARTNER, 'Lab Partner'),
        (LAB_TECHNICIAN, 'Lab Technician'),
        (INVENTORY_STAFF, 'Inventory Staff'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'accounts_user'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['role', 'status']),
            models.Index(fields=['status', 'date_joined']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['phone'],
                condition=~Q(phone=''),
                name='unique_non_empty_user_phone',
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def save(self, *args, **kwargs):
        """Ensure admin-role users always have is_staff=True."""
        if self.role == self.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        """Return the user's full name as a single stripped string."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def total_orders(self):
        """Return the total number of orders placed by this user."""
        return self.orders.count()


class Pharmacist(models.Model):
    """Dedicated pharmacist table linked to auth users with pharmacist role."""

    PERMISSION_PRESCRIPTION_REVIEW = 'prescription_review'
    PERMISSION_DISPENSE_ORDERS = 'dispense_orders'
    PERMISSION_INVENTORY_ADD = 'inventory_add'
    PERMISSION_CHOICES = [
        (PERMISSION_PRESCRIPTION_REVIEW, 'Prescription review'),
        (PERMISSION_DISPENSE_ORDERS, 'Dispense orders'),
        (PERMISSION_INVENTORY_ADD, 'Add inventory records'),
    ]
    VALID_PERMISSIONS = {value for value, _label in PERMISSION_CHOICES}

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pharmacist')
    # JSON list of permission strings granted to this pharmacist
    permissions = models.JSONField(default=list)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_pharmacists'
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_pharmacists'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'accounts_pharmacist'

    def __str__(self):
        return f"Pharmacist: {self.user.full_name}"

    def clean(self):
        super().clean()
        self.permissions = [
            permission for permission in (self.permissions or [])
            if permission in self.VALID_PERMISSIONS
        ]

    def save(self, *args, **kwargs):
        self.permissions = [
            permission for permission in (self.permissions or [])
            if permission in self.VALID_PERMISSIONS
        ]
        super().save(*args, **kwargs)

    def has_permission(self, permission):
        return permission in (self.permissions or [])


class Customer(models.Model):
    """Dedicated customer table linked to auth users with customer role."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_customers'
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_customers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_customer'

    def __str__(self):
        return f"Customer: {self.user.full_name}"


class PharmacistActivationToken(models.Model):
    """One-time activation token used by pharmacist invite flow."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pharmacist_activation_tokens')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    sent_to = models.EmailField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_pharmacist_activation_tokens',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_pharmacist_activation_token'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['user', 'used_at']),
        ]

    def __str__(self):
        return f"PharmacistActivationToken(user={self.user_id}, expires_at={self.expires_at})"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_used(self):
        return self.used_at is not None


class Address(models.Model):
    """A saved delivery address belonging to a user."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, blank=True, default='Home')
    phone = models.CharField(max_length=20, blank=True)
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default addresses appear first, then by newest
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', '-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='unique_default_address_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.user.full_name} - {self.street}, {self.city}"


class PaymentMethod(models.Model):
    """A masked customer payment method saved for faster checkout."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    brand = models.CharField(max_length=30, blank=True, default='unknown')
    last4 = models.CharField(max_length=4)
    expiry_month = models.PositiveSmallIntegerField()
    expiry_year = models.PositiveSmallIntegerField()
    cardholder_name = models.CharField(max_length=120)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_default'], name='accounts_pa_user_id_738eaa_idx'),
            models.Index(fields=['user', '-updated_at'], name='accounts_pa_user_id_0e7c79_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='unique_default_payment_method_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.user.full_name} - {self.brand} ending {self.last4}"


class UserNote(models.Model):
    """An internal note written by an admin about a specific user."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_notes')
    content = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='authored_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Note for {self.user.full_name} at {self.created_at}"


class AdminAuditLog(models.Model):
    """Immutable audit log entry recording an admin action on an entity."""

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='admin_audit_logs'
    )
    action = models.CharField(max_length=80)       # e.g. "user_suspended"
    entity_type = models.CharField(max_length=80)  # e.g. "user"
    entity_id = models.CharField(max_length=80, blank=True)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"{self.action} - {self.entity_type}"
