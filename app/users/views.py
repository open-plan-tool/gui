from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetView
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from projects.services import send_email as send_email_exchange
from .forms import CustomUserCreationForm, CustomUserChangeForm

DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL
EMAIL_HOST = settings.EMAIL_HOST
UserModel = get_user_model()


def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            current_site = get_current_site(request)
            subject = _("Activate your account.")
            protocol = "https" if settings.DEBUG is False else request.scheme
            message = render_to_string(
                "registration/acc_active_email.html",
                {
                    "user": user,
                    "domain": current_site.domain,
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": default_token_generator.make_token(user),
                    "protocol": protocol,
                },
            )
            to_email = form.cleaned_data.get("email")
            send_email_exchange(to_email=to_email, subject=subject, message=message)
            messages.info(
                request,
                _(
                    "Please confirm your email address to complete the registration  (note that the registration email may land in your spam box, if your email provider does not trust our domain name, we have unfortunately no control on our users' email provider)"
                ),
            )
            return redirect("home")
    else:
        form = CustomUserCreationForm(privacy_url=reverse("privacy"))
    return render(request, "registration/signup.html", {"form": form})


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = UserModel._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(
            request,
            _(
                "Thank you for your email confirmation. Now you can log in your account."
            ),
        )
        return redirect("login")
    else:
        return HttpResponse("Activation link is invalid!")
        return redirect("home")


@login_required
@require_http_methods(["GET", "POST"])
def user_info(request):
    if request.method == "POST":
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(request, _("User info successfully updated!"))
            return redirect("user_info")
        else:
            messages.error(request, _("Please check errors and resubmit!"))
    else:
        form = CustomUserChangeForm(instance=request.user)
    return render(request, "registration/user_info.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, _("Your password was successfully updated!"))
            return redirect("change_password")
        else:
            messages.error(request, _("Please check errors and resubmit!"))
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "registration/change_password.html", {"form": form})


class ExchangePasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        """
        Send a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        # Force the https for the production
        if settings.DEBUG is False:
            context["protocol"] = "https"
        message = render_to_string(email_template_name, context)
        send_email_exchange(to_email=to_email, subject=subject, message=message)


class ExchangePasswordResetView(PasswordResetView):
    form_class = ExchangePasswordResetForm


@login_required
@require_http_methods(["POST"])
def user_deletion_request(request):
    user_pk = request.user.pk
    logout(request)
    user_model = get_user_model()
    user_model.objects.filter(pk=user_pk).delete()
    messages.info(request, _("Your user account has been deleted."))
    return redirect("home")
