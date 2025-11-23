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

            # Extract natural message and action
            natural_message = gemini_response.get("message", "")
            action = gemini_response.get("action")

            # If no action, just send the conversational response
            if not action:
                self.send_telegram_message(chat_id, natural_message)
                return Response({"status": "success"}, status=status.HTTP_200_OK)

            # Process the action
            action_type = action.get("type")

            if action_type == "summary":
                # Send Gemini's initial message
                self.send_telegram_message(chat_id, natural_message)

                # Fetch and send summary data
                result = process_transaction(action)
                if result["success"]:
                    summary = result["data"]
                    reply_text = f"\n📊 *{summary['month']} Summary*\n\n"
                    reply_text += f"💰 Income: ${summary['total_income']:.2f}\n"
                    reply_text += f"💸 Spent: ${summary['total_spent']:.2f}\n"
                    reply_text += f"💵 Remaining: ${summary['remaining']:.2f}\n"

                    if summary["categories"]:
                        reply_text += "\n*By Category:*\n"
                        for cat in summary["categories"]:
                            budget_info = ""
                            if cat["budget"]:
                                remaining = cat["budget"] - cat["spent"]
                                percentage = (cat["spent"] / cat["budget"]) * 100
                                if percentage > 100:
                                    budget_info = f" ⚠️ ${abs(remaining):.2f} over"
                                elif percentage >= 90:
                                    budget_info = f" ⚠️ ${remaining:.2f} left"
                                else:
                                    budget_info = f" ✓ ${remaining:.2f} left"
                            reply_text += (
                                f"• {cat['name']}: ${cat['spent']:.2f}{budget_info}\n"
                            )
                else:
                    reply_text = "\n❌ Couldn't fetch the data right now."

                self.send_telegram_message(chat_id, reply_text)

            elif action_type == "budget_check":
                # Send Gemini's initial message
                self.send_telegram_message(chat_id, natural_message)

                # Fetch and send budget check
                result = process_transaction(action)
                if result["success"]:
                    check = result["data"]
                    reply_text = f"\n*{check.get('category', 'Category')} Budget*\n"

                    if check["status"] == "no_budget":
                        reply_text += (
                            f"No budget set.\nCurrent: ${check['current_spent']:.2f}\n"
                        )
                        reply_text += f"After: ${check['projected_spent']:.2f}"
                    elif check["status"] != "unknown":
                        reply_text += f"Current: ${check['current_spent']:.2f} / ${check['budget']:.2f}\n"
                        reply_text += (
                            f"After expense: ${check['projected_spent']:.2f}\n"
                        )
                        reply_text += f"Remaining: ${check['remaining']:.2f} ({check['percentage']:.0f}% used)\n\n"

                        # Natural status message
                        if check["status"] == "safe":
                            reply_text += "✅ You're good to go!"
                        elif check["status"] == "approaching_limit":
                            reply_text += "⚠️ Getting close to your limit."
                        elif check["status"] == "close_to_limit":
                            reply_text += "⚠️ Very close to budget limit!"
                        else:
                            reply_text += "🚫 This would put you over budget."
                else:
                    reply_text = (
                        f"\n❌ {result.get('message', 'Error checking budget')}"
                    )

                self.send_telegram_message(chat_id, reply_text)

            elif action_type in ["expense", "income"]:
                # Process transaction
                result = process_transaction(action)

                if result["success"]:
                    # Build success response
                    reply_text = natural_message

                    # Add details for partial success
                    if result.get("partial_success"):
                        reply_text += f"\n\n⚠️ Saved {result['count']} of {result['total_attempted']}:\n"
                        for item in result["saved_items"]:
                            reply_text += f"✅ {item['name']} (${item['amount']})\n"

                        reply_text += f"\n❌ Failed {result['failed_count']}:\n"
                        for failure in result["failures"]:
                            reply_text += f"• {failure['name']}: {failure['reason']}\n"

                    # Add budget warnings
                    if result.get("budget_warnings"):
                        reply_text += "\n\n⚠️ Budget alerts:\n"
                        for warning in result["budget_warnings"]:
                            reply_text += f"{warning}\n"

                    # Add checklist updates
                    if result.get("checklist_messages"):
                        reply_text += "\n✓ "
                        reply_text += "\n✓ ".join(result["checklist_messages"])
                else:
                    reply_text = f"❌ Couldn't save: {result['message']}"

                self.send_telegram_message(chat_id, reply_text)

            else:
                # Unknown action type, send natural message
                self.send_telegram_message(chat_id, natural_message)

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
