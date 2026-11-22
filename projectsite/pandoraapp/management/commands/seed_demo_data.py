"""Fill a development database with believable fake store data.

Sales, purchases and expenses go through the same services the app uses, so stock levels,
stock movements and totals stay consistent. Everything it creates is tagged DEMO- and the
command refuses to run twice or with DEBUG off (a production database).
"""

import random
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from pandoraapp import services
from pandoraapp.expense_services import record_expense
from pandoraapp.models import Category, ExpenseCategory, Product, Purchase, Sale, StockMovement, Supplier

SUPPLIERS = [
    ('Northwind Trading', 'Ana Cruz', '0917 555 0101', 'Ortigas Ave, Pasig City', '14.5869', '121.0614'),
    ('Luzon Gadget Hub', 'Marco Reyes', '0918 555 0144', 'EDSA, Quezon City', '14.6507', '121.0494'),
    ('Visayas Supply Co', 'Liza Tan', '0927 555 0188', 'Osmeña Blvd, Cebu City', '10.3157', '123.8854'),
    ('Mindanao Electronics', 'Paolo Lim', '0939 555 0122', 'J.P. Laurel Ave, Davao City', '7.0907', '125.6128'),
]
# name, brand, category, cost, price, reorder level
PRODUCTS = [
    ('Galaxy A55', 'Samsung', 'Phones', 17500, 22990, 5),
    ('Redmi Note 13', 'Xiaomi', 'Phones', 9800, 12990, 6),
    ('iPhone 15', 'Apple', 'Phones', 46000, 54990, 3),
    ('ThinkPad E14', 'Lenovo', 'Laptops', 38000, 45990, 3),
    ('IdeaPad Slim 3', 'Lenovo', 'Laptops', 26500, 32990, 4),
    ('Vivobook 15', 'ASUS', 'Laptops', 29000, 35490, 3),
    ('JBL Tune 520BT', 'JBL', 'Audio', 1900, 2790, 8),
    ('Sony WH-CH720N', 'Sony', 'Audio', 4800, 6490, 5),
    ('Galaxy Buds FE', 'Samsung', 'Audio', 3200, 4490, 6),
    ('USB-C Charger 65W', 'Anker', 'Accessories', 1100, 1690, 10),
    ('PowerCore 20000', 'Anker', 'Accessories', 1500, 2290, 8),
    ('M331 Silent Mouse', 'Logitech', 'Accessories', 650, 995, 10),
    ('HDMI Cable 2m', 'Ugreen', 'Accessories', 180, 349, 15),
    ('Tempered Glass Pack', 'Spigen', 'Accessories', 120, 299, 20),
    ('Galaxy Watch FE', 'Samsung', 'Wearables', 8200, 10990, 3),
    ('Mi Band 9', 'Xiaomi', 'Wearables', 1700, 2490, 6),
]
EXPENSES = [('Rent', 'Store rent', 35000), ('Utilities', 'Electricity bill', 6200),
            ('Utilities', 'Internet', 1899), ('Salaries', 'Staff payroll', 48000),
            ('Supplies', 'Receipt paper and bags', 1450), ('Marketing', 'Social media ads', 3500)]


