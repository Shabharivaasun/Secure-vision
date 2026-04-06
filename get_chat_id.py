import telebot

BOT_TOKEN = '7394832342:AAHwo_Q_nanv2F8Tet86W7aN7Qrpa8yDw5o'
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def get_chat_id(message):
    print("Chat ID:", message.chat.id)

bot.polling()
