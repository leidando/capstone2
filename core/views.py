import json
import csv
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from .models import (
    Barangay, Program, ProgramRequiredDocument, UserProfile,
    Beneficiary, AssistanceRequest, ApplicationDocument,
    StaffProfile, StaffActivityLog,
    ScheduledTransaction, ServiceHistory, Notification,
)
from .forms import (
    RegistrationForm, LoginForm, BeneficiaryForm,
    AssistanceRequestForm, ProgramForm, BeneficiaryAdminForm,
    StaffCreationForm, ScheduledTransactionForm, RescheduleRequestForm,
)
from .insights import generate_all_insights


# Decorators

def admin_required(view_func):
    """Only allow users with admin role."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_admin):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('home')
    return wrapper


def staff_required(view_func):
    """Only allow users with staff role."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_staff_role:
            messages.error(request, 'Access denied. Staff privileges required.')
            return redirect('home')
        # Check staff profile is active
        if not hasattr(request.user, 'staff_profile') or not request.user.staff_profile.is_active:
            messages.error(request, 'Your staff account has been deactivated. Contact an administrator.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_or_admin_required(view_func):
    """Allow staff OR admin."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if hasattr(request.user, 'profile'):
            if request.user.profile.is_admin or request.user.profile.is_staff_role:
                return view_func(request, *args, **kwargs)
        messages.error(request, 'Access denied.')
        return redirect('home')
    return wrapper


# Authentication

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )
            UserProfile.objects.create(
                user=user,
                role='user',
                barangay=form.cleaned_data['barangay'],
                phone=form.cleaned_data.get('phone', ''),
            )
            login(request, user)
            messages.success(request, 'Registration successful! Welcome.')
            return redirect('user_dashboard')
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


def landing_page(request):
    """Public landing page — no login required."""
    if request.user.is_authenticated:
        return redirect('home')

    # Basic stats
    from .models import Program, Beneficiary, Barangay, AssistanceRequest
    programs = Program.objects.filter(is_active=True).order_by('id')[:8]
    total_beneficiaries = Beneficiary.objects.filter(status='approved').count()
    total_barangays = Barangay.objects.count()
    total_requests = AssistanceRequest.objects.count()
    fulfilled_requests = AssistanceRequest.objects.filter(status='approved').count()

    # Calculate quarterly growth over the last 4 quarters
    now = timezone.now()
    growth_data = []
    for i in range(3, -1, -1):
        start_month = now.month - (i * 3)
        # Handle year wrap-around if necessary, but for simplicity:
        q_start = now - timezone.timedelta(days=i*90)
        q_end = q_start + timezone.timedelta(days=90)
        count = AssistanceRequest.objects.filter(date_submitted__range=(q_start, q_end)).count()
        growth_data.append(count)
    
    max_growth = max(growth_data) if growth_data and max(growth_data) > 0 else 100
    growth_percentages = [(c / max_growth) * 100 for c in growth_data]

    barangays = Barangay.objects.all()
    map_data = []
    for b in barangays:
        if b.latitude and b.longitude:
            map_data.append({
                'name': b.name,
                'lat': float(b.latitude),
                'lng': float(b.longitude),
                'count': Beneficiary.objects.filter(barangay=b, status='approved').count()
            })

    context = {
        'programs': programs,
        'total_beneficiaries': total_beneficiaries,
        'total_barangays': total_barangays,
        'total_requests': total_requests,
        'fulfilled_requests': fulfilled_requests,
        'growth_percentages': growth_percentages,
        'map_data_json': json.dumps(map_data),
        'growth_total': sum(growth_data),
    }

    return render(request, 'landing.html', context)


@login_required
def home_redirect(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    
    if hasattr(request.user, 'profile'):
        if request.user.profile.is_admin:
            return redirect('admin_dashboard')
        elif request.user.profile.is_staff_role or request.user.is_staff:
            return redirect('staff_dashboard')
            
    return redirect('user_dashboard')


# User Views

@login_required
def user_dashboard(request):
    my_requests = AssistanceRequest.objects.filter(
        user=request.user
    ).select_related('program', 'barangay', 'schedule')

    # Retrieve the user's beneficiary profile
    beneficiary_profile = Beneficiary.objects.filter(
        user=request.user
    ).select_related('barangay').first()
    has_approved_profile = beneficiary_profile and beneficiary_profile.status == 'approved'

    # Upcoming appointment
    upcoming_appointment = None
    service_history_count = 0
    recent_history = []
    if beneficiary_profile:
        today = timezone.localdate()
        upcoming_appointment = ScheduledTransaction.objects.filter(
            beneficiary=beneficiary_profile,
            schedule_date__gte=today,
            status__in=['scheduled', 'approved', 'pending'],
        ).select_related('program', 'barangay').order_by('schedule_date').first()

        history_qs = ServiceHistory.objects.filter(
            beneficiary=beneficiary_profile
        ).select_related('program').order_by('-created_at')
        service_history_count = history_qs.count()
        recent_history = list(history_qs[:3])

    return render(request, 'user_dashboard.html', {
        'requests': my_requests,
        'beneficiary_profile': beneficiary_profile,
        'has_approved_profile': has_approved_profile,
        'upcoming_appointment': upcoming_appointment,
        'service_history_count': service_history_count,
        'recent_history': recent_history,
    })


@login_required
def submit_beneficiary(request):
    existing_profile = Beneficiary.objects.filter(user=request.user).first()

    if existing_profile and existing_profile.status == 'approved':
        messages.warning(request, 'Your profile is already approved. You cannot edit it.')
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = BeneficiaryForm(request.POST, instance=existing_profile)
        if form.is_valid():
            ben = form.save(commit=False)
            ben.user = request.user
            
            if existing_profile and existing_profile.status == 'rejected':
                ben.status = 'pending'
            elif not existing_profile:
                ben.status = 'pending'
            ben.save()

            if existing_profile:
                messages.success(request, 'Profile updated successfully. Please wait for admin verification.')
            else:
                messages.success(request, 'Beneficiary profile submitted and is pending verification.')

            return redirect('user_dashboard')
    else:
        form = BeneficiaryForm(instance=existing_profile)

    context = {
        'form': form,
        'is_edit': existing_profile is not None
    }
    return render(request, 'submit_beneficiary.html', context)


@login_required
def request_assistance(request):
    # Check if user has an approved beneficiary profile
    approved_profile = Beneficiary.objects.filter(user=request.user, status='approved').first()
    if not approved_profile:
        messages.error(request, 'You must have an approved beneficiary profile before requesting assistance.')
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = AssistanceRequestForm(request.POST, request.FILES)
        if form.is_valid():
            req = form.save(commit=False)
            req.user = request.user
            req.beneficiary = approved_profile

            selected_category = request.POST.get('selected_category', '')
            req.selected_category = selected_category
            req.save()

            program = req.program
            required_docs = program.required_documents.all()

            if selected_category:
                required_docs = [rd for rd in required_docs if rd.category == selected_category or rd.category == '']

            for rd in required_docs:
                file_key = f'doc_{rd.pk}'
                uploaded_file = request.FILES.get(file_key)
                ApplicationDocument.objects.create(
                    request=req,
                    required_document=rd,
                    file=uploaded_file,
                    status='pending' if uploaded_file else 'missing',
                )

            messages.success(request, 'Assistance request submitted. You can track its status on your dashboard.')
            return redirect('user_dashboard')
    else:
        form = AssistanceRequestForm()
    return render(request, 'request_assistance.html', {'form': form})


# Staff Views

@staff_required
def staff_dashboard(request):
    """Staff dashboard — shows only data for assigned programs."""
    staff_profile = request.user.staff_profile
    assigned_programs = staff_profile.assigned_programs.all()
    program_ids = assigned_programs.values_list('id', flat=True)

    requests_qs = AssistanceRequest.objects.filter(
        program_id__in=program_ids
    ).select_related('user', 'program', 'barangay', 'beneficiary')

    pending_qs = requests_qs.filter(status__in=['submitted', 'under_review'])
    approved_count = requests_qs.filter(status='approved').count()
    rejected_count = requests_qs.filter(status='rejected').count()

    req_search = request.GET.get('req_search', '')
    if req_search:
        pending_qs = pending_qs.filter(
            Q(user__first_name__icontains=req_search) |
            Q(user__last_name__icontains=req_search) |
            Q(program__name__icontains=req_search) |
            Q(barangay__name__icontains=req_search)
        )

    # Paginate pending requests
    pending_paginator = Paginator(pending_qs.order_by('-date_submitted'), 10)
    pending_page = pending_paginator.get_page(request.GET.get('req_page'))

    # Beneficiaries under assigned programs
    beneficiary_ids = requests_qs.values_list('beneficiary_id', flat=True).distinct()
    bens_qs = Beneficiary.objects.filter(
        id__in=beneficiary_ids, status='approved'
    ).select_related('barangay')

    # Search for beneficiaries
    ben_search = request.GET.get('ben_search', '')
    if ben_search:
        bens_qs = bens_qs.filter(
            Q(full_name__icontains=ben_search) |
            Q(barangay__name__icontains=ben_search)
        )

    # Paginate beneficiaries
    ben_paginator = Paginator(bens_qs.order_by('-vulnerability_score'), 10)
    ben_page = ben_paginator.get_page(request.GET.get('ben_page'))

    # Today's schedules for assigned programs
    today = timezone.localdate()
    today_schedules = ScheduledTransaction.objects.filter(
        program_id__in=program_ids,
        schedule_date=today,
    ).select_related('beneficiary', 'program').order_by('time_slot')

    reschedule_requests = ScheduledTransaction.objects.filter(
        program_id__in=program_ids,
        reschedule_requested=True,
    ).select_related('beneficiary', 'program').order_by('-updated_at')

    return render(request, 'staff_dashboard.html', {
        'assigned_programs': assigned_programs,
        'pending_requests': pending_page,
        'pending_count': pending_qs.count(),
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'total_requests': requests_qs.count(),
        'beneficiaries': ben_page,
        'req_search': req_search,
        'ben_search': ben_search,
        'today_schedules': today_schedules[:5],
        'today_schedules_count': today_schedules.count(),
        'reschedule_requests_count': reschedule_requests.count(),
    })


@staff_required
def staff_request_detail(request, pk):
    """Staff can view request details for their assigned programs."""
    staff_profile = request.user.staff_profile
    program_ids = staff_profile.assigned_programs.values_list('id', flat=True)

    req_obj = get_object_or_404(
        AssistanceRequest.objects.select_related('user', 'program', 'barangay', 'beneficiary'),
        pk=pk, program_id__in=program_ids,
    )
    app_docs = req_obj.application_documents.select_related('required_document').all()
    total_docs = app_docs.count()
    uploaded_docs = app_docs.exclude(file='').exclude(file__isnull=True).count()
    verified_docs = app_docs.filter(status='verified').count()
    is_complete = total_docs > 0 and uploaded_docs == total_docs
    all_verified = total_docs > 0 and verified_docs == total_docs

    # Log view action
    StaffActivityLog.objects.create(
        staff=request.user, action='view',
        target_type='AssistanceRequest', target_id=pk,
        description=f'Viewed request #{pk} for {req_obj.program.name}',
    )

    return render(request, 'request_detail.html', {
        'req': req_obj,
        'app_docs': app_docs,
        'total_docs': total_docs,
        'uploaded_docs': uploaded_docs,
        'verified_docs': verified_docs,
        'is_complete': is_complete,
        'all_verified': all_verified,
        'is_staff_view': True,
    })


@staff_required
def staff_request_update_status(request, pk):
    """Staff can approve/reject requests for their assigned programs."""
    staff_profile = request.user.staff_profile
    program_ids = staff_profile.assigned_programs.values_list('id', flat=True)

    req = get_object_or_404(AssistanceRequest, pk=pk, program_id__in=program_ids)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('admin_notes', '')
        if new_status in ['under_review', 'approved', 'rejected']:
            # Block approval if docs are incomplete
            if new_status == 'approved':
                total = req.application_documents.count()
                uploaded = req.uploaded_count
                if total > 0 and uploaded < total:
                    messages.error(
                        request,
                        f'Cannot approve — only {uploaded}/{total} documents uploaded.'
                    )
                    return redirect('staff_dashboard')

            req.status = new_status
            req.admin_notes = notes
            req.save()

            # Update beneficiary's last_assistance_date on approval
            if new_status == 'approved' and req.beneficiary:
                req.beneficiary.last_assistance_date = timezone.now()
                req.beneficiary.save()

            # Log the action
            action = 'approve' if new_status == 'approved' else 'reject' if new_status == 'rejected' else 'review'
            StaffActivityLog.objects.create(
                staff=request.user, action=action,
                target_type='AssistanceRequest', target_id=pk,
                description=f'{action.title()}d request #{pk} for {req.program.name}',
            )

            messages.success(request, f'Request #{pk} updated to {new_status}.')
    return redirect('staff_dashboard')


@staff_required
def staff_document_verify(request, pk):
    """Staff action to verify or reject a single uploaded document."""
    doc = get_object_or_404(ApplicationDocument, pk=pk)
    # Verify staff has access to this program
    staff_profile = request.user.staff_profile
    program_ids = staff_profile.assigned_programs.values_list('id', flat=True)
    if doc.request.program_id not in program_ids:
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        admin_note = request.POST.get('admin_note', '')
        if new_status in ['verified', 'rejected', 'pending']:
            doc.status = new_status
            doc.admin_note = admin_note
            doc.save()
            messages.success(request, f'Document "{doc.required_document.document_name}" marked as {new_status}.')
    return redirect('staff_request_detail', pk=doc.request.pk)


# Admin Views

@admin_required
def admin_dashboard(request):
    total_beneficiaries = Beneficiary.objects.filter(status='approved').count()
    total_requests = AssistanceRequest.objects.count()
    pending_requests = AssistanceRequest.objects.filter(status='submitted').count()
    total_programs = Program.objects.filter(is_active=True).count()

    high_risk_count = Beneficiary.objects.filter(
        status='approved', vulnerability_level__in=['high', 'critical']
    ).count()

    # Population stats (only counting approved beneficiaries)
    total_population = Barangay.objects.aggregate(total=Sum('population'))['total'] or 0
    coverage_rate = round((total_beneficiaries / total_population * 100), 2) if total_population else 0

    # Charts data
    program_data = list(
        AssistanceRequest.objects.values('program__name')
        .annotate(count=Count('id'))
        .order_by('program__name')
    )
    barangay_data = list(
        Beneficiary.objects.filter(status='approved').values('barangay__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:15]
    )
    gender_data = list(
        Beneficiary.objects.filter(status='approved').values('gender')
        .annotate(count=Count('id'))
    )

    from django.db.models import Case, When, CharField, Value
    age_groups = list(
        Beneficiary.objects.annotate(
            age_group=Case(
                When(age__lte=17, then=Value('0-17')),
                When(age__lte=30, then=Value('18-30')),
                When(age__lte=50, then=Value('31-50')),
                When(age__lte=65, then=Value('51-65')),
                default=Value('65+'),
                output_field=CharField(),
            )
        ).values('age_group').annotate(count=Count('id')).order_by('age_group')
    )

    # Identify top 5 vulnerable barangays
    vulnerable_barangays = list(
        Barangay.objects.annotate(
            avg_vuln=Avg('beneficiaries__vulnerability_score',
                         filter=Q(beneficiaries__status='approved')),
            ben_count=Count('beneficiaries', filter=Q(beneficiaries__status='approved')),
            high_risk=Count('beneficiaries',
                            filter=Q(beneficiaries__status='approved',
                                     beneficiaries__vulnerability_level__in=['high', 'critical'])),
        ).filter(avg_vuln__isnull=False, ben_count__gt=0)
        .order_by('-avg_vuln')[:5]
    )

    # Identify service gap areas
    service_gap_areas = list(
        Barangay.objects.annotate(
            total_bens=Count('beneficiaries', filter=Q(beneficiaries__status='approved')),
            total_services=Count('requests', filter=Q(requests__status='approved')),
        ).filter(total_bens__gt=0)
        .order_by('-total_bens')[:5]
    )
    for area in service_gap_areas:
        area.sgi = round(area.total_bens / max(area.total_services, 1), 2)

    # Analyze program effectiveness
    program_effectiveness = list(
        Program.objects.filter(is_active=True).annotate(
            total_reqs=Count('requests'),
            approved_reqs=Count('requests', filter=Q(requests__status='approved')),
        ).filter(total_reqs__gt=0).order_by('-total_reqs')[:10]
    )
    for p in program_effectiveness:
        p.effectiveness = round((p.approved_reqs / max(p.total_reqs, 1)) * 100, 1)

    # Scheduled Transaction Stats
    today = timezone.localdate()
    today_schedules = ScheduledTransaction.objects.filter(
        schedule_date=today
    ).select_related('beneficiary', 'program')
    
    reschedule_requests = ScheduledTransaction.objects.filter(
        reschedule_requested=True
    ).select_related('beneficiary', 'program').order_by('-updated_at')

    total_schedules = ScheduledTransaction.objects.count()
    completed_schedules = ScheduledTransaction.objects.filter(status='completed').count()

    # Generate system insights
    insights = generate_all_insights()

    return render(request, 'admin_dashboard.html', {
        'total_beneficiaries': total_beneficiaries,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'total_programs': total_programs,
        'high_risk_count': high_risk_count,
        'total_population': total_population,
        'coverage_rate': coverage_rate,
        'program_data': json.dumps(program_data),
        'barangay_data': json.dumps(barangay_data),
        'gender_data': json.dumps(gender_data),
        'age_groups': json.dumps(age_groups),
        'vulnerable_barangays': vulnerable_barangays,
        'service_gap_areas': service_gap_areas,
        'program_effectiveness': program_effectiveness,
        'today_schedules': today_schedules[:5],
        'today_schedules_count': today_schedules.count(),
        'reschedule_requests': reschedule_requests[:5],
        'reschedule_requests_count': reschedule_requests.count(),
        'total_schedules': total_schedules,
        'completed_schedules': completed_schedules,
        'insights': insights,
    })


@admin_required
def admin_insights(request):
    """Dedicated page for viewing all system insights separated by category."""
    insights = generate_all_insights()
    high_conc = [i for i in insights if i['type'] == 'high_concentration']
    prog_gaps = [i for i in insights if i['type'] == 'program_gap']
    pop_gaps = [i for i in insights if i['type'] == 'population_gap']
    vuln_hotspots = [i for i in insights if i['type'] == 'vulnerability_hotspot']
    service_gaps = [i for i in insights if i['type'] == 'service_gap']
    overloaded = [i for i in insights if i['type'] == 'overloaded_program']
    elderly = [i for i in insights if i['type'] == 'elderly_vulnerability']

    return render(request, 'insights.html', {
        'high_concentration': high_conc,
        'program_gaps': prog_gaps,
        'population_gaps': pop_gaps,
        'vulnerability_hotspots': vuln_hotspots,
        'service_gaps': service_gaps,
        'overloaded_programs': overloaded,
        'elderly_vulnerability': elderly,
        'total_insights': len(insights),
    })


@admin_required
def beneficiary_list(request):
    qs = Beneficiary.objects.select_related('barangay').all()
    search = request.GET.get('search', '')
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(barangay__name__icontains=search)
        )
    barangay_filter = request.GET.get('barangay', '')
    if barangay_filter:
        qs = qs.filter(barangay__id=barangay_filter)
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    vuln_filter = request.GET.get('vulnerability', '')
    if vuln_filter:
        qs = qs.filter(vulnerability_level=vuln_filter)

    # Apply sorting criteria
    sort = request.GET.get('sort', '-created_at')
    valid_sorts = {
        'name_asc': 'full_name',
        'name_desc': '-full_name',
        'date_asc': 'created_at',
        'date_desc': '-created_at',
        'vuln_asc': 'vulnerability_score',
        'vuln_desc': '-vulnerability_score',
    }
    if sort in valid_sorts:
        qs = qs.order_by(valid_sorts[sort])
    else:
        qs = qs.order_by('-created_at')

    # Calculate summary statistics
    total_count = qs.count()
    high_risk_count = qs.filter(vulnerability_level__in=['critical', 'high']).count()
    moderate_count = qs.filter(vulnerability_level='medium').count()
    low_count = qs.filter(vulnerability_level='low').count()

    # Apply pagination
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Convert filter types for template comparison
    try:
        selected_barangay_id = int(barangay_filter) if barangay_filter else None
    except (ValueError, TypeError):
        selected_barangay_id = None

    return render(request, 'beneficiary_list.html', {
        'page_obj': page_obj,
        'barangays': Barangay.objects.all(),
        'search': search,
        'selected_barangay': selected_barangay_id,
        'status_filter': status_filter,
        'vuln_filter': vuln_filter,
        'sort': sort,
        # Summary stats
        'total_count': total_count,
        'high_risk_count': high_risk_count,
        'moderate_count': moderate_count,
        'low_count': low_count,
    })


@admin_required
def beneficiary_edit(request, pk):
    ben = get_object_or_404(Beneficiary, pk=pk)
    if request.method == 'POST':
        form = BeneficiaryAdminForm(request.POST, instance=ben)
        if form.is_valid():
            form.save()
            messages.success(request, 'Beneficiary updated.')
            return redirect('beneficiary_list')
    else:
        form = BeneficiaryAdminForm(instance=ben)
    return render(request, 'beneficiary_edit.html', {'form': form, 'beneficiary': ben})


@admin_required
def beneficiary_approve(request, pk):
    ben = get_object_or_404(Beneficiary, pk=pk)
    if request.method == 'POST':
        ben.status = 'approved'
        ben.save()
        messages.success(request, f'Beneficiary {ben.full_name} has been approved.')
    return redirect('beneficiary_list')


@admin_required
def beneficiary_delete(request, pk):
    ben = get_object_or_404(Beneficiary, pk=pk)
    if request.method == 'POST':
        ben.delete()
        messages.success(request, 'Beneficiary deleted.')
    return redirect('beneficiary_list')


@admin_required
def request_list(request):
    qs = AssistanceRequest.objects.select_related('user', 'program', 'barangay').prefetch_related('application_documents').all()
    search = request.GET.get('search', '')
    if search:
        qs = qs.filter(
            Q(beneficiary__full_name__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(program__name__icontains=search)
        )
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    program_filter = request.GET.get('program', '')
    if program_filter:
        qs = qs.filter(program__id=program_filter)

    # Apply sorting criteria
    sort = request.GET.get('sort', '-date_submitted')
    valid_sorts = {
        'date_asc': 'date_submitted',
        'date_desc': '-date_submitted',
        'name_asc': 'beneficiary__full_name',
        'name_desc': '-beneficiary__full_name',
    }
    if sort in valid_sorts:
        qs = qs.order_by(valid_sorts[sort])
    else:
        qs = qs.order_by('-date_submitted')

    # Calculate summary statistics
    total_count = qs.count()
    pending_count = qs.filter(status__in=['pending', 'under_review']).count()
    approved_count = qs.filter(status='approved').count()
    rejected_count = qs.filter(status='rejected').count()

    # Apply pagination
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    try:
        selected_program_id = int(program_filter) if program_filter else None
    except (ValueError, TypeError):
        selected_program_id = None

    return render(request, 'request_list.html', {
        'page_obj': page_obj,
        'programs': Program.objects.all(),
        'search': search,
        'status_filter': status_filter,
        'program_filter': selected_program_id,
        'sort': sort,
        # Summary stats
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    })


@admin_required
def request_detail(request, pk):
    """Admin application review page — view all documents, verify/reject each."""
    req_obj = get_object_or_404(
        AssistanceRequest.objects.select_related('user', 'program', 'barangay'),
        pk=pk,
    )
    app_docs = req_obj.application_documents.select_related('required_document').all()
    total_docs = app_docs.count()
    uploaded_docs = app_docs.exclude(file='').exclude(file__isnull=True).count()
    verified_docs = app_docs.filter(status='verified').count()
    is_complete = total_docs > 0 and uploaded_docs == total_docs
    all_verified = total_docs > 0 and verified_docs == total_docs
    return render(request, 'request_detail.html', {
        'req': req_obj,
        'app_docs': app_docs,
        'total_docs': total_docs,
        'uploaded_docs': uploaded_docs,
        'verified_docs': verified_docs,
        'is_complete': is_complete,
        'all_verified': all_verified,
    })


@admin_required
def document_verify(request, pk):
    """Admin action to verify or reject a single uploaded document."""
    doc = get_object_or_404(ApplicationDocument, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        admin_note = request.POST.get('admin_note', '')
        if new_status in ['verified', 'rejected', 'pending']:
            doc.status = new_status
            doc.admin_note = admin_note
            doc.save()
            messages.success(request, f'Document "{doc.required_document.document_name}" marked as {new_status}.')
    return redirect('request_detail', pk=doc.request.pk)


@admin_required
def request_update_status(request, pk):
    req = get_object_or_404(AssistanceRequest, pk=pk)
    redirect_to = request.POST.get('redirect', 'request_list')
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('admin_notes', '')
        if new_status in ['under_review', 'approved', 'rejected']:
            # Block approval if docs are incomplete
            if new_status == 'approved':
                total = req.application_documents.count()
                uploaded = req.uploaded_count
                if total > 0 and uploaded < total:
                    messages.error(
                        request,
                        f'Cannot approve — only {uploaded}/{total} documents uploaded. '
                        'All required documents must be uploaded first.'
                    )
                    if redirect_to == 'request_detail':
                        return redirect('request_detail', pk=pk)
                    return redirect('request_list')
            req.status = new_status
            req.admin_notes = notes
            req.save()

            # Update beneficiary's last_assistance_date on approval
            if new_status == 'approved' and req.beneficiary:
                req.beneficiary.last_assistance_date = timezone.now()
                req.beneficiary.save()

            messages.success(request, f'Request #{pk} updated to {new_status}.')
    if redirect_to == 'request_detail':
        return redirect('request_detail', pk=pk)
    return redirect('request_list')


@admin_required
def program_list(request):
    qs = Program.objects.annotate(
        beneficiary_count=Count('requests', filter=Q(requests__status='approved'))
    ).all()
    
    search = request.GET.get('search', '')
    if search:
        qs = qs.filter(name__icontains=search)

    # Apply sorting criteria
    sort = request.GET.get('sort', 'name_asc')
    valid_sorts = {
        'name_asc': 'name',
        'name_desc': '-name',
        'bens_desc': '-beneficiary_count',
        'bens_asc': 'beneficiary_count',
    }
    if sort in valid_sorts:
        qs = qs.order_by(valid_sorts[sort])
    else:
        qs = qs.order_by('name')

    # Apply pagination
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'program_list.html', {
        'page_obj': page_obj,
        'search': search,
        'sort': sort,
        'total_count': qs.count(),
    })


@login_required
def program_detail(request, pk):
    program = get_object_or_404(Program, pk=pk)
    program = get_object_or_404(Program, pk=pk)
    required_docs = program.required_documents.all()
    
    # Group required documents by category
    categories = {}
    for doc in required_docs:
        cat = doc.category or 'General'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(doc)
    return render(request, 'program_detail.html', {
        'program': program,
        'categories': categories,
    })


@admin_required
def program_add(request):
    if request.method == 'POST':
        form = ProgramForm(request.POST)
        if form.is_valid():
            prog = form.save()
            from core.models import ProgramRequiredDocument
            import json
            docs_json = request.POST.get('documents_json', '[]')
            try:
                docs = json.loads(docs_json)
                for idx, doc in enumerate(docs):
                    if doc.get('name'):
                        ProgramRequiredDocument.objects.create(
                            program=prog,
                            document_name=doc.get('name', ''),
                            description=doc.get('description', ''),
                            category=doc.get('category', ''),
                            is_required=doc.get('is_required', True),
                            order=idx
                        )
            except json.JSONDecodeError:
                pass
            
            messages.success(request, 'Program created.')
            return redirect('program_list')
    else:
        form = ProgramForm()
    return render(request, 'program_form.html', {'form': form, 'title': 'Add Program'})


@admin_required
def program_edit(request, pk):
    prog = get_object_or_404(Program, pk=pk)
    if request.method == 'POST':
        form = ProgramForm(request.POST, instance=prog)
        if form.is_valid():
            prog = form.save()
            from core.models import ProgramRequiredDocument
            import json
            docs_json = request.POST.get('documents_json', '[]')
            try:
                docs = json.loads(docs_json)
                prog.required_documents.all().delete()
                for idx, doc in enumerate(docs):
                    if doc.get('name'):
                        ProgramRequiredDocument.objects.create(
                            program=prog,
                            document_name=doc.get('name', ''),
                            description=doc.get('description', ''),
                            category=doc.get('category', ''),
                            is_required=doc.get('is_required', True),
                            order=idx
                        )
            except json.JSONDecodeError:
                pass
            
            messages.success(request, 'Program updated.')
            return redirect('program_list')
    else:
        form = ProgramForm(instance=prog)
        
    # Serialize required documents for frontend rendering
    existing_docs = []
    for d in prog.required_documents.order_by('order'):
        existing_docs.append({
            'name': d.document_name,
            'description': d.description,
            'category': d.category,
            'is_required': d.is_required
        })
    import json
    docs_json = json.dumps(existing_docs)
    
    return render(request, 'program_form.html', {'form': form, 'title': 'Edit Program', 'program': prog, 'docs_json': docs_json})

@admin_required
def program_delete(request, pk):
    prog = get_object_or_404(Program, pk=pk)
    if request.method == 'POST':
        prog.delete()
        messages.success(request, f'Program "{prog.name}" deleted.')
        return redirect('program_list')
    return redirect('program_edit', pk=pk)


@login_required
def api_program_documents(request, pk):
    """JSON API: return required documents for a specific program."""
    program = get_object_or_404(Program, pk=pk)
    docs = program.required_documents.all()
    data = []
    for d in docs:
        data.append({
            'id': d.pk,
            'name': d.document_name,
            'description': d.description,
            'category': d.category,
            'is_required': d.is_required,
        })
    return JsonResponse(data, safe=False)


# Staff Management (Admin)

@admin_required
def staff_management(request):
    """Admin page to manage all staff accounts."""
    staff_profiles = StaffProfile.objects.select_related('user', 'user__profile').prefetch_related('assigned_programs').all()

    # Apply search filter
    search = request.GET.get('search', '')
    if search:
        staff_profiles = staff_profiles.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )

    all_programs = Program.objects.filter(is_active=True).order_by('name')
    return render(request, 'staff_management.html', {
        'staff_profiles': staff_profiles,
        'all_programs': all_programs,
        'search': search,
    })


@admin_required
def staff_create(request):
    """Admin creates a new staff account."""
    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )
            UserProfile.objects.create(user=user, role='staff')
            sp = StaffProfile.objects.create(user=user, is_active=True)
            sp.assigned_programs.set(form.cleaned_data['assigned_programs'])
            messages.success(request, f'Staff account "{user.username}" created successfully.')
            return redirect('staff_management')
    else:
        form = StaffCreationForm()
    return render(request, 'staff_create.html', {'form': form})


@admin_required
def staff_toggle_active(request, pk):
    """Toggle staff active/inactive status."""
    sp = get_object_or_404(StaffProfile, pk=pk)
    if request.method == 'POST':
        sp.is_active = not sp.is_active
        sp.save()
        status = 'activated' if sp.is_active else 'deactivated'
        messages.success(request, f'Staff "{sp.user.username}" has been {status}.')
    return redirect('staff_management')


@admin_required
def staff_edit_programs(request, pk):
    """Admin edits which programs a staff member is assigned to."""
    sp = get_object_or_404(StaffProfile, pk=pk)
    if request.method == 'POST':
        program_ids = request.POST.getlist('programs')
        sp.assigned_programs.set(program_ids)
        messages.success(request, f'Programs updated for {sp.user.get_full_name() or sp.user.username}.')
    return redirect('staff_management')


@admin_required
def staff_activity_log(request, pk=None):
    """View staff activity logs. If pk given, filter to that staff."""
    if pk:
        logs = StaffActivityLog.objects.filter(staff_id=pk).select_related('staff').order_by('-timestamp')
        staff_user = get_object_or_404(User, pk=pk)
        title = f'Activity Log — {staff_user.get_full_name() or staff_user.username}'
    else:
        logs = StaffActivityLog.objects.select_related('staff').all().order_by('-timestamp')
        title = 'All Staff Activity Logs'

    # Apply pagination
    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff_activity_log.html', {
        'logs': page_obj,
        'page_obj': page_obj,
        'title': title,
    })


# Barangay Detail

@staff_or_admin_required
def barangay_detail(request, pk):
    """Detailed view of a single barangay's analytics."""
    barangay = get_object_or_404(Barangay, pk=pk)
    beneficiaries = Beneficiary.objects.filter(barangay=barangay, status='approved').order_by('-vulnerability_score')
    total_bens = beneficiaries.count()
    avg_vuln = beneficiaries.aggregate(avg=Avg('vulnerability_score'))['avg'] or 0
    high_risk = beneficiaries.filter(vulnerability_level__in=['high', 'critical'])
    total_services = AssistanceRequest.objects.filter(barangay=barangay, status='approved').count()
    sgi = round(total_bens / max(total_services, 1), 2)

    return render(request, 'barangay_detail.html', {
        'barangay': barangay,
        'beneficiaries': beneficiaries[:50],
        'total_beneficiaries': total_bens,
        'avg_vulnerability': round(avg_vuln, 1),
        'high_risk_individuals': high_risk[:20],
        'total_services': total_services,
        'service_gap_index': sgi,
    })


# Report Generation

@admin_required
def export_barangay_report(request):
    """Export barangay analytics as CSV."""
    from .reports import generate_barangay_report
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="barangay_report.csv"'
    response.write(generate_barangay_report())
    return response


@admin_required
def export_program_report(request):
    """Export program analytics as CSV."""
    from .reports import generate_program_report
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="program_report.csv"'
    response.write(generate_program_report())
    return response


@admin_required
def export_barangay_report_pdf(request):
    """Export barangay analytics as PDF."""
    from .reports import generate_barangay_report_pdf
    pdf_bytes = generate_barangay_report_pdf()
    if not pdf_bytes:
        messages.error(request, 'Failed to generate PDF report.')
        return redirect('admin_dashboard')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="barangay_report.pdf"'
    return response


@admin_required
def export_program_report_pdf(request):
    """Export program analytics as PDF."""
    from .reports import generate_program_report_pdf
    pdf_bytes = generate_program_report_pdf()
    if not pdf_bytes:
        messages.error(request, 'Failed to generate PDF report.')
        return redirect('admin_dashboard')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="program_report.pdf"'
    return response


# Geospatial Mapping (GIS)

@login_required
def map_view(request):
    programs = Program.objects.filter(is_active=True).values_list('name', flat=True)
    return render(request, 'map.html', {'programs': list(programs)})


@login_required
def api_map_data(request):
    """JSON API: per-barangay statistics for the map with vulnerability & service gap data."""
    # Group system insights by barangay
    insights_list = generate_all_insights()
    insights_by_brgy = {}
    for i in insights_list:
        bname = i.get('barangay', '')
        if bname and bname != 'System-wide':
            if bname not in insights_by_brgy:
                insights_by_brgy[bname] = []
            insights_by_brgy[bname].append(i)

    barangays = Barangay.objects.all()
    data = []
    for b in barangays:
        bens = Beneficiary.objects.filter(barangay=b, status='approved')
        reqs = AssistanceRequest.objects.filter(barangay=b)
        program_filter = request.GET.get('program')
        if program_filter:
            reqs = reqs.filter(program__name=program_filter)
            # Filter beneficiaries associated with specific program requests
            bens = bens.filter(id__in=reqs.values_list('beneficiary_id', flat=True))
            
        prog_counts = list(
            reqs.values('program__name').annotate(count=Count('id'))
        )
        ben_total = bens.count()
        approved_services = reqs.filter(status='approved').count()

        # Calculate vulnerability analytics
        avg_vuln = bens.aggregate(avg=Avg('vulnerability_score'))['avg'] or 0
        high_risk_count = bens.filter(vulnerability_level__in=['high', 'critical']).count()

        # Calculate service gap index
        sgi = round(ben_total / max(approved_services, 1), 2) if ben_total > 0 else 0

        # Gap detection: expected ~2% of population as minimum coverage
        expected = max(1, int(b.population * 0.02)) if b.population else 0
        gap = max(0, expected - ben_total)
        data.append({
            'id': b.pk,
            'name': b.name,
            'lat': b.latitude,
            'lng': b.longitude,
            'population': b.population,
            'total': ben_total,
            'programs': {p['program__name']: p['count'] for p in prog_counts},
            'expected': expected,
            'gap': gap,
            'avg_vulnerability': round(avg_vuln, 1),
            'high_risk_count': high_risk_count,
            'service_gap_index': sgi,
            'insights': insights_by_brgy.get(b.name, []),
        })
    return JsonResponse(data, safe=False)


@login_required
def api_gap_data(request):
    """JSON API: gap detection per barangay per program."""
    from .insights import detect_population_gaps
    gaps = detect_population_gaps()
    return JsonResponse(gaps, safe=False)


# ══════════════════════════════════════════════════════════════
#  NOTIFICATION UTILITIES
# ══════════════════════════════════════════════════════════════

def create_notification(recipient, notification_type, title, message, related_url=''):
    """Helper — create an in-app notification for a user."""
    Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        related_url=related_url,
    )


