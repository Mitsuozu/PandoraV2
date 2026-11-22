from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db.models import Sum
from django.test import TestCase, override_settings

from .models import OperatingExpense, Product, Purchase, Sale


@override_settings(DEBUG=True)
class SeedDemoDataTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser('seed_admin', 'seed@example.com', 'unused-Pass-123')

    def test_creates_consistent_data_once(self):
        call_command('seed_demo_data', days=21, stdout=StringIO())
        self.assertTrue(Sale.objects.filter(status='completed').exists())
        self.assertTrue(Sale.objects.filter(status='cancelled').exists())
        self.assertTrue(Purchase.objects.filter(status='pending').exists())
        self.assertTrue(OperatingExpense.objects.exists())
        for product in Product.objects.filter(sku__startswith='DEMO-'):
            moved = product.stock_movements.aggregate(total=Sum('quantity_change'))['total'] or 0
            self.assertEqual(product.current_stock, moved, product.sku)
        self.assertTrue(Product.objects.filter(current_stock=0).exists())
        with self.assertRaisesMessage(CommandError, 'already loaded'):
            call_command('seed_demo_data')

    @override_settings(DEBUG=False)
    def test_refuses_without_debug(self):
        with self.assertRaisesMessage(CommandError, 'DEBUG is off'):
            call_command('seed_demo_data')
