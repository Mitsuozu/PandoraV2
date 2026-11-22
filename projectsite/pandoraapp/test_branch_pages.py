from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Branch, Customer, WarrantyClaim
from .test_services import Fixtures


class BranchAndWarrantyPagesTests(Fixtures, TestCase):
    def setUp(self):
        self.make_fixtures()
        self.client.force_login(self.admin)

    def url(self, name, pk=None):
        return reverse('pandoraapp:' + name, args=[pk] if pk else [])

    @patch('pandoraapp.supplier_views.coordinates_for', return_value={'latitude': 14.6, 'longitude': 121.0})
    def test_branch_add_geocodes_and_lists(self, _):
        response = self.client.post(self.url('branch_create'), {'name': 'Test North', 'address': 'Test City',
                                                                'is_active': 'on'})
        self.assertRedirects(response, self.url('branches'))
        branch = Branch.objects.get(name='Test North')
        self.assertIsNotNone(branch.latitude)
        Branch.objects.create(name='Closed branch', is_active=False)
        response = self.client.get(self.url('branches'), {'status': 'active'})
        self.assertEqual([b.name for b in response.context['page']], ['Test North'])

    def test_warranty_claim_with_new_customer_then_update(self):
        branch = Branch.objects.create(name='Test branch')
        data = {'new_customer': 'Synthetic customer', 'product': self.product.pk, 'branch': branch.pk,
                'issue': 'Keys stick', 'received_date': '2026-11-20', 'status': 'received'}
        self.assertRedirects(self.client.post(self.url('warranty_create'), data), self.url('warranty_claims'))
        claim = WarrantyClaim.objects.get()
        self.assertEqual(claim.customer.name, 'Synthetic customer')
        data.update(new_customer='', customer=claim.customer.pk, status='released')
        self.client.post(self.url('warranty_edit', claim.pk), data)
        self.assertEqual(Customer.objects.count(), 1)
        response = self.client.get(self.url('warranty_claims'), {'status': 'released'})
        self.assertContains(response, 'Synthetic customer')

    def test_warranty_claim_needs_a_customer(self):
        response = self.client.post(self.url('warranty_create'), {
            'product': self.product.pk, 'issue': 'x', 'received_date': '2026-11-20', 'status': 'received'})
        self.assertContains(response, 'Choose a customer')
        self.assertFalse(WarrantyClaim.objects.exists())

    def test_cashier_sees_claims_but_cannot_add_branch(self):
        cashier = self.role_user('test_cashier', 'Cashier',
                                 ['view_branch', 'view_warrantyclaim', 'add_warrantyclaim', 'view_customer'])
        self.client.force_login(cashier)
        response = self.client.get(self.url('warranty_create'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('new_customer', response.context['form'].fields)  # no add_customer permission
        self.assertEqual(self.client.get(self.url('branches')).status_code, 200)
        self.assertEqual(self.client.get(self.url('branch_create')).status_code, 403)
        self.assertContains(self.client.get(self.url('home')), self.url('warranty_claims'))
