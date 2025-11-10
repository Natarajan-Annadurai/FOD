import json
import socket
from datetime import datetime
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from .models import ToolCreation, ToolPurchase, UserProfile, ProfileInformation
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from .models import ToolEventTracking
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

def tool_activity_dashboard(request):
    # All events ordered by latest
    events_list = ToolEventTracking.objects.all().order_by('-timestamp')

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

from django.db.models import Subquery, OuterRef, DateTimeField, Prefetch


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
    return render(request, 'inventory.html', {'inventory_data': inventory_data})

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
    unit_id = tray.unit.id
    tray.delete()
    return redirect('create_tray', unit_id=unit_id)

from django.db.models import Q, F, OuterRef, Subquery, IntegerField, Value
from django.db.models.functions import Coalesce

def assign_tools(request, tray_id):
    tray = get_object_or_404(Tray, id=tray_id)
    search_query = request.GET.get('search', '')

    # Subquery to fetch existing assigned quantity per inventory item for this tray
    traytool_subquery = TrayTool.objects.filter(
        tray=tray,
        inventory=OuterRef('pk')
    ).values('assigned_quantity')[:1]

    # Include assigned quantity from TrayTool (default 0 if not assigned)
    inventory_items = Inventory.objects.select_related('tool').annotate(
        assigned_in_tray=Coalesce(Subquery(traytool_subquery, output_field=IntegerField()), Value(0)),
        updated_at_in_tray = Subquery(traytool_subquery.values('updated_at')[:1], output_field=DateTimeField())
    )

    # Apply search filter
    if search_query:
        inventory_items = inventory_items.filter(
            Q(tool__tool_name__icontains=search_query) |
            Q(tool__tool_id__icontains=search_query) |
            Q(tool__part_number__icontains=search_query) |
            Q(tool__brand__icontains=search_query) |
            Q(tool__tool_type__icontains=search_query)
        )

    if request.method == 'POST':
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

            # 🔄 If already assigned → update instead of create
            if existing_record:
                # Calculate difference to adjust stock
                diff = assign_qty - existing_record.assigned_quantity
                if diff > 0 and diff > inventory_item.in_stock:
                    messages.error(
                        request,
                        f"Cannot increase {tool.tool_name} to {assign_qty}. Only {inventory_item.in_stock} available."
                    )
                    continue

                # Adjust inventory stock based on difference
                inventory_item.in_stock -= diff
                inventory_item.assigned_quantity += diff
                inventory_item.available_quantity = inventory_item.assigned_quantity
                inventory_item.save()

                # Update TrayTool record
                existing_record.assigned_quantity = assign_qty
                existing_record.remarks = remarks
                existing_record.save()

            else:
                # New assignment
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

    context = {
        'tray_tools': tray_tools,
        'stations': stations,
        'units': units,
        'trays': trays,
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

from django.contrib.auth.models import Group

@login_required
def manage_users(request):
    users = User.objects.all().order_by('username')
    stations = ServiceStation.objects.all()
    units = Unit.objects.all()
    trays = Tray.objects.all()

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

        elif role == "Mechanic":
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

    return render(request, 'manage_users.html', {
        'users': users,
        'stations': stations,
        'units': units,
        'trays': trays,
    })

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
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            now_utc = timezone.now()  # always aware UTC time

            # If client provided timestamp, parse and make aware
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
            event_type = data.get("event")
            user_name = data.get("user_name") or data.get("username") or data.get("user")
            tool_name = data.get("tool_name")
            unit_id = data.get("unit_id")
            tray_id = data.get("tray_id")

            print("Event :",event_type)

            is_duplicate = False

            # ----------------- GENERIC DUPLICATE CHECK -----------------
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

                # Ensure timezone-aware comparison
                if timezone.is_naive(last_time):
                    last_time = timezone.make_aware(last_time, timezone.get_current_timezone())

                time_diff = (timestamp - last_time).total_seconds()

                if time_diff < DUPLICATE_THRESHOLD:
                    print(
                        f"[{timestamp}] ⚠️ Duplicate event ignored: {event_type} from {client_ip} (Δ={time_diff:.2f}s)"
                    )
                    is_duplicate = True

            if is_duplicate:
                return JsonResponse({"status": "ignored"}, status=200)
            # -----------------------------------------------------------------------------

            hostname = socket.gethostname()
            server_ip = socket.gethostbyname(hostname)

            # Save event to database
            event = ToolEventTracking.objects.create(
                # timestamp=data.get("timestamp", timestamp),
                timestamp=timestamp,
                service_station=data.get("service_station"),
                unit=data.get("unit"),
                unit_id=data.get("unit_id"),
                user_id=data.get("user_id"),
                user_name=data.get("user_name"),
                event=event_type,
                tray_id=data.get("tray_id"),
                tool_id=data.get("tool_id"),
                tool_name=data.get("tool_name"),
                device_id=data.get("device_id"),
                client_ip=client_ip,
                raw_data=data
            )

            print(f"[{timestamp}] Event saved: {event.event} from client {client_ip}")

            # 🔁 Update inventory separately
            inventory_result = update_inventory_for_event(event)

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

    return JsonResponse({"status": "error", "message": "Only POST allowed"}, status=405)