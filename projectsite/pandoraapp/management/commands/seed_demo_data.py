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
from pandoraapp.models import (Branch, Category, Customer, ExpenseCategory, Product, Purchase, Sale,
                               StockMovement, Supplier, WarrantyClaim)

SUPPLIERS = [
    ('Northwind Trading', 'Ana Cruz', '0917 555 0101', 'Ortigas Ave, Pasig City', '14.5869', '121.0614'),
    ('Luzon Gadget Hub', 'Marco Reyes', '0918 555 0144', 'EDSA, Quezon City', '14.6507', '121.0494'),
    ('Visayas Supply Co', 'Liza Tan', '0927 555 0188', 'Osmeña Blvd, Cebu City', '10.3157', '123.8854'),
    ('Mindanao Electronics', 'Paolo Lim', '0939 555 0122', 'J.P. Laurel Ave, Davao City', '7.0907', '125.6128'),
]
# name, brand, model, category, cost, price, reorder level (higher = faster seller)
PRODUCTS = [
    ('Legion Tower 5i Gen 8', 'Lenovo', '90UU00JWPH', 'Desktops', 72000, 84995, 2),
    ('ROG Strix G16CH', 'ASUS', 'G16CHR-71470F', 'Desktops', 88000, 102995, 2),
    ('Mac mini M4', 'Apple', 'MU9D3PP/A', 'Desktops', 31500, 36990, 3),
    ('OptiPlex 7020 Micro', 'Dell', 'OPTI7020MFF', 'Desktops', 36000, 42500, 2),
    ('MacBook Air 13 M3', 'Apple', 'MRXN3PP/A', 'Laptops', 54000, 62990, 3),
    ('ThinkPad E14 Gen 6', 'Lenovo', '21M7002QPH', 'Laptops', 41000, 48995, 3),
    ('Vivobook 15 X1504VA', 'ASUS', 'X1504VA-NJ1033WS', 'Laptops', 26500, 31995, 4),
    ('TUF Gaming A15', 'ASUS', 'FA507NVR-LP091W', 'Laptops', 52000, 61995, 3),
    ('Nitro V 15', 'Acer', 'ANV15-51-58AN', 'Laptops', 43500, 51995, 3),
    ('Victus 15', 'HP', '15-fa1093TX', 'Laptops', 40000, 47999, 3),
    ('Ryzen 5 7600', 'AMD', '100-100001015BOX', 'Processors', 10200, 12450, 5),
    ('Ryzen 7 7800X3D', 'AMD', '100-100000910WOF', 'Processors', 22500, 26750, 3),
    ('Core i5-14400F', 'Intel', 'BX8071514400F', 'Processors', 8900, 10995, 5),
    ('Core i7-14700K', 'Intel', 'BX8071514700K', 'Processors', 22000, 25995, 3),
    ('GeForce RTX 4060 Windforce OC 8G', 'Gigabyte', 'GV-N4060WF2OC-8GD', 'Graphics Cards', 17000, 19995, 4),
    ('GeForce RTX 4070 Super Dual OC', 'ASUS', 'DUAL-RTX4070S-O12G', 'Graphics Cards', 36500, 42500, 2),
    ('Radeon RX 7600 Pulse 8GB', 'Sapphire', '11324-01-20G', 'Graphics Cards', 14800, 17495, 3),
    ('Radeon RX 7800 XT Hellhound', 'PowerColor', 'RX7800XT 16G-L/OC', 'Graphics Cards', 29500, 34495, 2),
    ('B650M Pro RS WiFi', 'ASRock', 'B650M PRO RS WIFI', 'Motherboards', 8200, 9995, 4),
    ('MAG B760M Mortar WiFi', 'MSI', 'MAG B760M MORTAR WIFI', 'Motherboards', 9600, 11495, 4),
    ('ROG Strix X670E-E Gaming WiFi', 'ASUS', 'ROG STRIX X670E-E', 'Motherboards', 27000, 31995, 2),
    ('Fury Beast 16GB (2x8GB) DDR4-3200', 'Kingston', 'KF432C16BBK2/16', 'Memory', 1900, 2450, 8),
    ('Vengeance 32GB (2x16GB) DDR5-6000', 'Corsair', 'CMK32GX5M2B6000C36', 'Memory', 5400, 6750, 6),
    ('Trident Z5 RGB 32GB DDR5-6400', 'G.Skill', 'F5-6400J3239G16GX2-TZ5RK', 'Memory', 7600, 9250, 3),
    ('990 Pro 1TB NVMe', 'Samsung', 'MZ-V9P1T0BW', 'Storage', 5300, 6495, 6),
    ('WD Blue SN580 1TB', 'Western Digital', 'WDS100T3B0E', 'Storage', 3300, 3995, 8),
    ('Barracuda 2TB HDD', 'Seagate', 'ST2000DM008', 'Storage', 2900, 3550, 5),
    ('RM750e 750W 80+ Gold', 'Corsair', 'CP-9020262-NA', 'Power Supplies', 4900, 5995, 4),
    ('MWE 650 Bronze V2', 'Cooler Master', 'MPE-6501-ACABW-BEU', 'Power Supplies', 2500, 3150, 5),
    ('H5 Flow (2024)', 'NZXT', 'CC-H52FW-01', 'Cases', 4300, 5250, 3),
    ('O11 Dynamic EVO', 'Lian Li', 'O11DEW', 'Cases', 7400, 8995, 2),
    ('CH560 Digital', 'DeepCool', 'R-CH560-BKAPE4D-G-1', 'Cases', 3600, 4395, 3),
    ('AK400 Digital', 'DeepCool', 'R-AK400-BKADMN-G', 'Cooling', 1550, 1950, 6),
    ('Kraken 240 RGB', 'NZXT', 'RL-KR240-B1', 'Cooling', 6900, 8450, 2),
    ('UltraGear 27GR75Q 27" QHD 165Hz', 'LG', '27GR75Q-B', 'Monitors', 12000, 14495, 3),
    ('Odyssey G5 32" Curved', 'Samsung', 'LS32CG552EEXXP', 'Monitors', 15500, 18495, 2),
    ('VA2432-H 24" IPS', 'ViewSonic', 'VA2432-H', 'Monitors', 4500, 5495, 5),
    ('G502 X Lightspeed', 'Logitech', '910-006182', 'Mice', 5600, 6995, 5),
    ('DeathAdder V3', 'Razer', 'RZ01-04640100-R3M1', 'Mice', 3200, 3995, 5),
    ('M240 Silent Bluetooth', 'Logitech', '910-007121', 'Mice', 620, 895, 12),
    ('Alloy Origins Core', 'HyperX', '4P5P3AA', 'Keyboards', 3800, 4795, 4),
    ('Royal Kludge RK61', 'Royal Kludge', 'RK61-BLK-RED', 'Keyboards', 1700, 2195, 8),
    ('MK295 Silent Combo', 'Logitech', '920-009814', 'Keyboards', 1050, 1395, 10),
    ('Cloud III', 'HyperX', '727A8AA', 'Headsets', 4400, 5495, 4),
    ('Arctis Nova 1', 'SteelSeries', '61606', 'Headsets', 2600, 3295, 5),
    ('Brio 100 1080p Webcam', 'Logitech', '960-001585', 'Webcams', 1600, 1995, 6),
    ('Archer AX55 WiFi 6 Router', 'TP-Link', 'Archer AX55', 'Networking', 3500, 4295, 4),
    ('Archer TX20E WiFi 6 PCIe Adapter', 'TP-Link', 'Archer TX20E', 'Networking', 1500, 1895, 4),
]
WARRANTY_MONTHS = {'Desktops': 24, 'Laptops': 24, 'Processors': 36, 'Memory': 36, 'Storage': 36,
                   'Power Supplies': 36, 'Motherboards': 36, 'Graphics Cards': 36, 'Monitors': 36}  # others: 12
