from io import StringIO
from unittest.mock import patch
from django.test import TestCase
from apps.orders.tasks import retry_outbound_order_pushes_task


class ScheduledRetryTaskTests(TestCase):
    def test_task_uses_management_command_defaults(self):
        # Calling Command.handle() directly omitted required parsed defaults.
        with patch('sys.stdout', new_callable=StringIO) as output:
            result = retry_outbound_order_pushes_task.apply(throw=True)
        self.assertTrue(result.successful())
        self.assertIn('Processed 0 queued push(es)', output.getvalue())
