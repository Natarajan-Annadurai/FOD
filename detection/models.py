from django.db import models
from django.contrib.auth.models import User

class ProfileInformation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        blank=True, null=True
    )
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return self.user.username

class ToolCreation(models.Model):
    tool_id = models.CharField(max_length=50, unique=True)
    tool_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    tool_type = models.CharField(max_length=50, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tool_id} - {self.tool_name}"

# models.py
class ToolPurchase(models.Model):
    tool = models.ForeignKey(ToolCreation, on_delete=models.CASCADE)
    supplier_name = models.CharField(max_length=200)
    invoice_number = models.CharField(max_length=100)
    quantity = models.IntegerField()
    unit_cost = models.FloatField()
    purchase_cost = models.FloatField()
    purchase_date = models.DateField()
    calibration = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Inventory(models.Model):
    inventory_id = models.CharField(max_length=20, primary_key=True, editable=False)
    tool = models.ForeignKey(ToolCreation, on_delete=models.CASCADE, related_name='inventory_items')
    location = models.CharField(max_length=100, default='Warehouse')
    total_quantity = models.PositiveIntegerField(default=0)
    in_stock = models.PositiveIntegerField(default=0)
    assigned_quantity = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)
    in_use = models.PositiveIntegerField(default=0)
    damaged = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.inventory_id:
            last = Inventory.objects.order_by('-inventory_id').first()
            if last:
                # Extract numeric part safely from something like "INV005"
                last_num = int(last.inventory_id.replace('INV', ''))
                self.inventory_id = f"INV{last_num + 1:03d}"
            else:
                self.inventory_id = "INV001"
        super().save(*args, **kwargs)

class ServiceStation(models.Model):
    station_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=255, blank=True, null=True)
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_stations'
    )
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.station_id:
            last = ServiceStation.objects.order_by('-id').first()
            next_id = 1 if not last else last.id + 1
            self.station_id = f"SS{next_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.station_id} - {self.name}"


class Unit(models.Model):
    station = models.ForeignKey(ServiceStation, on_delete=models.CASCADE, related_name='units')
    station_code = models.CharField(max_length=20, blank=True, null=True)
    unit_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    incharge = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='unit_incharges'
    )
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.unit_id:
            last = Unit.objects.order_by('-id').first()
            next_id = 1 if not last else last.id + 1
            self.unit_id = f"U{next_id:03d}"

        if self.station:
            self.station_code = self.station.station_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.unit_id} - {self.name}"


class Tray(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='trays')
    unit_code = models.CharField(max_length=20, blank=True, null=True)
    tray_id = models.CharField(max_length=20, unique=True, editable=False)
    tray_name = models.CharField(max_length=100)
    max_capacity = models.PositiveIntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.tray_id:
            last = Tray.objects.order_by('-id').first()
            next_id = 1 if not last else last.id + 1
            self.tray_id = f"T{next_id:03d}"
        # Auto-fill unit_code from related Unit
        if self.unit and not self.unit_code:
            self.unit_code = self.unit.unit_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tray_id} - {self.tray_name}"

class TrayTool(models.Model):
    tray = models.ForeignKey('Tray', on_delete=models.CASCADE, related_name='tray_tools')
    inventory = models.ForeignKey('Inventory', on_delete=models.CASCADE)
    tool_id = models.CharField(max_length=100, default="unknown_tool")
    assigned_quantity = models.PositiveIntegerField()
    remarks = models.TextField(blank=True, null=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tray.tray_name} → {self.inventory.tool.tool_name} ({self.assigned_quantity})"

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Supervisor', 'Supervisor'),
        ('Mechanic', 'Mechanic'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True)

    # Only store readable names
    stations_display = models.TextField(null=True, blank=True)
    units_display = models.TextField(null=True, blank=True)
    trays_display = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class ToolEventTracking(models.Model):
    EVENT_CHOICES = [
        ('tray_open', 'Tray Open'),
        ('tray_close', 'Tray Close'),
        ('tool_Issued', 'Tool Issued'),
        ('tool_Returned', 'Tool Returned'),
        ('tool_Damaged', 'Tool Damaged'),
        ('auto_logout', 'Auto Logout'),
        ('system_offline', 'System Offline'),
        ('system_online', 'System Online'),
    ]

    timestamp = models.DateTimeField()
    service_station = models.CharField(max_length=100, null=True, blank=True)
    unit = models.CharField(max_length=100, null=True, blank=True)
    unit_id = models.IntegerField(null=True, blank=True)
    user_id = models.CharField(max_length=50, null=True, blank=True)
    user_name = models.CharField(max_length=100, null=True, blank=True)
    event = models.CharField(max_length=50, choices=EVENT_CHOICES)
    tray_id = models.CharField(max_length=50, null=True, blank=True)
    tool_id = models.CharField(max_length=50, null=True, blank=True)
    tool_name = models.CharField(max_length=200, null=True, blank=True)
    device_id = models.CharField(max_length=100, null=True, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    raw_data = models.JSONField(null=True, blank=True)  # Store full original payload
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event} - {self.tool_name or self.tool_id or self.tray_id}"
