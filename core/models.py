from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Barangay(models.Model):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    population = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Barangays'

    def __str__(self):
        return self.name


class Program(models.Model):
    name = models.CharField(max_length=300, unique=True)
    description = models.TextField(blank=True)
    transaction_type = models.CharField(max_length=100, default='G2C - Government to Citizen')
    who_may_avail = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProgramRequiredDocument(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='required_documents')
    document_name = models.CharField(max_length=300)
    description = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'order']

    def __str__(self):
        return f"{self.program.name} — {self.document_name}"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('user', 'User'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    barangay = models.ForeignKey(Barangay, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_staff_role(self):
        return self.role == 'staff'


class StaffProfile(models.Model):
    """Extended profile for staff members — links to assigned programs."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    assigned_programs = models.ManyToManyField(Program, blank=True, related_name='assigned_staff')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Staff: {self.user.get_full_name() or self.user.username}"


class StaffActivityLog(models.Model):
    """Audit log for staff actions — viewable by admins."""
    ACTION_CHOICES = [
        ('approve', 'Approved Request'),
        ('reject', 'Rejected Request'),
        ('review', 'Reviewed Request'),
        ('view', 'Viewed Record'),
        ('update', 'Updated Status'),
    ]
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50, help_text='e.g. AssistanceRequest, Beneficiary')
    target_id = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.staff.username} — {self.get_action_display()} ({self.timestamp:%Y-%m-%d %H:%M})"


class Beneficiary(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    EMPLOYMENT_CHOICES = [
        ('employed', 'Employed'),
        ('unemployed', 'Unemployed'),
        ('self_employed', 'Self-Employed'),
        ('retired', 'Retired'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='beneficiaries')
    full_name = models.CharField(max_length=200)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name='beneficiaries')
    household_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    family_members = models.PositiveIntegerField(default=1)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, default='unemployed', blank=True)
    disability_status = models.BooleanField(default=False, help_text='Does the beneficiary have a disability?')
    vulnerability_score = models.FloatField(default=0, help_text='Auto-computed 0-100 score')
    vulnerability_level = models.CharField(max_length=10, default='low', help_text='Auto: low/medium/high/critical')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True, null=True)
    last_assistance_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Beneficiaries'

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        from .vulnerability import compute_vulnerability_score, get_vulnerability_level
        self.vulnerability_score = compute_vulnerability_score(self)
        self.vulnerability_level = get_vulnerability_level(self.vulnerability_score)
        super().save(*args, **kwargs)


class AssistanceRequest(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests')
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests')
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='requests')
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name='requests', null=True)
    reason = models.TextField()
    selected_category = models.CharField(max_length=200, blank=True, help_text='Sub-category chosen by applicant (e.g. Sa Medikal, Senior Citizen)')
    document = models.FileField(upload_to='request_documents/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    admin_notes = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_submitted']

    def __str__(self):
        return f"{self.user.username} — {self.program.name} ({self.status})"

    @property
    def uploaded_count(self):
        return self.application_documents.exclude(file='').exclude(file__isnull=True).count()

    @property
    def verified_count(self):
        return self.application_documents.filter(status='verified').count()


class ApplicationDocument(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('missing', 'Missing'),
    ]
    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name='application_documents')
    required_document = models.ForeignKey(ProgramRequiredDocument, on_delete=models.CASCADE)
    file = models.FileField(upload_to='application_documents/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.CharField(max_length=300, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['required_document__order']

    def __str__(self):
        return f"{self.required_document.document_name} — {self.get_status_display()}"


# ══════════════════════════════════════════════════════════════
#  SCHEDULED TRANSACTIONS / APPOINTMENT SYSTEM
# ══════════════════════════════════════════════════════════════

class ScheduledTransaction(models.Model):
    """Tracks the full claiming lifecycle for an approved assistance request."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('scheduled', 'Scheduled'),
        ('claimed', 'Claimed'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]

    TIME_SLOT_CHOICES = [
        ('08:00', '8:00 AM – 9:00 AM'),
        ('09:00', '9:00 AM – 10:00 AM'),
        ('10:00', '10:00 AM – 11:00 AM'),
        ('11:00', '11:00 AM – 12:00 PM'),
        ('13:00', '1:00 PM – 2:00 PM'),
        ('14:00', '2:00 PM – 3:00 PM'),
        ('15:00', '3:00 PM – 4:00 PM'),
        ('16:00', '4:00 PM – 5:00 PM'),
    ]

    assistance_request = models.OneToOneField(
        AssistanceRequest, on_delete=models.CASCADE,
        related_name='schedule', null=True, blank=True,
    )
    beneficiary = models.ForeignKey(
        Beneficiary, on_delete=models.CASCADE, related_name='schedules',
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name='schedules',
    )
    barangay = models.ForeignKey(
        Barangay, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedules',
    )

    # Appointment details
    schedule_date = models.DateField(null=True, blank=True)
    time_slot = models.CharField(
        max_length=5, choices=TIME_SLOT_CHOICES, blank=True,
        help_text='Hour block (HH:MM)',
    )
    claim_location = models.CharField(max_length=300, default='CSWDO Office, Tayabas City')
    assigned_staff = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_schedules',
    )

    # Capacity control
    max_per_slot = models.PositiveIntegerField(default=10, help_text='Max beneficiaries per slot')

    # Status & notes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    # Reschedule tracking
    reschedule_count = models.PositiveIntegerField(default=0)
    reschedule_requested = models.BooleanField(default=False)
    reschedule_reason = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_schedules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scheduled Transaction'
        verbose_name_plural = 'Scheduled Transactions'

    def __str__(self):
        date_str = self.schedule_date.strftime('%b %d, %Y') if self.schedule_date else 'Unscheduled'
        return f"{self.beneficiary.full_name} — {self.program.name} ({date_str})"

    @property
    def is_upcoming(self):
        if self.schedule_date:
            return self.schedule_date >= timezone.localdate() and self.status in ['scheduled', 'approved']
        return False

    @property
    def is_overdue(self):
        if self.schedule_date:
            return self.schedule_date < timezone.localdate() and self.status in ['scheduled', 'approved']
        return False

    @classmethod
    def get_slot_count(cls, date, time_slot, exclude_pk=None):
        """Returns current booking count for a date+time slot (for conflict/capacity checks)."""
        qs = cls.objects.filter(
            schedule_date=date,
            time_slot=time_slot,
            status__in=['scheduled', 'approved', 'pending'],
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.count()


# ══════════════════════════════════════════════════════════════
#  SERVICE HISTORY
# ══════════════════════════════════════════════════════════════

class ServiceHistory(models.Model):
    """Immutable record of every assistance received by a beneficiary."""

    beneficiary = models.ForeignKey(
        Beneficiary, on_delete=models.CASCADE, related_name='service_history',
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name='service_history',
    )
    assistance_request = models.ForeignKey(
        AssistanceRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='history',
    )
    scheduled_transaction = models.OneToOneField(
        ScheduledTransaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='history',
    )

    # Details captured at completion time (snapshot)
    amount_value = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Monetary value of assistance received (if applicable)',
    )
    claim_date = models.DateField(null=True, blank=True)
    assigned_staff = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_records',
    )
    transaction_status = models.CharField(max_length=20, default='completed')
    remarks = models.TextField(blank=True)
    document_attachment = models.FileField(
        upload_to='service_history_docs/', blank=True, null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Service History'
        verbose_name_plural = 'Service Histories'

    def __str__(self):
        date_str = self.claim_date.strftime('%b %d, %Y') if self.claim_date else 'N/A'
        return f"{self.beneficiary.full_name} — {self.program.name} ({date_str})"


# ══════════════════════════════════════════════════════════════
#  NOTIFICATION SYSTEM
# ══════════════════════════════════════════════════════════════

class Notification(models.Model):
    """In-app notification for all user roles."""

    TYPE_CHOICES = [
        ('new_request', 'New Assistance Request'),
        ('request_approved', 'Request Approved'),
        ('request_rejected', 'Request Rejected'),
        ('schedule_assigned', 'Schedule Assigned'),
        ('schedule_reminder', 'Schedule Reminder'),
        ('schedule_missed', 'Missed Appointment'),
        ('claim_completed', 'Claim Completed'),
        ('reschedule_request', 'Reschedule Requested'),
        ('pending_approval', 'Pending Approval'),
        ('general', 'General'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.recipient.username}"
