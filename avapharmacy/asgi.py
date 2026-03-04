"""
ASGI config for AvaPharma project.

Exposes the ASGI callable via avapharmacy.routing.application to support
both HTTP (Django) and WebSocket (Django Channels) connections.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'avapharmacy.settings.production')
application = get_asgi_application()
