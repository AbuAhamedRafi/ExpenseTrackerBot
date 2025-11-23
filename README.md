# 💰 Expense Tracker Telegram Bot

A smart Telegram bot that tracks your expenses and income using natural language processing. Powered by Google Gemini AI and integrated with Notion for seamless data management.

## ✨ Features

### 💬 Natural Conversational AI

- **Human-like Interactions**: Chat naturally like texting a friend, not a machine
- **Context-Aware Responses**: Gemini 2.0 Flash provides personalized, encouraging replies
- **Emoji Support**: Appropriate emojis for better engagement (🍽️💰📊)
- **Smart Conversations**: Can handle casual chat ("Hey!", "Thanks!") alongside expense tracking

### 🤖 Intelligent Expense Parsing

- **Natural Language Input**: "Lunch 150", "Taxi 500 for office", "Bought bike 200, youtube 330"
- **Multi-Expense Support**: Log multiple expenses in one message
- **AI-Powered Parsing**: Google Gemini automatically extracts expense details
- **Smart Category Matching**: Intelligently categorizes expenses based on description
- **Multi-Account Support**: Dynamically detects or uses specified bank accounts

### 📊 Notion Integration

- **Real-time Sync**: All expenses/income saved directly to your Notion databases
- **Budget Tracking**: Automatic budget warnings when you exceed category limits
- **Expense Summary**: Monthly overview with category breakdown and remaining budget
- **Budget Check**: Check hypothetical expense impact before spending
- **Duplicate Detection**: Prevents duplicate entries for recurring expenses (subscriptions, bills)
- **Fixed Expense Checklist**: Auto-ticks paid items in your subscription checklist
- **Dynamic Categories & Accounts**: Fetches your actual categories and accounts from Notion

### ✅ Robust Transaction Processing

- **Validate-Then-Execute**: All items validated before ANY writes to prevent partial data
- **Partial Success Handling**: Saves valid expenses, clearly reports failures with reasons
- **Detailed Error Messages**: Tells you exactly what went wrong (category not found, etc.)
- **Atomic Behavior**: No more half-saved transactions with unclear states

### 🚀 Performance Optimized

- **Smart Caching**: Categories and accounts cached for 1 hour (budget checks remain real-time)
- **70% Fewer API Calls**: Reduced from 8-10 to 2-3 calls per transaction
- **Fast Response Time**: ~5-10 seconds (down from 30-40 seconds)
- **Deployment-Ready**: Optimized for slow deployments like Render free tier

### 🔒 Security

- **User Whitelist**: Only authorized Telegram user IDs can access the bot
- **Environment Variables**: All sensitive data stored in `.env` file

## 🏗️ Architecture

```
User Message (Telegram)
        ↓
Telegram Webhook → Django API
        ↓
Google Gemini AI (Parse message)
        ↓
Process & Validate
        ↓
Notion API (Save expense/income)
        ↓
Response with confirmation + warnings
```

## 📦 Tech Stack

