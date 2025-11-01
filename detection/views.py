from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ToolCreation, ToolPurchase, UserProfile
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User

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

def tool_creation_view(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        tool_id = request.POST.get('tool_id')
        tool_name = request.POST.get('tool_name')
        description = request.POST.get('description')
        part_number = request.POST.get('part_number')
        brand = request.POST.get('brand')
        tool_type = request.POST.get('tool_type')
        remarks = request.POST.get('remarks')

        if not tool_name or not tool_id:
            return JsonResponse({'status':'error', 'errors':'Tool ID and Name are required'})

        obj, created = ToolCreation.objects.update_or_create(
            tool_id=tool_id,
            defaults={
                'tool_name': tool_name,
                'description': description,
                'part_number': part_number,
                'brand': brand,
                'tool_type': tool_type,
                'remarks': remarks,
            }
        )
        return JsonResponse({'status':'success', 'created':created})

    # GET request: load all tools
    tools = ToolCreation.objects.all().order_by('-created_at')
    return render(request, 'tool_creation.html', {'tools': tools})

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

    if request.method == 'POST':
        unit_name = request.POST.get('unit_name')
        incharge_id = request.POST.get('incharge')
        remarks = request.POST.get('remarks')

        incharge_user = User.objects.filter(id=incharge_id).first() if incharge_id else None

        unit = Unit.objects.create(
            station=station,
            name=unit_name,
            incharge=incharge_user,
            remarks=remarks
        )

        # Check if request is AJAX
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'unit_id': unit.id,
                'unit_name': unit.name
            })

        return redirect('create_unit', station_id=station.id)

    # GET request - show existing units for the station
    units = Unit.objects.filter(station=station).order_by('id')
    context = {
        'station': station,
        'users': users,
        'units': units
    }
    return render(request, 'create_unit.html', context)

@login_required
def create_tray(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    if request.method == 'POST':
        tray_name = request.POST.get('tray_name')
        max_capacity = request.POST.get('max_capacity')
        remarks = request.POST.get('remarks')

        tray = Tray.objects.create(
            unit=unit,
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
    trays = Tray.objects.filter(unit=unit).order_by('id')
    context = {
        'unit': unit,
        'trays': trays
    }
    return render(request, 'create_tray.html', context)

def assign_tools(request, tray_id):
    tray = get_object_or_404(Tray, id=tray_id)
    search_query = request.GET.get('search', '')

    # Join Inventory with ToolCreation
    inventory_items = Inventory.objects.select_related('tool').all()

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

            # Extract string-based inventory_id (e.g., "INV001")
            inventory_id = key.replace('assign_qty_', '').strip()
            if not inventory_id:
                continue

            try:
                assign_qty = int(value) if value.strip() else 0
            except ValueError:
                assign_qty = 0

            if assign_qty <= 0:
                continue

            remarks = request.POST.get(f'remarks_{inventory_id}', '').strip()
            inventory_item = get_object_or_404(Inventory, inventory_id=inventory_id)
            tool = inventory_item.tool

            # Validate stock
            if assign_qty > inventory_item.in_stock:
                messages.error(
                    request,
                    f"Cannot assign {assign_qty} units of {tool.tool_name}. "
                    f"Only {inventory_item.in_stock} available."
                )
                continue  # Skip instead of full redirect

            # Deduct stock
            inventory_item.in_stock -= assign_qty
            inventory_item.assigned_quantity += assign_qty
            inventory_item.available_quantity = inventory_item.assigned_quantity
            inventory_item.save()

            # Create TrayTool record
            TrayTool.objects.create(
                tray=tray,
                inventory=inventory_item,
                assigned_quantity=assign_qty,
                remarks=remarks,
                assigned_by=request.user if request.user.is_authenticated else None
            )

        messages.success(request, "Tools assigned successfully!")
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
    ).filter(tray_id=tray_id)

    context = {
        'assigned_tools': assigned_tools,
        'tray_id': tray_id,
    }

    # Use render to display the template with context
    return render(request, 'assigned_tools_list.html', context)

# views.py
from django.db.models import Q
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
    ).all()

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

    print("=== DEBUG: Users and Roles Before Rendering ===")  # Debug start

    for user in users:
        profile, _ = UserProfile.objects.get_or_create(user=user)

        # Get the first Django group if exists
        group_role = user.groups.first().name if user.groups.exists() else None

        # Determine display_role with priority: UserProfile.role > Group.name
        if profile.role:
            # Auto-correct if profile.role != group_role
            if group_role and profile.role.strip() != group_role.strip():
                print(f"Fixing role for {user.username}: {profile.role} -> {group_role}")
                profile.role = group_role.strip()
                profile.save()
            user.display_role = profile.role.strip()
        elif group_role:
            profile.role = group_role.strip()
            profile.save()
            user.display_role = group_role.strip()
        else:
            user.display_role = "Not Assigned"

        # Debug: print each user info
        print(f"User: {user.username}, Role: '{user.display_role}'")

    print("=== END DEBUG ===")

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role = request.POST.get('role').strip() if request.POST.get('role') else None
        station_ids = request.POST.getlist('stations')
        unit_ids = request.POST.getlist('units')
        tray_ids = request.POST.getlist('trays')

        user = get_object_or_404(User, id=user_id)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role

        # Assign access rules
        if role == "Admin":
            profile.station = None
            profile.unit = None
            profile.tray = None
        elif role == "Supervisor":
            profile.station_ids = ",".join(station_ids) if station_ids else None
            profile.unit = None
            profile.tray = None
        elif role == "Mechanic":
            profile.station_id = station_ids[0] if station_ids else None
            profile.unit_ids = ",".join(unit_ids) if unit_ids else None
            profile.tray_id = tray_ids[0] if tray_ids else None

        profile.save()

        # Sync Django group for this user
        user.groups.clear()
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
        user.save()

        print(f"=== DEBUG POST: Updated User {user.username} with role {role} ===")  # Debug POST
        return redirect('manage_users')

    return render(request, 'manage_users.html', {
        'users': users,
        'stations': stations,
        'units': units,
        'trays': trays,
    })