# name, phone, address, latitude, longitude, active
BRANCHES = [
    ('Pandora Makati', '02 8555 0110', 'Ayala Ave, Makati City', '14.5547', '121.0244', True),
    ('Pandora Quezon City', '02 8555 0120', 'Gilmore Ave, Quezon City', '14.6136', '121.0339', True),
    ('Pandora Cebu', '032 555 0130', 'Gen. Maxilom Ave, Cebu City', '10.3181', '123.9015', True),
    ('Pandora Davao', '082 555 0140', 'C.M. Recto St, Davao City', '7.0700', '125.6087', True),
    ('Pandora Baguio', '074 555 0150', 'Session Rd, Baguio City', '16.4123', '120.5960', False),  # closed branch
]
FIRST_NAMES = ['Juan', 'Maria', 'Jose', 'Angela', 'Mark', 'Kristine', 'Paolo', 'Bea', 'Carlo', 'Nicole',
               'Miguel', 'Patricia', 'Rafael', 'Camille', 'Joshua', 'Andrea', 'Gabriel', 'Isabel', 'Kevin', 'Sofia']
LAST_NAMES = ['Santos', 'Reyes', 'Cruz', 'Bautista', 'Garcia', 'Mendoza', 'Torres', 'Villanueva',
              'Ramos', 'Aquino', 'Castillo', 'Flores', 'Navarro', 'Dela Cruz', 'Gonzales', 'Lopez']