- **Backend**: Django + Django REST Framework
- **AI**: Google Gemini 2.0 Flash
- **Database**: Notion API (Expenses, Income, Categories, Accounts, Subscriptions)
- **Bot Platform**: Telegram Bot API
- **Deployment**: Render (or any Python hosting)
- **Language**: Python 3.11+

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token ([Get from @BotFather](https://t.me/botfather))
- Google Gemini API Key ([Get from Google AI Studio](https://makersuite.google.com/app/apikey))
- Notion Integration Token & Database IDs

### 1. Clone Repository

```bash
git clone https://github.com/AbuAhamedRafi/ExpenseTrackerBot.git
cd ExpenseTrackerBot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ALLOWED_USER_ID=your_telegram_user_id

# Google Gemini AI
GEMINI_API_KEY=your_gemini_api_key

# Notion Integration
NOTION_TOKEN=your_notion_integration_token
NOTION_VERSION=2022-06-28

# Notion Database IDs
NOTION_EXPENSE_DB_ID=your_expense_database_id
NOTION_INCOME_DB_ID=your_income_database_id
NOTION_CATEGORIES_DB_ID=your_categories_database_id
NOTION_ACCOUNTS_DB_ID=your_accounts_database_id
NOTION_SUBSCRIPTIONS_DB_ID=your_subscriptions_database_id

# Django Settings
SECRET_KEY=your_django_secret_key
DEBUG=True
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Run Development Server

```bash
python manage.py runserver
```

### 6. Set Up Webhook

#### For Local Development (using ngrok):

```bash
# In a separate terminal
ngrok http 8000

# In another terminal, run the webhook setup script
python set_webhook.py
```

#### For Production (Render/Heroku):

```bash
# Your webhook URL will be:
https://your-app-name.onrender.com/api/webhook/

# Set it using:
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app-name.onrender.com/api/webhook/"
```

## 🎯 Usage Examples

### 💬 Natural Conversations

```
You: Hey!
Bot: Hey! 👋 I'm doing great, thanks for asking! Ready to help you track
     your expenses. What's up?

You: Thanks!
Bot: You're welcome! 😊 Anytime you need help with your finances, I'm here!
```

### Adding Expenses

```
You: Lunch 150
Bot: Got it! 🍽️ Saved your lunch expense of $200. Enjoy your meal!

You: Bought bike 200, youtube premium 330, paid utilities 300
Bot: Nice! I'm logging these 3 expenses for you - bike, YouTube premium,
     and utilities. Let me save them! 💾

You: Netflix subscription 999
Bot: Awesome! Saved your Netflix subscription for $999. 📺
     ✓ Marked 'Netflix subscription' as paid in Fixed Expenses Checklist
```

### Partial Success (Smart Error Handling)

```
You: Paid 200 for bike, 330 for youtube, 300 for xyz
Bot: Alright! Saving your expenses...

     ⚠️ Saved 2 of 3:
     ✅ Bike ($200)
     ✅ YouTube ($330)

     ❌ Failed 1:
     • xyz: Expense #3 (xyz): Category 'xyz' not found in Notion
```

### Adding Income

```
You: Salary credited 50000
Bot: Awesome! 💰 Your salary of $50,000 has been logged. Great way to
     start the month!
```

### Expense Summary

```
You: Show my expenses
Bot: Let me pull up your expense summary! 📊

     📊 November Summary

     💰 Income: $5000.00
     💸 Spent: $3200.00
     💵 Remaining: $1800.00

     *By Category:*
     • Food: $450.00 ✓ $50.00 left
     • Transportation: $200.00 ✓ $300.00 left
     • Entertainment: $550.00 ⚠️ $50.00 over
     • Shopping: $1000.00 ✓ $200.00 left
```

### Budget Check (Hypothetical)

```
You: Can I afford a 500 dollar phone?
Bot: Let me check your budget for that! 🤔

     *Shopping Budget*
     Current: $200.00 / $600.00
     After expense: $700.00
     Remaining: -$100.00 (117% used)

     🚫 This would put you over budget.

You: What if I spend 300 on food?
Bot: Let me see... 🤔

     *Food Budget*
     Current: $450.00 / $500.00
     After expense: $750.00
     Remaining: $250.00 (150% used)

     ✅ You're good to go!
```

### Budget Warnings

```
You: Shopping 5000
Bot: Saved! Your shopping expense of $5000. 🛍️

     ⚠️ Budget alerts:
     You've spent $6500.00 in 'Shopping' this month (Budget: $5000.00).
     You're over by $1500.00!
```

### Duplicate Detection

```
You: Spotify subscription 149
Bot: ⚠️ You already paid 'Spotify subscription' on November 05, 2025 this month.
```

## 📁 Project Structure

```
ExpenseTrackerBot/
├── expenses/                        # Main app
│   ├── views.py                    # Telegram webhook handler
│   ├── services.py                 # Gemini AI integration + caching
│   ├── notion_client.py            # Low-level Notion API client
│   ├── transaction_manager.py      # Expense/income business logic
│   ├── budget_tracker.py           # Budget calculations & summaries
│   ├── utils.py                    # Utility functions
│   ├── urls.py                     # API routes
│   ├── models.py                   # Django models
│   └── ARCHITECTURE.md             # Module documentation
├── main/                           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py                       # Django management script
├── requirements.txt                # Python dependencies
├── set_webhook.py                  # Webhook setup script
├── render.yaml                     # Render deployment config
├── build.sh                        # Build script for deployment
├── PERFORMANCE_OPTIMIZATIONS.md    # Performance documentation
└── .env                            # Environment variables (not in repo)
```

### Module Responsibilities

- **notion_client.py**: Core Notion API operations (queries, creates, updates)
- **transaction_manager.py**: Expense/income processing, duplicate detection, validation
- **budget_tracker.py**: Budget calculations, monthly summaries, spending analysis
- **services.py**: Gemini AI integration, caching layer, natural conversation handling
- **views.py**: Telegram webhook endpoint, response formatting

## 🗄️ Notion Database Structure

### Required Databases:

1. **Expenses Database**

   - Name (Title)
   - Amount (Number)
   - Date (Date)
   - Categories (Relation to Categories DB)
   - Accounts (Relation to Accounts DB)

2. **Income Database**

   - Name (Title)
   - Amount (Number)
   - Date (Date)
   - Accounts (Relation to Accounts DB)

3. **Categories Database**

   - Name (Title)
   - Budget/Monthly Budget (Number) - Optional

4. **Accounts Database**

   - Name (Title)

5. **Subscriptions/Fixed Expenses Database** (Optional)
   - Name (Title)
   - Checkbox (Checkbox)

## 🚀 Deployment

### Deploy to Render

1. Push your code to GitHub
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Add all environment variables in Render dashboard
5. Deploy!

The `render.yaml` and `build.sh` are already configured for automatic deployment.

### Deploy to Heroku

```bash
# Install Heroku CLI and login
heroku login

# Create a new app
heroku create your-expense-bot

# Set environment variables
heroku config:set TELEGRAM_BOT_TOKEN=your_token
heroku config:set GEMINI_API_KEY=your_key
# ... (set all other env vars)

# Deploy
git push heroku main

# Set webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-expense-bot.herokuapp.com/api/webhook/"
```

## ⚙️ Configuration

### Customizing Categories

The bot fetches categories dynamically from your Notion. Simply add/remove categories in your Notion Categories database.

### Customizing Accounts

Add your bank accounts/payment methods in the Notion Accounts database. The bot will recognize them in messages.

### Recurring Expense Keywords

Edit the `recurring_keywords` list in `notion_services.py` to add more subscription/bill keywords for duplicate detection.

## 🔧 Troubleshooting

### Bot not responding?

- Check if webhook is set correctly: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Verify environment variables are loaded
- Check server logs for errors

### "Not authorized" message?

- Ensure `ALLOWED_USER_ID` in `.env` matches your Telegram user ID
- Get your user ID from [@userinfobot](https://t.me/userinfobot)

### Notion integration not working?

- Verify Notion token has access to all required databases
- Check database IDs are correct in `.env`
- Ensure database properties match expected names

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 👨‍💻 Author

**Abu Ahamed Rafi**

- GitHub: [@AbuAhamedRafi](https://github.com/AbuAhamedRafi)

## 🙏 Acknowledgments

- [Google Gemini AI](https://ai.google.dev/) for natural language processing
- [Notion API](https://developers.notion.com/) for database management
- [Telegram Bot API](https://core.telegram.org/bots/api) for bot platform

---
