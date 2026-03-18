from django.contrib import admin

from .models import (
    ClinicianDocument,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
)


class ClinicianDocumentInline(admin.TabularInline):
    model = ClinicianDocument
    extra = 0


@admin.register(ClinicianProfile)
class ClinicianProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'specialty', 'status', 'rating', 'submitted_at')
    list_filter = ('provider_type', 'status')
    search_fields = ('name', 'email', 'license_number', 'reference')
    readonly_fields = ('reference', 'submitted_at', 'created_at', 'updated_at')
    inlines = [ClinicianDocumentInline]


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('reference', 'patient_name', 'clinician', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'is_pediatric')
    search_fields = ('reference', 'patient_name', 'issue')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    autocomplete_fields = ('clinician', 'patient')


@admin.register(ConsultationMessage)
class ConsultationMessageAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'sender_name', 'sent_at')
    list_filter = ('sent_at',)
    search_fields = ('consultation__reference', 'sender_name', 'message')
    autocomplete_fields = ('consultation', 'sender')


@admin.register(ClinicianPrescription)
class ClinicianPrescriptionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'clinician', 'patient_name', 'status', 'created_at')
    list_filter = ('status', 'clinician__provider_type')
    search_fields = ('reference', 'patient_name', 'clinician__name')
    autocomplete_fields = ('clinician', 'consultation')


@admin.register(ClinicianEarning)
class ClinicianEarningAdmin(admin.ModelAdmin):
    list_display = ('clinician', 'amount', 'description', 'earned_at')
    list_filter = ('clinician__provider_type',)
    search_fields = ('clinician__name', 'description')
    autocomplete_fields = ('clinician', 'consultation')
