from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError

from apps.core.sanitize import clean_plain

User = get_user_model()
INPUT = {"class": "input"}


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={**INPUT, "autocomplete": "username", "placeholder": "you@aubsquare.com", "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "current-password", "placeholder": "Password"}))


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={**INPUT, "placeholder": "Full name", "autocomplete": "name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={**INPUT, "placeholder": "Work email", "autocomplete": "email"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password", "placeholder": "Password"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password", "placeholder": "Confirm password"}))
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off", "class": "hp"}))  # honeypot

    def clean_full_name(self):
        return clean_plain(self.cleaned_data["full_name"], 120)

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise ValidationError("Request rejected.")
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        if data.get("password1"):
            try:
                password_validation.validate_password(data["password1"])
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class InviteAcceptForm(forms.Form):
    full_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={**INPUT, "placeholder": "Full name"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password"}))

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        elif data.get("password1"):
            try:
                password_validation.validate_password(data["password1"])
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "job_title", "phone", "avatar_url", "notify_email"]
        widgets = {"full_name": forms.TextInput(attrs=INPUT), "job_title": forms.TextInput(attrs=INPUT), "phone": forms.TextInput(attrs=INPUT), "avatar_url": forms.TextInput(attrs=INPUT)}


class StyledPasswordChange(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "current-password"}))
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password"}))
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "new-password"}))

    def __init__(self, user, *a, **kw):
        super().__init__(*a, **kw)
        self.user = user

    def clean_old_password(self):
        if not self.user.check_password(self.cleaned_data["old_password"]):
            raise ValidationError("Your current password is incorrect.")
        return self.cleaned_data["old_password"]

    def clean(self):
        data = super().clean()
        if data.get("new_password1") != data.get("new_password2"):
            self.add_error("new_password2", "Passwords do not match.")
        elif data.get("new_password1"):
            try:
                password_validation.validate_password(data["new_password1"], self.user)
            except ValidationError as exc:
                self.add_error("new_password1", exc)
        return data

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save(update_fields=["password"])
        return self.user


class QueuedPasswordResetForm(PasswordResetForm):
    """Sends reset links through the outbox. The view never reveals whether the email exists."""

    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={**INPUT, "autocomplete": "email", "placeholder": "you@aubsquare.com"}))

    def get_users(self, email):
        return (u for u in User.objects.filter(email__iexact=email, is_active=True, status=User.APPROVED) if u.has_usable_password())

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        from django.template import loader
        from apps.mailer.service import queue_email

        subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        body = loader.render_to_string(email_template_name, context)
        queue_email(to=[to_email], subject=subject, body_text=body, kind="account")


class StyledSetPassword(SetPasswordForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.widget.attrs.update(INPUT)
