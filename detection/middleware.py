import ipaddress
import logging
import sys
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# -------------------- IP Restrict --------------------
class IPRestrictMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

        allowed_ips = getattr(
            settings,
            "ALLOWED_IPS",
            ["127.0.0.1", "192.168.0.110", "192.168.0.137", "192.168.0.195"]
        )

        self.allowed_networks = []
        for ip in allowed_ips:
            try:
                self.allowed_networks.append(ipaddress.ip_network(ip, strict=False))
            except ValueError:
                logger.error(f"Invalid IP/network: {ip}")

        self.forbidden_message = getattr(
            settings, "FORBIDDEN_MESSAGE", "Access Denied"
        )

    def __call__(self, request):

        # Skip IP restriction for API/device endpoints
        if request.path.startswith("/api/"):
            return self.get_response(request)

        # Skip checks during pytest/tests
        if 'pytest' in sys.modules or getattr(settings, "TESTING", False):
            return self.get_response(request)

        client_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "")
            .split(",")[0]
            .strip()
            or request.META.get("REMOTE_ADDR")
        )

        try:
            ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            logger.warning(f"Blocked invalid IP: {client_ip}")
            return HttpResponseForbidden(self.forbidden_message)

        if not any(ip_obj in net for net in self.allowed_networks):
            logger.warning(f"Blocked IP: {client_ip}")
            return HttpResponseForbidden(self.forbidden_message)

        return self.get_response(request)

# -------------------- Auto Logout --------------------
class AutoLogoutMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'AUTO_LOGOUT_TIMEOUT', 300)

    def __call__(self, request):

        # Skip /api paths
        if request.path.startswith("/api/"):
            return self.get_response(request)

        if hasattr(request, 'user') and request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = timezone.now().timestamp()

            if last_activity and now - last_activity > self.timeout:
                logout(request)
                request.session.flush()
                return redirect('login')
            else:
                request.session['last_activity'] = now

        return self.get_response(request)

# -------------------- Login + No Cache --------------------
class LoginAndNoCacheMiddleware(MiddlewareMixin):

    def process_request(self, request):

        # Skip API completely
        if request.path.startswith('/api/'):
            return None

        login_url = reverse('login')
        logout_url = reverse('logout')

        if request.path in [login_url, logout_url]:
            return None

        if not request.user.is_authenticated:
            return redirect('login')

        return None

    def process_response(self, request, response):
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response