def notify_admins(notification_type, title, message, related_url=''):
    """Send a notification to all active admin users."""
    admins = User.objects.filter(
        Q(is_superuser=True) | Q(profile__role='admin')
    ).distinct()
    for admin in admins:
        create_notification(admin, notification_type, title, message, related_url)


def notify_staff_for_program(program, notification_type, title, message, related_url=''):
    """Notify all staff assigned to a given program."""
    staff_users = User.objects.filter(
        staff_profile__assigned_programs=program,
        staff_profile__is_active=True,
        profile__role='staff',
    ).distinct()
    for staff in staff_users:
        create_notification(staff, notification_type, title, message, related_url)


# ── Notification API ──────────────────────────────────────────

@login_required
def api_notifications(request):
    """JSON: return latest 10 notifications for the current user."""
    notifs = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:15]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id': n.pk,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'url': n.related_url,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%b %d, %Y %I:%M %p'),
            }
            for n in notifs
        ],
    }
    return JsonResponse(data)


@login_required
@require_POST
def mark_notification_read(request, pk=None):
    """Mark one or all notifications as read."""
    if pk:
        Notification.objects.filter(pk=pk, recipient=request.user).update(is_read=True)
    else:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


# ══════════════════════════════════════════════════════════════
#  SCHEDULED TRANSACTIONS — ADMIN / STAFF VIEWS
# ══════════════════════════════════════════════════════════════

