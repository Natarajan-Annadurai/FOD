import json
import smtplib
import socket
import ssl
import time
from django.contrib.auth import login as auth_login
import pdfkit
from datetime import datetime
from django.contrib.auth import logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.http import JsonResponse, FileResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import never_cache
from mysite import settings
from .models import ToolCreation, ToolPurchase, UserProfile, ProfileInformation, JobCard, Aircraft, JobToolUsage, \
    JobAuditLog, JobCardNotes
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from .models import ToolEventTracking
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

MAX_FAILED_ATTEMPTS = 3
LOCKOUT_TIME = 1 * 60  # 1 minute in seconds

@csrf_exempt
def login_view(request):
    lockout_remaining = 0  # default

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        lockout_key = f'lockout_{username}'
        failed_key = f'failed_{username}'
        lockout_time_key = f'lockout_time_{username}'

        # Check if account is locked
        if cache.get(lockout_key):
            lockout_start = cache.get(lockout_time_key, time.time())
            elapsed = time.time() - lockout_start
            lockout_remaining = max(0, int(LOCKOUT_TIME - elapsed))
            messages.error(request, f'Account locked. Try again in {lockout_remaining} seconds.')
            return render(request, 'login.html', {'lockout_remaining': lockout_remaining})

        user = authenticate(request, username=username, password=password)
        if user:
            cache.delete(failed_key)
            cache.delete(lockout_key)
            cache.delete(lockout_time_key)
            auth_login(request, user)
            return redirect('dashboard')

        # Failed login
        failed_attempts = cache.get(failed_key, 0) + 1
        cache.set(failed_key, failed_attempts, LOCKOUT_TIME)

        if failed_attempts >= MAX_FAILED_ATTEMPTS:
            cache.set(lockout_key, True, LOCKOUT_TIME)
            cache.set(lockout_time_key, time.time(), LOCKOUT_TIME)
            lockout_remaining = LOCKOUT_TIME
            messages.error(request, f'Your account is locked for {LOCKOUT_TIME} seconds.')
        else:
            remaining = MAX_FAILED_ATTEMPTS - failed_attempts
            messages.error(request, f'Invalid login. {remaining} attempts left.')

    return render(request, 'login.html', {'lockout_remaining': lockout_remaining})

@login_required
@never_cache
def dashboard_view(request):
    return render(request, 'dashboard.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')

def add_user(request):
    groups = Group.objects.all()

    if request.method == "POST":

        # AUTH USER FIELDS
        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        first_name = request.POST.get("first_name").strip()
        last_name = request.POST.get("last_name").strip()

        # PROFILE FIELDS
        phone = request.POST.get("phone")
        department = request.POST.get("department")
        location = request.POST.get("location")
        employee_id = request.POST.get("employee_id")
        designation = request.POST.get("designation")
        date_of_birth = request.POST.get("date_of_birth")
        address = request.POST.get("address")
        gender = request.POST.get("gender")
        profile_picture = request.FILES.get("profile_picture")
        role_id = request.POST.get("role")

        status = request.POST.get("status", "ACTIVE")

        # -------- VALIDATIONS -------- #

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("add_user")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("add_user")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("add_user")

        try:
            validate_password(password)
        except ValidationError as e:
            for error in e:
                messages.error(request, error)
            return redirect("add_user")

        # -------- CREATE USER -------- #
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # -------- ASSIGN ROLE (GROUP) -------- #
        if role_id:
            group = Group.objects.get(id=role_id)
            user.groups.add(group)

        # -------- CREATE PROFILE -------- #
        ProfileInformation.objects.create(
            user=user,
            phone=phone,
            department=department,
            location=location,
            employee_id=employee_id,
            designation=designation,
            date_of_birth=date_of_birth if date_of_birth else None,
            address=address,
            gender=gender,
            status=status,
            profile_picture=profile_picture
        )

        messages.success(request, "User created successfully!")
        return redirect("manage_users")

    return render(request, "users/add_user.html", {"groups": groups})

def create_role(request):
    if request.method == "POST":
        role_name = request.POST.get("role_name")

        if Group.objects.filter(name=role_name).exists():
            messages.error(request, "Role already exists.")
        else:
            Group.objects.create(name=role_name)
            messages.success(request, "Role created successfully.")

        return redirect("add_user")   # return to your user creation page

    return redirect("add_user")

from django.contrib.auth.models import Group

@login_required
def manage_users(request):
    users = User.objects.all().order_by('username')
    stations = ServiceStation.objects.all()
    units = Unit.objects.all()
    trays = Tray.objects.all()
    groups = Group.objects.all()

    # Debug: print user roles before rendering
    for user in users:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile_info, _ = ProfileInformation.objects.get_or_create(user=user) # user profile information
        group_role = user.groups.first().name if user.groups.exists() else None

        if profile.role:
            if group_role and profile.role.strip() != group_role.strip():
                profile.role = group_role.strip()
                profile.save()
            user.display_role = profile.role.strip()
        elif group_role:
            profile.role = group_role.strip()
            profile.save()
            user.display_role = group_role.strip()
        else:
            user.display_role = "Not Assigned"

        # Attach personal info from ProfileInformation
        user.phone = profile_info.phone
        user.department = profile_info.department
        user.location = profile_info.location
        user.employee_id = profile_info.employee_id
        user.designation = profile_info.designation
        user.date_of_birth = profile_info.date_of_birth
        user.address = profile_info.address
        user.gender = profile_info.gender
        user.status = profile_info.status
        user.profile_picture = profile_info.profile_picture

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role = request.POST.get('role').strip() if request.POST.get('role') else None
        station_ids = request.POST.getlist('stations')
        unit_ids = request.POST.getlist('units')
        tray_ids = request.POST.getlist('trays')

        user = get_object_or_404(User, id=user_id)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role

        # --- Assign access rules and display names ---
        if role == "Admin":
            all_stations = ServiceStation.objects.all()
            all_units = Unit.objects.all()
            all_trays = Tray.objects.all()

            profile.stations_display = ", ".join([s.name for s in all_stations])
            profile.units_display = ", ".join([u.name for u in all_units])
            profile.trays_display = ", ".join([t.tray_name for t in all_trays])

        elif role == "Supervisor":
            selected_stations = ServiceStation.objects.filter(id__in=station_ids)
            selected_units = Unit.objects.filter(station_id__in=station_ids)
            selected_trays = Tray.objects.filter(unit__station_id__in=station_ids)

            profile.stations_display = ", ".join([s.name for s in selected_stations])
            profile.units_display = ", ".join([u.name for u in selected_units])
            profile.trays_display = ", ".join([t.tray_name for t in selected_trays])

        elif role == "User":
            selected_stations = ServiceStation.objects.filter(id__in=station_ids)
            selected_units = Unit.objects.filter(id__in=unit_ids)
            selected_trays = Tray.objects.filter(id__in=tray_ids)

            profile.stations_display = ", ".join([s.name for s in selected_stations])
            profile.units_display = ", ".join([u.name for u in selected_units])
            profile.trays_display = ", ".join([t.tray_name for t in selected_trays])

        # Save IDs as comma-separated strings
        profile.station_id = ",".join(station_ids) if station_ids else None
        profile.unit_ids = ",".join(unit_ids) if unit_ids else None
        profile.tray_id = ",".join(tray_ids) if tray_ids else None

        profile.save()

        # --- Sync Django group ---
        user.groups.clear()
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
        user.save()

        return redirect('manage_users')

    return render(request, 'users/manage_users.html', {
        'users': users,
        'groups': groups,
        'stations': stations,
        'units': units,
        'trays': trays,
    })

