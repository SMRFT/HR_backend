from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Employee
from .serializers import EmployeeSerializer, EmployeeCreateSerializer
from .face_utils import imagefile_to_encoding, base64_to_encoding
from .models import EmployeeAttendance
from pyauth.auth import HasRolePermission
# @api_view(['POST'])
# @permission_classes([AllowAny])
# def register_employee(request):
#     serializer = EmployeeCreateSerializer(data=request.data)
#     if not serializer.is_valid():
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     data = serializer.validated_data
#     employee_id = data['employee_id']
#     image_file = data.get('image')

#     if not image_file:
#         return Response({"error": "No image provided"}, status=400)

#     encoding = imagefile_to_encoding(image_file)
#     if not encoding:
#         return Response({"error": "No face detected in the uploaded image"}, status=400)

#     emp = Employee.objects.filter(employee_id=employee_id).first()

#     if emp:
#         # ✅ Call the correct method
#         emp.update_encoding(encoding)
#     else:
#         # Create new employee
#         emp = Employee.objects.create(
#             employee_id=employee_id,
#             current_face_encoding=encoding,
#             created_by=request.user if request.user.is_authenticated else None
#         )

#     return Response({
#         "success": True,
#         "employee_id": emp.employee_id,
#         "current_face_encoding_count": len(emp.current_face_encoding),
#         "face_encoding_history_count": len(emp.face_encoding_data_history)
#     })



from .serializers import EmployeeStatusSerializer