@staff_or_admin_required
def schedule_list(request):
    """Paginated schedule list with search, filter, and sort."""
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.is_admin
    )

    if is_admin:
        qs = ScheduledTransaction.objects.select_related(
            'beneficiary', 'program', 'barangay', 'assigned_staff', 'assistance_request'
        ).all()
    else:
        # Staff sees only schedules for their assigned programs
        program_ids = request.user.staff_profile.assigned_programs.values_list('id', flat=True)
        qs = ScheduledTransaction.objects.filter(program_id__in=program_ids).select_related(
            'beneficiary', 'program', 'barangay', 'assigned_staff', 'assistance_request'
        )

    # Search
    search = request.GET.get('search', '')
    if search:
        qs = qs.filter(
            Q(beneficiary__full_name__icontains=search) |
            Q(program__name__icontains=search) |
            Q(barangay__name__icontains=search) |
            Q(claim_location__icontains=search)
        )

    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    program_filter = request.GET.get('program', '')
    if program_filter:
        qs = qs.filter(program__id=program_filter)

    date_filter = request.GET.get('date', '')
    if date_filter:
        qs = qs.filter(schedule_date=date_filter)

    # Sorting
    sort = request.GET.get('sort', '-created_at')
    valid_sorts = {
        'date_asc': 'schedule_date',
        'date_desc': '-schedule_date',
        'name_asc': 'beneficiary__full_name',
        'name_desc': '-beneficiary__full_name',
        'status_asc': 'status',
        'newest': '-created_at',
    }
    qs = qs.order_by(valid_sorts.get(sort, '-created_at'))

    # Summary stats
    today = timezone.localdate()
    total_count = qs.count()
    today_count = qs.filter(schedule_date=today).count()
    pending_count = qs.filter(status__in=['pending', 'under_review']).count()
    missed_count = qs.filter(status='missed').count()
    completed_count = qs.filter(status='completed').count()

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    programs = Program.objects.filter(is_active=True).order_by('name')
    try:
        selected_program_id = int(program_filter) if program_filter else None
    except (ValueError, TypeError):
        selected_program_id = None

    return render(request, 'schedules/schedule_list.html', {
        'page_obj': page_obj,
        'programs': programs,
        'search': search,
        'status_filter': status_filter,
        'program_filter': selected_program_id,
        'date_filter': date_filter,
        'sort': sort,
        'total_count': total_count,
        'today_count': today_count,
        'pending_count': pending_count,
        'missed_count': missed_count,
        'completed_count': completed_count,
        'is_admin': is_admin,
        'STATUS_CHOICES': ScheduledTransaction.STATUS_CHOICES,
    })


