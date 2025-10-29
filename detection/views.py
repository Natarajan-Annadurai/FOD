from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import ToolCreation, ToolPurchase, Inventory

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