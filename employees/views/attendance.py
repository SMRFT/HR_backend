from datetime import datetime
import numpy as np
import os
from pymongo import MongoClient

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from employees.models import Employee, EmployeeAttendance
from employees.face_utils import base64_to_encoding, compare_encodings, imagefile_to_encoding
from pyauth.auth import HasRolePermission

from .utils import to_list

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

        # We only care about the distance here to find the absolute best match
        # compare_encodings returns (is_match, distance)
        _, dist = compare_encodings(emp_encoding, unknown_encoding_np)
        
        if dist < best_distance:
            best_distance = dist
            matched_employee = emp

    # Check if the best match found is within our acceptable threshold (0.5)
    if not matched_employee or best_distance > 0.5:
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
