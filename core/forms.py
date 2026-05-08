from django import forms
from django.contrib.auth.models import User
from .models import (
    Barangay, Program, Beneficiary, AssistanceRequest, UserProfile,
    ScheduledTransaction,
)


class RegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': 'First Name', 'class': 'form-control', 'id': 'reg-first-name'
    }))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': 'Last Name', 'class': 'form-control', 'id': 'reg-last-name'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Email Address', 'class': 'form-control', 'id': 'reg-email'
    }))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'placeholder': 'Username', 'class': 'form-control', 'id': 'reg-username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Password', 'class': 'form-control', 'id': 'reg-password'
    }))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirm Password', 'class': 'form-control', 'id': 'reg-password-confirm'
    }))
    barangay = forms.ModelChoiceField(
        queryset=Barangay.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'reg-barangay'}),
        empty_label='Select Barangay'
    )
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Phone Number', 'class': 'form-control', 'id': 'reg-phone'
    }))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered.')
        return email

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', 'Passwords do not match.')
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Username', 'class': 'form-control', 'id': 'login-username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Password', 'class': 'form-control', 'id': 'login-password'
    }))


class BeneficiaryForm(forms.ModelForm):
    class Meta:
        model = Beneficiary
        fields = ['full_name', 'age', 'gender', 'barangay',
                  'household_income', 'family_members',
                  'employment_status', 'disability_status']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name', 'id': 'ben-fullname'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Age', 'id': 'ben-age'}),
            'gender': forms.Select(attrs={'class': 'form-select', 'id': 'ben-gender'}),
            'barangay': forms.Select(attrs={'class': 'form-select', 'id': 'ben-barangay'}),
            'household_income': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Monthly Income (PHP)', 'id': 'ben-income'}),
            'family_members': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of Family Members', 'id': 'ben-family'}),
            'employment_status': forms.Select(attrs={'class': 'form-select', 'id': 'ben-employment'}),
            'disability_status': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'ben-disability'}),
        }


class AssistanceRequestForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['program', 'barangay', 'reason', 'document']
        widgets = {
            'program': forms.Select(attrs={'class': 'form-select', 'id': 'req-program'}),
            'barangay': forms.Select(attrs={'class': 'form-select', 'id': 'req-barangay'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Explain your reason for requesting assistance...', 'id': 'req-reason'}),
            'document': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'req-document'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['program'].queryset = Program.objects.filter(is_active=True)


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ['name', 'description', 'transaction_type', 'who_may_avail', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Program Name', 'id': 'prog-name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'About the Service', 'id': 'prog-desc'}),
            'transaction_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. G2C - Government to Citizen', 'id': 'prog-type'}),
            'who_may_avail': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Who may avail this program', 'id': 'prog-avail'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'prog-active'}),
        }


class BeneficiaryAdminForm(forms.ModelForm):
    """Form for admins to edit beneficiary records."""
    class Meta:
        model = Beneficiary
        fields = ['full_name', 'age', 'gender', 'barangay',
                  'household_income', 'family_members',
                  'employment_status', 'disability_status',
                  'status', 'admin_note']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'admin-ben-fullname'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'id': 'admin-ben-age'}),
            'gender': forms.Select(attrs={'class': 'form-select', 'id': 'admin-ben-gender'}),
            'barangay': forms.Select(attrs={'class': 'form-select', 'id': 'admin-ben-barangay'}),
            'household_income': forms.NumberInput(attrs={'class': 'form-control', 'id': 'admin-ben-income'}),
            'family_members': forms.NumberInput(attrs={'class': 'form-control', 'id': 'admin-ben-family'}),
            'employment_status': forms.Select(attrs={'class': 'form-select', 'id': 'admin-ben-employment'}),
            'disability_status': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'admin-ben-disability'}),
            'status': forms.Select(attrs={'class': 'form-select', 'id': 'admin-ben-status'}),
            'admin_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'admin-ben-note', 'placeholder': 'Optional. Reason for rejection or other notes.'}),
        }


class StaffCreationForm(forms.Form):
    """Admin form to create staff accounts."""
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First Name', 'id': 'staff-first-name'
    }))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last Name', 'id': 'staff-last-name'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Email Address', 'id': 'staff-email'
    }))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username', 'id': 'staff-username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password', 'id': 'staff-password'
    }))
    assigned_programs = forms.ModelMultipleChoiceField(
        queryset=Program.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        help_text='Select programs this staff member will manage.'
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered.')
        return email


class ScheduledTransactionForm(forms.ModelForm):
    """Admin/Staff form to create or edit a scheduled transaction."""

    schedule_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'sched-date',
        }),
        required=False,
    )

    class Meta:
        model = ScheduledTransaction
        fields = [
            'schedule_date', 'time_slot', 'claim_location',
            'assigned_staff', 'max_per_slot', 'status', 'remarks', 'admin_notes',
        ]
        widgets = {
            'time_slot': forms.Select(attrs={'class': 'form-select', 'id': 'sched-slot'}),
            'claim_location': forms.TextInput(attrs={
                'class': 'form-control', 'id': 'sched-location',
                'placeholder': 'e.g. CSWDO Office, Tayabas City',
            }),
            'assigned_staff': forms.Select(attrs={'class': 'form-select', 'id': 'sched-staff'}),
            'max_per_slot': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'sched-max', 'min': 1, 'max': 50,
            }),
            'status': forms.Select(attrs={'class': 'form-select', 'id': 'sched-status'}),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2, 'id': 'sched-remarks',
                'placeholder': 'Optional remarks for the beneficiary',
            }),
            'admin_notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2, 'id': 'sched-admin-notes',
                'placeholder': 'Internal admin notes (not visible to beneficiary)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User as AuthUser
        self.fields['assigned_staff'].queryset = AuthUser.objects.filter(
            profile__role='staff', staff_profile__is_active=True
        ).select_related('profile')
        self.fields['assigned_staff'].required = False
        self.fields['assigned_staff'].empty_label = '— Unassigned —'


class RescheduleRequestForm(forms.Form):
    """Beneficiary form to request a reschedule."""
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'reschedule-reason',
            'placeholder': 'Please explain why you need to reschedule...',
        }),
        label='Reason for Reschedule',
        max_length=1000,
    )
    preferred_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'reschedule-preferred-date',
        }),
        required=False,
        label='Preferred Date (optional)',
    )
