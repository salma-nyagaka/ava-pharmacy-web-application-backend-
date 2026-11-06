from django.contrib.admin.apps import AdminConfig


class MFAAdminConfig(AdminConfig):
    default_site = 'apps.accounts.admin_site.MFAAdminSite'
