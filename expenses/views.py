import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services import ask_gemini, process_transaction


class TelegramWebhookView(APIView):
    """
    Handles incoming webhook requests from Telegram.
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

            # Process with Gemini
            gemini_response = ask_gemini(text)

            if gemini_response["type"] in ["expense", "income"]:
                # It's an expense or income, save to Notion
                result = process_transaction(gemini_response)

                if result["success"]:
                    type_label = "expense(s)" if gemini_response["type"] == "expense" else "income entry(s)"
                    reply_text = f"✅ Saved {result['count']} {type_label}.\n"
                    
                    for item in gemini_response["data"]:
                        name = item.get("item") or item.get("source")
                        reply_text += f"- {name} ({item.get('amount')})\n"
                    
                    # Add budget warnings if any
                    if result.get("budget_warnings"):
                        reply_text += "\n"
                        for warning in result["budget_warnings"]:
                            reply_text += f"{warning}\n"
                    
                    # Add checklist messages if any
                    if result.get("checklist_messages"):
                        reply_text += "\n"
                        for msg in result["checklist_messages"]:
                            reply_text += f"{msg}\n"
                else:
                    reply_text = f"❌ Failed to save: {result['message']}"

                self.send_telegram_message(chat_id, reply_text)

            elif gemini_response["type"] == "message":
                # It's just conversation
                self.send_telegram_message(chat_id, gemini_response["text"])

            else:
                # Error
                self.send_telegram_message(chat_id, gemini_response.get("text", "Unknown error"))

            return Response({"status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in webhook: {e}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def send_telegram_message(self, chat_id, text):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, json=payload)
