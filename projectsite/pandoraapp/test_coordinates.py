"""Coordinate range CHECKs from migration 0006 (Supplier, Branch, Customer)."""
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from .models import Branch, Customer, Supplier

migration = import_module('pandoraapp.migrations.0006_coordinate_checks')
# The preflight only reads schema_editor.connection; a real editor can't open inside a SQLite test transaction.
EDITOR = SimpleNamespace(connection=connection)


def make(model, **coords):
    extra = {'contact_person': 'Test', 'contact_number': '0917'} if model is Supplier else {}
    return model.objects.create(name=f'{model.__name__} {len(coords)} {sorted(coords.items())}', **extra, **coords)


class CoordinateCheckTests(TestCase):
    def test_null_and_boundary_values_are_allowed(self):
        for model in (Supplier, Branch, Customer):
            make(model)  # no coordinates yet
            make(model, latitude=Decimal('90'), longitude=Decimal('180'))
            make(model, latitude=Decimal('-90'), longitude=Decimal('-180'))
            make(model, latitude=Decimal('14.554700'), longitude=Decimal('121.024400'))

    def test_database_rejects_out_of_range_coordinates(self):
        # update() skips Django's field validators, so only the database CHECK can stop these.
        for model in (Supplier, Branch, Customer):
            row = make(model, latitude=Decimal('1'), longitude=Decimal('1'))
            for field, value in (('latitude', '90.000001'), ('latitude', '-90.5'),
                                 ('longitude', '180.000001'), ('longitude', '-181')):
                with self.subTest(model=model.__name__, field=field, value=value):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        model.objects.filter(pk=row.pk).update(**{field: Decimal(value)})

    def test_full_clean_reports_out_of_range(self):
        branch = Branch(name='Out of range', latitude=Decimal('91'), longitude=Decimal('0'))
        with self.assertRaises(ValidationError):
            branch.full_clean()

    def test_constraints_exist_on_each_table(self):
        with connection.cursor() as cursor:
            for model in (Supplier, Branch, Customer):
                names = connection.introspection.get_constraints(cursor, model._meta.db_table)
                prefix = model._meta.model_name
                self.assertIn(f'{prefix}_latitude_range', names)
                self.assertIn(f'{prefix}_longitude_range', names)


class CoordinatePreflightTests(TestCase):
    def test_passes_on_valid_data(self):
        make(Branch, latitude=Decimal('10'), longitude=Decimal('120'))
        migration.check_existing_coordinates(apps, EDITOR)  # no exception

    def test_stops_without_changing_rows_when_bad_data_exists(self):
        # Bad rows cannot be inserted once the CHECK exists, so simulate a pre-0006 table with 2 bad rows.
        fake_model = mock.Mock()
        fake_model.objects.using.return_value.exclude.return_value.count.return_value = 2
        fake_apps = mock.Mock(get_model=mock.Mock(return_value=fake_model))
        with self.assertRaisesMessage(RuntimeError, 'no rows changed'):
            migration.check_existing_coordinates(fake_apps, EDITOR)
