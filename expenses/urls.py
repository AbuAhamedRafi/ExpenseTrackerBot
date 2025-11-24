from django.urls import path
from .views import TelegramWebhookView
from .health import HealthCheckView

urlpatterns = [
    path("webhook/", TelegramWebhookView.as_view(), name="telegram_webhook"),
    path("health/", HealthCheckView.as_view(), name="health_check"),
]
