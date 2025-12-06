import ipaddress
import logging
import sys

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import logout

logger = logging.getLogger(__name__)

class IPRestrictMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

        # Read allowed IPs from settings
        allowed_ips = getattr(settings, "ALLOWED_IPS", ["127.0.0.1", "192.168.0.110", "192.168.0.103"])
        self.allowed_networks = []
        for ip in allowed_ips:
            try:
                self.allowed_networks.append(ipaddress.ip_network(ip, strict=False))
            except ValueError:
                logger.error(f"Invalid IP/network in ALLOWED_IPS: {ip}")

        self.forbidden_message = getattr(
            settings, "FORBIDDEN_MESSAGE", "Access Denied: Your IP is not allowed."
        )
        self.log_blocked = getattr(settings, "LOG_BLOCKED_IPS", True)

    def __call__(self, request):

        # SKIP MIDDLEWARE DURING TESTS (VERY IMPORTANT)
        if 'pytest' in sys.modules or getattr(settings, "TESTING", False):
            return self.get_response(request)

        # Detect client IP
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        try:
            ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            if self.log_blocked:
                logger.warning(f"Blocked invalid IP: {client_ip}")
            return HttpResponseForbidden(self.forbidden_message)

        # IP not in allowed list
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

from django.utils.deprecation import MiddlewareMixin

class LoginAndNoCacheMiddleware(MiddlewareMixin):
    def process_request(self, request):
        login_url = reverse('login')
        logout_url = reverse('logout')

        # Skip login/logout pages
        if request.path in [login_url, logout_url]:
            return None

        # Redirect if user is not authenticated
        if not request.user.is_authenticated:
            return redirect('login')
        return None

    def process_response(self, request, response):
        # Disable caching for all responses
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response