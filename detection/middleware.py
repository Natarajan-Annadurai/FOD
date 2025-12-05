import ipaddress
import logging
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib.auth import logout

logger = logging.getLogger(__name__)

class IPRestrictMiddleware:
    """
    Middleware to restrict access based on client IP.
    Supports single IPs and CIDR ranges.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Read allowed IPs from settings
        allowed_ips = getattr(settings, "ALLOWED_IPS", ["127.0.0.1", "192.168.0.110","192.168.0.103"])
        self.allowed_networks = [ipaddress.ip_network(ip) for ip in allowed_ips]

        # Forbidden message
        self.forbidden_message = getattr(
            settings, "FORBIDDEN_MESSAGE", "Access Denied: Your IP is not allowed."
        )

        # Logging flag
        self.log_blocked = getattr(settings, "LOG_BLOCKED_IPS", False)

    def __call__(self, request):
        # Detect client IP
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        # Validate IP and restrict access if not allowed
        try:
            ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            return HttpResponseForbidden(self.forbidden_message)

        if not any(ip_obj in net for net in self.allowed_networks):
            if self.log_blocked:
                logger.warning(f"Blocked access from IP: {client_ip}")
            return HttpResponseForbidden(self.forbidden_message)

        return self.get_response(request)

class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'AUTO_LOGOUT_TIMEOUT', 300)  # default 5 minutes

    def __call__(self, request):
        # Ensure request.user exists
        if hasattr(request, 'user') and request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = timezone.now().timestamp()

            if last_activity and now - last_activity > self.timeout:
                # Logout user
                logout(request)
                request.session.flush()  # clear session
                return redirect('login')  # redirect to login page immediately
            else:
                # Update last activity timestamp
                request.session['last_activity'] = now

        response = self.get_response(request)
        return response