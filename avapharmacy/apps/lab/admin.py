from django.contrib import admin
from .models import (
    LabTest, LaboratoryFacility, FacilityLabTest, LaboratoryFacilityDocument,
    LabRequest, LabAuditLog, LabResult,
)


class LabAuditLogInline(admin.TabularInline):
    model = LabAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'timestamp')


class FacilityLabTestInline(admin.TabularInline):
    model = FacilityLabTest
    extra = 0


class LaboratoryFacilityDocumentInline(admin.TabularInline):
    model = LaboratoryFacilityDocument
    extra = 0


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'turnaround', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'reference')
    readonly_fields = ('reference', 'created_at')


@admin.register(LaboratoryFacility)
class LaboratoryFacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner', 'county', 'status', 'home_collection_enabled', 'is_active')
    list_filter = ('status', 'county', 'home_collection_enabled', 'physical_result_pickup_enabled', 'is_active')
    search_fields = ('name', 'reference', 'partner__name', 'license_number', 'address')
    readonly_fields = ('reference', 'submitted_at', 'updated_at', 'verified_at')
    filter_horizontal = ('technicians',)
    inlines = [FacilityLabTestInline, LaboratoryFacilityDocumentInline]


@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'patient_name', 'test', 'channel',
        'assigned_partner', 'laboratory', 'assigned_pharmacist', 'assigned_technician',
        'status', 'payment_status', 'priority', 'requested_at',
    )
    list_filter = (
        'status', 'payment_status', 'priority', 'channel',
        'result_delivery_method', 'assigned_partner', 'laboratory',
    )
    search_fields = (
        'reference', 'patient_name', 'patient_phone',
        'collection_address', 'assigned_partner__name', 'laboratory__name',
    )
    readonly_fields = ('reference', 'requested_at', 'updated_at')
    inlines = [LabAuditLogInline]


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ('reference', 'request', 'is_abnormal', 'reviewed_by', 'uploaded_at')
    list_filter = ('is_abnormal',)
    readonly_fields = ('reference', 'uploaded_at')
