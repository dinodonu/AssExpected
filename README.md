# AssExpected

Telegram userbot to track the market.

## Features

- Forward BWETradFi news into a Telegram group/topic in real time

## TODO

- [ ] Scan stocks in watchlist daily at market open and close.

## Setup

Create a `.env` file in the project root with the following variables:

```
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
TELEGRAM_SOURCE_CHAT=your-source-chat
TELEGRAM_TARGET_CHAT=your-target-chat-id
TELEGRAM_TARGET_TOPIC=your-topic-id
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_GROUP_LINK=https://t.me/+your-group-link
```