"""Form widgets/fields used by the dashboard: media picker, rich text, line list, structured repeater."""
import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape


class MediaPickerWidget(forms.TextInput):
    template_name = "dashboard/widgets/media_picker.html"

    def __init__(self, attrs=None, kind="image"):
        super().__init__(attrs)
        self.kind = kind

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["kind"] = self.kind
        return ctx


class FontPickerWidget(forms.TextInput):
    """Searchable Google Fonts picker (the list is built in the browser from the whitelist in apps.core.fonts)."""
    template_name = "dashboard/widgets/font_picker.html"
    input_type = "hidden"


class RichTextWidget(forms.Textarea):
    template_name = "dashboard/widgets/richtext.html"


class LinesField(forms.Field):
    """JSON list of strings <-> one item per line."""

    widget = forms.Textarea(attrs={"rows": 5, "class": "input", "placeholder": "One item per line"})

    def prepare_value(self, value):
        if isinstance(value, list):
            return "\n".join(str(v) for v in value)
        return value or ""

    def to_python(self, value):
        if isinstance(value, list):
            return value
        return [ln.strip() for ln in (value or "").splitlines() if ln.strip()]

    def has_changed(self, initial, data):
        return self.to_python(initial or []) != self.to_python(data)


class RepeaterWidget(forms.Widget):
    template_name = "dashboard/widgets/repeater.html"

    def __init__(self, spec, attrs=None, add_label="Add item"):
        super().__init__(attrs)
        self.spec = spec  # [(key, label, 'text'|'textarea'|'number')]
        self.add_label = add_label

    def format_value(self, value):
        if isinstance(value, str):
            return value
        return json.dumps(value or [])

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["spec_json"] = json.dumps([{"key": k, "label": l, "type": t} for k, l, t in self.spec])
        ctx["widget"]["add_label"] = self.add_label
        return ctx


class RepeaterField(forms.Field):
    """JSON list of flat dicts, edited as repeatable rows."""

    def __init__(self, spec, add_label="Add item", **kw):
        self.spec = spec
        kw.setdefault("widget", RepeaterWidget(spec, add_label=add_label))
        super().__init__(**kw)

    def prepare_value(self, value):
        return value if isinstance(value, str) else json.dumps(value or [])

    def to_python(self, value):
        if value in (None, ""):
            return []
        if isinstance(value, list):
            data = value
        else:
            try:
                data = json.loads(value)
            except ValueError:
                raise ValidationError("Invalid data submitted.")
        if not isinstance(data, list):
            raise ValidationError("Invalid data submitted.")
        keys = [k for k, _, _ in self.spec]
        out = []
        for row in data:
            if not isinstance(row, dict):
                continue
            clean = {k: str(row.get(k, "")).strip()[:2000] for k in keys}
            if any(clean.values()):
                out.append(clean)
        return out

    def has_changed(self, initial, data):
        try:
            return self.to_python(initial) != self.to_python(data)
        except ValidationError:
            return True


class JSONTextField(forms.Field):
    widget = forms.Textarea(attrs={"rows": 6, "class": "input mono", "spellcheck": "false"})

    def __init__(self, *a, **kw):
        kw.setdefault("required", False)
        super().__init__(*a, **kw)

    def prepare_value(self, value):
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2) if value not in (None, "", [], {}) else ""

    def to_python(self, value):
        if value in (None, ""):
            return None
        try:
            return json.loads(value) if isinstance(value, str) else value
        except ValueError as exc:
            raise ValidationError(f"Invalid JSON: {exc}")

    def has_changed(self, initial, data):
        try:
            return self.to_python(initial if not isinstance(initial, str) else initial) != self.to_python(data)
        except ValidationError:
            return True