@staff_or_admin_required
def schedule_create(request, request_pk):
    """Create a schedule for an approved assistance request."""
    assistance_req = get_object_or_404(
        AssistanceRequest.objects.select_related('user', 'program', 'barangay', 'beneficiary'),
        pk=request_pk, status='approved',
    )

    # Check if schedule already exists
    if hasattr(assistance_req, 'schedule') and assistance_req.schedule:
        messages.warning(request, 'A schedule already exists for this request.')
        return redirect('schedule_detail', pk=assistance_req.schedule.pk)

    if not assistance_req.beneficiary:
        messages.error(request, 'This request has no linked beneficiary profile.')
        return redirect('request_detail', pk=request_pk)

    if request.method == 'POST':
        form = ScheduledTransactionForm(request.POST)
        if form.is_valid():
            sched = form.save(commit=False)
            sched.assistance_request = assistance_req
            sched.beneficiary = assistance_req.beneficiary
            sched.program = assistance_req.program
            sched.barangay = assistance_req.barangay
            sched.created_by = request.user

            # Conflict & capacity validation
            if sched.schedule_date and sched.time_slot:
                slot_count = ScheduledTransaction.get_slot_count(sched.schedule_date, sched.time_slot)
                if slot_count >= sched.max_per_slot:
                    messages.error(
                        request,
                        f'Time slot {sched.get_time_slot_display()} on '
                        f'{sched.schedule_date} is fully booked ({slot_count}/{sched.max_per_slot}).'
                    )
                    return render(request, 'schedules/schedule_create.html', {
                        'form': form, 'assistance_req': assistance_req,
                    })

            sched.save()

            # Notify beneficiary
            create_notification(
                recipient=assistance_req.user,
                notification_type='schedule_assigned',
                title='Appointment Scheduled',
                message=(
                    f'Your appointment for {sched.program.name} has been scheduled on '
                    f'{sched.schedule_date.strftime("%B %d, %Y") if sched.schedule_date else "a date TBD"} '
                    f'at {sched.claim_location}.'
                ),
                related_url=f'/user/appointments/{sched.pk}/',
            )

            messages.success(request, f'Schedule created for {sched.beneficiary.full_name}.')
            return redirect('schedule_detail', pk=sched.pk)
    else:
        form = ScheduledTransactionForm(initial={'status': 'scheduled'})

    return render(request, 'schedules/schedule_create.html', {
        'form': form,
        'assistance_req': assistance_req,
    })


