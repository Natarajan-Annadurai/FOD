import random
import threading
import time
from django.apps import AppConfig
from django.utils import timezone
import sys
from django.db.models import F
from django.db import transaction

def background_dummy_event_generator():
    """
    Continuously inserts dummy ToolEventTracking events and updates Inventory correctly.
    Will skip updates if available_quantity is 0 for issue/damage, or in_use is 0 for return.
    """
    from detection.models import ToolEventTracking, Inventory

    print("🔄 [Background Event Generator] Started generating dummy events...")

    tools = [
        ("TL-20251029-VUFF", "Spanner 7 inch"),
        ("TL-20251029-0SBS", "Spanner 10 inch"),
        ("TL-20251029-PTY9", "Hammer 5 kg"),
        ("TL-20251029-Y4I6", "Screw Driver"),
        ("TL-20251031-NVRR", "Hammer 10 kg"),
        ("TL-20251101-WUT8", "Spanner 20 inch")
    ]

    users = [
        ("1", "mechanic1"),
        ("2", "mechanic2"),
        ("3", "mechanic3"),
        ("4", "mechanic4"),
        ("5", "mechanic5"),
        ("6", "mechanic6"),
        ("7", "mechanic7"),
    ]

    while True:
        user_id, user_name = random.choice(users)
        tool_id, tool_name = random.choice(tools)

        # Fetch inventory for the tool
        try:
            inventory = Inventory.objects.get(tool__tool_id=tool_id)
        except Inventory.DoesNotExist:
            print(f"⚠️ Inventory not found for {tool_name}")
            time.sleep(2)
            continue

        # Determine which event is allowed based on inventory state
        event = None
        if inventory.available_quantity > 0 and inventory.in_use == 0:
            # Can issue or damage
            event = random.choice(["tool_Issued", "tool_Damaged"])
        elif inventory.available_quantity > 0 and inventory.in_use > 0:
            # Can issue, return, or damage
            event = random.choice(["tool_Issued", "tool_Returned", "tool_Damaged"])
        elif inventory.available_quantity == 0 and inventory.in_use > 0:
            # Can only return
            event = "tool_Returned"
        else:
            # No available or in_use tools — cannot issue or damage
            print(f"⚠️ Cannot perform any event on {tool_name}: available={inventory.available_quantity}, in_use={inventory.in_use}")
            time.sleep(5)
            continue  # skip to next iteration

        # Check event validity
        if (event == "tool_Issued" and inventory.available_quantity <= 0) or \
           (event == "tool_Damaged" and inventory.available_quantity <= 0) or \
           (event == "tool_Returned" and inventory.in_use <= 0):
            print(f"⚠️ Event {event} not allowed for {tool_name} (available={inventory.available_quantity}, in_use={inventory.in_use})")
            time.sleep(5)
            continue  # skip invalid event

        # Apply event safely
        with transaction.atomic():
            ToolEventTracking.objects.create(
                timestamp=timezone.now(),
                user_id=user_id,
                user_name=user_name,
                event=event,
                tray_id=1,
                unit_id=1,
                tool_id=tool_id,
                tool_name=tool_name,
            )

            if event == "tool_Issued":
                Inventory.objects.filter(pk=inventory.pk).update(
                    in_use=F('in_use') + 1,
                    available_quantity=F('available_quantity') - 1
                )
            elif event == "tool_Returned":
                Inventory.objects.filter(pk=inventory.pk).update(
                    in_use=F('in_use') - 1,
                    available_quantity=F('available_quantity') + 1
                )
            elif event == "tool_Damaged":
                Inventory.objects.filter(pk=inventory.pk).update(
                    damaged=F('damaged') + 1,
                    available_quantity=F('available_quantity') - 1
                )
            inventory.refresh_from_db()

        print(f"✅ Event: {event} | Tool: {tool_name} | User: {user_name} | In Use: {inventory.in_use} | Damaged: {inventory.damaged} | Available: {inventory.available_quantity}")
        time.sleep(5)

class DetectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "detection"

    def ready(self):
        if "runserver" in sys.argv:
            thread = threading.Thread(target=background_dummy_event_generator, daemon=True)
            thread.start()