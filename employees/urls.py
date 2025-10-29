from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_employee, name='register_employee'),
    path('employees/', views.get_all_employees_with_images, name='get_all_employees'),
    path('employees_from_global/', views.get_all_employee_from_global),  # New endpoint
    path("employees/<str:employee_id>/encode_face/", views.encode_employee_face),
    path('employees/<str:employee_id>/enable_face/', views.enable_facial_recognition),
    path('employees/<str:employee_id>/disable_face/', views.disable_facial_recognition),
    path('serve-file/<str:file_id>/', views.serve_file, name="serve_file"),
    path('get_device_info/', views.get_device_info, name="serve_file"),
    path('employees/md5/<str:image_md5>/', views.get_employee_by_md5, name='get_employee_by_md5'),
    path('mark/', views.mark_attendance, name='mark_attendance'),
    path('hrregistration/', views.registration, name='registration'),
    path('login/', views.login, name='login'),
    path('attendance-report/', views.attendance_report_with_employee_details, name='attendance_report'),
    path("transcribe/", views.transcribe_audio, name="transcribe_audio"),
    path('fingerprint-login/', views.fingerprint_login, name='fingerprint-login'),


]
