from django.apps import AppConfig
import threading, time, socket

class DetectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'detection'

    def ready(self):
        def background_task():
            hostname = socket.gethostname()
            server_ip = socket.gethostbyname(hostname)
            while True:
                print(f"[Background] ✅ Server active on {server_ip}, waiting for client events...")
                time.sleep(30)

        t = threading.Thread(target=background_task, daemon=True)
        t.start()

    def ready(self):
        import detection.signals

# python manage.py runserver 192.168.0.113:8000