@staff_or_admin_required
def schedule_detail(request, pk):
    """Full detail view of a single scheduled transaction."""
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.is_admin
    )
    if is_admin:
        sched = get_object_or_404(
            ScheduledTransaction.objects.select_related(
                'beneficiary', 'program', 'barangay', 'assigned_staff',
                'assistance_request', 'created_by',
            ),
            pk=pk,
        )
    else:
        program_ids = request.user.staff_profile.assigned_programs.values_list('id', flat=True)
        sched = get_object_or_404(
            ScheduledTransaction.objects.select_related(
                'beneficiary', 'program', 'barangay', 'assigned_staff',
                'assistance_request', 'created_by',
            ),
            pk=pk, program_id__in=program_ids,
        )

    # Service history record if completed
    history_record = None
    if hasattr(sched, 'history'):
        history_record = sched.history

    return render(request, 'schedules/schedule_detail.html', {
        'sched': sched,
        'history_record': history_record,
        'is_admin': is_admin,
    })


@staff_or_admin_required
def schedule_edit(request, pk):
    """Edit/reschedule an existing appointment."""
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.is_admin
    )
    if is_admin:
        sched = get_object_or_404(ScheduledTransaction, pk=pk)
    else:
        program_ids = request.user.staff_profile.assigned_programs.values_list('id', flat=True)
        sched = get_object_or_404(ScheduledTransaction, pk=pk, program_id__in=program_ids)

    if sched.status in ['completed', 'rejected']:
        messages.error(request, 'Cannot edit a completed or rejected schedule.')
        return redirect('schedule_detail', pk=pk)

    if request.method == 'POST':
        old_date = sched.schedule_date
        old_slot = sched.time_slot
        form = ScheduledTransactionForm(request.POST, instance=sched)
        if form.is_valid():
            updated = form.save(commit=False)

            # Conflict check (excluding self)
            if updated.schedule_date and updated.time_slot:
                slot_count = ScheduledTransaction.get_slot_count(
                    updated.schedule_date, updated.time_slot, exclude_pk=pk
                )
                if slot_count >= updated.max_per_slot:
                    messages.error(
                        request,
                        f'Time slot {updated.get_time_slot_display()} on '
                        f'{updated.schedule_date} is fully booked ({slot_count}/{updated.max_per_slot}).'
                    )
                    return render(request, 'schedules/schedule_edit.html', {
                        'form': form, 'sched': sched,
                    })

            # Track reschedule
            if old_date and updated.schedule_date != old_date:
                updated.reschedule_count += 1

            updated.reschedule_requested = False
            updated.save()

            # Notify beneficiary of reschedule
            if old_date and updated.schedule_date != old_date:
                create_notification(
                    recipient=sched.assistance_request.user if sched.assistance_request else None,
                    notification_type='schedule_assigned',
                    title='Appointment Rescheduled',
                    message=(
                        f'Your appointment for {sched.program.name} has been rescheduled to '
                        f'{updated.schedule_date.strftime("%B %d, %Y") if updated.schedule_date else "TBD"}.'
                    ),
                    related_url=f'/user/appointments/{sched.pk}/',
                )

            messages.success(request, 'Schedule updated successfully.')
            return redirect('schedule_detail', pk=pk)
    else:
        form = ScheduledTransactionForm(instance=sched)

    return render(request, 'schedules/schedule_edit.html', {
        'form': form,
        'sched': sched,
        'is_admin': is_admin,
    })


