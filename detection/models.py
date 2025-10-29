from django.db import models

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
