from django.conf import settings
from django.db import models

from apps.core.crypto import decrypt, encrypt
from apps.core.models import SingletonModel, TimeStamped

PROVIDER_PRESETS = {
    "gmail": {"label": "Gmail (personal)", "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_security": "tls",
              "imap_host": "imap.gmail.com", "imap_port": 993, "imap_security": "ssl",
              "note": "Use a Google 'App password' (2-Step Verification must be on). Your normal password will not work."},
    "google_workspace": {"label": "Google Workspace", "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_security": "tls",
                         "imap_host": "imap.gmail.com", "imap_port": 993, "imap_security": "ssl",
                         "note": "Use an App password, or an SMTP relay configured by your Workspace admin."},
    "outlook": {"label": "Outlook / Hotmail", "smtp_host": "smtp-mail.outlook.com", "smtp_port": 587, "smtp_security": "tls",
                "imap_host": "outlook.office365.com", "imap_port": 993, "imap_security": "ssl",
                "note": "Microsoft has been retiring basic-auth SMTP for personal accounts; an app password may be required."},
    "microsoft365": {"label": "Microsoft 365", "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_security": "tls",
                     "imap_host": "outlook.office365.com", "imap_port": 993, "imap_security": "ssl",
                     "note": "SMTP AUTH must be enabled for the mailbox by your tenant admin. Tenants that enforce OAuth-only need a relay or provider API."},
    "custom": {"label": "Custom SMTP", "smtp_host": "", "smtp_port": 587, "smtp_security": "tls",
               "imap_host": "", "imap_port": 993, "imap_security": "ssl", "note": "Enter the values supplied by your email provider."},
}


class EmailSettings(SingletonModel, TimeStamped):
    SECURITY = [("tls", "STARTTLS (usually port 587)"), ("ssl", "SSL/TLS (usually port 465)"), ("none", "None (not recommended)")]
    provider = models.CharField(max_length=20, default="custom", choices=[(k, v["label"]) for k, v in PROVIDER_PRESETS.items()])
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_security = models.CharField(max_length=5, choices=SECURITY, default="tls")
    smtp_username = models.CharField(max_length=200, blank=True)
    smtp_password_enc = models.TextField(blank=True, editable=False)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=100, default="AUB SQUARE")
    reply_to = models.EmailField(blank=True)
    notification_recipients = models.TextField(blank=True, help_text="One email per line. Receives new-lead, chat and comment alerts.")

    notify_new_lead = models.BooleanField(default=True)
    notify_new_chat = models.BooleanField(default=True)
    notify_new_comment = models.BooleanField(default=True)
    notify_new_staff = models.BooleanField(default=True)
    notify_marketing_lead = models.BooleanField(default=True)
    notify_system = models.BooleanField(default=True)

    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_ok = models.BooleanField(null=True)
    last_test_message = models.CharField(max_length=300, blank=True)

    # inbound (IMAP) – separate from SMTP, which can only send
    imap_enabled = models.BooleanField(default=False)
    imap_host = models.CharField(max_length=200, blank=True)
    imap_port = models.PositiveIntegerField(default=993)
    imap_security = models.CharField(max_length=8, default="ssl", choices=[("ssl", "SSL/TLS (993)"), ("starttls", "STARTTLS (143)"), ("none", "None")])
    imap_username = models.CharField(max_length=200, blank=True)
    imap_password_enc = models.TextField(blank=True, editable=False)
    imap_folder = models.CharField(max_length=100, default="INBOX")
    imap_last_uid = models.PositiveBigIntegerField(default=0)
    imap_uidvalidity = models.CharField(max_length=40, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_ok = models.BooleanField(null=True)
    last_sync_message = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Email settings"

    def __str__(self):
        return "Email settings"

    # credentials never leave the server in plaintext API/HTML responses
    def set_smtp_password(self, raw):
        self.smtp_password_enc = encrypt(raw)

    def get_smtp_password(self):
        return decrypt(self.smtp_password_enc)

    def set_imap_password(self, raw):
        self.imap_password_enc = encrypt(raw)

    def get_imap_password(self):
        return decrypt(self.imap_password_enc)

    @property
    def has_smtp_password(self):
        return bool(self.smtp_password_enc)

    @property
    def has_imap_password(self):
        return bool(self.imap_password_enc)

    @property
    def effective_from_email(self):
        """The From address; if it was left blank and the SMTP username is an e-mail address (Gmail style), that is used."""
        if self.from_email:
            return self.from_email
        return self.smtp_username if "@" in (self.smtp_username or "") else ""

    @property
    def effective_username(self):
        """Gmail/Outlook need a login. If the username was left blank but a password is saved, log in with the From address."""
        if self.smtp_username:
            return self.smtp_username
        return self.effective_from_email if self.smtp_password_enc else ""

    @property
    def smtp_configured(self):
        return bool(self.smtp_host and self.effective_from_email)

    @property
    def imap_configured(self):
        return bool(self.imap_enabled and self.imap_host and self.imap_username and self.imap_password_enc)

    def recipients(self):
        return [e.strip() for e in self.notification_recipients.replace(",", "\n").splitlines() if e.strip()]


class EmailThread(TimeStamped):
    subject = models.CharField(max_length=300)
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="threads")
    participant = models.EmailField(blank=True)
    last_message_at = models.DateTimeField(auto_now_add=True, db_index=True)
    has_unread = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return self.subject


class EmailMessage(models.Model):
    IN, OUT = "in", "out"
    QUEUED, SENDING, SENT, FAILED, RECEIVED = "queued", "sending", "sent", "failed", "received"
    STATUS = [(QUEUED, "Queued"), (SENDING, "Sending"), (SENT, "Sent"), (FAILED, "Failed"), (RECEIVED, "Received")]
    KINDS = [("notification", "Notification"), ("reply", "Reply"), ("test", "Test"), ("account", "Account"), ("marketing", "Marketing"),
             ("system", "System"), ("inbound", "Inbound"), ("outbound", "Outbound sales")]
    thread = models.ForeignKey(EmailThread, null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    direction = models.CharField(max_length=3, default=OUT, choices=[(IN, "Inbound"), (OUT, "Outbound")], db_index=True)
    kind = models.CharField(max_length=14, choices=KINDS, default="system")
    status = models.CharField(max_length=10, choices=STATUS, default=QUEUED, db_index=True)
    message_id = models.CharField(max_length=300, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=300, blank=True)
    references = models.TextField(blank=True)
    from_email = models.CharField(max_length=300, blank=True)
    from_name = models.CharField(max_length=200, blank=True)
    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=300)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    attachments_info = models.JSONField(default=list, blank=True)
    attachment_refs = models.JSONField(default=list, blank=True)
    extra_headers = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    imap_uid = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["message_id"], condition=models.Q(direction="in") & ~models.Q(message_id=""), name="uniq_inbound_message_id"),
        ]

    def __str__(self):
        return f"{self.get_direction_display()}: {self.subject[:60]}"