@login_required
def update_user_status(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        status = request.POST.get("status")
        user = get_object_or_404(User, id=user_id)
        profile_info, _ = ProfileInformation.objects.get_or_create(user=user)
        profile_info.status = status
        profile_info.save()
        messages.success(request, f"{user.username}'s status updated to {status}.")
    return redirect('manage_users')

def edit_user(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, pk=user_id)
        profile = get_object_or_404(ProfileInformation, user=user)

        # ---------- AUTH USER FIELDS ----------
        email = request.POST.get("email").strip()
        first_name = request.POST.get("first_name").strip()
        last_name = request.POST.get("last_name").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # ---------- PROFILE FIELDS ----------
        phone = request.POST.get("phone")
        department = request.POST.get("department")
        location = request.POST.get("location")
        employee_id = request.POST.get("employee_id")
        designation = request.POST.get("designation")
        date_of_birth = request.POST.get("date_of_birth")
        address = request.POST.get("address")
        gender = request.POST.get("gender")
        profile_picture = request.FILES.get("profile_picture")
        role_id = request.POST.get("role")
        status = request.POST.get("status", "ACTIVE")

        # ---------- VALIDATE PASSWORD ----------
        if password:
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("manage_users")
            try:
                validate_password(password)
            except ValidationError as e:
                for error in e:
                    messages.error(request, error)
                return redirect("manage_users")
            user.set_password(password)

        # ---------- UPDATE USER ----------
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # ---------- UPDATE ROLE ----------
        if role_id:
            group = Group.objects.get(id=role_id)
            user.groups.clear()  # remove old roles
            user.groups.add(group)

        # ---------- UPDATE PROFILE ----------
        profile.phone = phone
        profile.department = department
        profile.location = location
        profile.employee_id = employee_id
        profile.designation = designation
        profile.date_of_birth = date_of_birth if date_of_birth else None
        profile.address = address
        profile.gender = gender
        profile.status = status
        if profile_picture:
            profile.profile_picture = profile_picture
        profile.save()

        messages.success(request, f"User {user.username} updated successfully!")
        return redirect("manage_users")

    messages.error(request, "Invalid request method.")
    return redirect("manage_users")


@login_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    username = user.username
    user.delete()
    messages.success(request, f"User {username} deleted successfully!")
    return redirect("manage_users")

def centralized_service_station_dashboard(request):
    service_stations = ServiceStation.objects.all()

    dashboard_data = []
    total_units = 0
    total_tools = 0
    total_jobcards = 0

    for station in service_stations:

        station_id = station.id  # Integer PK, not station_id field
        # Units under this station
        units_count = Unit.objects.filter(station_id=station_id).count()
        # Trays under this station
        trays_count = Tray.objects.filter(unit__station_id=station_id).count()
        # Tools under this station (via Tray → TrayTool)
        tools_count = TrayTool.objects.filter(tray__unit__station_id=station_id).count()

        # JobCards queryset and count
        jobcards = JobCard.objects.filter(service_station_id=station_id)
        jobcard_count = jobcards.count()

        total_units += units_count
        total_tools += tools_count
        total_jobcards += jobcard_count

        # Collect technicians info per jobcard
        technicians_info = []
        for job in jobcards:
            for tech in job.assigned_technicians.all():
                technicians_info.append({
                    'tech_name': tech.get_full_name() or tech.username,
                    'tech_id': tech.id,
                    'assigned_at': job.created_at  # or your actual assignment timestamp
                })

        dashboard_data.append({
            "station": station,
            "units_count": units_count,
            "trays_count": trays_count,
            "tools_count": tools_count,
            "jobcard_count": jobcard_count,
            "technicians": technicians_info,
        })

    return render(request, "dashboard/centralized_system_monitoring.html", {
        "dashboard_data": dashboard_data,
        "total_units": total_units,
        "total_tools": total_tools,
        "total_jobcards": total_jobcards,
    })

def service_station_report(request, station_id):

    # Get the service station
    station = get_object_or_404(ServiceStation, id=station_id)

    # Units under this station
    units_qs = Unit.objects.filter(station=station_id).prefetch_related(
        'trays',
        'jobcards',
    )

    active_jobcards_count = JobCard.objects.filter(
        service_station=station
    ).exclude(status__iexact='closed').count()

    unit_details = []
    trays_count = 0
    tools_count = 0
    jobcards_count = 0

    # To collect ALL technicians assigned across station
    station_technicians = set()

    for unit in units_qs:
        trays = list(unit.trays.values_list('tray_name', flat=True))

        unit_trays_count = unit.trays.count()

        # Tools count from TrayTool
        unit_tools_count = sum(
            TrayTool.objects.filter(tray=tray).count()
            for tray in unit.trays.all()
        )

        # Jobcards assigned to this unit
        unit_jobcards_count = unit.jobcards.count()

        # Technicians assigned to jobcards of this unit
        unit_techs = set()
        for jc in unit.jobcards.all():
            for tech in jc.assigned_technicians.all():
                unit_techs.add(tech.username)
                station_technicians.add(tech.username)

        # Tray Details
        tray_details = []
        for tray in unit.trays.all():
            tray_tools = list(
                tray.tray_tools.values_list('inventory__tool__tool_name', flat=True)
            )

            # Clean None values
            tray_tools = [tool for tool in tray_tools if tool]

            # Set status based on tools
            if tray_tools:
                tray_status = "AVAILABLE"
            else:
                tray_status = getattr(tray, 'status', 'N/A')

            tray_details.append({
                'name': tray.tray_name,
                'tools': tray_tools,
                'status': tray_status  # ← UPDATED
            })

        trays_count += unit_trays_count
        tools_count += unit_tools_count
        jobcards_count += unit_jobcards_count

        unit_details.append({
            'name': unit.name,
            'trays': trays,
            'tools_count': unit_tools_count,
            'jobcards_count': unit_jobcards_count,
            'technicians': list(unit_techs),
            'tray_details': tray_details
        })

    # Station-level jobcards
    jobcards = JobCard.objects.filter(service_station=station).prefetch_related(
        'assigned_units',
        'assigned_technicians'
    )

    context = {
        'station': station,
        'units_count': units_qs.count(),
        'trays_count': trays_count,
        'tools_count': tools_count,
        'jobcards_count': jobcards_count,

        # Correct: show total unique technicians
        'technicians_count': len(station_technicians),

        'unit_details': unit_details,
        'jobcards': jobcards,
        "user": request.user,

        # Pass sorted list of technicians
        'technicians': sorted(list(station_technicians)),
        'active_jobcards_count': active_jobcards_count,
    }

    return render(request, 'dashboard/service_station_report.html', context)


def get_service_station_report_context(station_id):
    station = ServiceStation.objects.get(id=station_id)

    # Units for this station
    units = Unit.objects.filter(station=station)

    # Count statistics
    units_count = units.count()
    trays_count = Tray.objects.filter(unit__station=station).count()
    tools_count = Inventory.objects.filter(location=station).count()
    jobcards_count = JobCard.objects.filter(service_station=station).count()
    technicians_count = User.objects.filter(
        technician_jobs__service_station=station
    ).distinct().count()

    # Unit details with trays, tools, jobcards, and technicians
    unit_details = []
    for unit in units:
        trays = Tray.objects.filter(unit=unit)

        # Get tray names
        tray_names = [t.tray_name for t in trays]

        # Count tools assigned to this UNIT via tray tools
        tools_in_unit = TrayTool.objects.filter(tray__unit=unit).count()

        jobcards_in_unit = JobCard.objects.filter(assigned_units=unit).count()
        technicians_in_unit = User.objects.filter(
            technician_jobs__assigned_units=unit
        ).distinct()

        tray_details = []
        for tray in trays:
            # Get tool names
            tray_tools = list(
                tray.tray_tools.values_list('inventory__tool__tool_name', flat=True)
            )

            # Clean up None values
            tray_tools = [tool for tool in tray_tools if tool]

            # Determine status based on whether tools exist
            if tray_tools:  # If there are tools
                tray_status = "AVAILABLE"
            else:
                tray_status = getattr(tray, 'status', 'N/A')

            tray_details.append({
                "name": tray.tray_name,
                "tools": tray_tools,
                "status": tray_status
            })

        unit_details.append({
            "name": unit.name,
            "trays": tray_names,
            "trays_count": trays.count(),
            "tools_count": tools_in_unit,
            "jobcards_count": jobcards_in_unit,
            "technicians": [
                tech.get_full_name() or tech.username
                for tech in technicians_in_unit
            ],
            "tray_details": tray_details
        })

    technicians = User.objects.filter(
        technician_jobs__service_station=station
    ).distinct()

    jobcards = JobCard.objects.filter(
        service_station=station
    ).order_by('-created_at')

    from django.utils.timezone import now

    context = {
        "station": station,
        "units_count": units_count,
        "trays_count": trays_count,
        "tools_count": tools_count,
        "jobcards_count": jobcards_count,
        "technicians_count": technicians_count,
        "unit_details": unit_details,
        "technicians": [
            tech.get_full_name() or tech.username for tech in technicians
        ],
        "jobcards": jobcards,
        "current_date": now(),
        "for_pdf": True
    }

    return context

# ----------------- PDF GENERATION -----------------

def service_station_report_pdf(request, station_id):
    station = ServiceStation.objects.get(id=station_id)
    context = get_service_station_report_context(station_id)
    context['for_pdf'] = True

    html_string = render_to_string("dashboard/service_station_pdf.html", context)

    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    )

    pdf_file = pdfkit.from_string(html_string, False, configuration=config)

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Service_Station_{station.name}.pdf"'
    )
    return response

# ----------------- EMAIL WITH PDF -----------------
from django.conf import settings
from email.message import EmailMessage


def service_station_report_email(request, station_id):
    try:
        station = ServiceStation.objects.get(id=station_id)

        # Generate PDF
        context_data = get_service_station_report_context(station_id)
        html_string = render_to_string("dashboard/service_station_pdf.html", context_data)
        config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
        pdf_file = pdfkit.from_string(html_string, False, configuration=config)

        # Prepare email
        msg = EmailMessage()
        msg['Subject'] = f"Service Station Report - {station.name}"
        msg['From'] = settings.EMAIL_HOST_USER
        msg['To'] = station.contact_email
        msg.set_content(f"Hello,\n\nPlease find attached the Service Station Report for {station.name}.")
        msg.add_attachment(pdf_file, maintype="application", subtype="pdf", filename=f"Service_Station_{station.name}.pdf")

        # Send email (bypass SSL verification for dev)
        context_ssl = ssl._create_unverified_context()
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.ehlo()
            server.starttls(context=context_ssl)
            server.ehlo()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)

        return JsonResponse({"message": "Email sent successfully!"})

    except Exception as e:
        return JsonResponse({"message": f"Error sending email: {str(e)}"})

def get_units_by_station(request, station_id):
    units = Unit.objects.filter(station_id=station_id)

    data = []
    for u in units:
        tray_count = Tray.objects.filter(unit=u).count()
        tool_count = TrayTool.objects.filter(tray__unit=u).count()

        data.append({
            "unit_id": u.id,
            "name": u.name,
            "status": u.status,
            "tray_count": tray_count,
            "tool_count": tool_count,
        })

    return JsonResponse(data, safe=False)

