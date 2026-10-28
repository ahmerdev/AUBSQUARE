from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.validators import RegexValidator
from django.shortcuts import redirect, render

from apps.core import fonts
from apps.core.models import SiteSettings
from apps.core.services import log_activity
from . import widgets as W
from .mixins import forbidden, needs

HEX = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a colour like #EC008C.")
PREVIEW_PAGES = [("Home", "/"), ("Services", "/services"), ("Portfolio", "/portfolio"), ("Case studies", "/case-studies"), ("Blog", "/blog"), ("About", "/about"), ("Contact", "/contact")]


class BrandingForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["logo_url", "favicon_url", "site_name", "tagline", "header_show_name", "heading_font", "body_font",
                  "primary_color", "secondary_color", "accent_color", "background_color"]
        widgets = {
            "logo_url": W.MediaPickerWidget(), "favicon_url": W.MediaPickerWidget(),
            "site_name": forms.TextInput(attrs={"class": "input", "maxlength": 80}), "tagline": forms.TextInput(attrs={"class": "input", "maxlength": 200}),
            "header_show_name": forms.CheckboxInput(attrs={"class": "check"}),
            "heading_font": W.FontPickerWidget(), "body_font": W.FontPickerWidget(),
            **{c: forms.TextInput(attrs={"type": "color", "class": "color"}) for c in ("primary_color", "secondary_color", "accent_color", "background_color")},
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for c in ("primary_color", "secondary_color", "accent_color", "background_color"):
            self.fields[c].validators.append(HEX)
        self.fields["logo_url"].help_text = "Shown in the website header and footer and on the dashboard sign-in page. PNG, WebP or JPG with a transparent background works best."
        self.fields["favicon_url"].help_text = "The small icon in the browser tab. Falls back to the logo if empty."
        self.fields["site_name"].help_text = "Used for the page title, the logo's accessible label and emails."


def default_preview_base():
    """Where the live preview should load the website from.

    Production / built site: Django serves it, so the preview uses the dashboard's own address (empty = same origin).
    Development without a built site: the React dev server (Vite, port 3000) – the address can still be changed on the page.
    Override with PREVIEW_SITE_URL in .env.
    """
    from pathlib import Path

    explicit = getattr(settings, "PREVIEW_SITE_URL", "")
    if explicit:
        return explicit
    if settings.DEBUG and not (Path(settings.FRONTEND_DIST) / "index.html").exists():
        return "http://localhost:3000"
    return ""


@needs("settings", "view")
def branding(request):
    s = SiteSettings.load()
    can_edit = request.user.can("settings", "edit")
    form = BrandingForm(request.POST or None, instance=s)
    if request.method == "POST":
        if not can_edit:
            return forbidden(request)
        if form.is_valid():
            form.save()
            log_activity(request.user, "branding.updated", s, ", ".join(sorted(form.changed_data)) or "no changes", request)
            messages.success(request, "Branding saved. The website and this dashboard now use it.")
            return redirect("dashboard:branding")
        messages.error(request, "Please fix the highlighted fields.")
    return render(request, "dashboard/branding.html", {
        "form": form, "s": s, "can_edit": can_edit, "fonts_data": fonts.picker_data(), "preview_base": default_preview_base(), "preview_pages": PREVIEW_PAGES,
        "page_title": "Branding & logo", "crumbs": [("Dashboard", "/dashboard/"), ("Branding & logo", "")],
    })
