from pathlib import Path
import sys

# Keep the apps namespace importable without shadowing installed packages
# such as Celery with avapharmacy/celery.py.
_package_path = str(Path(__file__).resolve().parent)
if _package_path not in sys.path:
    sys.path.append(_package_path)

from .celery import app as celery_app

__all__ = ('celery_app',)
