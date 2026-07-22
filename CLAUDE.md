# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**HR_backend** is a Django REST API for biometric-based HR management featuring facial recognition for attendance marking, employee registration, shift management, and security monitoring. The system integrates with a MongoDB backend (global and HR-specific databases) for employee data and uses face recognition for identity verification with anti-spoofing detection.

**Repository:** https://github.com/SMRFT/HR_backend

## Tech Stack

- **Framework:** Django 3.2 with Django REST Framework 3.13.1
- **Database:** MongoDB (Djongo ORM for MongoDB-Django integration)
- **Face Recognition:**
  - `face_recognition` (encoding/matching with HOG detector)
  - `DeepFace` (anti-spoofing/liveness detection with MTCNN)
  - `opencv-python`, `pillow` (image processing)
- **ML/Detection:** TensorFlow, Keras, PyTorch, MTCNN, InsightFace, RetinaFace
- **API Auth:** SimpleJWT, custom IP-based device whitelisting
- **Utilities:** pandas, openpyxl (roster exports), requests, qrcode, twilio
- **Deployment:** Gunicorn, django-sslserver, CORS headers

## Environment Setup

**Required Environment Variables** (set in `.env` or `.env.local`):
```
GLOBAL_DB_HOST=mongodb://[user:password@]host:port/
GLOBAL_DB_NAME=Global                    # Global enterprise database
GLOBAL_DB_NAME_HR=HR                     # Local HR-specific database (face encodings)
GLOBAL_DB_NAME_GLOBAL=Global             # Fallback for employee profiles
HR_DB_NAME=HR                            # Primary HR database name
```

**Quick Setup:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver 0.0.0.0:8000
```

## Core Architecture

### Models & Data Flow

**Primary Models** (Django ORM + MongoDB via Djongo):
- **Employee:** Stores face encodings (current + history), MD5 hashes for duplicate detection, audit fields
- **EmployeeAttendance:** Punch records with confidence scores from face matching
- **Register:** User registration for HR portal (credentials, device info)
- **AllowedDevice:** Whitelist of devices (IP + fingerprint) for face recognition endpoints
- **Shift/Department:** Schedule management with many-to-many relationships
- **EmployeeShiftSchedule:** Maps employees to shifts per date
- **SpoofingAttempt:** Logs flagged spoofing/liveness check failures (stores base64 images)
- **FaceMismatchLog:** Logs face verification mismatches for audit

### Multi-Database Architecture

The system uses **two MongoDB databases**:
1. **HR Database** (`GLOBAL_DB_NAME_HR`): Face encodings, attendance, spoofing logs (Django ORM)
2. **Global Database** (`GLOBAL_DB_NAME`): Employee profiles, departments, designations (read-only via MongoClient)

**Key Pattern:** Views access Global DB directly for employee/department resolution, then filter HR DB records by resolved IDs.

### Face Recognition Pipeline

**Encoding Storage:**
```python
Employee.current_face_encoding        # Latest 128D vector (from face_recognition library)
Employee.face_encoding_data_history   # JSONField list of previous encodings
Employee.image_md5                    # MD5 hash for duplicate image detection
```

**Matching (1:N Identification):**
- `get_optimized_encodings()` loads all active employee encodings into a numpy matrix (cached)
- `match_face_1_to_n()` uses Euclidean distance (threshold=0.45) with Lowe's NNDR (min_margin=0.05) to prevent false positives
- Anti-spoofing via `DeepFace.extract_faces()` with MiniFASNet (MTCNN detector) rejects faces with `is_real=False` or low antispoof_score (<0.25)

**Image Preprocessing:**
- CLAHE (Contrast Limited Adaptive Histogram Equalization) for lighting correction
- Automatic resizing if image >800px (speed optimization)
- Face detection uses HOG-based encoding (fast, ~0.3s per image)

### Authentication & Security

**Authorization:**
- Custom `ip_whitelist_required` decorator restricts face recognition endpoints to devices in `AllowedDevice` (by IP/fingerprint)
- Device identification via `X-Device-Id` header or `fingerprint` field
- User authentication via `Register` model + SimpleJWT (optional)
- Custom `pyauth.auth.HasRolePermission` for role-based access (imported but minimal usage in current code)

**Device Security:**
- AllowedDevice whitelist by IP address and device fingerprint
- Unrecognized devices trigger `UNDV` (unknown device violation) spoofing logs
- HTTP headers checked: `CF_CONNECTING_IP` → `X_FORWARDED_FOR` → `X_REAL_IP` → `REMOTE_ADDR`

## Key Endpoints

### Face Recognition & Attendance
- `POST /_b_a_c_k_e_n_d/HR/mark/` — Mark attendance (dual-image verification)
- `POST /verify-face/` — Verify single face (fast check, requires device whitelist)
- `POST /employees/<id>/encode_face/` — Register/update employee face encoding
- `GET /employees/<id>/` — Get employee details with face status

### Employee Management
- `GET /employees/` — List all employees with face encodings
- `GET /employees/export-xls/` — Export to Excel
- `POST /register/` — Register new employee with face image

### Shift & Roster Management
- `GET/POST /shifts/` — List/create shifts
- `GET/POST /departments/` — List/create departments
- `GET /roster/` — Get monthly roster
- `POST /roster/assign/` — Assign employee to shift
- `GET /roster/export/` — Export roster (CSV/XLSX)
- `POST /roster/import-xlsx/` — Import roster from Excel

### Reports & Monitoring
- `GET /attendance-report/` — Attendance details with employee info
- `GET /roster-report/` — Roster + actual attendance reconciliation
- `GET /spoofing-reports/` — List spoofing attempts
- `POST /spoofing-reports/delete/` — Clear spoofing logs

### Device & IP Management
- `GET /my-ip/` — Return caller's IP
- `GET /allowed-devices/` — List whitelisted devices
- `POST /allowed-devices/` — Register device
- `GET /get_device_info/` — Browser/device fingerprinting

## URL Routing

Main routes defined in `hr_backend/urls.py`:
- `/admin/` — Django admin
- `/_b_a_c_k_e_n_d/HR/` — Obfuscated backend prefix (redirects to `/employees/urls`)
- `/` — Primary namespace for `/employees/urls`

All endpoints in `employees/urls.py` are accessible via both `/` and `/_b_a_c_k_e_n_d/HR/` prefixes.

## Common Development Tasks

### Running the Project
```bash
# Development server (with auto-reload)
python manage.py runserver