@staff_or_admin_required
@require_POST
def schedule_update_status(request, pk):
    """Update the status of a scheduled transaction (claim, complete, cancel, miss, reject)."""
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.is_admin
    )
    if is_admin:
        sched = get_object_or_404(ScheduledTransaction, pk=pk)
    else:
        program_ids = request.user.staff_profile.assigned_programs.values_list('id', flat=True)
        sched = get_object_or_404(ScheduledTransaction, pk=pk, program_id__in=program_ids)

    new_status = request.POST.get('status', '')
    remarks = request.POST.get('remarks', '')
    amount_value = request.POST.get('amount_value', '0') or '0'

    allowed = ['pending', 'under_review', 'approved', 'scheduled', 'claimed',
               'completed', 'missed', 'cancelled', 'rejected']
    if new_status not in allowed:
        messages.error(request, 'Invalid status.')
        return redirect('schedule_detail', pk=pk)

    old_status = sched.status
    sched.status = new_status
    if remarks:
        sched.admin_notes = remarks
    sched.save()

    # Auto-create ServiceHistory when marked completed
    if new_status == 'completed' and old_status != 'completed':
        try:
            amount = float(amount_value)
        except (ValueError, TypeError):
            amount = 0.0

        ServiceHistory.objects.get_or_create(
            scheduled_transaction=sched,
            defaults={
                'beneficiary': sched.beneficiary,
                'program': sched.program,
                'assistance_request': sched.assistance_request,
                'amount_value': amount,
                'claim_date': sched.schedule_date or timezone.localdate(),
                'assigned_staff': sched.assigned_staff,
                'transaction_status': 'completed',
                'remarks': sched.admin_notes,
            }
        )
        # Update beneficiary last_assistance_date
        sched.beneficiary.last_assistance_date = timezone.now()
        sched.beneficiary.save()

        # Notify beneficiary
        if sched.assistance_request:
            create_notification(
                recipient=sched.assistance_request.user,
                notification_type='claim_completed',
                title='Assistance Claim Completed',
                message=f'Your claim for {sched.program.name} has been successfully completed.',
                related_url='/user/service-history/',
            )

    # Notify for missed
    if new_status == 'missed' and old_status != 'missed':
        if sched.assistance_request:
            create_notification(
                recipient=sched.assistance_request.user,
                notification_type='schedule_missed',
                title='Missed Appointment',
                message=(
                    f'You missed your appointment for {sched.program.name} on '
                    f'{sched.schedule_date}. Please contact the CSWDO office to reschedule.'
                ),
                related_url=f'/user/appointments/{sched.pk}/',
            )
        # Log activity
        StaffActivityLog.objects.create(
            staff=request.user, action='update',
            target_type='ScheduledTransaction', target_id=pk,
            description=f'Marked schedule #{pk} as missed for {sched.beneficiary.full_name}',
        )

    messages.success(request, f'Schedule status updated to "{sched.get_status_display()}".')

    redirect_to = request.POST.get('redirect', 'schedule_list')
    if redirect_to == 'schedule_detail':
        return redirect('schedule_detail', pk=pk)
    return redirect('schedule_list')


