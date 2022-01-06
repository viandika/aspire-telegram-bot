import calendar
import datetime
from itertools import groupby

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


def get_all_categories(spreadsheet) -> dict[str, list]:
    worksheet = spreadsheet.worksheet("Configuration")
    values = worksheet.get("r_ConfigurationData")

    # Find groups and exclude credit card payments
    groups = [i[1] for i in values if i[0] == "✦" and "Credit Card" not in i[1]]

    # get categories from configuration worksheet
    categories = []
    for k, g in groupby(values, key=lambda x: x[0] != "✦" and x[0] != "◘"):
        if k:
            categories.append(list(g))
    categories_titles = [[k[1] for k in i] for i in categories]

    grouped_cats = dict(zip(groups, categories_titles))
    # Add missing options
    category = worksheet.get("TransactionCategories")
    grouped_cats["Others"] = list(
        set([i for j in category for i in j])
        ^ set([i for j in categories_titles for i in j])
    )

    return grouped_cats


def get_accounts(spreadsheet):
    worksheet = spreadsheet.worksheet("Configuration")
    accounts = worksheet.get("cfg_Accounts")
    return accounts


def write_trx(spreadsheet, data: [[]]):
    worksheet = spreadsheet.worksheet("Transactions")
    next_row = next(n for n in worksheet.range("trx_Dates") if n.value == "")
    worksheet.update(next_row.address + ":H" + str(next_row.row), data)


def separate_callback_data(data):
    """Separate the callback data"""
    return data.split(";")


def create_calendar_callback_data(action, year, month, day):
    """Create the callback data associated to each button"""
    return "CALENDAR" + ";" + ";".join([action, str(year), str(month), str(day)])


def create_calendar(year=None, month=None):
    """
    Create an inline keyboard with the provided year and month
    """
    now = datetime.datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    data_ignore = create_calendar_callback_data("IGNORE", year, month, 0)
    keyboard = []
    # First row - Month and Year
    row = [
        InlineKeyboardButton(
            calendar.month_name[month] + " " + str(year), callback_data=data_ignore
        )
    ]
    keyboard.append(row)
    # Second row - Week Days
    row = []
    for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
        row.append(InlineKeyboardButton(day, callback_data=data_ignore))
    keyboard.append(row)

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
            else:
                row.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=create_calendar_callback_data(
                            "DAY", year, month, day
                        ),
                    )
                )
        keyboard.append(row)
    # Last row - Buttons
    row = [
        InlineKeyboardButton(
            "<",
            callback_data=create_calendar_callback_data("PREV-MONTH", year, month, day),
        ),
        InlineKeyboardButton(" ", callback_data=data_ignore),
        InlineKeyboardButton(
            ">",
            callback_data=create_calendar_callback_data("NEXT-MONTH", year, month, day),
        ),
    ]
    keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


def process_calendar_selection(update, context):
    """
    Process the callback_query. This method generates a new calendar if forward or
    backward is pressed. This method should be called inside a CallbackQueryHandler.
    """
    ret_data = (False, None)
    query = update.callback_query
    # print(query)
    (_, action, year, month, day) = separate_callback_data(query.data)
    curr = datetime.datetime(int(year), int(month), 1)
    if action == "IGNORE":
        context.bot.answer_callback_query(callback_query_id=query.id)
    elif action == "DAY":
        context.bot.edit_message_text(
            text=query.message.text,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
        )
        ret_data = True, datetime.datetime(int(year), int(month), int(day))
    elif action == "PREV-MONTH":
        pre = curr - datetime.timedelta(days=1)
        context.bot.edit_message_text(
            text=query.message.text,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_calendar(int(pre.year), int(pre.month)),
        )
    elif action == "NEXT-MONTH":
        ne = curr + datetime.timedelta(days=31)
        context.bot.edit_message_text(
            text=query.message.text,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_calendar(int(ne.year), int(ne.month)),
        )
    else:
        context.bot.answer_callback_query(
            callback_query_id=query.id, text="Something went wrong!"
        )
        # UNKNOWN
    return ret_data


def create_category_callback_data(action, selection):
    return action + ";" + selection


def create_category_inline(options, action):
    cats_keyboard = [list(options)[i : i + 2] for i in range(0, len(list(options)), 2)]
    for i, x in enumerate(cats_keyboard):
        for j, k in enumerate(x):
            cats_keyboard[i][j] = InlineKeyboardButton(
                k, callback_data=create_category_callback_data(action, str(k))
            )
    if action == "cat_selection":
        cats_keyboard.append(
            [
                InlineKeyboardButton(
                    "< Back", callback_data=create_category_callback_data("back", "")
                )
            ]
        )
    return InlineKeyboardMarkup(cats_keyboard)


def handle_category_inline(update, context, categories):
    return_data = (False, None)
    query = update.callback_query
    action, choice = separate_callback_data(query.data)

    if action == "group_sel":
        context.bot.edit_message_text(
            text="Pick Category",
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_category_inline(
                categories[str(choice)], "cat_selection"
            ),
        )
    elif action == "back":
        context.bot.edit_message_text(
            text="Pick Group",
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_category_inline(categories.keys(), "group_sel"),
        )
    elif action == "cat_selection":
        return_data = (True, choice)
    return return_data
