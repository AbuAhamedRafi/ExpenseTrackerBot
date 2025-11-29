from django.db import models


class TelegramLog(models.Model):
    user_id = models.CharField(max_length=100)
    role = models.CharField(max_length=10)  # 'user' or 'model'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True)  # Store tool outputs/context

    def __str__(self):
        return f"{self.user_id} - {self.role} - {self.timestamp}"


class PendingConfirmation(models.Model):
    user_id = models.CharField(max_length=100, unique=True)
    operation_data = models.JSONField()
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Confirmation for {self.user_id} expires {self.expires_at}"
