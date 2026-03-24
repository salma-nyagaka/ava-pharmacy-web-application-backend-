import json
from urllib.parse import parse_qs

from django.contrib.auth.models import AnonymousUser

try:  # pragma: no cover - optional dependency in local dev
    from channels.db import database_sync_to_async
    from channels.generic.websocket import AsyncJsonWebsocketConsumer
    from rest_framework_simplejwt.authentication import JWTAuthentication
except Exception:  # pragma: no cover
    AsyncJsonWebsocketConsumer = object
    database_sync_to_async = None
    JWTAuthentication = None


class ConsultationConsumer(AsyncJsonWebsocketConsumer):  # pragma: no cover - websocket integration
    async def connect(self):
        user = await self._authenticate()
        consultation_id = self.scope['url_route']['kwargs']['pk']
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = f'consultation_{consultation_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get('type')
        if event_type == 'typing.indicator':
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'consultation.event',
                    'event_type': 'typing.indicator',
                    'payload': {
                        'user_id': self.user.id,
                        'user_name': self.user.full_name,
                        'is_typing': bool(content.get('is_typing', True)),
                    },
                },
            )

    async def consultation_event(self, event):
        await self.send_json({
            'type': event['event_type'],
            'payload': event['payload'],
        })

    @database_sync_to_async
    def _authenticate(self):
        if JWTAuthentication is None:
            return AnonymousUser()
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        token = parse_qs(query_string).get('token', [''])[0]
        if not token:
            return AnonymousUser()
        authenticator = JWTAuthentication()
        validated = authenticator.get_validated_token(token)
        return authenticator.get_user(validated)
