# 💰 Autonomous Expense Tracker Telegram Bot

A **truly intelligent** Telegram bot powered by Google Gemini 2.0 that autonomously manages your finances using **function calling**. Chat naturally, and Gemini decides what to do - no rigid commands, no hardcoded logic.

## 🌟 What Makes This Different?

Unlike traditional bots with hardcoded "if/else" logic, this bot uses **Gemini 2.0's function calling** to autonomously perform **ANY** Notion operation:

- 🧠 **Gemini Decides**: AI determines what operations to perform based on context
- 🔧 **Dynamic Function Calling**: AI can query, create, update, delete, or analyze ANY database
- 🔄 **Context-Aware**: Maintains conversation history for multi-turn interactions
- 🚀 **Fully Autonomous**: Can handle complex requests like "show my credit card spending" without explicit commands
- ✅ **Safety First**: Destructive operations (delete/update) require user confirmation

## ✨ Features

### 🤖 Autonomous Operations (Gemini 2.0 Function Calling)

- **Single Function, Infinite Possibilities**: One `autonomous_operation` function handles ALL Notion operations
- **AI-Driven Execution**: Gemini chooses operation type (query/create/update/delete/analyze) based on intent
- **Smart Filter Resolution**: Automatically resolves relation names to IDs (e.g., "BRAC Bank" → UUID)
- **Schema-Aware Validation**: Dynamically fetches database schemas to validate operations before execution
- **Rollup/Formula Awareness**: Reads computed values directly (e.g., "What's my credit card balance?")
- **Confirmation System**: Stores pending destructive operations in database until user confirms

### 💬 Natural Conversational AI

