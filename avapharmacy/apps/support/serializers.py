from rest_framework import serializers
from .models import SupportTicket, SupportNote


class SupportNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportNote
        fields = ('id', 'author', 'author_name', 'message', 'created_at')
        read_only_fields = ('id', 'author', 'author_name', 'created_at')


class SupportTicketSerializer(serializers.ModelSerializer):
    notes = SupportNoteSerializer(many=True, read_only=True)
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.full_name')

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'reference', 'customer', 'customer_name', 'customer_email',
            'channel', 'reference_id', 'subject', 'priority', 'status',
            'assigned_to', 'assigned_to_name', 'notes', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'customer', 'created_at', 'updated_at')


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ('channel', 'reference_id', 'subject', 'priority')


class SupportTicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ('status', 'priority', 'assigned_to')


class SupportNoteCreateSerializer(serializers.Serializer):
    message = serializers.CharField()
