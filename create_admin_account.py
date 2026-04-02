import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cswdo_system.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile

# Create or update the admin user
user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
user.set_password('admin')
user.is_superuser = True
user.is_staff = True
user.save()

# Ensure the UserProfile has role='admin'
profile, p_created = UserProfile.objects.get_or_create(user=user)
profile.role = 'admin'
profile.save()

print("Admin account created successfully. Username: 'admin', Password: 'admin'")