CITIES = ['Makati City', 'Quezon City', 'Pasig City', 'Taguig City', 'Cebu City', 'Davao City', 'Baguio City']
ISSUES = {
    'Desktops': ['Does not power on', 'Random restarts under load', 'No display output'],
    'Laptops': ['Battery not charging', 'Dead pixels on screen', 'Keyboard keys not responding', 'Overheating and shutting down'],
    'Processors': ['System will not POST with this CPU', 'Crashes at stock clocks'],
    'Graphics Cards': ['Artifacting in games', 'Fan rattling noise', 'Black screen after driver install'],
    'Motherboards': ['Bent socket pins on arrival', 'One RAM slot not detected', 'LAN port not working'],
    'Memory': ['Fails MemTest86', 'Only one stick detected'],
    'Storage': ['Drive not detected', 'SMART errors reported', 'Very slow write speeds'],
    'Power Supplies': ['Coil whine and burning smell', 'PC shuts off under load'],
    'Monitors': ['Backlight bleed', 'Flickering at 165Hz', 'Dead pixel cluster'],
}
DEFAULT_ISSUES = ['Stopped working after a few weeks', 'Intermittent connection drops', 'Physical defect on arrival']

EXPENSES = [('Rent', 'Store rent', 35000), ('Utilities', 'Electricity bill', 6200),
            ('Utilities', 'Internet', 1899), ('Salaries', 'Staff payroll', 48000),
            ('Supplies', 'Receipt paper and bags', 1450), ('Marketing', 'Social media ads', 3500)]


