import asyncio
import os
from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest

_DIR = os.path.dirname(os.path.abspath(__file__))

api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
api_hash = os.getenv("TELEGRAM_API_HASH", "")
group = os.getenv("TELEGRAM_GROUP_LINK", "")

async def show_group_id():
    async with TelegramClient(os.path.join(_DIR, "id_lookup.session"), api_id, api_hash) as client:
        entity = await client.get_entity(group)
        print(f"raw id: {entity.id}")
        # Telethon expects the chat ID with the -100 prefix for supergroups
        supergroup_id = f"-100{entity.id}"
        print(f"use this in config: {supergroup_id}")

async def list_topics():
    async with TelegramClient(os.path.join(_DIR, "topic_lookup.session"), api_id, api_hash) as client:
        channel = await client.get_input_entity(group)
        forum = await client(
            GetForumTopicsRequest(
                channel=channel,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=20,  # adjust if you have many topics
            )
        )
        for topic in forum.topics:
            print(topic.title, topic.id)

async def topic_from_thread():
    async with TelegramClient(os.path.join(_DIR, "topic_lookup.session"), api_id, api_hash) as client:
        # open the topic in Telegram, grab any message link, and paste below
        topic_dialog = await client.get_entity("https://t.me/c/CHANNELID/STARTERMSGID")
        async for msg in client.iter_messages(topic_dialog, limit=1):
            print(f"Topic ID: {msg.id}")  # starter message ID == topic ID

asyncio.run(list_topics())

# asyncio.run(show_group_id())
