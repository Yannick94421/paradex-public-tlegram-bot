from paradex.market import get_bbo, get_orderbook, get_trades
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import os
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN is None:
    raise ValueError("TELEGRAM_TOKEN environment variable not set")



async def cmd_get_bbo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get_bbo <market>")
        return
    market = context.args[0]
    bbo = await get_bbo(market)
    await update.message.reply_text(f"BBO for {market}: {bbo}")

async def cmd_get_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get_trades <market> [limit]")
        return
    market = context.args[0]
    limit = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 5
    trades = await get_trades(market, limit=limit)
    await update.message.reply_text(f"Trades for {market} (limit={limit}): {trades}")

    
async def cmd_get_orderbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get_orderbook <market>")
        return
    market = context.args[0]
    orderbook = await get_orderbook(market)
    await update.message.reply_text(f"Orderbook for {market}: {orderbook}")

import asyncio

# Dictionnaire pour stocker les tâches de surveillance par utilisateur
watch_tasks = {}

async def watch_bbo_task(chat_id, markets, update):
    last_bbos = {market: None for market in markets}
    while True:
        for market in markets:
            bbo = await get_bbo(market)
            last_bbo = last_bbos[market]
            if last_bbo is None or bbo.get('bid') != last_bbo.get('bid') or bbo.get('ask') != last_bbo.get('ask'):
                await update.message.reply_text(f"Nouveau BBO pour {market}: {bbo}")
                last_bbos[market] = bbo
        await asyncio.sleep(10)

async def cmd_watch_bbo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch_bbo <market1> <market2> ...")
        return
    markets = context.args
    chat_id = update.effective_chat.id

    # Stoppe la surveillance précédente si elle existe
    if chat_id in watch_tasks:
        watch_tasks[chat_id].cancel()

    # Lance la nouvelle surveillance
    task = asyncio.create_task(watch_bbo_task(chat_id, markets, update))
    watch_tasks[chat_id] = task
    await update.message.reply_text(f"Surveillance des BBO pour {', '.join(markets)} (notifications toutes les 5s si changement)...")

async def cmd_stop_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in watch_tasks:
        watch_tasks[chat_id].cancel()
        del watch_tasks[chat_id]
        await update.message.reply_text("Surveillance BBO arrêtée.")
    else:
        await update.message.reply_text("Aucune surveillance en cours.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("get_bbo", cmd_get_bbo))
    app.add_handler(CommandHandler("get_trades", cmd_get_trades))
    app.add_handler(CommandHandler("get_orderbook", cmd_get_orderbook))
    app.add_handler(CommandHandler("watch_bbo", cmd_watch_bbo))
    app.add_handler(CommandHandler("stop_watch", cmd_stop_watch))
    app.run_polling()


if __name__ == "__main__":
    main()