from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):

    email = forms.CharField(
        required=True, widget=forms.TextInput(attrs={"placeholder": "name@example.com"})
    )

    accept_privacy = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        privacy_url = kwargs.pop("privacy_url", "")
        super().__init__(*args, **kwargs)
        self.fields["accept_privacy"].label = _(
            "I have read and accept the <a target='_blank' href='%(privacy_url)s'>privacy statement</a> from OpenPlan"
        ) % {"privacy_url": privacy_url}

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "username")


class CustomUserChangeForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "username")
