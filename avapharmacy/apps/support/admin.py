from django.contrib import admin
from .checks import REQUIRED_COMPLIANCE_FIELDS, _is_missing
from .models import NewsletterSubscriber, SiteSettings, SupportTicket, SupportNote


class SupportNoteInline(admin.TabularInline):
    model = SupportNote
    extra = 0


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'support_email', 'support_phone', 'compliance_status',
        'base_delivery_fee', 'free_delivery_threshold', 'updated_at',
    )
    readonly_fields = ('compliance_status', 'updated_at')
    fieldsets = (
        ('Support', {
            'fields': (
                'support_email', 'support_phone', 'whatsapp_phone',
                'support_address', 'support_hours', 'postal_address',
            ),
        }),
        ('Pharmacy Compliance', {
            'fields': (
                'compliance_status', 'health_safety_code', 'premises_registration_number',
                'online_pharmacy_license_number', 'superintendent_name',
                'superintendent_registration_number', 'pharmacist_consultation_hours',
            ),
        }),
        ('PPB Contact', {
            'fields': (
                'ppb_contact_name', 'ppb_contact_address', 'ppb_contact_phone',
                'ppb_contact_email', 'ppb_website',
            ),
        }),
        ('Policies', {
            'fields': ('complaint_policy_url', 'privacy_policy_url', 'returns_policy_url'),
        }),
        ('Delivery', {
            'fields': ('base_delivery_fee', 'free_delivery_threshold', 'active_delivery_zones'),
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
        }),
    )

    @admin.display(description='Compliance readiness')
    def compliance_status(self, obj):
        missing = [
            label
            for field, label in REQUIRED_COMPLIANCE_FIELDS.items()
            if _is_missing(getattr(obj, field, ''))
        ]
        if not missing:
            return 'Ready'
        return f'Missing: {", ".join(missing)}'

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'source', 'is_active', 'subscribed_at', 'last_confirmation_sent_at')
    list_filter = ('is_active', 'source')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at', 'last_confirmation_sent_at')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer_name', 'channel', 'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('channel', 'priority', 'status')
    search_fields = ('reference', 'customer_name', 'customer_email', 'subject')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    inlines = [SupportNoteInline]


@admin.register(SupportNote)
class SupportNoteAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'author_name', 'created_at')