import base64
import gridfs
import os
from pymongo import MongoClient
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import Employee


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_employees_with_images(request):
    """
    Fetch all employees from Django DB with image previews.
    - First checks the 'HR' MongoDB database for the image.
    - If not found, checks the 'Global' MongoDB database.
    """
    try:
        # 1️⃣ Fetch employees from local Django DB
        employees = Employee.objects.all().order_by("employee_id")
        if not employees.exists():
            return JsonResponse({"message": "No employees found"}, status=404)

        # 2️⃣ Connect to MongoDB & GridFS for both databases
        mongo_uri = os.getenv("GLOBAL_DB_HOST")
        hr_db_name = os.getenv("GLOBAL_DB_NAME_HR", "HR")
        global_db_name = os.getenv("GLOBAL_DB_NAME_GLOBAL", "Global")

        client = MongoClient(mongo_uri)
        fs_hr = gridfs.GridFS(client[hr_db_name])
        fs_global = gridfs.GridFS(client[global_db_name])

        # 3️⃣ Build response list
        employee_list = []
        for emp in employees:
            base64_img = None

            if emp.image_md5:
                file_obj = fs_hr.find_one({"md5": emp.image_md5})
                if not file_obj:  # ⏩ Check Global DB if not found in HR
                    file_obj = fs_global.find_one({"md5": emp.image_md5})

                if file_obj:
                    try:
                        img_bytes = file_obj.read()
                        base64_img = (
                            f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
                        )
                    except Exception:
                        base64_img = None

            employee_list.append({
                "employee_id": emp.employee_id,
                "name": emp.name,
                "is_active": emp.is_active,
                "image_md5": emp.image_md5,
                "created_date": emp.created_date,
                "lastmodified_date": emp.lastmodified_date,
                "image_preview": base64_img,
            })

        # 4️⃣ Return JSON response
        return JsonResponse(employee_list, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

import base64
from django.http import JsonResponse, FileResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import Employee
from pymongo import MongoClient
from bson import ObjectId
import gridfs
import os
from io import BytesIO


@api_view(['GET'])
@permission_classes([AllowAny])
def get_employee_by_md5(request, image_md5):
    """
    Fetch employee details and image (preview) by image_md5
    """
    try:
        # 1️⃣ Find employee in Django DB
        emp = Employee.objects.filter(image_md5=image_md5).first()
        if not emp:
            return JsonResponse({"error": "No employee found for this MD5"}, status=404)

        # 2️⃣ Connect to MongoDB to fetch image
        mongo_uri = os.getenv("GLOBAL_DB_HOST")
        global_db = os.getenv("GLOBAL_DB_NAME", "HR")
        client = MongoClient(mongo_uri)
        fs = gridfs.GridFS(client[global_db])

        # 3️⃣ Find image file by MD5 hash in GridFS
        file_obj = fs.find_one({"md5": image_md5})
        if not file_obj:
            # Image not found in GridFS — still return employee info
            return JsonResponse({
                "employee_id": emp.employee_id,
                "name": emp.name,
                "is_active": emp.is_active,
                "image_md5": emp.image_md5,
                "image_preview": None,
                "message": "Employee found, but image not found in GridFS"
            }, status=200)

        # 4️⃣ Read image bytes
        img_bytes = file_obj.read()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')

        # 5️⃣ Return employee + base64 preview
        return JsonResponse({
            "employee_id": emp.employee_id,
            "name": emp.name,
            "is_active": emp.is_active,
            "image_md5": emp.image_md5,
            "created_date": emp.created_date,
            "lastmodified_date": emp.lastmodified_date,
            "image_preview": f"data:image/jpeg;base64,{base64_img}",
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

from django.shortcuts import get_object_or_404

@api_view(['POST'])
def enable_facial_recognition(request, employee_id):
    emp = get_object_or_404(Employee, employee_id=employee_id)
    emp.is_active = True
    emp.save(update_fields=['is_active'])
    return Response({"success": True, "employee_id": emp.employee_id})




@api_view(['POST'])
def disable_facial_recognition(request, employee_id):
    emp = get_object_or_404(Employee, employee_id=employee_id)

    if not emp.current_face_encoding:
        return Response({"error": "No active face encoding found"}, status=400)

    emp.is_active = False
    emp.save(update_fields=['is_active'])
    return Response({"success": True, "employee_id": emp.employee_id})

import gridfs
from pymongo import MongoClient
import json
import os
import mimetypes
from django.http import HttpResponse, Http404
from bson import ObjectId
from gridfs import GridFS
from dotenv import load_dotenv
import os
load_dotenv()



from bson import ObjectId
from django.http import JsonResponse
from pymongo import MongoClient
import os
from rest_framework.decorators import api_view

@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_employee_from_global(request):
    """
    Get ALL employee profiles with department & designation names resolved,
    include profile image URLs, encoding status, and local is_active flag.
    """
    try:
        # ✅ Connect to Global MongoDB
        mongo_uri = os.environ.get("GLOBAL_DB_HOST")
        db_name = os.environ.get("GLOBAL_DB_NAME", "Global")
        client = MongoClient(mongo_uri)
        db = client[db_name]

        profiles_col = db['backend_diagnostics_profile']
        departments_col = db['backend_diagnostics_Departments']
        designations_col = db['backend_diagnostics_Designation']

        # ✅ Fetch all employees from Global DB
        global_employees = list(profiles_col.find())

        # ✅ Create department & designation lookup maps
        dept_map = {
            d.get('department_code'): d.get('department_name')
            for d in departments_col.find({'is_active': True})
        }
        desig_map = {
            d.get('Designation_code'): d.get('designation')
            for d in designations_col.find({'is_active': True})
        }

        # ✅ Fetch all locally stored employees
        local_employees = Employee.objects.all().values(
            "employee_id", "current_face_encoding", "is_active"
        )

        # Build a dictionary of {employee_id: {has_encoding, is_active}}
        local_employee_map = {
            str(emp["employee_id"]): {
                "has_encoding": bool(emp["current_face_encoding"]),
                "is_active": emp["is_active"]
            }
            for emp in local_employees
        }

        # ✅ Base URL for image serving
        base_url = request.build_absolute_uri('/')[:-1]

        result = []
        for emp in global_employees:
            emp_id = str(emp.get("employeeId"))

            # Determine encoding and active status
            if emp_id in local_employee_map:
                encoding_status = (
                    "Encoded" if local_employee_map[emp_id]["has_encoding"] else "No Encoding"
                )
                is_active = local_employee_map[emp_id]["is_active"]
            else:
                encoding_status = "Not Found Locally"
                is_active = False  # Default for missing local record

            emp_data = {
                "employeeId": emp_id,
                "employeeName": emp.get("employeeName"),
                "email": emp.get("email"),
                "department": dept_map.get(emp.get("department"), emp.get("department")),
                "designation": desig_map.get(emp.get("designation"), emp.get("designation")),
                "mobileNumber": emp.get("mobileNumber"),
                "gender": emp.get("gender"),
                "age": emp.get("age"),
                "primaryRole": emp.get("primaryRole"),
                "additionalRoles": emp.get("additionalRoles", []),
                "profileImage": None,
                "encodingStatus": encoding_status,  # ✅ Add encoding check result
                "is_active": is_active,             # ✅ Add local is_active flag
            }

            # ✅ Add profile image URL if available
            profile_img_id = emp.get("profileImage")
            if profile_img_id:
                emp_data["profileImage"] = f"{base_url}/_b_a_c_k_e_n_d/HR/serve-file/{profile_img_id}/"

            result.append(emp_data)

        return JsonResponse(result, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

from django.db import transaction
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from bson import ObjectId
from io import BytesIO
import requests, os
from pymongo import MongoClient
from .models import Employee
from .serializers import EmployeeCreateSerializer
from .face_utils import imagefile_to_encoding ,compute_md5 # assuming you have this

# ✅ Common function for both register and encode APIs
def save_or_update_encoding(employee_id, encoding, created_by=None):
    """
    Common logic for saving or updating an employee's face encoding.
    - If exists → move current encoding to history, update new one
    - If not exists → create new entry
    Works for both ORM (Django) and MongoDB depending on setup.
    """
    emp = Employee.objects.filter(employee_id=employee_id).first()
    if emp:
        emp.update_encoding(encoding)
    else:
        emp = Employee.objects.create(
            employee_id=employee_id,
            current_face_encoding=encoding,
            created_by=created_by
        )
    return emp


# ✅ 1. Register Employee (via uploaded image)
# ✅ 1. Register Employee (save encoding + image to GridFS)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_employee(request):
    serializer = EmployeeCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    data = serializer.validated_data
    employee_id = data['employee_id']
    name = data.get('name', '')
    image_file = data.get('image')

    if not image_file:
        return JsonResponse({"error": "No image provided"}, status=400)

    # ✅ Compute image MD5 hash
    image_md5 = compute_md5(image_file)

    # ✅ Convert image to face encoding
    encoding = imagefile_to_encoding(image_file)
    if not encoding:
        return JsonResponse({"error": "No face detected in uploaded image"}, status=400)

    try:
        # ✅ Connect to MongoDB (use your local or cloud URI)
        mongo_uri = os.getenv("GLOBAL_DB_HOST")
        global_db = os.getenv("HR_DB_NAME", "HR")
        client = MongoClient(mongo_uri)
        db = client[global_db]
        fs = gridfs.GridFS(db)

        # ✅ Save image to GridFS
        image_file.seek(0)  # reset pointer
        gridfs_file_id = fs.put(
            image_file.read(),
            filename=f"{employee_id}_{name}.jpg",
            content_type=image_file.content_type,
            employeeId=employee_id,
            md5=image_md5
        )

        # ✅ Save encoding & metadata in Employee model
        emp = save_or_update_encoding(
            employee_id,
            encoding,
            created_by=request.user if request.user.is_authenticated else None,
            name=name,
            image_md5=image_md5
        )

        # ✅ Store reference to GridFS ID in model (if field exists)
        if hasattr(emp, "gridfs_image_id"):
            emp.gridfs_image_id = str(gridfs_file_id)
            emp.save(update_fields=["gridfs_image_id"])

        return JsonResponse({
            "success": True,
            "employee_id": emp.employee_id,
            "name": emp.name,
            "image_md5": emp.image_md5,
            "gridfs_image_id": str(gridfs_file_id),
            "current_face_encoding_count": len(emp.current_face_encoding or []),
            "face_encoding_history_count": len(emp.face_encoding_data_history or [])
        })

    except Exception as e:
        return JsonResponse({"error": f"Failed to save image in GridFS: {str(e)}"}, status=500)
    
    
def save_or_update_encoding(employee_id, encoding, created_by=None, name=None, image_md5=None):
    emp, created = Employee.objects.get_or_create(
        employee_id=employee_id,
        defaults={
            "name": name or "",
            "current_face_encoding": encoding,
            "image_md5": image_md5,
            "created_by": created_by
        }
    )

    if not created:
        # Update existing record
        emp.name = name or emp.name
        emp.update_encoding(encoding, new_image_md5=image_md5)
        emp.lastmodified_by = created_by
        emp.save(update_fields=['name', 'lastmodified_by', 'lastmodified_date', 'image_md5'])

    return emp

import hashlib
# ✅ 2. Encode Employee Face (from Global DB)
@api_view(['POST'])
@permission_classes([AllowAny])
def encode_employee_face(request, employee_id):
    try:
        mongo_uri = os.getenv("GLOBAL_DB_HOST")
        global_db = os.getenv("GLOBAL_DB_NAME", "Global")
        client = MongoClient(mongo_uri)
        global_profiles = client[global_db]['backend_diagnostics_profile']

        emp = global_profiles.find_one({"employeeId": employee_id})
        if not emp:
            return JsonResponse({"error": f"Employee {employee_id} not found"}, status=404)

        profile_img_id = emp.get("profileImage")
        name = emp.get("employeeName", "")
        if not profile_img_id:
            return JsonResponse({"error": "Profile image missing"}, status=400)

        base_url = request.build_absolute_uri('/')[:-1]
        image_url = f"{base_url}/_b_a_c_k_e_n_d/HR/serve-file/{profile_img_id}/"
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()

        img_bytes = BytesIO(resp.content)
        
        # ✅ Compute MD5 for fetched image
        image_md5 = hashlib.md5(resp.content).hexdigest()

        encoding = imagefile_to_encoding(img_bytes)
        if not encoding:
            return JsonResponse({"error": "No face detected in image"}, status=422)

        emp_obj = save_or_update_encoding(
            employee_id,
            encoding,
            created_by=request.user if request.user.is_authenticated else None,
            name=name,
            image_md5=image_md5
        )

        return JsonResponse({
            "success": True,
            "employee_id": emp_obj.employee_id,
            "name": emp_obj.name,
            "image_md5": emp_obj.image_md5,
            "is_active": emp_obj.is_active,
            "current_face_encoding": emp_obj.current_face_encoding
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



@api_view(['GET'])
def serve_file(request, file_id):
    try:
        client = MongoClient(os.getenv('GLOBAL_DB_HOST'))
        db = client[os.getenv('GLOBAL_DB_NAME','Global')]
        fs = GridFS(db)

        file_id = ObjectId(file_id)
        file = fs.get(file_id)

        # Try to detect MIME type from filename
        content_type, _ = mimetypes.guess_type(file.filename)
        if not content_type:
            content_type = file.content_type or 'application/octet-stream'  # fallback

        response = HttpResponse(file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{file.filename}"'
        return response

    except Exception as e:
        raise Http404(f"File not found or invalid: {str(e)}")
    



# views.py
from django.http import JsonResponse

from django.http import JsonResponse
from user_agents import parse

def get_device_info(request):
    ua_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = parse(ua_string)

    device_details = {
        "browser": user_agent.browser.family,       # e.g. Chrome
        "browser_version": user_agent.browser.version_string,
        "os": user_agent.os.family,                 # e.g. Windows
        "os_version": user_agent.os.version_string,
        "device": user_agent.device.family,         # e.g. iPhone, Desktop
        "is_mobile": user_agent.is_mobile,
        "is_tablet": user_agent.is_tablet,
        "is_pc": user_agent.is_pc,
        "ip_address": (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0]
            or request.META.get('REMOTE_ADDR')
        )
    }
    return JsonResponse(device_details)

from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from employees.models import Employee
from .models import EmployeeAttendance
from employees.face_utils import base64_to_encoding, compare_encodings, imagefile_to_encoding
import numpy as np
import ast
from .models import Register
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from pyauth.auth import HasRolePermission

def to_list(encoding):
    if isinstance(encoding, str):
        return ast.literal_eval(encoding)
    return encoding


@api_view(['POST'])
@permission_classes([HasRolePermission])
def mark_attendance(request):
    image_file = request.FILES.get('image')
    image_b64 = request.data.get('image')
    employee_id = request.data.get('auth-user-id')
    # print(f"Marking attendance for employee_id: {employee_id}")
    # Handle both file and base64 image input
    if image_file:
        unknown_encoding = imagefile_to_encoding(image_file)
    elif image_b64:
        unknown_encoding = base64_to_encoding(image_b64)
    else:
        return Response({"error": "Image is required"}, status=400)

    if not unknown_encoding:
        return Response({"error": "No face found in image"}, status=400)

    # Load all employees with valid face encodings
    employees = Employee.objects.exclude(current_face_encoding__isnull=True)

    matched_employee = None
    best_distance = float('inf')

    for emp in employees:
        # ✅ Use custom active check instead of field
        if not emp.is_active:
            continue

        emp_encoding = to_list(emp.current_face_encoding)
        unknown_encoding_np = np.array(unknown_encoding)

        if len(emp_encoding) == 0 or len(unknown_encoding_np) == 0:
            continue  # skip invalid encodings

        match, dist = compare_encodings(emp_encoding, unknown_encoding_np)
        if dist < best_distance:
            best_distance = dist
            matched_employee = emp
            if match:
                break

    if not matched_employee or best_distance > 0.6:
        return Response({"error": "No matching active employee found"}, status=404)

    mode = request.data.get('mode', 'IN')

    # Save Attendance
    att = EmployeeAttendance.objects.create(
        employee_id=matched_employee.employee_id,
        device_id=request.data.get('auth-user-id', 'unknown_device'),
        attendence_type=mode,
        confidence=best_distance
    )

    return Response({
        "employee": matched_employee.employee_id,
        "name": matched_employee.name,
        "mode": att.attendence_type,
        "timestamp": att.attendence_time,
        "confidence": best_distance
    }, status=201)

from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from pymongo import MongoClient
from django.http import JsonResponse
import os
from .models import EmployeeAttendance  # adjust the import path

@api_view(['GET'])
@permission_classes([AllowAny])
def attendance_report_with_employee_details(request):
    """
    Get attendance records filtered by date and merged with employee details.
    Example: /api/attendance-report/?from_date=2025-10-01&to_date=2025-10-14
    """
    try:
        # ---- Date Filtering ----
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')

        if not from_date or not to_date:
            now = datetime.now()
            from_date = datetime(now.year, now.month, 1)
            to_date = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d")
            to_date = datetime.strptime(to_date, "%Y-%m-%d")

        # ---- Fetch Attendance Records ----
        records = EmployeeAttendance.objects.filter(
            attendence_time__gte=from_date,
            attendence_time__lt=to_date
        ).order_by('-attendence_time')

        if not records.exists():
            return Response([], status=200)

        # ---- Mongo Connection ----
        mongo_uri = os.environ.get("GLOBAL_DB_HOST")
        db_name = os.environ.get("GLOBAL_DB_NAME", "Global")
        client = MongoClient(mongo_uri)
        db = client[db_name]

        profiles = db['backend_diagnostics_profile']
        departments = db['backend_diagnostics_Departments']
        designations = db['backend_diagnostics_Designation']

        # ---- Create Lookup Maps ----
        dept_map = {
            d.get('department_code'): d.get('department_name')
            for d in departments.find({'is_active': True})
        }
        desig_map = {
            d.get('Designation_code'): d.get('designation')
            for d in designations.find({'is_active': True})
        }

        # ---- Create Employee Lookup ----
        employee_map = {}
        for emp in profiles.find():
            employee_map[emp.get("employeeId")] = {
                "employeeName": emp.get("employeeName"),
                "department": dept_map.get(emp.get("department"), emp.get("department")),
                "designation": desig_map.get(emp.get("designation"), emp.get("designation")),
            }

        # ---- Combine Attendance + Employee Info ----
        result = []
        for r in records:
            emp_info = employee_map.get(r.employee_id, {})
            result.append({
                "employee_id": r.employee_id,
                "employee_name": emp_info.get("employeeName", "Unknown"),
                "department": emp_info.get("department", "N/A"),
                "designation": emp_info.get("designation", "N/A"),
                "device_id": r.device_id,
                "attendence_type": r.attendence_type,
                "attendence_time": r.attendence_time,
                "confidence": r.confidence,
            })

        return Response(result, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['GET', 'POST', 'PUT'])
@csrf_exempt
def registration(request):
    if request.method == 'POST':
        # Handle Registration
        name = request.data.get('name')
        role = request.data.get('role')
        password = request.data.get('password')
        confirm_password = request.data.get('confirmPassword')
        fingerprint_id = request.data.get('fingerprint_id')
        device = request.data.get('device')

        # Validate password match
        if password != confirm_password:
            return Response({"error": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST)

        # Check for duplicates
        if Register.objects.filter(name=name, role=role).exists():
            return Response({"error": "User with this name and role already exists"}, status=status.HTTP_400_BAD_REQUEST)

        # Create new record including fingerprint_id and device
        Register.objects.create(
            name=name,
            role=role,
            password=password,
            confirmPassword=confirm_password,
            fingerprint_id=fingerprint_id,
            device=device
        )

        return Response({"message": "Registration successful!"}, status=status.HTTP_201_CREATED)
    

import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import JsonResponse
from dotenv import load_dotenv
from .models import Register

load_dotenv()  # Load .env file

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    name = request.data.get('name')
    password = request.data.get('password')
    try:
        user = Register.objects.get(name=name)

        if user.password != password:
            return Response({"error": "Invalid password"}, status=401)

        device_name = user.device
        token_env_key = f"{device_name}_TOKEN"  # e.g., LAB_MAC_01_TOKEN
        print("token_env_key",token_env_key)
        token = os.getenv(token_env_key)
        print("token",token)
        if not token:
            return Response({
                "error": f"No token found for device {device_name}. Please check environment settings."
            }, status=403)

        return Response({
            "message": f"Login successful as {user.role}, {user.name}",
            "device": device_name,
            "name": user.name,
            "token": token
        }, status=200)

    except Register.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@api_view(['POST'])
@permission_classes([AllowAny])
def fingerprint_login(request):
    fingerprint_id = request.data.get('fingerprint_id')

    if not fingerprint_id:
        return JsonResponse({'error': 'Fingerprint ID is required'}, status=400)

    try:
        employee = Register.objects.get(fingerprint_id=fingerprint_id)
        device_name = employee.device
        print(f"Device name from DB: {device_name}")
        token_env_key = f"{device_name}_TOKEN"
        token = os.getenv(token_env_key)

        if not token:
            return JsonResponse({
                'error': f'No token found for device {device_name}. Please check environment settings.'
            }, status=403)

        return JsonResponse({
            'success': True,
            'device': device_name,
            'name': employee.name,
            'token': token,
            'message': 'Fingerprint authentication successful'
        }, status=200)

    except Register.DoesNotExist:
        return JsonResponse({
            'error': 'Device fingerprint not registered. Please contact administrator.'
        }, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# app/views.py
import os
import tempfile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from faster_whisper import WhisperModel

# load once at startup (change size as needed)
model = WhisperModel("base", device="cpu", compute_type="int8")

@csrf_exempt
def transcribe_audio(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    audio = request.FILES["file"]

    # save temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        for chunk in audio.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    # run transcription
    segments, info = model.transcribe(tmp_path)
    text = " ".join([seg.text for seg in segments])

    os.remove(tmp_path)
    return JsonResponse({
        "text": text,
        "language": info.language,
        "probability": info.language_probability,
    })