class Command(BaseCommand):
    help = 'Add a fake computer store (PCs, parts, laptops, peripherals) with purchases, sales and expenses.'

    def add_arguments(self, parser):
        parser.add_argument('--user', help='Username to record the transactions as (default: first superuser).')
        parser.add_argument('--days', type=int, default=730, help='How many days of history to create (default 730, enough for year-over-year comparisons).')
        parser.add_argument('--seed', type=int, default=7, help='Random seed, for repeatable data.')

    def handle(self, *args, user=None, days=730, seed=7, **options):
        if not settings.DEBUG:
            raise CommandError('Refusing to add fake data while DEBUG is off (this looks like a production database).')
        if Purchase.objects.filter(reference_no__startswith='DEMO-').exists():
            raise CommandError('Demo data is already loaded.')
        if not 7 <= days <= 1095:
            raise CommandError('--days must be between 7 and 1095.')
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
            f'{Sale.objects.filter(receipt_no__startswith="DEMO-").count()} sales, {self.expense_count} expenses, '
            f'{len(BRANCHES)} branches, {Customer.objects.count()} customers and {self.claim_count} warranty claims.'))

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
        categories = {name: Category.objects.get_or_create(name=name)[0] for name in {p[3] for p in PRODUCTS}}
        suppliers = [Supplier.objects.create(name=name, contact_person=person, contact_number=phone, address=address,
                                             latitude=Decimal(lat), longitude=Decimal(lng),
                                             email=f'orders@{name.split()[0].lower()}.example')
                     for name, person, phone, address, lat, lng in SUPPLIERS]
        self.products = [Product.objects.create(
            sku=f'DEMO-{i + 1:03}', name=name, brand=brand, model=model, category=categories[category],
            preferred_supplier=suppliers[i % len(suppliers)], cost_price=Decimal(cost), selling_price=Decimal(price),
            reorder_level=reorder, warranty_months=WARRANTY_MONTHS.get(category, 12))
            for i, (name, brand, model, category, cost, price, reorder) in enumerate(PRODUCTS)]
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
                    # Fast movers (high reorder level) sell more often than desktops and flagship GPUs.
                    picks = self.rng.choices(stocked, weights=[p.reorder_level for p in stocked], k=self.rng.randint(1, 3))
                    self.sale(f'DEMO-R-{sale_no:05}', day, list(dict.fromkeys(picks)))
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
        self.service(start)

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

    def service(self, start):
        """Branches, customers and warranty claims for products that were actually sold."""
        branches = [Branch.objects.create(name=name, contact_number=phone, address=address, latitude=Decimal(lat),
                                          longitude=Decimal(lng), is_active=active)
                    for name, phone, address, lat, lng, active in BRANCHES]
        names = self.rng.sample([(f, l) for f in FIRST_NAMES for l in LAST_NAMES], 60)
        customers = [Customer.objects.create(
            name=f'{first} {last}', contact_number=f'09{self.rng.randint(15, 99)} 555 {self.rng.randint(1000, 9999)}',
            email=f'{first}.{last}'.lower().replace(' ', '') + '@example.com' if self.rng.random() < .7 else None,
            address=self.rng.choice(CITIES)) for first, last in names]
        sold = list(Sale.objects.filter(receipt_no__startswith='DEMO-', status='completed')
                    .values_list('sale_date', 'items__product_id'))
        products = {p.pk: p for p in self.products}
        self.claim_count = 0
        for sale_date, product_id in self.rng.sample(sold, min(len(sold), max(8, len(sold) // 40))):
            product = products[product_id]
            window = min(30 * product.warranty_months, (self.today - sale_date).days)  # within warranty, not in the future
            if window < 1:
                continue
            received = sale_date + timedelta(days=self.rng.randint(1, window))
            age = (self.today - received).days
            if age < 5:
                status = 'received'
            elif age < 20:
                status = self.rng.choice(['received', 'in_repair', 'in_repair', 'released'])
            else:
                status = self.rng.choice(['released'] * 5 + ['rejected'])
            resolution = {'released': self.rng.choice(['Replaced with a new unit', 'Repaired and tested OK',
                                                       'Forwarded to brand service center, unit replaced']),
                          'rejected': self.rng.choice(['Physical damage, not covered by warranty',
                                                       'Warranty seal broken', 'No defect found after testing'])
                          }.get(status, '')
            claim = WarrantyClaim.objects.create(
                customer=self.rng.choice(customers), product=product, received_date=received, status=status,
                branch=self.rng.choice([b for b in branches if b.is_active] if age < 180 else branches),
                serial_number=f'{product.brand[:3].upper()}{self.rng.randint(10**9, 10**10 - 1)}',
                issue=self.rng.choice(ISSUES.get(product.category.name, DEFAULT_ISSUES)), resolution=resolution)
            moment = self.when(received)
            WarrantyClaim.objects.filter(pk=claim.pk).update(created_at=moment, updated_at=moment)
            self.claim_count += 1
