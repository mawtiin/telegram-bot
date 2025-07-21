import os
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]

app = Client("bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
user_state = {}

CFG = "config.json"
PENDING_FILE = "pending_post.json"
MEDIA_FILE = "temp_media"

def back_menu(to="main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back_to_main" if to == "main" else "manage_sources")]])

@app.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_panel(client, message: Message):
    buttons = [
        [InlineKeyboardButton("Manage Source Channels", callback_data="manage_sources")],
        [InlineKeyboardButton("Change Target Channel", callback_data="set_target")],
        [InlineKeyboardButton("Check Pending Post", callback_data="check_post")],
        [InlineKeyboardButton("Clear Queue", callback_data="clear_queue")]
    ]
    await message.reply("Bot Management Panel:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("back_to_main"))
async def back_main(client, cb: CallbackQuery):
    await start_panel(client, cb.message)

@app.on_callback_query(filters.regex("manage_sources"))
async def manage_sources(client, cb: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("Add Source", callback_data="add_source")],
        [InlineKeyboardButton("Remove Source", callback_data="remove_source")],
        [InlineKeyboardButton("List Sources", callback_data="list_sources")],
        [InlineKeyboardButton("Back", callback_data="back_to_main")]
    ]
    await cb.message.edit_text("Manage Source Channels:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("list_sources"))
async def list_sources(client, cb: CallbackQuery):
    if not os.path.exists(CFG):
        await cb.message.edit_text("No channels in list.", reply_markup=back_menu("sources"))
        return
    with open(CFG, "r") as f:
        cfg = json.load(f)
    sources = cfg.get("default_sources", [])
    text = "Source Channels:\n" + "\\n".join([f"- {ch}" for ch in sources]) if sources else "No channels in list."

text = "Source Channels:\n" + ("\n".join([f"- {ch}" for ch in sources]) if sources else "No channels in list.")
    await cb.message.edit_text(text, reply_markup=back_menu("sources"))

@app.on_callback_query(filters.regex("add_source"))
async def ask_add(client, cb: CallbackQuery):
    user_state[cb.from_user.id] = "add"
    await cb.message.edit_text("Send the channel ID to add:", reply_markup=back_menu("sources"))

@app.on_callback_query(filters.regex("remove_source"))
async def ask_remove(client, cb: CallbackQuery):
    user_state[cb.from_user.id] = "remove"
    await cb.message.edit_text("Send the channel ID to remove:", reply_markup=back_menu("sources"))

@app.on_callback_query(filters.regex("set_target"))
async def ask_target(client, cb: CallbackQuery):
    user_state[cb.from_user.id] = "target"
    await cb.message.edit_text("Send the target channel ID:", reply_markup=back_menu("main"))

@app.on_message(filters.private & filters.user(ADMIN_IDS) & filters.text)
async def handle_input(client, msg: Message):
    action = user_state.get(msg.from_user.id)
    if not action:
        return
    value = msg.text.strip()
    cfg = {}
    if os.path.exists(CFG):
        with open(CFG, "r") as f:
            cfg = json.load(f)

    if action == "add":
        cfg.setdefault("default_sources", [])
        if value not in cfg["default_sources"]:
            cfg["default_sources"].append(value)
            await msg.reply(f"{value} added.")
        else:
            await msg.reply("Already in list.")
    elif action == "remove":
        if value in cfg.get("default_sources", []):
            cfg["default_sources"].remove(value)
            await msg.reply(f"{value} removed.")
        else:
            await msg.reply("Channel not found.")
    elif action == "target":
        cfg["target_channel"] = value
        await msg.reply(f"Target channel set to: {value}")

    with open(CFG, "w") as f:
        json.dump(cfg, f, indent=4)
    user_state.pop(msg.from_user.id)

@app.on_callback_query(filters.regex("check_post"))
async def check_post(client, cb: CallbackQuery):
    if not os.path.exists(PENDING_FILE):
        await cb.message.edit_text("No post pending.", reply_markup=back_menu())
        return
    with open(PENDING_FILE, "r") as f:
        data = json.load(f)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Approve", callback_data="approve"),
         InlineKeyboardButton("Schedule", callback_data="schedule"),
         InlineKeyboardButton("Reject", callback_data="reject")]
    ])
    if data.get("has_media") and os.path.exists(MEDIA_FILE):
        await client.send_document(cb.from_user.id, MEDIA_FILE, caption=data["caption"], reply_markup=kb)
    else:
        await client.send_message(cb.from_user.id, data["caption"], reply_markup=kb)

@app.on_callback_query(filters.regex("approve"))
async def approve_post(client, cb: CallbackQuery):
    if not os.path.exists(PENDING_FILE):
        return
    with open(CFG) as f: cfg = json.load(f)
    with open(PENDING_FILE) as f: post = json.load(f)
    if post.get("has_media") and os.path.exists(MEDIA_FILE):
        await client.send_document(cfg["target_channel"], MEDIA_FILE, caption=post["caption"])
        os.remove(MEDIA_FILE)
    else:
        await client.send_message(cfg["target_channel"], post["caption"])
    os.remove(PENDING_FILE)
    await cb.message.edit_text("Post sent.")

@app.on_callback_query(filters.regex("reject"))
async def reject_post(client, cb: CallbackQuery):
    if os.path.exists(PENDING_FILE): os.remove(PENDING_FILE)
    if os.path.exists(MEDIA_FILE): os.remove(MEDIA_FILE)
    await cb.message.edit_text("Post rejected.")

@app.on_callback_query(filters.regex("clear_queue"))
async def clear_queue(client, cb: CallbackQuery):
    removed = False
    if os.path.exists(PENDING_FILE): os.remove(PENDING_FILE); removed = True
    if os.path.exists(MEDIA_FILE): os.remove(MEDIA_FILE); removed = True
    await cb.message.edit_text("Queue cleared." if removed else "Nothing to clear.", reply_markup=back_menu())

@app.on_callback_query(filters.regex("schedule"))
async def ask_schedule(client, cb: CallbackQuery):
    user_state[cb.from_user.id] = "delay"
    await cb.message.edit_text("How many minutes to delay? Send a number:")

@app.on_message(filters.user(ADMIN_IDS) & filters.text)
async def schedule_msg(client, msg: Message):
    if user_state.get(msg.from_user.id) != "delay":
        return
    try:
        mins = int(msg.text.strip())
        await msg.reply(f"Post will be sent in {mins} minutes...")
        await asyncio.sleep(mins * 60)
        with open(CFG) as f: cfg = json.load(f)
        with open(PENDING_FILE) as f: post = json.load(f)
        if post.get("has_media") and os.path.exists(MEDIA_FILE):
            await client.send_document(cfg["target_channel"], MEDIA_FILE, caption=post["caption"])
            os.remove(MEDIA_FILE)
        else:
            await client.send_message(cfg["target_channel"], post["caption"])
        os.remove(PENDING_FILE)
    except:
        await msg.reply("Error during scheduling.")
    user_state.pop(msg.from_user.id)

app.run()
