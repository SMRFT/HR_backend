from django.db import models

# Create your models here.
from django.db import models
from django.utils.timezone import now

from djongo import models


from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()  # assuming you have a user model for created_by / lastmodified_by

from django.contrib.auth.models import User
from django.db import models

class Employee(models.Model):
    employee_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=100)
    
    # Latest/current face encoding
    current_face_encoding = models.JSONField(blank=True, null=True, default=list)
    
    # Store all past face encodings
    face_encoding_data_history = models.JSONField(blank=True, null=True, default=list)
    
    # Store image hash (for duplicate check)
    image_md5 = models.CharField(max_length=64, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_biometrics')
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_biometrics')
    lastmodified_date = models.DateTimeField(auto_now=True)

    def update_encoding(self, new_encoding, new_image_md5=None):
        """Save previous encoding to history, update current encoding and optional image MD5."""
        if self.current_face_encoding:
            self.face_encoding_data_history.append(self.current_face_encoding)
        self.current_face_encoding = new_encoding
        if new_image_md5:
            self.image_md5 = new_image_md5
        self.save(update_fields=['current_face_encoding', 'face_encoding_data_history', 'image_md5', 'lastmodified_date'])

    def __str__(self):
        return f"{self.employee_id} - {self.name} - Active: {self.is_active}"




from django.db import models
from employees.models import Employee

class EmployeeAttendance(models.Model):
    ATTEND_TYPE = (('IN','IN'),('OUT','OUT'))

    attendence_id = models.AutoField(primary_key=True)
    employee_id = models.CharField(max_length=50)  # store actual employee ID
    device_id = models.CharField(max_length=50, blank=True, null=True)
    attendence_time = models.DateTimeField(auto_now_add=True)
    attendence_type = models.CharField(max_length=3, choices=ATTEND_TYPE, default='IN')
    confidence = models.FloatField(null=True, blank=True)  # optional similarity score

    def __str__(self):
        return f"{self.employee_id} - {self.attendence_type} @ {self.attendence_time}"

class Register(models.Model):
    name = models.CharField(max_length=500)
    role = models.CharField(max_length=500)
    password = models.CharField(max_length=500)
    confirmPassword = models.CharField(max_length=500)
    fingerprint_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    device = models.CharField(max_length=255, unique=True, null=True, blank=True)