@admin_required
@require_POST
def schedule_bulk_action(request):
    """Bulk update multiple schedule statuses."""
    ids = request.POST.getlist('selected_ids')
    action = request.POST.get('bulk_action', '')
    allowed_actions = {
        'mark_missed': 'missed',
        'mark_cancelled': 'cancelled',
        'mark_completed': 'completed',
    }
    if action not in allowed_actions or not ids:
        messages.error(request, 'Invalid bulk action or no schedules selected.')
        return redirect('schedule_list')

    new_status = allowed_actions[action]
    updated = ScheduledTransaction.objects.filter(pk__in=ids).update(status=new_status)
    messages.success(request, f'{updated} schedule(s) updated to "{new_status}".')
    return redirect('schedule_list')


@staff_or_admin_required
def api_schedule_slots(request):
    """JSON API: return slot availability for a given date."""
    date_str = request.GET.get('date', '')
    max_per_slot = int(request.GET.get('max_per_slot', 10))
    if not date_str:
        return JsonResponse({'error': 'date required'}, status=400)

    from datetime import date as date_type
    try:
        from datetime import datetime
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'invalid date format'}, status=400)

    slots = []
    for code, label in ScheduledTransaction.TIME_SLOT_CHOICES:
        count = ScheduledTransaction.get_slot_count(query_date, code)
        slots.append({
            'value': code,
            'label': label,
            'count': count,
            'max': max_per_slot,
            'available': count < max_per_slot,
        })
    return JsonResponse({'date': date_str, 'slots': slots})


# ══════════════════════════════════════════════════════════════
#  SERVICE HISTORY — ADMIN VIEWS
# ══════════════════════════════════════════════════════════════

