import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_PACKAGE = PROJECT_ROOT / 'avapharmacy'

if str(PROJECT_PACKAGE) not in sys.path:
    sys.path.insert(0, str(PROJECT_PACKAGE))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'avapharmacy.settings.production')

from django.core.asgi import get_asgi_application  # noqa: E402

# Load Django before routing imports websocket consumers that use auth models.
django_asgi_application = get_asgi_application()

from avapharmacy.routing import application  # noqa: E402,F401