class Command(BaseCommand):
    help = 'Add fake products, suppliers, purchases, sales and expenses for development.'

    def add_arguments(self, parser):
        parser.add_argument('--user', help='Username to record the transactions as (default: first superuser).')
        parser.add_argument('--days', type=int, default=90, help='How many days of history to create (default 90).')
        parser.add_argument('--seed', type=int, default=7, help='Random seed, for repeatable data.')

    def handle(self, *args, user=None, days=90, seed=7, **options):
        if not settings.DEBUG:
            raise CommandError('Refusing to add fake data while DEBUG is off (this looks like a production database).')
        if Purchase.objects.filter(reference_no__startswith='DEMO-').exists():
            raise CommandError('Demo data is already loaded.')
        if not 7 <= days <= 365:
            raise CommandError('--days must be between 7 and 365.')
        users = get_user_model().objects.filter(is_active=True)
        actor = users.filter(username=user).first() if user else users.filter(is_superuser=True).order_by('pk').first()
        if not actor or not actor.is_superuser:
            raise CommandError('Pass --user with an active superuser account (createsuperuser makes one).')
        self.rng, self.actor = random.Random(seed), actor
        self.today = timezone.localdate()
        with transaction.atomic():
            self.seed(days)
        self.stdout.write(self.style.SUCCESS(
            f'Added {len(self.products)} products, {Purchase.objects.filter(reference_no__startswith="DEMO-").count()} purchases, '
            f'{Sale.objects.filter(receipt_no__startswith="DEMO-").count()} sales and {self.expense_count} expenses.'))

    def when(self, day):
        """A store-hours timestamp on the given business day."""
        clock = time(self.rng.randint(9, 19), self.rng.randint(0, 59))
        return timezone.make_aware(datetime.combine(day, clock))

    def backdate(self, header, moment, **extra):
        # The services stamp "now"; move each record to the day it belongs to.
        type(header).objects.filter(pk=header.pk).update(created_at=moment, updated_at=moment, **extra)
        header.items.update(created_at=moment, updated_at=moment)
        StockMovement.objects.filter(**{('purchase_item__purchase' if isinstance(header, Purchase) else 'sale_item__sale'): header}
                                     ).update(created_at=moment, updated_at=moment)

    def seed(self, days):
        categories = {name: Category.objects.get_or_create(name=name)[0] for name in {p[2] for p in PRODUCTS}}
        suppliers = [Supplier.objects.create(name=name, contact_person=person, contact_number=phone, address=address,
                                             latitude=Decimal(lat), longitude=Decimal(lng),
                                             email=f'orders@{name.split()[0].lower()}.example')
                     for name, person, phone, address, lat, lng in SUPPLIERS]
        self.products = [Product.objects.create(
            sku=f'DEMO-{i + 1:03}', name=name, brand=brand, model=str(2024 + i % 3), category=categories[category],
            preferred_supplier=suppliers[i % len(suppliers)], cost_price=Decimal(cost), selling_price=Decimal(price),
            reorder_level=reorder, warranty_months=12 if category in ('Phones', 'Laptops') else 6)
            for i, (name, brand, category, cost, price, reorder) in enumerate(PRODUCTS)]
        never_stocked = self.products[-1]  # one item stays out of stock: ordered but not yet received
        start = self.today - timedelta(days=days - 1)
        purchase_no = sale_no = 0
        for offset in range(days):
            day = start + timedelta(days=offset)
            # Restock what has run low; stop a week before today so some items show as low stock.
            due = [p for p in self.products if p is not never_stocked and p.current_stock <= p.reorder_level
                   and (offset == 0 or (offset < days - 7 and self.rng.random() < .5))]
            for supplier in suppliers:
                lines = [p for p in due if p.preferred_supplier_id == supplier.pk]
                if lines:
                    purchase_no += 1
                    self.purchase(f'DEMO-PO-{purchase_no:04}', supplier, day, lines, receive=True)
            weekend = day.weekday() >= 5
            for _ in range(self.rng.randint(3, 8) if weekend else self.rng.randint(1, 5)):
                stocked = [p for p in self.products if p.current_stock]
                if stocked:
                    sale_no += 1
                    self.sale(f'DEMO-R-{sale_no:05}', day, self.rng.sample(stocked, min(len(stocked), self.rng.randint(1, 3))))
        purchase_no += 1
        self.purchase(f'DEMO-PO-{purchase_no:04}', never_stocked.preferred_supplier, self.today, [never_stocked], receive=False)
        # A couple of abandoned (cancelled) sales so the history shows every status.
        for back in (1, 3):
            sale_no += 1
            product = next(p for p in self.products if p.current_stock)
            header = services.create_sale_draft(actor=self.actor, receipt_no=f'DEMO-R-{sale_no:05}',
                                                sale_date=self.today - timedelta(days=back),
                                                lines=[dict(product_id=product.pk, quantity=1)])
            services.cancel_sale(actor=self.actor, sale_id=header.pk, reason='Customer changed their mind')
            moment = self.when(self.today - timedelta(days=back))
            self.backdate(header, moment, voided_at=moment + timedelta(minutes=10))
        self.expenses(start)

    def purchase(self, reference, supplier, day, products, receive):
        lines = [dict(product_id=p.pk, quantity=self.rng.randint(15, 40) if p.reorder_level >= 8 else self.rng.randint(6, 14),
                      unit_cost=str(p.cost_price.quantize(Decimal('0.01')))) for p in products]
        header = services.create_purchase_draft(actor=self.actor, reference_no=reference, supplier_id=supplier.pk,
                                                order_date=day, lines=lines)
        moment = self.when(day)
        if receive:
            services.receive_purchase(actor=self.actor, purchase_id=header.pk,
                                      expected_lines=services.purchase_snapshot(actor=self.actor, purchase_id=header.pk))
            self.backdate(header, moment, received_at=moment + timedelta(hours=2))
            for product in products:
                product.refresh_from_db()
        else:
            self.backdate(header, moment)

    def sale(self, receipt, day, products):
        lines = [dict(product_id=p.pk, quantity=self.rng.randint(1, min(3, p.current_stock))) for p in products]
        header = services.create_sale_draft(actor=self.actor, receipt_no=receipt, sale_date=day, lines=lines)
        total = sum(p.selling_price * line['quantity'] for p, line in zip(products, lines))
        method = self.rng.choice(['cash', 'cash', 'credit_card', 'mobile_payment'])
        paid = (total // 500 + 1) * 500 if method == 'cash' else total  # cash rounds up to the next ₱500
        services.complete_sale(actor=self.actor, sale_id=header.pk, payment_method=method, amount_paid=str(paid),
                               expected_lines=services.sale_snapshot(actor=self.actor, sale_id=header.pk))
        self.backdate(header, self.when(day))
        for product in products:
            product.refresh_from_db()

    def expenses(self, start):
        self.expense_count = 0
        month = start.replace(day=1)
        while month <= self.today:
            for category, description, amount in EXPENSES:
                day = month.replace(day=self.rng.randint(1, 28))
                if start <= day <= self.today:
                    jitter = 1 if category == 'Rent' else 1 + Decimal(self.rng.randint(-8, 8)) / 100
                    record_expense(actor=self.actor, request_id=uuid.uuid4(), expense_date=day,
                                   category=ExpenseCategory.objects.get_or_create(name=category)[0],
                                   description=description, amount=(Decimal(amount) * jitter).quantize(Decimal('0.01')))
                    self.expense_count += 1
            month = (month + timedelta(days=32)).replace(day=1)