def get_trays_by_unit(request, unit_id):
    trays = Tray.objects.filter(unit_id=unit_id)
    data = []

    for t in trays:
        tray_tools = TrayTool.objects.filter(tray=t)

        total_available = 0
        total_inuse = 0

        for tt in tray_tools:
            tool_id = tt.tool_id
            assigned_qty = tt.assigned_quantity

            # Count events properly
            issued = ToolEventTracking.objects.filter(
                tray_id=t.tray_id,
                tool_id=tool_id,
                event__iexact="tool_issued"
            ).count()

            returned = ToolEventTracking.objects.filter(
                tray_id=t.tray_id,
                tool_id=tool_id,
                event__iexact="tool_returned"
            ).count()

            # Correct count
            inuse = min(max(issued - returned, 0), assigned_qty)
            available = max(assigned_qty - inuse, 0)

            total_inuse += inuse
            total_available += available

        total_tools = total_inuse + total_available

        data.append({
            "tray_id": t.id,
            "tray_id_original": t.tray_id,
            "tray_name": t.tray_name,
            "total_tools": total_tools,
            "available_tools": total_available,
            "inuse_tools": total_inuse,
        })

    return JsonResponse(data, safe=False)

def get_tools_by_tray(request, tray_id):

    # Try both with and without 'T' prefix
    tray_id_variations = [tray_id]

    # If tray_id doesn't start with 'T', try adding it
    if not str(tray_id).startswith('T'):
        tray_id_with_t = f"T{tray_id:0>3}"  # Format as T032 if tray_id is 32
        tray_id_variations.append(tray_id_with_t)
    # If tray_id starts with 'T', try removing it
    elif str(tray_id).startswith('T'):
        tray_id_without_t = tray_id.lstrip('T')
        tray_id_variations.append(tray_id_without_t)

    # Check which variation exists in ToolEventTracking
    existing_tray_id = None
    for variation in tray_id_variations:
        exists = ToolEventTracking.objects.filter(tray_id=variation).exists()
        if exists:
            existing_tray_id = variation
            break

    if existing_tray_id:
        event_tray_id = existing_tray_id
    else:
        event_tray_id = tray_id  # Use original for queries, will return 0 results

    tray_tools = TrayTool.objects.filter(tray_id=tray_id).select_related(
        'inventory', 'inventory__tool'
    )

    data = []

    for t in tray_tools:
        inv = t.inventory
        tool_obj = inv.tool if inv else None

        tool_name = tool_obj.tool_name if tool_obj else "Unknown"
        tool_serial = tool_obj.tool_id if tool_obj else None
        total_assigned_qty = t.assigned_quantity

        issued_count = returned_count = 0

        if tool_serial:
            # Query events using the correct tray_id
            events_for_tool = ToolEventTracking.objects.filter(
                tray_id=event_tray_id,
                tool_id=tool_serial
            )

            if events_for_tool.exists():
                for ev in events_for_tool:
                    print(f"  ID {ev.id}: event='{ev.event}', "
                          f"tool_id='{ev.tool_id}', tray_id='{ev.tray_id}', "
                          f"timestamp={ev.timestamp}")

                # Count events
                issued_count = events_for_tool.filter(event='tool_Issued').count()
                returned_count = events_for_tool.filter(event='tool_Returned').count()
            else:
                print(f"No events found for tool '{tool_serial}' in tray '{event_tray_id}'")

        # Compute stock
        in_use_count = min(max(issued_count - returned_count, 0), total_assigned_qty)
        available_count = max(total_assigned_qty - in_use_count, 0)

        status_parts = []
        if in_use_count > 0:
            status_parts.append(f"IN-USE ({in_use_count})")
        if available_count > 0:
            status_parts.append(f"AVAILABLE ({available_count})")

        status = " ".join(status_parts) if status_parts else "UNASSIGNED"

        data.append({
            "name": tool_name,
            "tool_id": tool_serial,
            "tray_name": t.tray.tray_name,
            "status": status,
            "assigned": total_assigned_qty,
            "issued": issued_count,
            "returned": returned_count,
            "in_use": in_use_count,
            "available": available_count,
        })

    for item in data:
        print(f"  {item['name']}: {item['status']}")

    return JsonResponse(data, safe=False)

def jobcard_list_by_station(request, station_id):
    jobcards = JobCard.objects.select_related(
        'aircraft', 'qa_inspector', 'service_station', 'created_by'
    ).prefetch_related(
        'assigned_units', 'assigned_technicians'
    ).filter(service_station_id=station_id).order_by('-created_at')

    # Summary counts
    total_jobcards = jobcards.count()
    in_progress_count = jobcards.filter(status='IN_PROGRESS').count()
    completed_count = jobcards.filter(status='CLOSED').count()
    high_priority_count = jobcards.filter(priority='HIGH').count()
    critical_count = jobcards.filter(priority='CRITICAL').count()

    units = Unit.objects.filter(station_id=station_id)  # Only units in this station

    mechanics = User.objects.filter(
        userprofile__role='User',
        profile__status='ACTIVE',
        technician_jobs__service_station_id=station_id
    ).distinct()

    qa_users = User.objects.filter(
        Q(userprofile__role__iexact='Supervisor') |
        Q(userprofile__role__iexact='Admin') |
        Q(is_superuser=True)
    ).distinct()

    context = {
        'jobcards': jobcards,
        'total_jobcards': total_jobcards,
        'units': units,
        'mechanics': mechanics,
        'qa_users': qa_users,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'high_priority_count': high_priority_count,
        'critical_count': critical_count,
        'station_id': station_id,
    }

    return render(request, 'jobcards/jobcard_list.html', context)

def tool_activity_dashboard(request):
    # All events ordered by latest
    events_list = ToolEventTracking.objects.all().order_by('-timestamp')

    for event in events_list:
        if event.job_id:
            event.short_job_id = event.job_id.split(" ")[0]
        else:
            event.short_job_id = None

    # Pagination for events (25 per page)
    events_paginator = Paginator(events_list, 10)
    page_number = request.GET.get('events_page', 1)
    events_page = events_paginator.get_page(page_number)

    # Calculate Tool Usage Duration (anyone returned)
    durations_list = []

    # Get all tool_ids
    tool_ids = ToolEventTracking.objects.values_list('tool_id', flat=True).distinct()

    for tool_id in tool_ids:
        # Get all events for this tool ordered by timestamp
        events = ToolEventTracking.objects.filter(tool_id=tool_id).order_by('timestamp')

        last_issued = None
        for event in events:
            if event.event == 'tool_Issued':
                last_issued = event  # remember latest issued
            elif event.event == 'tool_Returned' and last_issued:
                # Calculate duration from last issued to this returned
                duration = event.timestamp - last_issued.timestamp
                short_job_id = last_issued.job_id.split(" ")[0] if last_issued.job_id else None
                durations_list.append({
                    'tool_id': tool_id,
                    'tool_name': last_issued.tool_name,
                    'issued_by': last_issued.user_name,
                    'returned_by': event.user_name,
                    'service_station': last_issued.service_station,
                    'unit': last_issued.unit,
                    'tray_id': last_issued.tray_id,
                    'client_ip': last_issued.client_ip,
                    'device_id': last_issued.device_id,
                    'issued_at': last_issued.timestamp,
                    'returned_at': event.timestamp,
                    'duration_in_use': duration,
                    'short_job_id': short_job_id,
                })
                last_issued = None

        # Sort newest issued first
        durations_list = sorted(durations_list, key=lambda x: x['issued_at'], reverse=True)

    # Pagination for durations (25 per page)
    durations_paginator = Paginator(durations_list, 10)
    durations_page_number = request.GET.get('durations_page', 1)
    durations_page = durations_paginator.get_page(durations_page_number)

    # Summary calculations
    today = timezone.now().date()
    todays_events = ToolEventTracking.objects.filter(timestamp__date=today)
    total_events = todays_events.count()

    # Get latest event per tool_id
    latest_tool_events = ToolEventTracking.objects.values('tool_id').annotate(
        last_event_time=Max('timestamp')
    )

    active_tools_count = 0
    active_users_set = set()

    for item in latest_tool_events:
        latest_event = ToolEventTracking.objects.filter(
            tool_id=item['tool_id'],
            timestamp=item['last_event_time']
        ).first()
        if latest_event and latest_event.event == 'tool_Issued':
            active_tools_count += 1
            active_users_set.add(latest_event.user_id)

    active_users = len(active_users_set)

    # Damaged tools
    damaged_tools = ToolEventTracking.objects.filter(event='tool_Damaged').values('tool_id').count()

    context = {
        'events': events_page,
        'durations': durations_page,
        'total_events': total_events,
        'active_users': active_users,
        'active_tools': active_tools_count,
        'damaged_tools': damaged_tools,
    }
    return render(request, 'tool_activity_dashboard.html', context)

from django.db.models import Subquery, OuterRef, DateTimeField, Prefetch, Avg, Sum


