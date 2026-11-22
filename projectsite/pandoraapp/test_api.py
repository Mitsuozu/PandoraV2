"""REST API, OpenStreetMap geocoding and Leaflet map tests. The network is always mocked."""
import io
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .geocode import geocode
from .models import Branch, Category, Customer, Product, Supplier

MANILA = (Decimal('14.599512'), Decimal('120.984220'))


def nominatim(payload):
    return patch('pandoraapp.geocode.urlopen', return_value=io.BytesIO(json.dumps(payload).encode()))


class ApiTests(TestCase):
    def setUp(self):
        call_command('configure_pandora_roles', stdout=io.StringIO())
        self.admin = get_user_model().objects.create_superuser('api_admin', password='x')
        self.cashier = get_user_model().objects.create_user('api_cashier', password='x')
        self.cashier.groups.add(Group.objects.get(name='Cashier'))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.category = Category.objects.create(name='Laptops')

    def crud(self, endpoint, create, change):
        url = f'/api/{endpoint}/'
        made = self.client.post(url, create, format='json')
        self.assertEqual(made.status_code, 201, made.data)
        item = f"{url}{made.data['id']}/"
        self.assertEqual(self.client.get(url).data['count'], 1)
        self.assertEqual(self.client.get(item).status_code, 200)
        updated = self.client.patch(item, change, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        for key, value in change.items():
            self.assertEqual(str(updated.data[key]), str(value))
        self.assertEqual(self.client.delete(item).status_code, 204)
        self.assertEqual(self.client.get(item).status_code, 404)

    @nominatim([])
    def test_crud_on_seven_tables(self, _):
        Category.objects.all().delete()
        self.crud('categories', {'name': 'Phones'}, {'description': 'Smartphones'})
        self.crud('expense-categories', {'name': 'Rent'}, {'name': 'Utilities'})
        self.crud('suppliers', {'name': 'Acme', 'contact_person': 'Ana', 'contact_number': '0917'},
                  {'contact_person': 'Ben'})
        self.crud('branches', {'name': 'Main branch'}, {'contact_number': '0917'})
        self.crud('customers', {'name': 'Carla'}, {'email': 'carla@example.com'})
        category = Category.objects.create(name='Laptops')
        self.crud('products', {'category': category.pk, 'sku': 'LP-1', 'name': 'Laptop', 'brand': 'B',
                               'model': 'M', 'selling_price': '999.00'}, {'selling_price': '899.00'})
        customer = Customer.objects.create(name='Dan')
        product = Product.objects.create(category=category, sku='LP-2', name='Laptop 2', brand='B',
                                         model='M', selling_price=Decimal('1'))
        self.crud('warranty-claims', {'customer': customer.pk, 'product': product.pk, 'issue': 'No power',
                                      'received_date': '2026-11-22'}, {'status': 'in_repair'})

    def test_stock_and_cost_cannot_be_set_through_api(self):
        made = self.client.post('/api/products/', {
            'category': self.category.pk, 'sku': 'S1', 'name': 'Mouse', 'brand': 'B', 'model': 'M',
            'selling_price': '10.00', 'current_stock': 50, 'cost_price': '1'}, format='json')
        self.assertEqual(made.status_code, 201)
        product = Product.objects.get(sku='S1')
        self.assertEqual((product.current_stock, product.cost_price), (0, 0))

    def test_cashier_reads_catalog_without_cost_and_cannot_delete(self):
        product = Product.objects.create(category=self.category, sku='S2', name='Keyboard', brand='B',
                                         model='M', selling_price=Decimal('5'))
        self.client.force_authenticate(self.cashier)
        row = self.client.get(f'/api/products/{product.pk}/').data
        self.assertNotIn('cost_price', row)
        self.assertEqual(self.client.delete(f'/api/products/{product.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/api/suppliers/').status_code, 403)
        self.assertEqual(self.client.get('/api/expense-categories/').status_code, 403)

    def test_anonymous_is_rejected(self):
        self.assertIn(APIClient().get('/api/categories/').status_code, (401, 403))

    def test_delete_in_use_returns_conflict(self):
        Product.objects.create(category=self.category, sku='S3', name='Cable', brand='B', model='M',
                               selling_price=Decimal('1'))
        response = self.client.delete(f'/api/categories/{self.category.pk}/')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_address_is_geocoded_unless_coordinates_typed(self):
        with nominatim([{'lat': '14.5995124', 'lon': '120.9842195'}]) as call:
            made = self.client.post('/api/branches/', {'name': 'Manila', 'address': 'Manila'}, format='json')
            self.assertEqual((Decimal(made.data['latitude']), Decimal(made.data['longitude'])), MANILA)
            self.client.patch(f"/api/branches/{made.data['id']}/", {'contact_number': '1'}, format='json')
            self.assertEqual(call.call_count, 1)  # unchanged address: no new lookup
            typed = self.client.post('/api/customers/', {'name': 'E', 'address': 'Somewhere',
                                     'latitude': '10.000000', 'longitude': '120.000000'}, format='json')
            self.assertEqual(typed.data['latitude'], '10.000000')
            self.assertEqual(call.call_count, 1)

    def test_geocode_failure_never_blocks_saving(self):
        with patch('pandoraapp.geocode.urlopen', side_effect=OSError('offline')):
            self.assertIsNone(geocode('Manila'))
            made = self.client.post('/api/branches/', {'name': 'Offline', 'address': 'Manila'}, format='json')
        self.assertEqual(made.status_code, 201)
        self.assertIsNone(made.data['latitude'])
        self.assertIsNone(geocode('   '))

    def test_supplier_form_geocodes_address(self):
        web = self.client_class()
        web.force_login(self.admin)
        with nominatim([{'lat': '14.5995124', 'lon': '120.9842195'}]):
            web.post(reverse('pandoraapp:supplier_create'), {
                'name': 'Acme', 'contact_person': 'A', 'contact_number': '1', 'address': 'Manila',
                'is_active': 'on'})
        supplier = Supplier.objects.get(name='Acme')
        self.assertEqual((supplier.latitude, supplier.longitude), MANILA)

    def test_map_shows_only_permitted_located_records(self):
        Branch.objects.create(name='North', latitude=MANILA[0], longitude=MANILA[1])
        Supplier.objects.create(name='Hidden', contact_person='A', contact_number='1',
                                latitude=MANILA[0], longitude=MANILA[1])
        Customer.objects.create(name='No address')
        web = self.client_class()
        web.force_login(self.cashier)
        page = web.get(reverse('pandoraapp:location_map'))
        self.assertContains(page, 'leaflet.js')
        self.assertContains(page, 'North')
        self.assertNotContains(page, 'Hidden')
        self.assertEqual(page.context['missing'], 1)
        nobody = get_user_model().objects.create_user('nobody', password='x')
        web.force_login(nobody)
        self.assertEqual(web.get(reverse('pandoraapp:location_map')).status_code, 403)
