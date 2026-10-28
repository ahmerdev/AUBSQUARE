import uuid

from django.conf import settings
from django.db import models

from apps.core.crypto import decrypt, encrypt
from apps.core.models import SingletonModel, TimeStamped


def new_token():
    return uuid.uuid4().hex


class ChatbotSettings(SingletonModel, TimeStamped):
    PROVIDERS = [("none", "None – rule-based FAQ assistant"), ("openai", "OpenAI"), ("anthropic", "Anthropic"), ("openai_compatible", "OpenAI-compatible endpoint")]
    enabled = models.BooleanField(default=True)
    bot_name = models.CharField(max_length=60, default="AUB Assistant")
    welcome_message = models.TextField(default="Hi there! 👋 Welcome to AUB SQUARE. How can our creative directors help you elevate your brand today?")
    quick_replies = models.TextField(default="Our Services\nPrices & Packages\nHow Long Does a Logo Take?\nHow Do We Start?", help_text="One per line – suggested starter questions.")
    fallback_message = models.TextField(default="I'm not sure about that one. I can connect you with our team — would you like to request a quote or talk to a human?")
    privacy_notice = models.CharField(max_length=300, default="Chats are saved so our team can follow up. Please don't share passwords or payment details.")
    offline_message = models.CharField(max_length=300, default="Our team is offline right now. Leave your message and email and we'll reply soon.")
    human_handoff_enabled = models.BooleanField(default=True)
    handoff_message = models.CharField(max_length=300, default="Got it — I've alerted our team. A human will reply here shortly.")
    handoff_keywords = models.TextField(default="human\nagent\nperson\nreal person\nsupport\ntalk to someone", help_text="Words that trigger a hand-off to a human.")
    ask_contact_details = models.BooleanField("Ask visitors for name & email before handing off", default=True)

    ai_provider = models.CharField(max_length=20, choices=PROVIDERS, default="none")
    ai_api_key_enc = models.TextField(blank=True, editable=False)
    ai_model = models.CharField(max_length=80, blank=True, help_text="e.g. gpt-4o-mini or claude-3-5-haiku-latest")
    ai_base_url = models.URLField(blank=True, help_text="Only for OpenAI-compatible endpoints.")
    ai_extra_instructions = models.TextField(blank=True)
    last_ai_error = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Chatbot settings"

    def __str__(self):
        return "Chatbot settings"

    def set_api_key(self, raw):
        self.ai_api_key_enc = encrypt(raw)

    def get_api_key(self):
        return decrypt(self.ai_api_key_enc)

    @property
    def ai_active(self) -> bool:
        return self.ai_provider != "none" and bool(self.ai_api_key_enc) and bool(self.ai_model)

    def quick_reply_list(self):
        return [q.strip() for q in self.quick_replies.splitlines() if q.strip()]

    def handoff_words(self):
        return [w.strip().lower() for w in self.handoff_keywords.splitlines() if w.strip()]


class KnowledgeEntry(TimeStamped):
    question = models.CharField(max_length=300)
    keywords = models.CharField(max_length=300, blank=True, help_text="Comma separated words that should trigger this answer.")
    answer = models.TextField()
    link_label = models.CharField(max_length=80, blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    suggest_quote = models.BooleanField("Offer a quote button with this answer", default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "knowledge entries"

    def __str__(self):
        return self.question[:80]


class Conversation(TimeStamped):
    BOT, WAITING, ACTIVE, CLOSED = "bot", "waiting", "active", "closed"
    STATUS = [(BOT, "Bot"), (WAITING, "Waiting for agent"), (ACTIVE, "With agent"), (CLOSED, "Closed")]
    token = models.CharField(max_length=40, unique=True, default=new_token)
    status = models.CharField(max_length=8, choices=STATUS, default=BOT, db_index=True)
    visitor_name = models.CharField(max_length=100, blank=True)
    visitor_email = models.EmailField(blank=True)
    visitor_phone = models.CharField(max_length=40, blank=True)
    page_url = models.CharField(max_length=300, blank=True)
    visitor_hash = models.CharField(max_length=32, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    unread_for_agent = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_message_preview = models.CharField(max_length=140, blank=True)
    privacy_acknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Chat #{self.pk} · {self.visitor_name or 'Visitor'}"


class ChatMessage(models.Model):
    VISITOR, BOT, AGENT, SYSTEM = "visitor", "bot", "agent", "system"
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=8, choices=[(VISITOR, "Visitor"), (BOT, "Bot"), (AGENT, "Agent"), (SYSTEM, "System")])
    body = models.TextField(max_length=4000)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    meta = models.JSONField(default=dict, blank=True)  # {action:'quote'|'whatsapp', links:[{label,url}], ai:bool}
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]
