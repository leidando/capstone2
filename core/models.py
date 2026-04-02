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
