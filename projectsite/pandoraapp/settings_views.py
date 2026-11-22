"""Admin-only Settings: who can sign in (and with which role), and database backups.

An invited person gets an account with no password: they sign in with Google or GitHub using that email.
Restoring a backup replaces every table, so only superusers can do it.
"""
from datetime import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import backup_tools
from .management.commands.create_demo_accounts import DEMO_ACCOUNTS
from .navigation import access_for

# Role -> may open Django admin, the same as the demo accounts.
ROLES = {role: staff for role, staff in DEMO_ACCOUNTS.values()}
NO_ACCESS = 'No access'
RESTORE_WORD = 'RESTORE'


class InviteForm(forms.Form):
    email = forms.EmailField(label='Email (their Google or GitHub email)')
    role = forms.ChoiceField(choices=[(role, role) for role in ROLES])

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise forms.ValidationError('This email already has an account. Change its role in the list below.')
        return email


def _require_admin(user):
    if not access_for(user)['admin_access']:
        raise PermissionDenied('Only admins can open Settings.')


def _can_edit(actor, target):
    # Never yourself (no accidental lockout); superusers are managed in Django admin.
    return target.pk != actor.pk and not target.is_superuser


def role_of(user):
    if user.is_superuser:
        return 'Superuser'
    if not user.is_active:
        return NO_ACCESS
    return next((g.name for g in user.groups.all() if g.name in ROLES), NO_ACCESS)


def _apply_role(request, user, role):
    """Give the user exactly one role, or switch the account off. Returns False if roles aren't set up."""
    group = Group.objects.filter(name=role).first()
    if role != NO_ACCESS and group is None:
        messages.error(request, "Roles aren't set up yet. Run 'python manage.py configure_pandora_roles'.")
        return False
    user.is_active = role != NO_ACCESS
    user.is_staff = ROLES.get(role, False)
    user.save()
    user.groups.set([group] if group else [])
    return True


def _backups():
    return [{'name': path.name, 'saved': datetime.fromtimestamp(path.stat().st_mtime),
             'kb': path.stat().st_size / 1024}
            for path in backup_tools.list_backups(backup_tools.default_directory())]


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    _require_admin(request.user)
    form = InviteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email, role = form.cleaned_data['email'], form.cleaned_data['role']
        with transaction.atomic():
            user = get_user_model()(username=email, email=email)
            user.set_unusable_password()
            if _apply_role(request, user, role):
                messages.success(request, f'{email} can now sign in with Google or GitHub as {role}.')
                return redirect('pandoraapp:settings')
            transaction.set_rollback(True)
    users = get_user_model().objects.prefetch_related('groups').order_by('-is_active', 'username')
    return render(request, 'pandoraapp/settings.html', {
        'form': form, 'rows': [(user, role_of(user), _can_edit(request.user, user)) for user in users],
        'roles': [*ROLES, NO_ACCESS], 'backups': _backups(),
        'backup_directory': backup_tools.default_directory(), 'restore_word': RESTORE_WORD})


@login_required(login_url='/login/')
@require_POST
def team_role(request, pk):
    _require_admin(request.user)
    user = get_object_or_404(get_user_model(), pk=pk)
    role = request.POST.get('role')
    if not _can_edit(request.user, user):
        raise PermissionDenied("You can't change this account's role here.")
    if role not in ROLES and role != NO_ACCESS:
        messages.error(request, 'Choose a valid role.')
    elif _apply_role(request, user, role):
        messages.success(request, f'{user.email or user.username}: {role}.')
    return redirect('pandoraapp:settings')


@login_required(login_url='/login/')
@require_POST
def backup_now(request):
    _require_admin(request.user)
    try:
        result = backup_tools.run_backup(backup_tools.default_directory())
    except Exception as exc:
        messages.error(request, f'Backup failed ({type(exc).__name__}). Details are in backup-log.jsonl.')
    else:
        if result['status'] == 'skipped_busy':
            messages.error(request, 'A backup or restore is already running. Try again in a moment.')
        else:
            messages.success(request, f'Backup saved as {result["file"]}.')
    return redirect('pandoraapp:settings')


@login_required(login_url='/login/')
@require_POST
def restore(request):
    _require_admin(request.user)
    if not request.user.is_superuser:
        raise PermissionDenied('Only superusers can restore a backup.')
    directory = backup_tools.default_directory()
    # Only names from the backup list resolve, so no other file can be read.
    path = backup_tools.find_backup(directory, request.POST.get('backup', ''))
    if path is None:
        messages.error(request, 'Choose a backup from the list.')
    elif request.POST.get('confirm', '').strip() != RESTORE_WORD:
        messages.error(request, f'Type {RESTORE_WORD} to confirm. Nothing was changed.')
    else:
        try:
            result = backup_tools.restore_live(path, directory)
        except backup_tools.BackupBusy:
            messages.error(request, 'A backup or restore is already running. Nothing was changed.')
        except backup_tools.RestoreError as error:
            entry = error.entry
            if entry.get('rolled_back') is False:
                messages.error(request, 'Restore failed and putting the old data back also failed. Restore '
                               f'{entry["safety_backup"]} from this page or with manage.py restore_pandora.')
            else:
                messages.error(request, f'Restore failed ({entry.get("error_type")}). Your data was not changed.')
        else:
            messages.success(request, f'Restored {result["file"]}. The data from before is saved as '
                             f'{result["safety_backup"]}. You may need to sign in again.')
    return redirect('pandoraapp:settings')