@admin_required
def admin_service_history(request):
    """Admin view: complete service history list with search, filter, export."""
    qs = ServiceHistory.objects.select_related(
        'beneficiary', 'program', 'assigned_staff', 'assistance_request',
    ).all()

    search = request.GET.get('search', '')
    if search:
        qs = qs.filter(
            Q(beneficiary__full_name__icontains=search) |
            Q(program__name__icontains=search)
        )

    program_filter = request.GET.get('program', '')
    if program_filter:
        qs = qs.filter(program__id=program_filter)

    barangay_filter = request.GET.get('barangay', '')
    if barangay_filter:
        qs = qs.filter(beneficiary__barangay__id=barangay_filter)

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        qs = qs.filter(claim_date__gte=date_from)
    if date_to:
        qs = qs.filter(claim_date__lte=date_to)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="service_history.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Beneficiary', 'Program', 'Barangay', 'Claim Date',
            'Amount (PHP)', 'Staff', 'Status', 'Remarks',
        ])
        for h in qs:
            writer.writerow([
                h.beneficiary.full_name,
                h.program.name,
                h.beneficiary.barangay.name if h.beneficiary.barangay else '',
                h.claim_date or '',
                h.amount_value,
                h.assigned_staff.get_full_name() if h.assigned_staff else '',
                h.transaction_status,
                h.remarks,
            ])
        return response

    total_count = qs.count()
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    try:
        selected_program_id = int(program_filter) if program_filter else None
    except (ValueError, TypeError):
        selected_program_id = None

    try:
        selected_barangay_id = int(barangay_filter) if barangay_filter else None
    except (ValueError, TypeError):
        selected_barangay_id = None

    return render(request, 'history/service_history_list.html', {
        'page_obj': page_obj,
        'programs': Program.objects.filter(is_active=True).order_by('name'),
        'barangays': Barangay.objects.all().order_by('name'),
        'search': search,
        'program_filter': selected_program_id,
        'barangay_filter': selected_barangay_id,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
    })


@admin_required
def beneficiary_service_history(request, pk):
    """Admin: complete history timeline for one beneficiary."""
    beneficiary = get_object_or_404(Beneficiary.objects.select_related('barangay'), pk=pk)
    history = ServiceHistory.objects.filter(beneficiary=beneficiary).select_related(
        'program', 'assigned_staff', 'scheduled_transaction',
    ).order_by('-created_at')
    schedules = ScheduledTransaction.objects.filter(beneficiary=beneficiary).select_related(
        'program', 'assigned_staff',
    ).order_by('-created_at')
    requests_qs = AssistanceRequest.objects.filter(beneficiary=beneficiary).select_related(
        'program',
    ).order_by('-date_submitted')

    total_received = history.count()
    total_requests_count = requests_qs.count()
    total_amount = history.aggregate(total=Sum('amount_value'))['total'] or 0

    return render(request, 'history/beneficiary_history.html', {
        'beneficiary': beneficiary,
        'history': history,
        'schedules': schedules,
        'requests': requests_qs,
        'total_received': total_received,
        'total_requests_count': total_requests_count,
        'total_amount': total_amount,
    })


# ══════════════════════════════════════════════════════════════
#  BENEFICIARY / USER SIDE — APPOINTMENTS & HISTORY
# ══════════════════════════════════════════════════════════════

@login_required
def user_appointments(request):
    """Beneficiary: view all own appointments."""
    beneficiary = Beneficiary.objects.filter(user=request.user).first()
    if not beneficiary:
        messages.info(request, 'Please submit your beneficiary profile first.')
        return redirect('submit_beneficiary')

    schedules = ScheduledTransaction.objects.filter(
        beneficiary=beneficiary
    ).select_related('program', 'barangay', 'assigned_staff').order_by('-created_at')

    # Upcoming
    today = timezone.localdate()
    upcoming = schedules.filter(
        schedule_date__gte=today,
        status__in=['scheduled', 'approved', 'pending'],
    ).order_by('schedule_date').first()

    return render(request, 'user/appointments.html', {
        'schedules': schedules,
        'upcoming': upcoming,
        'beneficiary': beneficiary,
        'today': today,
    })


@login_required
def user_appointment_detail(request, pk):
    """Beneficiary: detail view of a single appointment."""
    beneficiary = get_object_or_404(Beneficiary, user=request.user)
    sched = get_object_or_404(
        ScheduledTransaction.objects.select_related(
            'program', 'barangay', 'assigned_staff', 'assistance_request',
        ),
        pk=pk, beneficiary=beneficiary,
    )
    return render(request, 'user/appointment_detail.html', {
        'sched': sched,
        'beneficiary': beneficiary,
    })


@login_required
def user_request_reschedule(request, pk):
    """Beneficiary requests a reschedule for their appointment."""
    beneficiary = get_object_or_404(Beneficiary, user=request.user)
    sched = get_object_or_404(
        ScheduledTransaction,
        pk=pk, beneficiary=beneficiary,
        status__in=['scheduled', 'approved', 'missed'],
    )

    if request.method == 'POST':
        form = RescheduleRequestForm(request.POST)
        if form.is_valid():
            sched.reschedule_requested = True
            sched.reschedule_reason = form.cleaned_data['reason']
            sched.save()

            # Notify admins and staff
            msg = (
                f'{beneficiary.full_name} has requested a reschedule for their '
                f'{sched.program.name} appointment'
                f'{" (preferred: " + str(form.cleaned_data["preferred_date"]) + ")" if form.cleaned_data.get("preferred_date") else ""}. '
                f'Reason: {form.cleaned_data["reason"][:100]}'
            )
            notify_admins('reschedule_request', 'Reschedule Requested', msg,
                          related_url=f'/schedules/{sched.pk}/')
            notify_staff_for_program(sched.program, 'reschedule_request',
                                     'Reschedule Requested', msg,
                                     related_url=f'/schedules/{sched.pk}/')

            messages.success(request, 'Reschedule request submitted. We will contact you soon.')
            return redirect('user_appointment_detail', pk=pk)
    else:
        form = RescheduleRequestForm()

    return render(request, 'user/request_reschedule.html', {
        'form': form,
        'sched': sched,
        'beneficiary': beneficiary,
    })


@login_required
def user_service_history(request):
    """Beneficiary: personal service history timeline."""
    beneficiary = Beneficiary.objects.filter(user=request.user).first()
    if not beneficiary:
        messages.info(request, 'Please submit your beneficiary profile first.')
        return redirect('submit_beneficiary')

    history = ServiceHistory.objects.filter(beneficiary=beneficiary).select_related(
        'program', 'assigned_staff', 'scheduled_transaction',
    ).order_by('-created_at')

    total_received = history.count()
    total_amount = history.aggregate(total=Sum('amount_value'))['total'] or 0
    programs_helped = history.values('program').distinct().count()

    return render(request, 'user/service_history.html', {
        'history': history,
        'beneficiary': beneficiary,
        'total_received': total_received,
        'total_amount': total_amount,
        'programs_helped': programs_helped,
    })


@login_required
def print_appointment_slip(request, pk):
    """Printable appointment slip for beneficiary."""
    beneficiary = get_object_or_404(Beneficiary, user=request.user)
    sched = get_object_or_404(
        ScheduledTransaction.objects.select_related(
            'program', 'barangay', 'assigned_staff', 'beneficiary',
        ),
        pk=pk, beneficiary=beneficiary,
    )
    return render(request, 'schedules/appointment_slip.html', {
        'sched': sched,
        'beneficiary': beneficiary,
    })