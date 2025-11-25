import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services import ask_gemini, execute_function_calls
from .models import TelegramLog


class TelegramWebhookView(APIView):
    """
    Handles incoming webhook requests from Telegram using Gemini autonomous operations.
    """

    def post(self, request, *args, **kwargs):
        try:
            data = request.data

            # Basic validation of Telegram update structure
            if "message" not in data:
                return Response({"status": "ignored"}, status=status.HTTP_200_OK)

            message = data["message"]
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            user_id = message.get("from", {}).get("id")

            # Security: Whitelist check
            allowed_user_id = os.getenv("ALLOWED_USER_ID")
            if allowed_user_id and str(user_id) != str(allowed_user_id):
                self.send_telegram_message(
                    chat_id, "Sorry, you are not authorized to use this bot."
                )
                return Response({"status": "unauthorized"}, status=status.HTTP_200_OK)

            if not text:
                return Response({"status": "no_text"}, status=status.HTTP_200_OK)

            # Check for reply context
            reply_to = message.get("reply_to_message", {})
            reply_text = reply_to.get("text", "")

            if reply_text:
                # Append reply context to the text
                text = f"{text}\n\n[Context - User replied to]: {reply_text}"

            # Save user message to log
            TelegramLog.objects.create(user_id=str(user_id), role="user", content=text)

            # Check for explicit confirmation override
            if text.lower().strip() in ["yes", "y", "confirm", "sure", "ok", "do it"]:
                from .models import PendingConfirmation
                from .autonomous import SmartExecutor

                try:
                    pending_obj = PendingConfirmation.objects.get(user_id=str(user_id))

                    # Check expiry (optional, but good practice)
                    from datetime import datetime

                    # Use naive comparison if project is naive, or aware if aware.
                    # Using timestamp comparison to be safe and consistent with autonomous.py
                    if datetime.now().timestamp() > pending_obj.expires_at.timestamp():
                        pending_obj.delete()
                        raise PendingConfirmation.DoesNotExist

                    # Execute
                    result = SmartExecutor.execute(pending_obj.operation_data)
                    pending_obj.delete()

                    # Wrap in the format expected by the response handler
                    execution_results = [
                        {"function": "autonomous_operation", "result": result}
                    ]

                    # Process results directly
                    self._handle_execution_results(chat_id, user_id, execution_results)
                    return Response({"status": "success"}, status=status.HTTP_200_OK)

                except PendingConfirmation.DoesNotExist:
                    pass  # Fall through to Gemini

            # Process with Gemini
            gemini_response = ask_gemini(text, user_id=str(user_id))

            # Extract natural message and function calls
            natural_message = gemini_response.get("message", "")
            function_calls = gemini_response.get("function_calls")

            # Always send Gemini's natural response first
            if natural_message:
                self.send_telegram_message(chat_id, natural_message)
                # Save model response to log
                TelegramLog.objects.create(
                    user_id=str(user_id), role="model", content=natural_message
                )

            # If no function calls, we're done (pure conversation)
            if not function_calls:
                return Response({"status": "success"}, status=status.HTTP_200_OK)

            # Execute function calls (pass user_id for confirmations)
            execution_results = execute_function_calls(
                function_calls, user_id=str(user_id)
            )

            # Process results
            self._handle_execution_results(chat_id, user_id, execution_results)

            return Response({"status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in webhook: {e}")
            import traceback

            traceback.print_exc()
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_execution_results(self, chat_id, user_id, execution_results):
        """Process execution results and send messages."""
        from .models import TelegramLog

        for exec_result in execution_results:
            func_name = exec_result["function"]
            result = exec_result["result"]

            if func_name == "autonomous_operation":
                # Handle autonomous operation results
                if result.get("requires_confirmation"):
                    # Operation needs confirmation
                    reply_text = f"⚠️ {result.get('message', 'Confirm this action')}"
                    if result.get("operation_details"):
                        reply_text += f"\n\n{result['operation_details']}"
                    self.send_telegram_message(chat_id, reply_text)

                    # Log the confirmation request
                    TelegramLog.objects.create(
                        user_id=str(user_id), role="model", content=reply_text
                    )

                elif result.get("success"):
                    # Operation succeeded
                    message = result.get("message", "Done!")
                    data = result.get("data")

                    # Format response based on data
                    if data:
                        if isinstance(data, list):
                            # Query results
                            if len(data) == 0:
                                reply_text = f"✅ {message}\n\nNo results found."
                            else:
                                reply_text = (
                                    f"✅ {message}\n\nFound {len(data)} result(s):\n"
                                )
                                for i, item in enumerate(data[:10], 1):  # Limit to 10
                                    # Format each item
                                    name = item.get("Name", "Unknown")
                                    amount = item.get("Amount")
                                    date = item.get("Date", "")

                                    if amount is not None:
                                        reply_text += f"{i}. {name}: ${amount:.2f}"
                                    else:
                                        reply_text += f"{i}. {name}"

                                    if date:
                                        reply_text += f" ({date[:10]})"
                                    reply_text += "\n"

                                if len(data) > 10:
                                    reply_text += f"\n... and {len(data) - 10} more"

                        elif isinstance(data, dict):
                            # Single result or analytics
                            reply_text = f"✅ {message}\n\n"
                            for key, value in data.items():
                                if isinstance(value, (int, float)):
                                    reply_text += f"{key}: ${value:.2f}\n"
                                else:
                                    reply_text += f"{key}: {value}\n"
                        else:
                            reply_text = f"✅ {message}"
                    else:
                        reply_text = f"✅ {message}"

                    self.send_telegram_message(chat_id, reply_text)

                    # Log the success message AND metadata (tool output)
                    TelegramLog.objects.create(
                        user_id=str(user_id),
                        role="model",
                        content=reply_text,
                        metadata=data,  # Store the raw data (including IDs) for context
                    )

                else:
                    # Operation failed
                    error_msg = result.get("message", "Something went wrong")
                    reply_text = f"❌ {error_msg}"

                    if result.get("retry_suggested"):
                        reply_text += "\n\nI'll try to fix this..."

                    self.send_telegram_message(chat_id, reply_text)

                    # Log the error message
                    TelegramLog.objects.create(
                        user_id=str(user_id), role="model", content=reply_text
                    )

    def send_telegram_message(self, chat_id, text):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
