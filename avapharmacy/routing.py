from django.core.asgi import get_asgi_application
from django.urls import re_path

try:  # pragma: no cover - optional dependency in local dev
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
except Exception:  # pragma: no cover
    application = get_asgi_application()
else:
    from apps.consultations.consumers import ConsultationConsumer

    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter([
                re_path(r'^ws/consultations/(?P<pk>\d+)/$', ConsultationConsumer.as_asgi()),
            ])
        ),
    })
