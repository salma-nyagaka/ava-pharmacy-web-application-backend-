from django.contrib import admin
from .models import Notification, NotificationDelivery, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'type', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('recipient__email', 'title', 'message')
    readonly_fields = ('created_at',)
    actions = ['mark_all_read']

    def mark_all_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_all_read.short_description = 'Mark selected as read'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_enabled', 'sms_enabled', 'push_enabled', 'updated_at')
    list_filter = ('email_enabled', 'sms_enabled', 'push_enabled')
    search_fields = ('user__email',)


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'channel', 'destination', 'status', 'provider', 'sent_at', 'created_at')
    list_filter = ('channel', 'status', 'provider')
    search_fields = ('recipient__email', 'destination', 'provider_reference')
