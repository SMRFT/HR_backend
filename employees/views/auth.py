import os
from dotenv import load_dotenv
from user_agents import parse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from employees.models import Register

load_dotenv()

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
        token = os.getenv(token_env_key)

        if not token:
            return Response({
                "error": f"No token found for device {device_name}. Please check environment settings."
            }, status=403)

        return Response({
            "message": f"Login successful as {user.role}, {user.name}",
            "device": device_name,
            "name": user.name,
            "role": user.role,
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
            'role': employee.role,
            'token': token,
            'message': 'Fingerprint authentication successful'
        }, status=200)

    except Register.DoesNotExist:
        return JsonResponse({
            'error': 'Device fingerprint not registered. Please contact administrator.'
        }, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
