from django.db import transaction
from .models import ComplianceEvent


def record_change(obj, actor, action):
    snapshot = {f.name: f.value_to_string(obj) for f in obj._meta.fields if f.name != 'file'}
    ComplianceEvent.objects.create(actor=actor, model_label=obj._meta.label_lower, record_id=obj.pk,
                                   action=action, snapshot=snapshot)


class AuditedSerializerMixin:
    @transaction.atomic
    def create(self, validated_data):
        obj = super().create(validated_data)
        record_change(obj, self.context['request'].user, 'create')
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        obj = super().update(instance, validated_data)
        record_change(obj, self.context['request'].user, 'update')
        return obj


class LockedUpdateMixin:
    @transaction.atomic
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.method in {'PATCH', 'PUT'}:
            return qs.select_for_update(of=('self',))
        return qs
