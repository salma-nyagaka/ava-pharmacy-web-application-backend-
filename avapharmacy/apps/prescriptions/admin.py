from django.contrib import admin
from .models import Prescription, PrescriptionFile, PrescriptionItem, PrescriptionAuditLog


class PrescriptionFileInline(admin.TabularInline):
    model = PrescriptionFile
    extra = 0


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 0
    autocomplete_fields = ('product',)


class PrescriptionAuditLogInline(admin.TabularInline):
    model = PrescriptionAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'timestamp')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'patient_name', 'status', 'dispatch_status', 'submitted_at')
    list_filter = ('status', 'dispatch_status')
    search_fields = ('reference', 'patient_name', 'doctor_name')
    readonly_fields = ('reference', 'submitted_at', 'updated_at')
    inlines = [PrescriptionFileInline, PrescriptionItemInline, PrescriptionAuditLogInline]


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ('prescription', 'name', 'product', 'quantity')
    list_select_related = ('prescription', 'product')
    search_fields = ('prescription__reference', 'name', 'product__name', 'product__sku')
    autocomplete_fields = ('product',)
