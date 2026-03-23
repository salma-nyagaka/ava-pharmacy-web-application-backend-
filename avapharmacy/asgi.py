"""
ASGI config for AvaPharma project.

Exposes the ASGI callable via avapharmacy.routing.application to support
both HTTP (Django) and WebSocket (Django Channels) connections.
"""
import os
import sys
from pathlib import Path
from django.core.asgi import get_asgi_application

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_PACKAGE = PROJECT_ROOT / 'avapharmacy'

if str(PROJECT_PACKAGE) not in sys.path:
    sys.path.insert(0, str(PROJECT_PACKAGE))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'avapharmacy.settings.production')
application = get_asgi_application()
