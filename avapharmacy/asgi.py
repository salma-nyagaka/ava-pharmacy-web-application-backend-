import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_PACKAGE = PROJECT_ROOT / 'avapharmacy'

if str(PROJECT_PACKAGE) not in sys.path:
    sys.path.insert(0, str(PROJECT_PACKAGE))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'avapharmacy.settings.production')

from avapharmacy.routing import application  # noqa: E402
