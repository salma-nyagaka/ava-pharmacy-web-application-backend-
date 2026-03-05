from django.contrib import admin
from .models import (
    DoctorProfile, DoctorDocument, PediatricianProfile, PediatricianDocument,
    Consultation, ConsultationMessage,
    DoctorPrescription, PediatricianPrescription,
    DoctorEarning, PediatricianEarning,
)


class DoctorDocumentInline(admin.TabularInline):
    model = DoctorDocument
    extra = 0


class PediatricianDocumentInline(admin.TabularInline):
    model = PediatricianDocument
    extra = 0


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'specialty', 'status', 'rating', 'submitted_at')
    list_filter = ('type', 'status')
    search_fields = ('name', 'email', 'license_number')
    readonly_fields = ('reference', 'submitted_at', 'updated_at')
    inlines = [DoctorDocumentInline]


@admin.register(PediatricianProfile)
class PediatricianProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialty', 'status', 'rating', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('name', 'email', 'license_number')
    readonly_fields = ('reference', 'submitted_at', 'updated_at')
    inlines = [PediatricianDocumentInline]


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('reference', 'patient_name', 'doctor', 'pediatrician', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'is_pediatric')
    search_fields = ('reference', 'patient_name')
    readonly_fields = ('reference', 'created_at', 'updated_at')


@admin.register(DoctorPrescription)
class DoctorPrescriptionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'doctor', 'patient_name', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(PediatricianPrescription)
class PediatricianPrescriptionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'pediatrician', 'patient_name', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(DoctorEarning)
class DoctorEarningAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'amount', 'description', 'earned_at')


@admin.register(PediatricianEarning)
class PediatricianEarningAdmin(admin.ModelAdmin):
    list_display = ('pediatrician', 'amount', 'description', 'earned_at')
