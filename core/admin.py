from django.contrib import admin
from .models import (
    Barangay, Program, ProgramRequiredDocument, UserProfile,
    Beneficiary, AssistanceRequest, ApplicationDocument,
)


class ProgramRequiredDocumentInline(admin.TabularInline):
    model = ProgramRequiredDocument
    extra = 1


class ApplicationDocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude', 'population')
    search_fields = ('name',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'transaction_type', 'is_active', 'created_at')
    list_filter = ('is_active',)
    inlines = [ProgramRequiredDocumentInline]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'barangay', 'phone')
    list_filter = ('role',)


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'age', 'gender', 'barangay', 'status', 'created_at')
    list_filter = ('status', 'barangay', 'gender')
    search_fields = ('full_name',)


@admin.register(AssistanceRequest)
class AssistanceRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'program', 'barangay', 'status', 'date_submitted')
    list_filter = ('status', 'program')
    inlines = [ApplicationDocumentInline]


@admin.register(ProgramRequiredDocument)
class ProgramRequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_name', 'program', 'category', 'description', 'is_required', 'order')
    list_filter = ('program',)


@admin.register(ApplicationDocument)
class ApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ('required_document', 'request', 'status', 'uploaded_at')
    list_filter = ('status',)
