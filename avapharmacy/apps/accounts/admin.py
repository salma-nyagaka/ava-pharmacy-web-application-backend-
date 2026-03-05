"""
Django admin registrations for the accounts app.

Registers User, Customer, Pharmacist, PharmacistActivationToken, Address, UserNote, and AdminAuditLog
with customised list displays, filters, and search configurations.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import AdminAuditLog, Customer, User, Pharmacist, PharmacistActivationToken, Address, UserNote


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'status', 'date_joined')
    list_filter = ('role', 'status', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'address')}),
        ('Role & Status', {'fields': ('role', 'status', 'is_active', 'is_staff', 'is_superuser')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


@admin.register(Pharmacist)
class PharmacistAdmin(admin.ModelAdmin):
    list_display = ('user', 'permissions', 'created_at', 'updated_at')


@admin.register(PharmacistActivationToken)
class PharmacistActivationTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sent_to', 'expires_at', 'used_at', 'created_at')
    list_filter = ('expires_at', 'used_at', 'created_at')
    search_fields = ('user__email', 'sent_to')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'street', 'city', 'county', 'is_default')
    list_filter = ('city', 'county', 'is_default')


@admin.register(UserNote)
class UserNoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'created_by', 'created_at')
    list_filter = ('created_at',)


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'entity_type', 'entity_id', 'created_at')
    list_filter = ('action', 'entity_type')
    search_fields = ('actor__email', 'entity_id', 'message')
