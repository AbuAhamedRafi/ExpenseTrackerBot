from django.db import models


class TelegramLog(models.Model):
    user_id = models.CharField(max_length=100)
    role = models.CharField(
        max_length=10, choices=[("user", "User"), ("model", "Model")]
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.user_id} - {self.role} - {self.timestamp}"
