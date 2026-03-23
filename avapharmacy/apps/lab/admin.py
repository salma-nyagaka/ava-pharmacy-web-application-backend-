from django.contrib import admin
from .models import LabTest, LabRequest, LabAuditLog, LabResult


class LabAuditLogInline(admin.TabularInline):
    model = LabAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'timestamp')


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'turnaround', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'reference')
    readonly_fields = ('reference', 'created_at')


@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'patient_name', 'test', 'status', 'payment_status', 'priority', 'requested_at')
    list_filter = ('status', 'payment_status', 'priority', 'channel')
    search_fields = ('reference', 'patient_name', 'patient_phone')
    readonly_fields = ('reference', 'requested_at', 'updated_at')
    inlines = [LabAuditLogInline]


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ('reference', 'request', 'is_abnormal', 'reviewed_by', 'uploaded_at')
    list_filter = ('is_abnormal',)
    readonly_fields = ('reference', 'uploaded_at')
