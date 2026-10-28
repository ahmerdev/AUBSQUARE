"""Module / action catalogue and the default roles."""

ACTIONS = [
    ("view", "View"), ("create", "Create"), ("edit", "Edit"), ("publish", "Publish"),
    ("delete", "Delete"), ("export", "Export"), ("approve", "Approve"), ("manage_settings", "Manage settings"),
]
ACTION_KEYS = [a for a, _ in ACTIONS]

# key -> label
MODULES = [
    ("dashboard", "Dashboard"),
    ("pages", "Website pages"),
    ("home", "Home page builder"),
    ("about", "About us"),
    ("services", "Services"),
    ("portfolio", "Portfolio"),
    ("case_studies", "Case studies"),
    ("blog", "Blog posts & comments"),
    ("taxonomy", "Categories & tags"),
    ("testimonials", "Testimonials & reviews"),
    ("faqs", "FAQs"),
    ("leads", "Contact messages & leads"),
    ("chatbot", "Chatbot & conversations"),
    ("email", "Email inbox & replies"),
    ("email_settings", "Email / SMTP settings"),
    ("media", "Media library"),
    ("seo", "SEO management"),
    ("campaigns", "Marketing campaigns"),
    ("ads", "Ads manager"),
    ("analytics", "Analytics & reports"),
    ("outbound", "Outbound sales (prospects & outreach)"),
    ("proposals", "Proposals"),
    ("invoices", "Invoices (create / issue / void)"),
    ("payments", "Payments, verification & refunds"),
    ("billing_reports", "Billing & collection reports"),
    ("billing_settings", "Company billing, bank details & gateways"),
    ("users", "Users & roles"),
    ("notifications", "Notifications"),
    ("settings", "General website settings"),
    ("security", "Security & activity logs"),
]
MODULE_KEYS = [k for k, _ in MODULES]
MODULE_LABELS = dict(MODULES)

ALL = ACTION_KEYS
CRUD = ["view", "create", "edit", "delete"]
CONTENT = ["view", "create", "edit", "publish", "delete", "export"]
VIEW = ["view"]

CONTENT_MODULES = ["pages", "home", "about", "services", "portfolio", "case_studies", "blog", "taxonomy", "testimonials", "faqs"]


def _all():
    return {m: list(ALL) for m in MODULE_KEYS}


DEFAULT_ROLES = {
    "super_admin": {
        "name": "Super Admin", "description": "Full control, including users, roles and approvals.",
        "permissions": _all(),
    },
    "administrator": {
        "name": "Administrator", "description": "Runs the site day to day. Cannot manage users or roles.",
        "permissions": {**{m: list(ALL) for m in MODULE_KEYS if m not in ("users",)}, "users": ["view"]},
    },
    "content_manager": {
        "name": "Content Manager", "description": "Creates and publishes website content.",
        "permissions": {**{m: list(CONTENT) for m in CONTENT_MODULES}, "dashboard": VIEW, "media": CONTENT, "notifications": VIEW, "leads": VIEW},
    },
    "seo_manager": {
        "name": "SEO Manager", "description": "Owns metadata, redirects and technical SEO.",
        "permissions": {**{m: ["view", "edit"] for m in CONTENT_MODULES}, "dashboard": VIEW, "seo": list(ALL), "media": ["view", "create", "edit"], "analytics": ["view", "export"], "notifications": VIEW},
    },
    "marketing_manager": {
        "name": "Marketing Manager", "description": "Campaigns, ads and marketing analytics.",
        "permissions": {"outbound": ["view", "create", "edit", "export"], "dashboard": VIEW, "campaigns": list(ALL), "ads": list(ALL), "analytics": ["view", "export"], "leads": ["view", "export"], "media": ["view", "create", "edit"], "blog": ["view", "create", "edit"], "notifications": VIEW, "seo": VIEW},
    },
    "sales_manager": {
        "name": "Sales / Lead Manager", "description": "Works the lead pipeline and replies to prospects.",
        "permissions": {"dashboard": VIEW, "outbound": list(ALL), "proposals": list(ALL), "invoices": ["view", "create", "edit"], "leads": list(ALL), "email": ["view", "create", "edit"], "chatbot": ["view", "edit"], "analytics": VIEW, "notifications": VIEW, "campaigns": VIEW},
    },
    "support_agent": {
        "name": "Support Agent", "description": "Answers chatbot conversations and lead replies.",
        "permissions": {"dashboard": VIEW, "chatbot": ["view", "edit"], "leads": ["view", "edit"], "email": ["view", "create"], "notifications": VIEW},
    },
    "analyst": {
        "name": "Analyst", "description": "Read-only access to reports and exports.",
        "permissions": {"outbound": ["view", "export"], "proposals": VIEW, "dashboard": VIEW, "analytics": ["view", "export"], "leads": ["view", "export"], "campaigns": ["view", "export"], "ads": VIEW, "seo": VIEW, "notifications": VIEW},
    },
    "read_only": {
        "name": "Read-only staff", "description": "Can look but not change anything.",
        "permissions": {m: VIEW for m in MODULE_KEYS if m not in ("users", "security", "email_settings", "settings", "billing_settings", "payments")},
    },
}
