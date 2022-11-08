from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.db.models import EmailField


class CustomUser(AbstractUser):
    email = EmailField(
        _("email address"),
        blank=False,
        error_messages={"unique": _("A user with that email already exists.")},
        null=False,
        unique=True,
    )
