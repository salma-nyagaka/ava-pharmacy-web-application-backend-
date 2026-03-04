from .models import AdminAuditLog


def log_admin_action(actor, action, entity_type, entity_id='', message='', metadata=None):
    if not actor or not getattr(actor, 'is_authenticated', False):
        return None

    return AdminAuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        message=message or action,
        metadata=metadata or {},
    )