- **Human-like Interactions**: Chat naturally - "I spent 150 on lunch" or "Show my BRAC expenses"
- **Context-Aware Responses**: Gemini 2.0 maintains conversation history stored in database
- **Multi-Turn Conversations**: Ask follow-up questions like "And my credit card?"
- **Smart Defaults**: Infers missing details (e.g., small expenses → default account, today's date)
- **Emoji Support**: Appropriate emojis for better engagement (🍽️💰📊)

### 🧠 Intelligent Logic

- **Payback Logic**: "Payback TO Farha" → Expense | "Payback FROM Farha" → Income
- **Category Mapping**: "Snacks", "Lunch" → Food | "Pathao", "Uber" → Transport
- **Account Shortcuts**: "Show my BRAC expenses" → Automatically filters by BRAC Bank
- **Transfer Handling**: "Transfer 5000 from BRAC to Credit Card" → Creates Payment entry
- **Month-Aware Subscriptions**: Won't double-pay if already paid this month

### 📊 Advanced Notion Operations

- **Complex Queries**: Compound filters (AND/OR), date ranges, checkbox states, relation filters
- **Bulk Updates**: Update multiple items matching filters (with confirmation)
- **Analytics**: Sum, average, count operations on filtered data
- **Subscription Workflow**: Month-aware payment tracking with automatic checklist management
- **Duplicate Detection**: Prevents duplicate recurring expenses with fuzzy matching

### 🔍 Schema Inspector

- **Dynamic Schema Fetching**: Caches Notion database schemas for 1 hour
- **Property Validation**: Validates property names before operations
- **Fallback Schemas**: Uses hardcoded schemas if Notion API fails
- **Type Checking**: Ensures data types match schema requirements

### 🚀 Performance Optimized

- **Smart Caching**: Categories/accounts cached for 1 hour, schemas cached dynamically
- **Connection Pooling**: Persistent HTTP session with retry strategy for Notion API
- **Parallel Reads**: Can batch independent queries
- **Fast Response Time**: ~5-10 seconds for simple operations

### 🔒 Security & Reliability

- **User Whitelist**: Only authorized Telegram user IDs can access
- **Confirmation Manager**: Database-backed pending confirmations with 5-minute expiry
- **Idempotency Checks**: Prevents duplicate operations on retries
- **Graceful Failures**: Detailed error messages with retry suggestions

## 🏗️ Architecture

### High-Level Flow

```
User Message (Telegram)
        ↓
Telegram Webhook → Django API
        ↓
Gemini 2.0 with Function Calling
  ├─ Maintains conversation history (TelegramLog)
  ├─ Analyzes intent + context
  ├─ Generates natural response
  └─ Decides function calls (autonomous_operation)
        ↓
Operation Validator
  ├─ Schema Inspector (validates properties)
  ├─ Filter Validator (checks Notion syntax)
  └─ Confirms destructive operations
        ↓
Smart Executor
  ├─ Resolves relation names → IDs
  ├─ Builds Notion-compliant properties
  ├─ Executes with retry logic
  └─ Formats results for Gemini
        ↓
Notion API (Query/Create/Update/Delete/Analyze)
        ↓
Response with natural message + function results
```

### Autonomous Operation Architecture

**Function Declaration** (in `services.py`):

```python
autonomous_operation(
    operation_type: "query" | "create" | "update" | "delete" | "analyze",
    database: "expenses" | "income" | "categories" | "accounts" | "subscriptions" | "payments",
    filters: {...},      # Notion filter syntax
    data: {...},         # Properties to create/update
    page_id: "...",      # For update/delete
    analysis_type: "sum" | "average" | "count",
    reasoning: "..."     # AI explains what it's doing
)
```

**Execution Pipeline**:

1. **Gemini Decides** → Chooses operation + parameters based on user intent
2. **Validator** → Checks schema, filters, destructive operations
3. **Confirmation Manager** → Stores pending operations if destructive
4. **Smart Executor** → Resolves relations, builds properties, executes
5. **Result Formatter** → Converts Notion response to user-friendly format

## 📦 Tech Stack

- **Backend**: Django 4.x + Django REST Framework
- **AI**: Google Gemini 2.0 Flash with Function Calling (`google-generativeai`)
- **Database**:
  - **Data Storage**: Notion API (Expenses, Income, Categories, Accounts, Subscriptions, Payments)
  - **Conversation History**: Django ORM (SQLite/PostgreSQL) - `TelegramLog`, `PendingConfirmation`
- **Bot Platform**: Telegram Bot API (Webhook-based)
- **Deployment**: Render-ready (or any Python hosting)
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
NOTION_PAYMENTS_DB_ID=your_payments_database_id
NOTION_LOANS_DB_ID=your_loans_database_id

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

You: I spent 150 on lunch
Bot: Got it! 🍽️ Saved your lunch expense of $150. Enjoy your meal!
```

### 🔍 Autonomous Queries

```
You: Show my BRAC expenses
Bot: [Gemini automatically adds account filter]
     Found 12 results from BRAC Bank Salary Account:
     1. Lunch: $150.00 (2025-01-20)
     2. Pathao Ride: $120.00 (2025-01-19)
     ...

You: What about my credit card?
Bot: [Uses conversation context]
     Found 8 results from MasterCard Platinum (UCB):
     1. Netflix: $999.00 (2025-01-15)
     2. Shopping: $5000.00 (2025-01-10)
     ...
```

### 💰 Complex Operations

```
You: Which subscriptions are unchecked?
Bot: [Queries subscriptions DB with checkbox filter]
     Found 2 unpaid subscriptions:
     1. Netflix: $999.00
     2. Spotify: $149.00

You: Pay Netflix subscription
Bot: [Month-aware workflow]
     ⚠️ This will create an expense and mark Netflix as paid.
     Reply 'yes' to confirm.

You: yes
Bot: ✅ Paid Netflix for this month and marked as checked.
```

### 📊 Analytics

```
You: What's my average daily spending?
Bot: [Queries past month, calculates average]
     Average: $283.45

     Based on last 30 days: Total $8503.50 across 30 days.
```

### 🔄 Transfers & Payments

```
You: Transfer 5000 from BRAC to UCB Credit Card
Bot: [Creates Payment entry linking both accounts]
     ✅ Created transfer from BRAC Bank Salary Account to
     MasterCard Platinum (UCB) for $5000.
```

### ⚠️ Error Handling

```
You: Add expense xyz 500
Bot: ❌ Operation failed: Property 'xyz' does not exist in expenses database

     I'll try to fix this...

     [Gemini retries with corrected parameters]
     ✅ Created xyz expense for $500.
```

## 📁 Project Structure

```
ExpenseTrackerBot/
├── expenses/                        # Main Django app
│   ├── views.py                    # Telegram webhook handler
│   ├── services.py                 # Gemini AI integration + function calling
│   ├── autonomous.py               # ⭐ Autonomous operations engine
│   │   ├── SchemaInspector        #    - Dynamic schema fetching/caching
│   │   ├── OperationValidator      #    - Pre-execution validation
│   │   ├── ConfirmationManager     #    - Destructive operation confirmations
│   │   └── SmartExecutor           #    - Operation execution with retry
│   ├── notion_client.py            # Low-level Notion API client
│   ├── models.py                   # Django models (TelegramLog, PendingConfirmation)
│   ├── urls.py                     # API routes
│   └── migrations/                 # Database migrations
├── main/                           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py                       # Django management script
├── requirements.txt                # Python dependencies
├── set_webhook.py                  # Webhook setup script
├── render.yaml                     # Render deployment config
├── build.sh                        # Build script for deployment
└── .env                            # Environment variables (not in repo)
```

### Module Responsibilities

- **services.py**: Gemini AI integration, function calling declaration, caching layer
- **autonomous.py**: Complete autonomous operations system:
  - `SchemaInspector`: Fetches and caches Notion database schemas
  - `OperationValidator`: Validates operations against schemas and Notion API constraints
  - `ConfirmationManager`: Manages pending confirmations for destructive operations
  - `SmartExecutor`: Executes operations with relation resolution, retry logic, and result formatting
- **views.py**: Telegram webhook endpoint, response formatting, confirmation handling
- **notion_client.py**: Core Notion API operations (queries, creates, updates, deletes)
- **models.py**: Django models for conversation history (`TelegramLog`) and pending confirmations (`PendingConfirmation`)

## 🗄️ Notion Database Structure

### Required Databases:

1. **Expenses Database**

   - Name (Title)
   - Amount (Number)
   - Date (Date)
   - Categories (Relation to Categories DB)
   - Accounts (Relation to Accounts DB)
   - Subscriptions (Relation to Subscriptions DB) - Optional
   - Loan Repayment (Relation to Loans DB) - Optional
   - Year, Monthly, Weekly, Misc (Formulas) - Optional

2. **Income Database**

   - Name (Title)
   - Amount (Number)
   - Date (Date)
   - Accounts (Relation to Accounts DB)
   - Loan Disbursement (Relation to Loans DB) - Optional
   - Misc (Text) - Optional

3. **Categories Database**

   - Name (Title)
   - Monthly Budget (Number) - Optional but recommended
   - Monthly Expense, Status Bar, Status (Formulas) - Optional

4. **Accounts Database**

   - Name (Title)
   - Account Type (Select: Bank/Credit Card) - Optional
   - Initial Amount, Credit Limit, Utilization (Numbers) - Optional
   - Current Balance, Total Income, Total Expense (Formulas/Rollups) - Optional
   - Linked Loans (Relation to Loans DB) - Optional

5. **Subscriptions Database** (Optional - for fixed expense tracking)

   - Name (Title)
   - Type (Select)
   - Amount (Number)
   - Checkbox (Checkbox)
   - Account, Category (Relations)
   - Expenses (Relation to Expenses DB)

6. **Payments Database** (Optional - for transfers/credit card payments)

   - Name (Title)
   - Amount (Number)
   - Date (Date)
   - From Account (Relation to Accounts DB)
   - To Account (Relation to Accounts DB)

7. **Loans Database** (Optional - for debt/loan tracking)
   - Name (Title)
   - Total Debt Value (Number) - Total amount to pay back (Principal + Interest)
   - Start Date (Date)
   - Lender/Source (Select) - Bank, Friend, etc.
   - Repayments (Relation to Expenses DB) - Synced relation
   - Disbursements (Relation to Income DB) - Synced relation
   - Related Account (Relation to Accounts DB)
   - Total Paid (Rollup) - Sum of Amount from Repayments
   - Remaining Balance (Formula) - Total Debt Value - Total Paid
   - Progress Bar (Formula) - Total Paid / Total Debt Value
   - Status (Formula) - "Paid Off" or "Active"

**Note**: The bot dynamically inspects schemas, so property names can vary. It will validate against your actual database structure.

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

### Customizing Databases

The bot dynamically fetches database schemas from Notion. Simply:

- Add/remove categories in your Notion Categories database
- Add/remove accounts in your Notion Accounts database
- Create new databases and update `get_database_id()` mapping in `notion_client.py`

### Customizing AI Behavior

Edit the system instruction in `services.py` (`ask_gemini()` function):

- Change personality/tone
- Add/remove logic rules
- Modify smart defaults (e.g., default account)
- Add new category mappings

## 🔧 Troubleshooting

### Bot not responding?

- Check webhook status: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Verify environment variables are loaded
- Check server logs for errors

### "Not authorized" message?

- Ensure `ALLOWED_USER_ID` in `.env` matches your Telegram user ID
- Get your user ID from [@userinfobot](https://t.me/userinfobot)

### Notion integration not working?

- Verify Notion token has access to all required databases
- Check database IDs are correct in `.env`
- Ensure database properties exist (bot validates against schemas)

### Gemini API quota exceeded?

- Free tier has limited tokens/requests per minute
- Consider upgrading to paid tier for higher limits
- Optimize system instruction length to reduce token usage

### Operations failing validation?

- Check database schemas match expected structure
- Ensure relation properties exist
- Review error messages - they specify which property/filter failed

## 📊 Performance Considerations

### Token Usage

The autonomous system uses more tokens than hardcoded logic:

- **Pros**: Infinite flexibility, natural conversations, no code changes for new features
- **Cons**: Higher token usage (function calling + natural language + history)
- **Optimization**: Limit conversation history length (currently 10 messages)

### API Calls

- **Caching**: Categories/accounts cached for 1 hour
- **Schema Caching**: Database schemas cached for 1 hour
- **Connection Pooling**: Persistent HTTP session reduces overhead
- **Batch Operations**: Bulk updates execute multiple operations in sequence

### Response Time

- Simple operations (create/query): ~5-10 seconds
- Complex operations (bulk update/analytics): ~10-20 seconds
- Confirmation flow: 2-step process (initial request + confirmation)

## 🛠️ Development

### Running Tests

```bash
python manage.py test
```

### Code Style

This project follows:

- PEP 8 style guide
- Type hints where applicable
- Docstrings for all public functions

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 👨‍💻 Author

**Abu Ahamed Rafi**

- GitHub: [@AbuAhamedRafi](https://github.com/AbuAhamedRafi)

## 🙏 Acknowledgments

- [Google Gemini AI](https://ai.google.dev/) for autonomous function calling capabilities
- [Notion API](https://developers.notion.com/) for flexible database management
- [Telegram Bot API](https://core.telegram.org/bots/api) for bot platform

---

**Built with ❤️ and AI** - This bot represents the future of conversational finance management, where AI autonomously handles complex operations based on natural language intent.