def tools_in_use(request):
    # Step 1️⃣: Find latest event timestamp for each tool
    latest_event_subquery = (
        ToolEventTracking.objects
        .filter(tool_id=OuterRef('tool_id'))
        .order_by('-timestamp')
        .values('timestamp')[:1]
    )

    # Step 2️⃣: Select latest records per tool
    latest_records = ToolEventTracking.objects.filter(
        timestamp=Subquery(latest_event_subquery)
    )

    # Step 3️⃣: Keep only those whose latest event is "tool_Issued"
    in_use_tools = latest_records.filter(event__iexact='tool_Issued')

    # Step 4️⃣: Apply filters from GET parameters
    filters = {
        'user_name': request.GET.get('user_name', '').strip(),
        'tray_id': request.GET.get('tray_id', '').strip(),
        'service_station': request.GET.get('service_station', '').strip(),
        'unit': request.GET.get('unit', '').strip(),
        'tool_name': request.GET.get('tool_name', '').strip(),
        'client_ip': request.GET.get('client_ip', '').strip(),
    }

    if filters['user_name']:
        in_use_tools = in_use_tools.filter(user_name__icontains=filters['user_name'])
    if filters['tray_id']:
        in_use_tools = in_use_tools.filter(tray_id__icontains=filters['tray_id'])
    if filters['service_station']:
        in_use_tools = in_use_tools.filter(service_station__icontains=filters['service_station'])
    if filters['unit']:
        in_use_tools = in_use_tools.filter(unit__icontains=filters['unit'])
    if filters['tool_name']:
        in_use_tools = in_use_tools.filter(tool_name__icontains=filters['tool_name'])
    if filters['client_ip']:
        in_use_tools = in_use_tools.filter(client_ip__icontains=filters['client_ip'])

    in_use_tools = in_use_tools.order_by('-timestamp')

    # Step 5️⃣: Build dropdown options (distinct lists)
    user_list = ToolEventTracking.objects.exclude(user_name__isnull=True).values_list('user_name', flat=True).distinct().order_by('user_name')
    tray_list = ToolEventTracking.objects.exclude(tray_id__isnull=True).values_list('tray_id', flat=True).distinct().order_by('tray_id')
    station_list = ToolEventTracking.objects.exclude(service_station__isnull=True).values_list('service_station', flat=True).distinct().order_by('service_station')
    unit_list = ToolEventTracking.objects.exclude(unit__isnull=True).values_list('unit', flat=True).distinct().order_by('unit')
    tool_list = ToolEventTracking.objects.exclude(tool_name__isnull=True).values_list('tool_name', flat=True).distinct().order_by('tool_name')
    ip_list = ToolEventTracking.objects.exclude(client_ip__isnull=True).values_list('client_ip', flat=True).distinct().order_by('client_ip')

    context = {
        'in_use_tools': in_use_tools,
        'filters': filters,
        'user_list': user_list,
        'tray_list': tray_list,
        'station_list': station_list,
        'unit_list': unit_list,
        'tool_list': tool_list,
        'ip_list': ip_list,
    }

    return render(request, 'tools_in_use.html', context)

def tool_creation_view(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        internal_id = request.POST.get('internal_id')  # hidden field in form
        tool_id = request.POST.get('tool_id')
        tool_name = request.POST.get('tool_name')
        description = request.POST.get('description')
        part_number = request.POST.get('part_number')
        brand = request.POST.get('brand')
        tool_type = request.POST.get('tool_type')
        remarks = request.POST.get('remarks')

        if not tool_name or not tool_id:
            return JsonResponse({'status':'error', 'errors':'Tool ID and Name are required'})

        if internal_id:  # EDIT existing tool
            obj = get_object_or_404(ToolCreation, pk=internal_id)
            obj.tool_id = tool_id
            obj.tool_name = tool_name
            obj.description = description
            obj.part_number = part_number
            obj.brand = brand
            obj.tool_type = tool_type
            obj.remarks = remarks
            obj.save()
            created = False
        else:  # CREATE new tool
            obj = ToolCreation.objects.create(
                tool_id=tool_id,
                tool_name=tool_name,
                description=description,
                part_number=part_number,
                brand=brand,
                tool_type=tool_type,
                remarks=remarks,
            )
            created = True

        return JsonResponse({'status':'success', 'created': created})

    # GET request: load all tools
    tools = ToolCreation.objects.all().order_by('-created_at')
    return render(request, 'tool_creation.html', {'tools': tools})

@csrf_exempt
def tool_delete(request, id):
    if request.method == 'POST':
        try:
            tool = ToolCreation.objects.get(id=id)
            tool.delete()
            return JsonResponse({'status':'success'})
        except ToolCreation.DoesNotExist:
            return JsonResponse({'status':'error', 'message':'Tool not found'})
    return JsonResponse({'status':'error','message':'POST required'})

@csrf_exempt
def tool_purchase_view(request):
    if request.method == 'POST':
        try:
            tool_id = request.POST.get('tool_id')
            tool = get_object_or_404(ToolCreation, id=tool_id)
            quantity = int(request.POST.get('quantity', 0))
            unit_cost = float(request.POST.get('unit_cost', 0))
            purchase_cost = quantity * unit_cost

            # Save purchase
            purchase = ToolPurchase.objects.create(
                tool=tool,
                supplier_name=request.POST.get('supplier_name'),
                invoice_number=request.POST.get('invoice_number'),
                purchase_date=request.POST.get('purchase_date'),
                quantity=quantity,
                unit_cost=unit_cost,
                purchase_cost=purchase_cost,
                calibration=request.POST.get('calibration') or None,
                remarks=request.POST.get('remarks', '')
            )

            # Update or create inventory
            inventory, created = Inventory.objects.get_or_create(tool=tool)
            if created:
                inventory.total_quantity = quantity
            else:
                inventory.total_quantity += quantity

            inventory.in_stock = (
                    inventory.total_quantity - inventory.assigned_quantity
            )
            inventory.save()

            return JsonResponse({'status': 'success', 'purchase_id': purchase.id})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'invalid', 'message': 'Invalid request method'})

def inventory_view(request):
    inventory_items = Inventory.objects.select_related('tool').all()

    inventory_data = []
    for item in inventory_items:
        inventory_data.append({
            'inventoryId': item.inventory_id,
            'toolId': item.tool.id,
            'toolName': item.tool.tool_name,
            'brand': item.tool.brand,
            'toolType': item.tool.tool_type,
            'description': item.tool.description,
            'location': item.location or 'Warehouse',
            'partNumber': item.tool.part_number,
            'totalQuantity': item.total_quantity,
            'inStock': item.in_stock,
            'assignedQuantity': item.assigned_quantity,
            'availableQuantity': item.available_quantity,
            'inUse': item.in_use,
            'damaged': item.damaged,
            'lastUpdated': item.last_updated.strftime('%Y-%m-%d %H:%M'),
            'remarks': item.remarks or '',
        })

        summary = {
            "total": sum(item['totalQuantity'] for item in inventory_data),
            "in_stock": sum(item['inStock'] for item in inventory_data),
            "assigned": sum(item['assignedQuantity'] for item in inventory_data),
            "available": sum(item['availableQuantity'] for item in inventory_data),
            "in_use": sum(item['inUse'] for item in inventory_data),
            "damaged": sum(item['damaged'] for item in inventory_data),
        }
    return render(request, 'inventory.html', {'inventory_data': inventory_data, 'summary': summary})

