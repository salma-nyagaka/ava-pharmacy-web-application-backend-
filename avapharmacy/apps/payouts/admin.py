from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('reference', 'recipient_name', 'role', 'amount', 'method', 'status', 'requested_at')
    list_filter = ('role', 'method', 'status')
    search_fields = ('reference', 'recipient_name')
    readonly_fields = tuple(field.name for field in Payout._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
