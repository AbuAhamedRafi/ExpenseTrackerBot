import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def set_webhook():
    if not TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    print("🔗 Telegram Webhook Setup")
    print("--------------------------------")
    print("To test your bot, you need to expose your local server to the internet.")
    print("1. Download & Run ngrok: 'ngrok http 8000'")
    print("2. Copy the HTTPS URL (e.g., https://1234-56-78.ngrok-free.app)")
    print("--------------------------------")

    public_url = input("👉 Paste your ngrok URL here: ").strip()

    if not public_url.startswith("http"):
        print("❌ Invalid URL. Must start with http or https.")
        return

    # Remove trailing slash if present
    if public_url.endswith("/"):
        public_url = public_url[:-1]

    webhook_url = f"{public_url}/api/webhook/"

    print(f"\nSetting webhook to: {webhook_url} ...")

    response = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("✅ Webhook set successfully!")
            print(f"Response: {result.get('description')}")
            print("\n🎉 You can now send messages to your bot on Telegram!")
        else:
            print("❌ Failed to set webhook.")
            print(f"Error: {result.get('description')}")
    else:
        print(f"❌ HTTP Error: {response.status_code}")


if __name__ == "__main__":
    set_webhook()