@login_required
def create_service_station(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        manager_id = request.POST.get('manager')
        remarks = request.POST.get('remarks')
        manager = User.objects.filter(id=manager_id).first() if manager_id else None

        station = ServiceStation.objects.create(
            name=name,
            location=location,
            manager=manager,
            remarks=remarks
        )
        return redirect('service_station_list')

    users = User.objects.all()
    return render(request, 'create_service_station.html', {'users': users})


@login_required
def service_station_list(request):
    stations = ServiceStation.objects.all().order_by('id')
    users = User.objects.all()  # For incharge dropdown if using modal
    context = {
        'stations': stations,
        'users': users,
    }
    return render(request, 'service_station_list.html', context)

@login_required
def create_unit(request, station_id):
    station = get_object_or_404(ServiceStation, id=station_id)
    users = User.objects.all()

    # Check if edit parameter is present
    edit_unit_id = request.GET.get('edit')
    unit_to_edit = None
    if edit_unit_id:
        unit_to_edit = get_object_or_404(Unit, id=edit_unit_id, station=station)

    # Handle POST request
    if request.method == 'POST':
        unit_id = request.POST.get('unit_id')
        unit_name = request.POST.get('unit_name')
        incharge_id = request.POST.get('incharge')
        remarks = request.POST.get('remarks')

        incharge_user = User.objects.filter(id=incharge_id).first() if incharge_id else None

        if unit_id:  # Update existing
            unit = get_object_or_404(Unit, id=unit_id, station=station)
            unit.name = unit_name
            unit.incharge = incharge_user
            unit.remarks = remarks
            unit.save()
            messages.success(request, "Unit updated successfully.")
        else:  # Create new
            unit = Unit.objects.create(
                station=station,
                name=unit_name,
                incharge=incharge_user,
                remarks=remarks
            )
            messages.success(request, "New unit created successfully.")

        return redirect('create_unit', station_id=station.id)

    # Handle GET (show units)
    units = Unit.objects.filter(station=station).order_by('id')
    context = {
        'station': station,
        'users': users,
        'units': units,
        'unit_to_edit': unit_to_edit
    }
    return render(request, 'create_unit.html', context)

@login_required
def delete_unit(request, station_id, unit_id):
    station = get_object_or_404(ServiceStation, id=station_id)
    unit = get_object_or_404(Unit, id=unit_id, station=station)

    # 1️⃣ Check if any trays exist under this unit
    has_trays = Tray.objects.filter(unit=unit).exists()
    if has_trays:
        messages.error(request,
            "Cannot delete this Unit. Trays are assigned under this unit. Delete them first.")
        return redirect('create_unit', station_id=station.id)

    # 2️⃣ Check if unit is assigned to any JobCards
    is_assigned_jobcard = JobCard.objects.filter(assigned_units=unit).exists()
    if is_assigned_jobcard:
        messages.error(request,
            "Unit cannot be deleted. It is assigned to one or more Job Cards.")
        return redirect('create_unit', station_id=station.id)

    # 3️⃣ Check if unit is involved in any Tool Usage
    used_in_tool_usage = JobToolUsage.objects.filter(unit=unit).exists()
    if used_in_tool_usage:
        messages.error(request,
            "Unit cannot be deleted. It is linked to tool usage history.")
        return redirect('create_unit', station_id=station.id)

    # 4️⃣ Safe to delete
    unit.delete()
    messages.success(request, "Unit deleted successfully.")
    return redirect('create_unit', station_id=station.id)

@login_required
@csrf_exempt
def edit_service_station(request, pk):
    station = get_object_or_404(ServiceStation, pk=pk)

    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        station.name = data.get('name', station.name)
        station.location = data.get('location', station.location)

        # Update manager (optional)
        manager_username = data.get('manager')
        if manager_username:
            from django.contrib.auth.models import User
            manager = User.objects.filter(username=manager_username).first()
            station.manager = manager

        station.save()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid request'})

@login_required
def delete_service_station(request, pk):
    station = get_object_or_404(ServiceStation, pk=pk)

    is_assigned = JobCard.objects.filter(service_station=station).exists()

    if is_assigned:
        messages.error(request, "Cannot delete. This service station is assigned to one or more job cards.")
        return redirect('service_station_list')

    station.delete()
    messages.success(request, "Service station deleted successfully.")
    return redirect('service_station_list')

@login_required
def create_tray(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    if request.method == 'POST':
        tray_name = request.POST.get('tray_name')
        max_capacity = request.POST.get('max_capacity')
        remarks = request.POST.get('remarks')

        tray = Tray.objects.create(
            unit=unit,
            unit_code=unit.unit_id,
            tray_name=tray_name,
            remarks=remarks,
            max_capacity=max_capacity if max_capacity else None
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'tray_id': tray.id,
                'tray_name': tray.tray_name
            })
        return redirect('create_tray', unit_id=unit.id)

    # GET request - show existing trays
    trays = Tray.objects.filter(unit=unit).prefetch_related(
        Prefetch(
            'tray_tools',
            queryset=TrayTool.objects.filter(assigned_quantity__gt=0)
            .select_related('inventory__tool')
            .order_by('inventory__tool__tool_name')
        )
    ).order_by('id')

    context = {
        'unit': unit,
        'trays': trays
    }
    return render(request, 'create_tray.html', context)

@login_required
def edit_tray(request, tray_id):
    tray = get_object_or_404(Tray, id=tray_id)
    unit = tray.unit  # To redirect back after editing

    if request.method == 'POST':
        tray.tray_name = request.POST.get('tray_name')
        tray.max_capacity = request.POST.get('max_capacity')
        tray.remarks = request.POST.get('remarks')
        tray.save()
        return redirect('create_tray', unit_id=unit.id)

    # Load existing data
    trays = Tray.objects.filter(unit=unit).order_by('id')
    context = {
        'unit': unit,
        'trays': trays,
        'edit_tray': tray  # Pass current tray for form prefill
    }
    return render(request, 'create_tray.html', context)

@login_required
def delete_tray(request, tray_id):
    tray = get_object_or_404(Tray, id=tray_id)

    # Check if any tools are assigned in TrayTool
    has_tools = TrayTool.objects.filter(tray=tray).exists()

    if has_tools:
        messages.error(request,
            "Cannot delete this tray. Tools are assigned to this tray. Remove them first.")
        return redirect('create_tray', unit_id=tray.unit.id)

    # Check if tray is linked with any JobCard (via JobToolUsage)
    in_job_usage = JobToolUsage.objects.filter(tray=tray).exists()

    if in_job_usage:
        messages.error(request,
            "Tray cannot be deleted. It is associated with one or more Job Cards.")
        return redirect('create_tray', unit_id=tray.unit.id)

    # Safe to delete
    tray.delete()
    messages.success(request, "Tray deleted successfully.")
    return redirect('create_tray', unit_id=tray.unit.id)

from django.db.models import Q, F, OuterRef, Subquery, IntegerField, Value
from django.db.models.functions import Coalesce

from django.db.models import Sum

def assign_tools(request, tray_id):
    tray = get_object_or_404(Tray, id=tray_id)
    search_query = request.GET.get('search', '')

    traytool_subquery = TrayTool.objects.filter(
        tray=tray,
        inventory=OuterRef('pk')
    ).values('assigned_quantity')[:1]

    inventory_items = Inventory.objects.select_related('tool').annotate(
        assigned_in_tray=Coalesce(Subquery(traytool_subquery, output_field=IntegerField()), Value(0)),
    )

    if search_query:
        inventory_items = inventory_items.filter(
            Q(tool__tool_name__icontains=search_query) |
            Q(tool__tool_id__icontains=search_query) |
            Q(tool__part_number__icontains=search_query) |
            Q(tool__brand__icontains=search_query) |
            Q(tool__tool_type__icontains=search_query)
        )

    if request.method == 'POST':

        # ✅ 1. Get current total assigned in this tray
        current_total = TrayTool.objects.filter(tray=tray).aggregate(
            total=Sum('assigned_quantity')
        )['total'] or 0

        # ✅ 2. Calculate new total after POST
        new_total = current_total

        for key, value in request.POST.items():
            if not key.startswith('assign_qty_'):
                continue

            inventory_id = key.replace('assign_qty_', '').strip()
            if not inventory_id:
                continue

            try:
                assign_qty = int(value) if value.strip() else 0
            except ValueError:
                assign_qty = 0

            inventory_item = get_object_or_404(Inventory, inventory_id=inventory_id)
            existing = TrayTool.objects.filter(tray=tray, inventory=inventory_item).first()

            old_qty = existing.assigned_quantity if existing else 0

            # Adjust total for capacity check
            new_total = new_total - old_qty + assign_qty

        # ✅ 3. Enforce maximum tray capacity
        if tray.max_capacity and new_total > tray.max_capacity:
            messages.error(
                request,
                f"Tray capacity exceeded! Max: {tray.max_capacity}, "
                f"Attempted: {new_total}"
            )
            return redirect('assign_tools', tray_id=tray.id)

        # ✅ 4. Proceed with normal save logic if capacity is valid
        for key, value in request.POST.items():
            if not key.startswith('assign_qty_'):
                continue

            inventory_id = key.replace('assign_qty_', '').strip()
            if not inventory_id:
                continue

            try:
                assign_qty = int(value) if value.strip() else 0
            except ValueError:
                assign_qty = 0

            remarks = request.POST.get(f'remarks_{inventory_id}', '').strip()
            inventory_item = get_object_or_404(Inventory, inventory_id=inventory_id)
            tool = inventory_item.tool
            existing_record = TrayTool.objects.filter(tray=tray, inventory=inventory_item).first()

            if existing_record:
                diff = assign_qty - existing_record.assigned_quantity

                if diff > 0 and diff > inventory_item.in_stock:
                    messages.error(
                        request,
                        f"Cannot increase {tool.tool_name} to {assign_qty}. "
                        f"Only {inventory_item.in_stock} available."
                    )
                    continue

                inventory_item.in_stock -= diff
                inventory_item.assigned_quantity += diff
                inventory_item.available_quantity = inventory_item.assigned_quantity
                inventory_item.save()

                existing_record.assigned_quantity = assign_qty
                existing_record.remarks = remarks
                existing_record.save()

            else:
                if assign_qty > inventory_item.in_stock:
                    messages.error(
                        request,
                        f"Cannot assign {assign_qty} units of {tool.tool_name}. "
                        f"Only {inventory_item.in_stock} available."
                    )
                    continue

                inventory_item.in_stock -= assign_qty
                inventory_item.assigned_quantity += assign_qty
                inventory_item.available_quantity = inventory_item.assigned_quantity
                inventory_item.save()

                TrayTool.objects.create(
                    tray=tray,
                    inventory=inventory_item,
                    tool_id=tool.tool_id,
                    assigned_quantity=assign_qty,
                    remarks=remarks,
                    assigned_by=request.user if request.user.is_authenticated else None
                )

        messages.success(request, "Tool assignments updated successfully!")
        return redirect('assign_tools', tray_id=tray.id)

    context = {
        'tray': tray,
        'inventory_items': inventory_items,
        'search_query': search_query,
    }
    return render(request, 'assign_tools.html', context)

def assigned_tools_list(request, tray_id):
    assigned_tools = TrayTool.objects.select_related(
        'tray', 'tray__unit', 'tray__unit__station',
        'inventory', 'inventory__tool', 'assigned_by'
    ).filter(tray_id=tray_id,  assigned_quantity__gt=0 )

    context = {
        'assigned_tools': assigned_tools,
        'tray_id': tray_id,
    }

    # Use render to display the template with context
    return render(request, 'assigned_tools_list.html', context)

from django.db.models import Q, F, Max
from .models import TrayTool, ServiceStation, Unit, Tray, Inventory

def global_assigned_tools(request):
    # Get filter parameters
    station_id = request.GET.get('station_id', '')
    unit_id = request.GET.get('unit_id', '')
    tray_id = request.GET.get('tray_id', '')
    tool_id = request.GET.get('tool_id', '')
    tool_name = request.GET.get('tool_name', '')

    tray_tools = TrayTool.objects.select_related(
        'tray',
        'tray__unit',
        'tray__unit__station',
        'inventory',
        'inventory__tool',
        'assigned_by'
    ).filter(assigned_quantity__gt=0)

    # Apply main filters
    if station_id:
        tray_tools = tray_tools.filter(tray__unit__station__id=station_id)
    if unit_id:
        tray_tools = tray_tools.filter(tray__unit__id=unit_id)
    if tray_id:
        tray_tools = tray_tools.filter(tray__id=tray_id)
    if tool_id:
        tray_tools = tray_tools.filter(inventory__tool__tool_id__icontains=tool_id)
    if tool_name:
        tray_tools = tray_tools.filter(inventory__tool__tool_name__icontains=tool_name)

    # Populate filter dropdowns based on selected station/unit
    stations = ServiceStation.objects.all()
    units = Unit.objects.filter(station__id=station_id) if station_id else Unit.objects.all()
    trays = Tray.objects.filter(unit__id=unit_id) if unit_id else Tray.objects.filter(unit__station__id=station_id) if station_id else Tray.objects.all()
    tools = Inventory.objects.filter(inventory_id__in=tray_tools.values_list('inventory__inventory_id', flat=True))

    tray_count = Tray.objects.count()
    station_count = ServiceStation.objects.count()
    unit_count = Unit.objects.count()
    tool_count = TrayTool.objects.count()

    context = {
        'tray_tools': tray_tools,
        'tool_count': tool_count,
        'stations': stations,
        'station_count': station_count,
        'units': units,
        'unit_count': unit_count,
        'trays': trays,
        'tray_count': tray_count,
        'tools': tools,
        'filters': {
            'station_id': station_id,
            'unit_id': unit_id,
            'tray_id': tray_id,
            'tool_id': tool_id,
            'tool_name': tool_name,
        }
    }
    return render(request, 'global_assigned_tools.html', context)

def user_assigned_list(request):
    users = User.objects.all().select_related('userprofile')

    user_data = []
    for user in users:
        profile = getattr(user, 'userprofile', None)
        user_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': profile.role if profile else 'Not Assigned',
            'stations_display': profile.stations_display if profile else 'None',
            'trays_display': profile.trays_display if profile else 'None',
            'units_display': profile.units_display if profile else 'None',
        })

    return render(request, 'user_assigned_list.html', {'users': user_data})

