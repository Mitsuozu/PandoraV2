from django.apps import AppConfig


class PandoraappConfig(AppConfig):
    name = 'pandoraapp'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save
        post_save.connect(trust_admin_email, sender=get_user_model())


def trust_admin_email(sender, instance, update_fields=None, **kwargs):
    """Emails are typed in by admins, so record them as verified for Google/GitHub sign-in.

    Without this, allauth wipes the account's password on its first social sign-in, and an
    old email would keep working after an admin changes it.
    """
    if update_fields is not None and 'email' not in update_fields:
        return  # e.g. the last_login update on every sign-in
    from allauth.account.models import EmailAddress
    email = instance.email.strip().lower()
    stale = EmailAddress.objects.filter(user=instance)
    (stale.exclude(email__iexact=email) if email else stale).delete()
    if email:
        EmailAddress.objects.update_or_create(user=instance, email__iexact=email,
                                              defaults={'email': email, 'verified': True, 'primary': True})
