import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services import ask_gemini, execute_function_calls


class TelegramWebhookView(APIView):
    """
    Handles incoming webhook requests from Telegram using Gemini function calling.
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
            update_id = data.get("update_id")

            # Security: Whitelist check
            allowed_user_id = os.getenv("ALLOWED_USER_ID")
            if allowed_user_id and str(user_id) != str(allowed_user_id):
                self.send_telegram_message(
                    chat_id, "Sorry, you are not authorized to use this bot."
                )
                return Response({"status": "unauthorized"}, status=status.HTTP_200_OK)

            if not text:
                return Response({"status": "no_text"}, status=status.HTTP_200_OK)

            # Check for duplicate webhook (simple deduplication)
            # Store last processed update_id in cache or skip if within 2 seconds
            if (
                hasattr(self.__class__, "_last_update_id")
                and self.__class__._last_update_id == update_id
            ):
                return Response({"status": "duplicate"}, status=status.HTTP_200_OK)
            self.__class__._last_update_id = update_id

            # Process with Gemini
            gemini_response = ask_gemini(text)

            # Extract natural message and function calls
            natural_message = gemini_response.get("message", "")
            function_calls = gemini_response.get("function_calls")

            # Always send Gemini's natural response first
            if natural_message:
                self.send_telegram_message(chat_id, natural_message)

            # If no function calls, we're done (pure conversation)
            if not function_calls:
                return Response({"status": "success"}, status=status.HTTP_200_OK)

            # Execute function calls
            execution_results = execute_function_calls(function_calls)

            # Process each function result
            for exec_result in execution_results:
                func_name = exec_result["function"]
                result = exec_result["result"]

                if func_name == "get_monthly_summary":
                    if result.get("success"):
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
                                reply_text += f"• {cat['name']}: ${cat['spent']:.2f}{budget_info}\n"
                    else:
                        reply_text = "\n❌ Couldn't fetch the data right now."

                    self.send_telegram_message(chat_id, reply_text)

                elif func_name == "check_budget_impact":
                    if result.get("success"):
                        check = result["data"]
                        reply_text = f"\n*{check.get('category', 'Category')} Budget*\n"

                        if check["status"] == "no_budget":
                            reply_text += f"No budget set.\nCurrent: ${check['current_spent']:.2f}\n"
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
                            f"\n❌ {result.get('error', 'Error checking budget')}"
                        )

                    self.send_telegram_message(chat_id, reply_text)

                elif func_name == "get_unpaid_subscriptions":
                    if result.get("success"):
                        unpaid_data = result["data"]
                        if unpaid_data["unpaid_count"] > 0:
                            reply_text = f"\n💡 You have {unpaid_data['unpaid_count']} unpaid subscription(s):\n"
                            for item in unpaid_data["unpaid_items"]:
                                reply_text += f"• {item}\n"
                        else:
                            reply_text = "\n✅ All subscriptions are paid this month!"
                    else:
                        reply_text = f"\n❌ {result.get('error', 'Error fetching subscriptions')}"

                    self.send_telegram_message(chat_id, reply_text)

                elif func_name == "delete_last_expense":
                    if result.get("success"):
                        details = result.get("details", {})
                        reply_text = f"\n🗑️ {result.get('message', 'Expense deleted')}"
                        self.send_telegram_message(chat_id, reply_text)
                    else:
                        reply_text = (
                            f"\n❌ {result.get('message', 'Could not delete expense')}"
                        )
                        self.send_telegram_message(chat_id, reply_text)

                elif func_name == "delete_last_income":
                    if result.get("success"):
                        details = result.get("details", {})
                        reply_text = f"\n🗑️ {result.get('message', 'Income deleted')}"
                        self.send_telegram_message(chat_id, reply_text)
                    else:
                        reply_text = (
                            f"\n❌ {result.get('message', 'Could not delete income')}"
                        )
                        self.send_telegram_message(chat_id, reply_text)

                elif func_name in ["save_expense", "save_income"]:
                    if result.get("success"):
                        # Add details for partial success
                        if result.get("partial_success"):
                            reply_text = f"\n\n⚠️ Saved {result['count']} of {result['total_attempted']}:\n"
                            for item in result["saved_items"]:
                                reply_text += f"✅ {item['name']} (${item['amount']})\n"

                            reply_text += f"\n❌ Failed {result['failed_count']}:\n"
                            for failure in result["failures"]:
                                reply_text += (
                                    f"• {failure['name']}: {failure['reason']}\n"
                                )
                        else:
                            # Full success - already in natural message
                            pass

                        # Add budget warnings
                        if result.get("budget_warnings"):
                            reply_text = "\n\n⚠️ Budget alerts:\n"
                            for warning in result["budget_warnings"]:
                                reply_text += f"{warning}\n"
                            self.send_telegram_message(chat_id, reply_text)

                        # Add checklist updates
                        if result.get("checklist_messages"):
                            reply_text = "\n✓ "
                            reply_text += "\n✓ ".join(result["checklist_messages"])
                            self.send_telegram_message(chat_id, reply_text)

                        # Send partial success message if exists
                        if result.get("partial_success"):
                            reply_text = f"\n⚠️ Saved {result['count']} of {result['total_attempted']}:\n"
                            for item in result["saved_items"]:
                                reply_text += f"✅ {item['name']} (${item['amount']})\n"
                            reply_text += f"\n❌ Failed {result['failed_count']}:\n"
                            for failure in result["failures"]:
                                reply_text += (
                                    f"• {failure['name']}: {failure['reason']}\n"
                                )
                            self.send_telegram_message(chat_id, reply_text)
                    else:
                        reply_text = f"\n❌ {result.get('message', 'Could not save')}"
                        self.send_telegram_message(chat_id, reply_text)

            return Response({"status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in webhook: {e}")
            import traceback

            traceback.print_exc()
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def send_telegram_message(self, chat_id, text):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, json=payload)
