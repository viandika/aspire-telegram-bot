import logging
from datetime import datetime
from functools import wraps
from typing import Dict
from zoneinfo import ZoneInfo

import gspread
import toml
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

from tools import (
    create_calendar,
    get_accounts,
    get_all_categories,
    process_calendar_selection,
    write_trx,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

config = toml.load("config.toml")

# initialize gspread
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

client = gspread.service_account(
    filename=config["gsheet"]["gsheet_api_key_filepath"], scopes=scope
)

sheet = client.open_by_key(config["gsheet"]["gsheet_worksheet_id"])

trx_categories = get_all_categories(sheet)
trx_accounts = get_accounts(sheet)
trx_accounts = [item for sublist in trx_accounts for item in sublist]

# Initializing options
(
    CHOOSE_TRX_OPTS,
    REPLY_CHOOSE_TRX_OPTS,
    ASK_TRX_OPTS,
    CHOOSE_TRX_CATEGORY,
    CATEGORY_REPLY_CHOOSE_TRX_OPTS,
    DATE_REPLY,
    DATE_END,
) = range(7)

reply_keyboard = [
    ["Outflow", "Inflow"],
    ["Category", "Account"],
    ["Memo", "Date"],
    ["Done"],
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


def restricted(func):
    """Wrapper function to restrict access to the bot"""

    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if (
            config["telegram"]["restrict_access"]
            and user_id not in config["telegram"]["list_of_users"]
        ):
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)

    return wrapped


def facts_to_str(user_data: Dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""
    facts = []
    for key, value in user_data.items():
        if key in ("Outflow", "Inflow") and value != "":
            facts.append(f"*{key}* - Rp {int(value):,}")
        else:
            facts.append(f"*{key}* - {value}")
    return "\n".join(facts).join(["\n", "\n"])


@restricted
def start(update: Update, context: CallbackContext) -> int:
    """
    Start the conversation and ask user for input.
    Initialize with options to fill in.
    """
    user_data = context.user_data
    user_data["Date"] = datetime.now(tz=ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
    user_data["Outflow"] = ""
    user_data["Inflow"] = ""
    user_data["Category"] = ""
    user_data["Account"] = ""
    user_data["Memo"] = ""

    update.message.reply_text(
        "Creating new transaction. \n"
        "Details to fill in:  "
        f"{facts_to_str(user_data)}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )

    return CHOOSE_TRX_OPTS


@restricted
def category_start(update, context):
    """Separate function for category selection to filter the options with inline keyboard."""
    cats_keyboard = [
        list(trx_categories.keys())[i : i + 2]
        for i in range(0, len(list(trx_categories.keys())), 2)
    ]
    for i, x in enumerate(cats_keyboard):
        for j, k in enumerate(x):
            cats_keyboard[i][j] = InlineKeyboardButton(k, callback_data=str(k))

    reply_markup = InlineKeyboardMarkup(cats_keyboard)
    update.message.reply_text("Choose a Group", reply_markup=reply_markup)

    return CHOOSE_TRX_CATEGORY


@restricted
def category_lists(update, context):
    """Update inline keyboard with selected category groups"""
    query = update.callback_query
    query.answer()

    choice = query.data
    options = [
        trx_categories[str(choice)][i : i + 2]
        for i in range(0, len(list(trx_categories[str(choice)])), 2)
    ]

    for i, x in enumerate(options):
        for j, k in enumerate(x):
            options[i][j] = InlineKeyboardButton(k, callback_data=str(k))
    reply_markup = InlineKeyboardMarkup(options)

    query.edit_message_text(text="which category", reply_markup=reply_markup)

    return CATEGORY_REPLY_CHOOSE_TRX_OPTS


@restricted
def category_end(update, context):
    """Receive the selected category and move on."""
    user_data = context.user_data

    query = update.callback_query
    query.answer()
    choice = query.data

    user_data["Category"] = choice
    query.message.reply_text(
        "So far:" f"{facts_to_str(user_data)} Add More or done",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )

    return CHOOSE_TRX_OPTS


@restricted
def accounts_lists(update, context):
    text = update.message.text
    context.user_data["choice"] = text

    options = [trx_accounts[i : i + 2] for i in range(0, len(trx_accounts), 2)]
    acc_markup = ReplyKeyboardMarkup(options, one_time_keyboard=True)
    update.message.reply_text("Select which account", reply_markup=acc_markup)

    return REPLY_CHOOSE_TRX_OPTS


@restricted
def date_start(update, context):
    update.message.reply_text("Please select a date: ", reply_markup=create_calendar())
    return DATE_REPLY


@restricted
def date_handler(update, context):
    selected, date = process_calendar_selection(update, context)
    if selected:
        context.bot.send_message(
            chat_id=update.callback_query.from_user.id,
            text="You selected %s" % (date.strftime("%d/%m/%Y")),
            reply_markup=ReplyKeyboardRemove(),
        )
        user_data = context.user_data
        user_data["Date"] = date.strftime("%d/%m/%Y")

        context.bot.send_message(
            chat_id=update.callback_query.from_user.id,
            text="So far:" f"{facts_to_str(user_data)} Add More or done",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )

        return CHOOSE_TRX_OPTS
    return DATE_REPLY


@restricted
def date_end(update, context):
    user_data = context.user_data

    # query = update.callback_query
    # query.answer()
    selected, date = process_calendar_selection(update, context)

    user_data["Date"] = date.strftime("%d/%m/%Y")

    update.message.reply_text(
        "So far:" f"{facts_to_str(user_data)} Add More or done",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )

    return CHOOSE_TRX_OPTS


@restricted
def regular_choice(update: Update, context: CallbackContext) -> int:
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text
    context.user_data["choice"] = text
    update.message.reply_text(f"What is the {text.lower()}?")

    return REPLY_CHOOSE_TRX_OPTS


@restricted
def received_information(update: Update, context: CallbackContext) -> int:
    """Store info provided by user and ask for the next option."""
    user_data = context.user_data
    text = update.message.text
    category = user_data["choice"]

    if category in ("Outflow", "Inflow"):
        try:
            user_data[category] = int(text)
        except ValueError:
            update.message.reply_text(
                f"Need a number for {category.lower()}. Please try again."
            )
            return REPLY_CHOOSE_TRX_OPTS
    else:
        user_data[category] = text
    del user_data["choice"]

    update.message.reply_text(
        "So far:" f"{facts_to_str(user_data)} Add More or done",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )

    return CHOOSE_TRX_OPTS


@restricted
def done(update: Update, context: CallbackContext) -> int:
    """Upload info to aspire google sheet, display the gathered info and end the conversation."""
    user_data = context.user_data
    if "choice" in user_data:
        del user_data["choice"]

    input_data = [
        [
            user_data["Date"],
            user_data["Outflow"],
            user_data["Inflow"],
            user_data["Category"],
            user_data["Account"],
            user_data["Memo"],
        ]
    ]
    write_trx(sheet, input_data)
    update.message.reply_text(
        f"Information has been saved: {facts_to_str(user_data)}\n /start to start again.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    updater = Updater(config["telegram"]["telegram_token"])
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_TRX_OPTS: [
                MessageHandler(
                    Filters.regex("^(Outflow|Inflow|Memo)$"),
                    regular_choice,
                ),
                MessageHandler(
                    Filters.regex("^(Category)$"),
                    category_start,
                ),
                MessageHandler(
                    Filters.regex("^(Account)$"),
                    accounts_lists,
                ),
                MessageHandler(
                    Filters.regex("^(Date)$"),
                    date_start,
                ),
            ],
            ASK_TRX_OPTS: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex("^Done$")),
                    regular_choice,
                )
            ],
            REPLY_CHOOSE_TRX_OPTS: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex("^Done$")),
                    received_information,
                )
            ],
            CHOOSE_TRX_CATEGORY: [CallbackQueryHandler(category_lists)],
            CATEGORY_REPLY_CHOOSE_TRX_OPTS: [
                CallbackQueryHandler(category_end),
            ],
            DATE_REPLY: [CallbackQueryHandler(date_handler)],
            DATE_END: [MessageHandler(Filters.text, date_end)],
        },
        fallbacks=[MessageHandler(Filters.regex("^Done$"), done)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
