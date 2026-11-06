from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from apps.products.views import AdminInventoryListView, AdminBannerListCreateView, AdminFAQListCreateView, AdminPromotionListCreateView, AdminOrderingFilter

class StoreLatestOrderingTests(SimpleTestCase):
    def test_admin_defaults_do_not_use_storefront_priority(self):
        for view in [AdminBannerListCreateView, AdminFAQListCreateView, AdminPromotionListCreateView]:
            self.assertEqual(view.queryset.query.order_by, ('-created_at', '-pk'))
        self.assertEqual(AdminInventoryListView.ordering, ['-created_at','-pk'])
        self.assertIn('created_at', AdminInventoryListView.ordering_fields)

    def test_newest_sort_uses_descending_id_for_equal_dates(self):
        request=Request(APIRequestFactory().get('/',{'ordering':'-created_at'}))
        view=AdminInventoryListView(); view.request=request
        self.assertEqual(AdminOrderingFilter().get_ordering(request,view.get_queryset(),view),['-created_at','-pk'])