def update_inventory_for_event(event):
    inventory = Inventory.objects.filter(tool__tool_id=event.tool_id).first()
    if not inventory:
        return {"success": False, "error": "Tool not found in inventory"}

    updated = False
    if event.event == "tool_Issued" and inventory.available_quantity > 0:
        Inventory.objects.filter(pk=inventory.pk).update(
            in_use=F('in_use') + 1,
            available_quantity=F('available_quantity') - 1
        )
        updated = True
    elif event.event == "tool_Returned" and inventory.in_use > 0:
        Inventory.objects.filter(pk=inventory.pk).update(
            in_use=F('in_use') - 1,
            available_quantity=F('available_quantity') + 1
        )
        updated = True
    elif event.event == "tool_Damaged" and inventory.available_quantity > 0:
        Inventory.objects.filter(pk=inventory.pk).update(
            damaged=F('damaged') + 1,
            available_quantity=F('available_quantity') - 1
        )
        updated = True

    if updated:
        inventory.refresh_from_db()
        return {
            "success": True,
            "tool_id": inventory.tool_id,
            "available_quantity": inventory.available_quantity,
            "in_use": inventory.in_use,
            "damaged": inventory.damaged,
            "event": event.event,
            "timestamp": event.timestamp,
        }
    else:
        return {"success": False, "error": "No inventory update possible"}

def inventory_update_api(request):
    latest_event = ToolEventTracking.objects.order_by('-timestamp').first()
    if not latest_event:
        return JsonResponse({"success": False, "error": "No recent event found"})

    result = update_inventory_for_event(latest_event)
    return JsonResponse(result)

# Set duplicate thresholds per event type
# Generic time threshold for duplicate suppression (seconds)
DUPLICATE_THRESHOLD = 5

