from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('reference', 'recipient_name', 'role', 'amount', 'method', 'status', 'requested_at')
    list_filter = ('role', 'method', 'status')
    search_fields = ('reference', 'recipient_name')
    readonly_fields = ('reference', 'requested_at')
