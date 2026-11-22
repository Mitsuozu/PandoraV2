from io import StringIO

from allauth.account.internal.userkit import filter_users_by_email
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

User = get_user_model()


class TeamAccessTests(TestCase):
    # Fictional accounts in the test DB.
    def setUp(self):
        call_command('configure_pandora_roles', stdout=StringIO())
        self.admin = User.objects.create_user('test_admin', password=None)
        self.admin.groups.add(Group.objects.get(name='Admin'))
        self.cashier = User.objects.create_user('test_cashier', 'cashier@example.test', password='x-test-pass-91')
        self.cashier.groups.add(Group.objects.get(name='Cashier'))
        self.client.force_login(self.admin)

    def set_role(self, user, role):
        return self.client.post(reverse('pandoraapp:team_role', args=[user.pk]), {'role': role})

    def test_only_admins_can_open_or_change_team(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(reverse('pandoraapp:settings')).status_code, 403)
        self.assertEqual(self.set_role(self.admin, 'No access').status_code, 403)
        self.assertTrue(User.objects.get(pk=self.admin.pk).is_active)

    def test_invite_creates_passwordless_user_findable_by_google_email(self):
        response = self.client.post(reverse('pandoraapp:settings'), {'email': ' New.Person@Example.test ', 'role': 'Cashier'})
        self.assertRedirects(response, reverse('pandoraapp:settings'))
        user = User.objects.get(email='new.person@example.test')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['Cashier'])
        self.assertTrue(EmailAddress.objects.get(user=user).verified)  # so allauth won't wipe/refuse it
        self.assertEqual(filter_users_by_email('NEW.person@example.test', prefer_verified=True, for_login=True), [user])
        again = self.client.post(reverse('pandoraapp:settings'), {'email': 'new.person@example.test', 'role': 'Admin'})
        self.assertContains(again, 'already has an account')

    def test_role_changes_and_no_access(self):
        self.set_role(self.cashier, 'Admin')
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.is_staff)
        self.assertEqual(list(self.cashier.groups.values_list('name', flat=True)), ['Admin'])
        self.set_role(self.cashier, 'No access')
        self.cashier.refresh_from_db()
        self.assertFalse(self.cashier.is_active)
        self.assertFalse(self.cashier.groups.exists())
        self.set_role(self.cashier, 'Superuser')  # not a choice
        self.cashier.refresh_from_db()
        self.assertFalse(self.cashier.is_superuser)

    def test_cannot_change_own_role_or_superusers(self):
        boss = User.objects.create_superuser('test_super', password=None)
        self.assertEqual(self.set_role(self.admin, 'Cashier').status_code, 403)
        self.assertEqual(self.set_role(boss, 'No access').status_code, 403)

    def test_changing_email_drops_old_address_and_keeps_password(self):
        self.cashier.email = 'moved@example.test'
        self.cashier.save()
        self.assertEqual(list(EmailAddress.objects.filter(user=self.cashier).values_list('email', 'verified')),
                         [('moved@example.test', True)])
        self.assertEqual(filter_users_by_email('cashier@example.test', for_login=True), [])
        self.assertTrue(User.objects.get(pk=self.cashier.pk).check_password('x-test-pass-91'))


@skipUnless(connection.vendor == 'sqlite', 'MySQL backups are covered in test_remaining')
class BackupPageTests(TransactionTestCase):
    def setUp(self):
        call_command('configure_pandora_roles', stdout=StringIO())
        self.boss = User.objects.create_superuser('test_super', password=None)
        self.admin = User.objects.create_user('test_admin', password=None)
        self.admin.groups.add(Group.objects.get(name='Admin'))
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        directory = patch('pandoraapp.backup_tools.default_directory', return_value=Path(self.folder.name))
        directory.start()
        self.addCleanup(directory.stop)

    def post(self, name, data=None):
        return self.client.post(reverse('pandoraapp:' + name), data or {})

    def test_backup_then_restore_undoes_later_changes(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.post('backup_now'), reverse('pandoraapp:settings'))
        (backup,) = [p.name for p in Path(self.folder.name).glob('pandora-*.sqlite3')]
        self.assertEqual(self.post('restore', {'backup': backup, 'confirm': 'RESTORE'}).status_code, 403)

        User.objects.create_user('added_after_backup', password=None)
        self.client.force_login(self.boss)
        self.post('restore', {'backup': backup, 'confirm': 'restore'})  # wrong word: nothing changes
        self.assertTrue(User.objects.filter(username='added_after_backup').exists())
        self.post('restore', {'backup': '..\db.sqlite3', 'confirm': 'RESTORE'})  # not a listed backup
        self.assertTrue(User.objects.filter(username='added_after_backup').exists())

        self.post('restore', {'backup': backup, 'confirm': 'RESTORE'})
        self.assertFalse(User.objects.filter(username='added_after_backup').exists())
        self.assertEqual(len(list(Path(self.folder.name).glob('pre-restore-*.sqlite3'))), 1)

    def test_non_admin_cannot_back_up(self):
        cashier = User.objects.create_user('test_cashier', password=None)
        cashier.groups.add(Group.objects.get(name='Cashier'))
        self.client.force_login(cashier)
        self.assertEqual(self.post('backup_now').status_code, 403)
        self.assertEqual(list(Path(self.folder.name).iterdir()), [])
