from django import forms
from django.db import models
from django.forms import modelform_factory

from . import widgets as W

MEDIA_HINT = ("image", "thumbnail", "photo", "avatar", "logo", "favicon", "icon_url")
SECRET_FIELDS = {
    "chatbotsettings": [("ai_api_key", "set_api_key", "ai_api_key_enc", "AI provider API key")],
}


def _style(field):
    w = field.widget
    cls = w.attrs.get("class", "")
    if isinstance(w, (forms.CheckboxInput,)):
        w.attrs["class"] = (cls + " check").strip()
    elif isinstance(w, forms.CheckboxSelectMultiple):
        pass
    elif isinstance(w, (W.MediaPickerWidget, W.RepeaterWidget, W.RichTextWidget, forms.HiddenInput)):
        pass
    elif isinstance(w, forms.SelectMultiple):
        w.attrs["class"] = (cls + " input multi").strip()
        w.attrs.setdefault("size", 6)
    else:
        w.attrs["class"] = (cls + " input").strip()
    return field


class DashboardFormMixin:
    """Common behaviour: status/permission guard, styled widgets, secret fields."""

    module = None
    user = None

    def clean(self):
        data = super().clean()
        status = data.get("status")
        if status in ("published", "scheduled") and self.user is not None and not self.user.can(self.module.perm, "publish"):
            was = getattr(self.instance, "status", None)
            if was != status:
                self.add_error("status", "You don't have permission to publish. Save as Draft or In review instead.")
        if status == "scheduled" and not data.get("publish_at"):
            self.add_error("publish_at", "Choose when this should go live.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        for fname, setter, _, _ in SECRET_FIELDS.get(self._meta.model._meta.model_name, []):
            val = self.cleaned_data.get(fname)
            if self.cleaned_data.get(fname + "_clear"):
                getattr(obj, setter)("")
            elif val:
                getattr(obj, setter)(val)
        if commit:
            obj.save()
            self._save_m2m()
        return obj


def make_form(module, user=None):
    Model = module.Model
    types = module.types

    def callback(db_field, **kw):
        name = db_field.name
        t = types.get(name)
        if isinstance(db_field, models.ManyToManyField) or isinstance(db_field, models.ForeignKey):
            if name == "author":
                from django.contrib.auth import get_user_model

                kw["queryset"] = get_user_model().objects.filter(status="approved")
            ff = db_field.formfield(**kw)
            if ff is not None:
                ff.label_from_instance = lambda obj: str(obj)
            return _style(ff) if ff else ff
        if isinstance(db_field, models.JSONField):
            if t == "lines":
                return _style(W.LinesField(required=False, label=db_field.verbose_name.capitalize(), help_text=db_field.help_text or "One item per line."))
            if isinstance(t, tuple) and t[0] == "repeater":
                return W.RepeaterField(t[1], required=False, label=db_field.verbose_name.capitalize(), help_text=db_field.help_text)
            return _style(W.JSONTextField(label=db_field.verbose_name.capitalize(), help_text=db_field.help_text))
        ff = db_field.formfield(**kw)
        if ff is None:
            return None
        if t == "media" or (isinstance(db_field, models.CharField) and t is None and any(h in name for h in MEDIA_HINT) and "alt" not in name and name != "icon_name"):
            ff.widget = W.MediaPickerWidget()
            return ff
        if t == "rich":
            ff.widget = W.RichTextWidget()
            return ff
        if isinstance(t, str) and t.startswith("textarea"):
            rows = int(t.split(":")[1]) if ":" in t else 4
            ff.widget = forms.Textarea(attrs={"rows": rows})
        if isinstance(ff.widget, forms.DateTimeInput) or isinstance(db_field, models.DateTimeField):
            ff.widget = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
            ff.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        elif isinstance(db_field, models.DateField):
            ff.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        if db_field.name in ("primary_color", "secondary_color", "accent_color", "background_color"):
            ff.widget = forms.TextInput(attrs={"type": "color", "class": "color"})
            return ff
        return _style(ff)

    base = type("Form", (DashboardFormMixin, forms.ModelForm), {})
    form_cls = modelform_factory(Model, form=base, fields=[f for f in module.form_fields if f not in {x[0] for x in SECRET_FIELDS.get(Model._meta.model_name, [])}], formfield_callback=callback)

    # extra, non-model "secret" inputs (e.g. API keys): write-only, never echoed back
    extras = {}
    for fname, _, has_attr, label in SECRET_FIELDS.get(Model._meta.model_name, []):
        extras[fname] = forms.CharField(required=False, label=label, widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password", "placeholder": "Leave blank to keep the saved key"}, render_value=False))
        extras[fname + "_clear"] = forms.BooleanField(required=False, label="Remove the saved key", widget=forms.CheckboxInput(attrs={"class": "check"}))
    form_cls = type("DashboardForm", (form_cls,), {**extras, "module": module, "user": user})

    # keep the declared fieldset ordering for rendering
    return form_cls


def bound_fieldsets(form, module):
    out = []
    for title, names in module.fieldsets:
        fields = []
        for n in names:
            if n in form.fields:
                fields.append(form[n])
            if n + "_clear" in form.fields:
                fields.append(form[n + "_clear"])
        # secret fields declared on the module
        for n in names:
            pass
        if fields:
            out.append((title, fields))
    return out