# With SSL (for local testing with HTTPS)
python manage.py runsslserver 0.0.0.0:8443

# Production (via Gunicorn)
gunicorn hr_backend.wsgi --bind 0.0.0.0:8000 --workers 4
```

### Database Operations
```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Populate missing IDs in MongoDB (utility command)
python manage.py populate_ids

# Django shell for manual queries
python manage.py shell
```

### Testing & Debugging
```bash
# No automated test suite currently; tests.py is empty
python manage.py test employees

# Debug mode enabled in settings.py (DEBUG=True)
# Server logs print face matching distances, spoofing checks, IP detection
```

### Adding New Endpoints
1. Add view function in `employees/views/[category].py` decorated with `@api_view(['GET'|'POST'|...])` and `@permission_classes([AllowAny] or [HasRolePermission])`
2. Import in `employees/views/__init__.py`
3. Register URL pattern in `employees/urls.py`
4. For face recognition endpoints, add `@ip_whitelist_required` decorator to restrict device access

### Adding New Fields to Employee
1. Update `Employee` model in `employees/models.py`
2. Create migration: `python manage.py makemigrations`
3. Apply migration: `python manage.py migrate`
4. Update `EmployeeSerializer` in `employees/serializers.py` if needed
5. Consider forcing face encoding cache refresh in dependent views

## Important Patterns & Gotchas

### Djongo Limitations
- Djongo doesn't support complex QuerySet filters (e.g., `Q()` objects with nested conditions on JSONFields)
- Workaround: Fetch all records in Python and filter in memory for small datasets (~300 employees)
- See `get_optimized_encodings()` which fetches all employees and filters by `is_active` in Python

### Face Encoding Cache
- Global `_ENCODING_CACHE` dict in `employees/views/attendance.py` holds numpy matrix of all active encodings
- Call `get_optimized_encodings(force_refresh=True)` after registering/updating employee faces
- Cache is automatically refreshed if empty or stale

### Mongo Database Naming Confusion
- Multiple database names used: `HR`, `Global`, `Global-HR`, etc.
- Check `.env` for actual mapping; code sometimes falls back to hardcoded defaults
- Department lookups cross both SQL (`Department` model) and Mongo (`backend_diagnostics_Departments`)

### Anti-Spoofing & Liveness Detection
- **Strict enforcement:** `is_real=False` blocks access immediately
- **Soft enforcement:** Low antispoof_score (<0.25) also blocks but is more lenient than `is_real` flag
- Liveness check runs on original image **before** CLAHE preprocessing to avoid corruption
- DeepFace errors default to `is_real=True` (fail-open for usability)

### Dual-Image Verification Flow
- `verify_face()` — Quick check on first frame; returns early if face match found and device authorized
- `mark_attendance()` — Requires two different images for final attendance mark (prevents single-image replay)
- Both images must pass anti-spoofing; distance must be below threshold

### Grid FS Image Storage
- Employee registration images stored in MongoDB GridFS, not on disk
- Accessed via `mongo_client['db_name'].fs.files` and `fs.chunks` collections
- Image MD5 stored in `Employee.image_md5` for lookup and duplicate detection

### CORS & Headers
- `CORS_ALLOW_ALL_ORIGINS=True` in development (restrict in production)
- Custom headers: `Authorization`, `X-User-Role`, `X-Device-Id`
- `USE_X_FORWARDED_HOST=True` for proxy/Nginx scenarios

### Email & SMS (Twilio)
- Twilio package imported but not actively used in current code
- Available for future notifications/alerts

## Settings Files

- **settings.py** — Development (DEBUG=True, CORS_ALLOW_ALL_ORIGINS=True)
- **settings-prod.py** — Production stub (same as dev; customize for production)
- **settings-test.py** — Test settings (not yet configured)

**Note:** `DJANGO_SETTINGS_MODULE` defaults to `hr_backend.settings` in `manage.py`

## Docker & Deployment

No Dockerfile or docker-compose.yml currently in repo. For deployment:
- Use `gunicorn` with `hr_backend.wsgi` application
- Ensure MongoDB is accessible at `GLOBAL_DB_HOST`
- Set `DEBUG=False`, restrict `ALLOWED_HOSTS`, customize `SECRET_KEY` for production
- Enable HTTPS, restrict `CORS_ALLOW_HEADERS` to known origins

## Known Issues & TODO

- Anti-spoofing DeepFace model is computationally expensive; consider caching or batch processing for high volume
- No automated test suite; `tests.py` is empty
- settings-prod.py and settings-test.py are not properly configured for production/testing
- Admin interface minimal (admin.py is empty); consider registering models for admin oversight
- Role-based permissions (via `pyauth`) are imported but underutilized; endpoints mostly use `AllowAny`
- Encoding cache uses global state; consider thread-safety for concurrent requests in production
- Face matching threshold (0.45) and margin (0.05) are hardcoded; consider making configurable

## File Structure (Key Files)

```
hr_backend/                         # Django project config
├── settings.py                      # Main settings (dev)
├── settings-prod.py                 # Production settings (stub)
├── urls.py                          # Root URL routing
├── wsgi.py                          # WSGI app entry point
employees/                           # Main app (models, views, serializers)
├── models.py                        # 8 models: Employee, Attendance, Register, etc.
├── serializers.py                   # DRF serializers
├── urls.py                          # Endpoint routing
├── views/                           # Modular views by feature
│   ├── attendance.py                # Face verification, mark_attendance, spoofing logs
│   ├── employee.py                  # Employee CRUD, encoding, export
│   ├── auth.py                      # Login, device registration, IP management
│   ├── shifts.py                    # Shift/department CRUD, roster assignment
│   ├── reports.py                   # Roster attendance reconciliation
│   ├── roster_report.py             # Roster import/export (CSV/XLSX)
│   ├── ip_guard.py                  # IP whitelist decorator
│   └── utils.py                     # save_or_update_encoding, to_list
├── face_utils.py                    # Face recognition: check_liveness, imagefile_to_encoding, compare_encodings, match_face_1_to_n
├── auth/
│   └── permissions_map.py           # Role mapping (minimal usage)
├── management/
│   └── commands/
│       └── populate_ids.py          # Populate missing ID fields in MongoDB
└── migrations/                      # Database migrations (18 migrations)
```

---

**Last Updated:** July 2026
**Django Version:** 3.2
**Python:** 3.x (3.8+ recommended for face_recognition compatibility)
