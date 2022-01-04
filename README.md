# aspire-telegram-bot
A telegram bot which intends to work with [Aspire Budgeting](https://aspirebudget.com/). Currently, it only supports adding new transactions. More features will be added progressively.

## Usage
Copy and rename `config.toml.example` to `config.toml` file needs to be filled in with your credentials.

1) Follow this [gspread docs](https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account) to get your API key and share spreadsheet access to the service account.
Add the file path to _**gsheet_api_key_filepath**_
2) Copy **your** Aspire Budgeting spreadsheet key (obtained from the url e.g. _1jUkhoC3CbaO0H4H01iYtTNPf1-ybi0UQ4aZ2aBG7q40_) to _**gsheet_worksheet_id**_
3) Get your telegram API key from [BotFather](https://t.me/botfather) and add it to _**telegram_token**_
4) Set _**restrict_access**_ to true if you want to limit access to certain users. If so, add the telegram user ids to _**list_of_users**_

Run the bot with:
```
python main.py
```