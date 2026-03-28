from django.contrib import admin
from .models import NewsletterSubscriber, SupportTicket, SupportNote


class SupportNoteInline(admin.TabularInline):
    model = SupportNote
    extra = 0


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'source', 'is_active', 'subscribed_at', 'last_confirmation_sent_at')
    list_filter = ('is_active', 'source')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at', 'last_confirmation_sent_at')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer_name', 'channel', 'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('channel', 'priority', 'status')
    search_fields = ('reference', 'customer_name', 'customer_email', 'subject')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    inlines = [SupportNoteInline]


@admin.register(SupportNote)
class SupportNoteAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'author_name', 'created_at')