# Machine A - Master recevies the client detections
# Log directory setup
def get_client_ip(request):
    """Return the actual client IP address (works behind proxies too)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@csrf_exempt
def receive_detections(request):
    print("[DEBUG] receive_detections called from IP:", get_client_ip(request))
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        now_utc = timezone.now()  # always aware UTC time

        # ---------------- Parse client timestamp ----------------
        client_ts = data.get("timestamp")
        if client_ts:
            try:
                parsed_ts = datetime.fromisoformat(str(client_ts))
                if timezone.is_naive(parsed_ts):
                    parsed_ts = timezone.make_aware(parsed_ts, timezone.get_current_timezone())
            except Exception:
                parsed_ts = now_utc
        else:
            parsed_ts = now_utc

        timestamp = parsed_ts
        client_ip = get_client_ip(request)
        user_id = data.get("user_id")
        event_type = data.get("event")
        user_name = data.get("user_name") or data.get("username") or data.get("user")
        job_id = data.get("job_id")
        tool_id = data.get("tool_id")
        tool_name = data.get("tool_name")
        unit_id = data.get("unit_id")
        tray_id = data.get("tray_id")

        print("Event :", event_type)

        # ----------------- Handle NOTE_ADDED separately -----------------
        if event_type == "NOTE_ADDED":
            # ----------------- DUPLICATE CHECK FOR NOTE_ADDED -----------------
            existing_note = JobCardNotes.objects.filter(
                job__job_id=data.get("jobcard_id") or job_id,
                technician_id=data.get("technician_id"),
                description=data.get("description"),
                working_component=data.get("working_component"),
                timestamp=timestamp
            ).first()

            if existing_note:
                print(f"[{timestamp}] ⚠️ Duplicate NOTE_ADDED ignored for technician {data.get('technician_name')}")
                return JsonResponse({"status": "ignored", "message": "Duplicate note"}, status=200)
            # ------------------------------------------------------------------

            # Fetch or create JobCard
            try:
                job_instance = JobCard.objects.get(job_id=data.get("jobcard_id") or job_id)
            except JobCard.DoesNotExist:
                job_instance = JobCard.objects.create(job_id=data.get("jobcard_id") or job_id, created_by=user_id)

            # Save note
            note = JobCardNotes.objects.create(
                job=job_instance,
                technician_id=data.get("technician_id"),
                technician_name=data.get("technician_name"),
                description=data.get("description"),
                working_component=data.get("working_component"),
                status=data.get("status") or "Pending",
                timestamp=timestamp,
            )
            print(f"NOTE_ADDED saved: {note.id}, job={job_instance.job_id}, technician={note.technician_name}")
            return JsonResponse({"status": "success", "message": "Note added", "note_id": note.id}, status=201)

        # ----------------- All other events -----------------
        # Duplicate check
        is_duplicate = False
        last_event = ToolEventTracking.objects.filter(
            client_ip=client_ip,
            event=event_type,
            user_name=user_name,
            tool_name=tool_name,
            unit_id=unit_id,
            tray_id=tray_id
        ).order_by('-timestamp').first()

        if last_event:
            last_time = last_event.timestamp
            if timezone.is_naive(last_time):
                last_time = timezone.make_aware(last_time, timezone.get_current_timezone())
            time_diff = (timestamp - last_time).total_seconds()
            if time_diff < DUPLICATE_THRESHOLD:
                print(f"[{timestamp}] ⚠️ Duplicate event ignored: {event_type} from {client_ip} (Δ={time_diff:.2f}s)")
                is_duplicate = True

        if is_duplicate:
            return JsonResponse({"status": "ignored"}, status=200)

        # Fetch JobCard
        job_instance, _ = JobCard.objects.get_or_create(job_id=job_id, defaults={"created_by": user_id})

        # Save ToolEventTracking
        status_map = {
            "tray_open": "opened",
            "tray_close": "closed",
            "tool_Issued": "issued",
            "tool_Returned": "returned",
            "tool_Damaged": "damaged",
            "auto_logout": "auto_logout",
            "system_offline": "system_offline",
            "system_online": "system_online"
        }
        status = data.get("status") or status_map.get(event_type, "unknown")
        verification_completed = data.get("verification_completed") or (event_type == "tool_Returned")

        event = ToolEventTracking.objects.create(
            timestamp=timestamp,
            service_station=data.get("service_station"),
            unit=data.get("unit"),
            unit_id=unit_id,
            user_id=user_id,
            user_name=user_name,
            event=event_type,
            tray_id=tray_id,
            tool_id=tool_id,
            tool_name=tool_name,
            device_id=data.get("device_id"),
            client_ip=client_ip,
            job_id=job_instance,
            status=status,
            verification_completed=verification_completed,
            raw_data=data
        )
        print(f"[{timestamp}] Event saved: {event.event} from client {client_ip}")

        # ----------------- JobToolUsage -----------------
        unit_instance = Unit.objects.filter(unit_id=unit_id).first() if unit_id else None
        tray_instance = Tray.objects.filter(tray_id=tray_id).first() if tray_id else None
        tool_instance = ToolCreation.objects.filter(tool_id=tool_id).first() if tool_id else None

        try:
            if event_type == "tool_Issued" and user_id and tool_instance:
                JobToolUsage.objects.create(
                    issued_time=timestamp,
                    status='issued',
                    issued_by_id=user_id,
                    job=job_instance,
                    tool=tool_instance,
                    tray=tray_instance,
                    unit=unit_instance,
                )
            elif event_type == "tool_Returned" and tool_instance:
                usage = JobToolUsage.objects.filter(
                    job=job_instance,
                    tool=tool_instance,
                    status="issued"
                ).order_by('-issued_time').first()
                if usage:
                    usage.returned_time = timestamp
                    usage.status = 'returned'
                    usage.returned_by_id = user_id
                    usage.save()
            elif event_type == "tool_Damaged" and tool_instance:
                usage = JobToolUsage.objects.filter(job=job_instance, tool=tool_instance).first()
                if usage:
                    usage.status = "damaged"
                    usage.save()
        except Exception as e:
            print("JobToolUsage creation failed:", e)

        # ----------------- JobAuditLog -----------------
        try:
            audit_action_map = {
                'tool_Issued': 'tool_Issued',
                'tool_Returned': 'tool_Returned',
                'tool_Damaged': 'tool_Damaged',
                'tray_open': 'tray_open',
                'tray_close': 'tray_close',
                'auto_logout': 'auto_logout',
                'system_offline': 'system_offline',
                'system_online': 'system_online',
            }
            JobAuditLog.objects.create(
                timestamp=timestamp,
                action=audit_action_map.get(event.event, event.event),
                details=json.dumps(data),
                user_id=user_id,
                job=job_instance
            )
        except Exception as e:
            print("JobAuditLog creation failed:", e)

        # ----------------- Inventory Update -----------------
        inventory_result = update_inventory_for_event(event)
        server_ip = socket.gethostbyname(socket.gethostname())

        return JsonResponse({
            "status": "success",
            "message": "Event stored successfully",
            "inventory_update": inventory_result,
            "server_ip": server_ip,
            "client_ip": client_ip,
            "saved_event_id": event.id
        }, status=201)

    except Exception as e:
        print("[Error receiving event]:", e)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

def aircraft_list(request):
    if request.method == 'POST':
        aircraft_id = request.POST.get('aircraft_id')
        registration_no = request.POST.get('registration_no')
        model = request.POST.get('model')
        manufacturer = request.POST.get('manufacturer')
        airline_name = request.POST.get('airline_name')
        flight_hours = request.POST.get('flight_hours') or 0
        flight_cycles = request.POST.get('flight_cycles') or 0
        remarks = request.POST.get('remarks')

        # Check uniqueness
        if Aircraft.objects.filter(aircraft_id=aircraft_id).exists():
            messages.error(request, f"Aircraft ID '{aircraft_id}' already exists.")
        elif Aircraft.objects.filter(registration_no=registration_no).exists():
            messages.error(request, f"Registration No '{registration_no}' already exists.")
        else:
            # Save new aircraft
            Aircraft.objects.create(
                aircraft_id=aircraft_id,
                registration_no=registration_no,
                model=model,
                manufacturer=manufacturer,
                airline_name=airline_name,
                flight_hours=int(flight_hours),
                flight_cycles=int(flight_cycles),
                remarks=remarks
            )
            messages.success(request, f"Aircraft '{aircraft_id}' added successfully.")
            return redirect('aircraft_list')

    # GET request
    query = request.GET.get('q', '')
    if query:
        aircrafts = Aircraft.objects.filter(
            Q(aircraft_id__icontains=query) |
            Q(registration_no__icontains=query) |
            Q(model__icontains=query) |
            Q(manufacturer__icontains=query) |
            Q(airline_name__icontains=query)
        )
    else:
        aircrafts = Aircraft.objects.all()

    total_aircraft = aircrafts.count()
    active_count = aircrafts.filter(flight_hours__gt=0).count()
    maintenance_count = aircrafts.filter(flight_hours=0).count()
    avg_hours = aircrafts.aggregate(avg=Avg('flight_hours'))['avg'] or 0

    context = {
        'aircrafts': aircrafts,
        'total_aircraft': total_aircraft,
        'active_count': active_count,
        'maintenance_count': maintenance_count,
        'avg_hours': int(avg_hours),
    }
    return render(request, 'aircraft/aircraft_list.html', context)

def aircraft_edit(request, pk):
    aircraft = get_object_or_404(Aircraft, pk=pk)
    if request.method == 'POST':
        aircraft_id = request.POST.get('aircraft_id').strip()
        reg_no = request.POST.get('registration_no').strip()
        model = request.POST.get('model')
        manufacturer = request.POST.get('manufacturer')
        airline_name = request.POST.get('airline_name')
        flight_hours = request.POST.get('flight_hours') or 0
        flight_cycles = request.POST.get('flight_cycles') or 0
        remarks = request.POST.get('remarks')

        if Aircraft.objects.filter(registration_no=reg_no).exclude(pk=pk).exists():
            messages.error(request, f"Aircraft with registration '{reg_no}' already exists.")
        else:
            aircraft.aircraft_id = aircraft_id
            aircraft.registration_no = reg_no
            aircraft.model = model
            aircraft.manufacturer = manufacturer
            aircraft.airline_name = airline_name
            aircraft.flight_hours = flight_hours
            aircraft.flight_cycles = flight_cycles
            aircraft.remarks = remarks
            aircraft.save()
            messages.success(request, "Aircraft updated successfully.")

        return redirect('aircraft_list')


def aircraft_delete(request, pk):
    aircraft = get_object_or_404(Aircraft, pk=pk)

    jobcard_exists = JobCard.objects.filter(aircraft=aircraft).exists()

    if jobcard_exists:
        messages.error(request, "Cannot delete. This aircraft is assigned to one or more job cards.")
        return redirect('aircraft_list')

    aircraft.delete()
    messages.success(request, "Aircraft deleted successfully.")
    return redirect('aircraft_list')

#  List all job cards
def jobcard_list(request):
    jobcards = JobCard.objects.select_related(
        'aircraft', 'qa_inspector', 'service_station', 'created_by'
    ).prefetch_related(
        'assigned_units', 'assigned_technicians'
    ).all().order_by('-created_at')

    # Calculate summary counts
    total_jobcards = jobcards.count()
    in_progress_count = jobcards.filter(status='IN_PROGRESS').count()
    completed_count = jobcards.filter(status='COMPLETED').count()
    high_priority_count = jobcards.filter(priority='HIGH').count()
    critical_count = jobcards.filter(priority='CRITICAL').count()

    units = Unit.objects.all()

    mechanics = User.objects.filter(
        userprofile__role='User',
        profile__status='ACTIVE'
    )

    qa_users = User.objects.filter(
        Q(userprofile__role__iexact='Supervisor') |
        Q(userprofile__role__iexact='Admin') |
        Q(is_superuser=True)
    ).distinct()

    context = {
        'jobcards': jobcards,
        'total_jobcards': total_jobcards,
        'units': units,
        'mechanics': mechanics,
        'qa_users': qa_users,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'high_priority_count': high_priority_count,
        'critical_count': critical_count,
    }

    return render(request, 'jobcards/jobcard_list.html', context)

#  Create a new job card
def jobcard_create(request):
    aircrafts = Aircraft.objects.all()
    stations = ServiceStation.objects.all()
    # Only available units
    units = Unit.objects.filter(status='AVAILABLE')
    # Only available mechanics
    mechanics = User.objects.filter(
        userprofile__role='User',
        userprofile__status='AVAILABLE',
        profile__status='ACTIVE'
    )
    qa_users = User.objects.filter(
        Q(userprofile__role__iexact='Supervisor') |
        Q(userprofile__role__iexact='Admin') |
        Q(is_superuser=True)
    ).distinct()

    if request.method == 'POST':
        aircraft_id = request.POST.get('aircraft')
        station_id = request.POST.get('service_station')
        job_title = request.POST.get('job_title')
        job_description = request.POST.get('job_description')
        job_type = request.POST.get('job_type')
        priority = request.POST.get('priority')
        bay_id = request.POST.get('bay_id')
        unit_ids = request.POST.getlist('assigned_units')
        technician_ids = request.POST.getlist('assigned_technicians')  # This should contain User IDs
        qa_id = request.POST.get('qa_inspector')
        reported_issues = request.POST.get('reported_issues')

        aircraft = get_object_or_404(Aircraft, id=aircraft_id)
        station = get_object_or_404(ServiceStation, id=station_id)

        # Auto-generate Job ID
        job_id = f"JOB{timezone.now().strftime('%Y%m%d%H%M%S')}"

        job = JobCard.objects.create(
            job_id=job_id,
            aircraft=aircraft,
            service_station=station,
            job_title=job_title,
            job_description=job_description,
            job_type=job_type,
            priority=priority,
            status='CREATED',
            bay_id=bay_id,
            qa_inspector=User.objects.filter(id=qa_id).first() if qa_id else None,
            reported_issues=reported_issues,
            created_by=request.user,
        )

        # Assign multiple units & technicians
        job.assigned_units.set(unit_ids)

        # Assign technicians - using User IDs directly
        if technician_ids:
            job.assigned_technicians.set(technician_ids)
        job.save()

        # Mark selected units as BUSY
        for unit in job.assigned_units.all():
            unit.status = "IN-USE"
            unit.save()

        # Mark selected technicians as BUSY
        for tech in job.assigned_technicians.all():
            profile = tech.userprofile
            profile.status = "IN-USE"
            profile.save()

        # Better way to print QA Inspector
        if job.qa_inspector:
            print(f"QA Inspector: {job.qa_inspector.get_full_name() or job.qa_inspector.username}")
        else:
            print("QA Inspector: None")

        # Print assigned units
        units_list = [f"{u.name} ({u.station.name})" for u in job.assigned_units.all()]

        # Print assigned technicians with better handling
        tech_list = []
        for tech in job.assigned_technicians.all():
            name = tech.get_full_name() or tech.username
            tech_list.append(name)

        messages.success(request, f"Job Card {job.job_id} created for {aircraft.registration_no}")
        return redirect('jobcard_detail', job_id=job.job_id)

    context = {
        'aircrafts': aircrafts,
        'stations': stations,
        'units': units,
        'mechanics': mechanics,  # Now passing User objects directly
        'qa_users': qa_users,
    }
    return render(request, 'jobcards/jobcard_create.html', context)

from django.db.models import Q, Count

def jobcard_notes(request, job_id):
    job = JobCard.objects.get(job_id=job_id)

    base_qs = JobCardNotes.objects.filter(job=job)

    # -----------------------------
    # Unique dropdown values
    # -----------------------------
    technicians = (
        base_qs.exclude(technician_name__isnull=True)
               .exclude(technician_name__exact="")
               .values_list("technician_name", flat=True)
               .distinct()
    )

    components = (
        base_qs.exclude(working_component__isnull=True)
               .exclude(working_component__exact="")
               .values_list("working_component", flat=True)
               .distinct()
    )

    statuses = (
        base_qs.exclude(status__isnull=True)
               .exclude(status__exact="")
               .values_list("status", flat=True)
               .distinct()
    )

    # -----------------------------
    # Filters
    # -----------------------------
    tech = request.GET.get("technician")
    comp = request.GET.get("component")
    status = request.GET.get("status")
    search = request.GET.get("search")

    notes = base_qs.order_by("-timestamp")

    if tech:
        notes = notes.filter(technician_name=tech)

    if comp:
        notes = notes.filter(working_component=comp)

    if status:
        notes = notes.filter(status=status)

    if search:
        notes = notes.filter(
            Q(description__icontains=search) |
            Q(technician_name__icontains=search) |
            Q(working_component__icontains=search)
        )

    # -----------------------------
    # Status counts (AFTER filters)
    # -----------------------------
    counts = notes.values("status").annotate(total=Count("id"))

    # Map raw status to normalized bucket
    status_map = {
        "completed": "Completed",
        "in progress": "In Progress",
        "pending": "Pending",
        "issue": "Pending",  # if you want issue to count as pending
    }

    completed_count = sum(
        i["total"] for i in counts if i["status"].strip().lower() == "completed"
    )
    in_progress_count = sum(
        i["total"] for i in counts if i["status"].strip().lower() == "in progress"
    )
    pending_count = sum(
        i["total"] for i in counts if i["status"].strip().lower() == "pending"
    )

    total_count = notes.count()

    # Filter notes based on search/filters
    notes_queryset = JobCardNotes.objects.filter(job=job).order_by('-timestamp')

    # Apply pagination (10 notes per page)
    paginator = Paginator(notes_queryset, 10)  # 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "jobcards/jobcard_notes.html", {
        "job": job,
        "notes": notes,
        'page_obj': page_obj,

        # dropdown data
        "technicians": technicians,
        "components": components,
        "statuses": statuses,

        # selected values
        "selected_tech": tech,
        "selected_comp": comp,
        "selected_status": status,
        "search": search,

        # counts
        "total_notes": total_count,
        "completed_count": completed_count,
        "in_progress_count": in_progress_count,
        "pending_count": pending_count,
    })

def jobcard_edit(request, job_id):
    job = get_object_or_404(JobCard, job_id=job_id)

    # Units → Available OR already assigned to this job
    units = Unit.objects.filter(
        Q(status="AVAILABLE") |
        Q(id__in=job.assigned_units.values_list('id', flat=True))
    )

    mechanics = User.objects.filter(
        userprofile__role="User"
    ).filter(
        Q(userprofile__status="AVAILABLE") & Q(profile__status='ACTIVE') |
        Q(id__in=job.assigned_technicians.values_list('id', flat=True))
    )

    qa_users = User.objects.filter(
        Q(userprofile__role__iexact='Supervisor') |
        Q(userprofile__role__iexact='Admin') |
        Q(is_superuser=True)
    ).distinct()

    if request.method == 'POST':
        job.job_title = request.POST.get('job_title')
        job.job_description = request.POST.get('job_description')
        job.job_type = request.POST.get('job_type')
        job.priority = request.POST.get('priority')
        job.status = request.POST.get('status')
        job.bay_id = request.POST.get('bay_id')
        job.reported_issues = request.POST.get('reported_issues')

        # Update QA Inspector
        qa_id = request.POST.get('qa_inspector')
        if qa_id:
            job.qa_inspector = User.objects.filter(id=qa_id).first()
        else:
            job.qa_inspector = None

        job.save()

        # Update assigned units
        unit_ids = request.POST.getlist('assigned_units[]')
        current_unit_ids = set(job.assigned_units.values_list('id', flat=True))
        new_unit_ids = set(map(int, unit_ids))

        # Assign new units
        job.assigned_units.set(new_unit_ids)

        # Update unit statuses
        # Mark newly assigned units as BUSY
        Unit.objects.filter(id__in=new_unit_ids).update(status="IN-USE")
        # Mark units unassigned from this job as AVAILABLE
        unassigned_units = current_unit_ids - new_unit_ids
        Unit.objects.filter(id__in=unassigned_units).update(status="AVAILABLE")

        # Update assigned technicians
        technician_ids = request.POST.getlist('assigned_technicians[]')
        current_tech_ids = set(job.assigned_technicians.values_list('id', flat=True))
        new_tech_ids = set(map(int, technician_ids))

        # Assign new technicians
        job.assigned_technicians.set(new_tech_ids)

        # Update technician statuses
        # Mark newly assigned as BUSY
        UserProfile.objects.filter(user_id__in=new_tech_ids).update(status="IN-USE")
        # Mark unassigned as AVAILABLE
        unassigned_techs = current_tech_ids - new_tech_ids
        UserProfile.objects.filter(user_id__in=unassigned_techs).update(status="AVAILABLE")

        messages.success(request, f"Job Card {job.job_id} updated successfully")
        return redirect('jobcard_list')

    context = {
        'job': job,
        'units': units,
        'mechanics': mechanics,
        'qa_users': qa_users,
    }
    return render(request, 'jobcards/jobcard_edit.html', context)

def jobcard_delete(request, job_id):
    job = get_object_or_404(JobCard, job_id=job_id)

    if request.method == 'POST':
        # Reset status of all assigned units
        for unit in job.assigned_units.all():
            unit.status = 'AVAILABLE'
            unit.save()

        # Reset status of all assigned technicians
        for tech in job.assigned_technicians.all():
            if hasattr(tech, 'userprofile'):
                tech.userprofile.status = 'AVAILABLE'
                tech.userprofile.save()

        job.delete()
        messages.success(request, f"Job Card {job.job_id} deleted successfully")
        return redirect('jobcard_list')

    messages.warning(request, "Invalid request method")
    return redirect('jobcard_list')

#  View JobCard details
def jobcard_detail(request, job_id):
    job = get_object_or_404(
        JobCard.objects.select_related(
            'created_by', 'qa_inspector', 'service_station', 'aircraft'
        ).prefetch_related(
            'assigned_units', 'assigned_technicians'
        ),
        job_id=job_id
    )

    tools = JobToolUsage.objects.filter(job=job)
    audit_logs = JobAuditLog.objects.filter(job=job).order_by('-timestamp')

    missing_tools = tools.filter(status='ISSUED')
    is_missing = missing_tools.exists()

    context = {
        'job': job,
        'tools': tools,
        'audit_logs': audit_logs,
        'missing_tools': missing_tools,
        'is_missing': is_missing
    }
    return render(request, 'jobcards/jobcard_detail.html', context)

#  Close a JobCard (only if all tools returned)
def jobcard_close(request, job_id):
    job = get_object_or_404(JobCard, job_id=job_id)

    # 1️⃣ Check unreturned tools
    unreturned_tools = JobToolUsage.objects.filter(job=job, status='issued')
    if unreturned_tools.exists():
        messages.error(request, "Cannot close job. Some tools are still issued!")
        return redirect('jobcard_detail', job_id=job_id)

    # 2️⃣ Close job if all tools returned
    job.status = 'CLOSED'
    job.save()

    # Release units
    for unit in job.assigned_units.all():
        unit.status = "AVAILABLE"
        unit.save()

    # Release technicians
    for tech in job.assigned_technicians.all():
        profile = tech.userprofile
        profile.status = "AVAILABLE"
        profile.save()

    # 3️⃣ Optional: log job closure in audit
    JobAuditLog.objects.create(
        job=job,
        action='job_closed',
        details=f"Job closed by user {request.user.username}",
        user_id=request.user.id
    )
    messages.success(request, "Job closed successfully!")
    return redirect('jobcard_list')