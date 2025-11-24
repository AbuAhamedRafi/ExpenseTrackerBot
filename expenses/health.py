"""
Health check endpoint for keeping the service alive and monitoring uptime.
"""

from django.http import JsonResponse
from django.views import View
from django.utils import timezone


class HealthCheckView(View):
    """
    Simple health check endpoint that returns 200 OK.
    Used by monitoring services to keep the application alive on free hosting tiers.
    """

    def get(self, request):
        """Handle GET requests to health endpoint."""
        return JsonResponse(
            {
                "status": "ok",
                "timestamp": timezone.now().isoformat(),
                "service": "ExpenseTrackerBot",
            }
        )

    def head(self, request):
        """Handle HEAD requests to health endpoint."""
        return JsonResponse({"status": "ok"})
