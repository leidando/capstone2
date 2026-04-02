from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Public Pages
    path('', views.landing_page, name='landing'),

    # User Views
    path('home/', views.home_redirect, name='home'),
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    path('user/submit-beneficiary/', views.submit_beneficiary, name='submit_beneficiary'),
    path('user/request-assistance/', views.request_assistance, name='request_assistance'),

    # Staff Views
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/requests/<int:pk>/', views.staff_request_detail, name='staff_request_detail'),
    path('staff/requests/<int:pk>/update/', views.staff_request_update_status, name='staff_request_update_status'),
    path('staff/documents/<int:pk>/verify/', views.staff_document_verify, name='staff_document_verify'),

    # Admin Views
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/insights/', views.admin_insights, name='admin_insights'),
    path('admin/beneficiaries/', views.beneficiary_list, name='beneficiary_list'),
    path('admin/beneficiaries/<int:pk>/edit/', views.beneficiary_edit, name='beneficiary_edit'),
    path('admin/beneficiaries/<int:pk>/approve/', views.beneficiary_approve, name='beneficiary_approve'),
    path('admin/beneficiaries/<int:pk>/delete/', views.beneficiary_delete, name='beneficiary_delete'),
    path('admin/requests/', views.request_list, name='request_list'),
    path('admin/requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('admin/requests/<int:pk>/update/', views.request_update_status, name='request_update_status'),
    path('admin/documents/<int:pk>/verify/', views.document_verify, name='document_verify'),
    path('admin/programs/', views.program_list, name='program_list'),
    path('admin/programs/add/', views.program_add, name='program_add'),
    path('admin/programs/<int:pk>/edit/', views.program_edit, name='program_edit'),
    path('admin/programs/<int:pk>/delete/', views.program_delete, name='program_delete'),
    path('programs/<int:pk>/', views.program_detail, name='program_detail'),

    # Staff Management (Admin)
    path('admin/staff/', views.staff_management, name='staff_management'),
    path('admin/staff/create/', views.staff_create, name='staff_create'),
    path('admin/staff/<int:pk>/toggle/', views.staff_toggle_active, name='staff_toggle_active'),
    path('admin/staff/<int:pk>/programs/', views.staff_edit_programs, name='staff_edit_programs'),
    path('admin/staff/logs/', views.staff_activity_log, name='staff_activity_log_all'),
    path('admin/staff/<int:pk>/logs/', views.staff_activity_log, name='staff_activity_log'),

    # Barangay Details
    path('barangay/<int:pk>/', views.barangay_detail, name='barangay_detail'),

    # Report Generation
    path('admin/reports/barangay/', views.export_barangay_report, name='export_barangay_report'),
    path('admin/reports/program/', views.export_program_report, name='export_program_report'),
    path('admin/reports/barangay/pdf/', views.export_barangay_report_pdf, name='export_barangay_report_pdf'),
    path('admin/reports/program/pdf/', views.export_program_report_pdf, name='export_program_report_pdf'),

    # Geospatial Mapping
    path('map/', views.map_view, name='map'),

    # API Endpoints (JSON)
    path('api/map-data/', views.api_map_data, name='api_map_data'),
    path('api/gap-data/', views.api_gap_data, name='api_gap_data'),
    path('api/program/<int:pk>/documents/', views.api_program_documents, name='api_program_documents'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
