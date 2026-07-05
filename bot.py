import telebot
from telebot import types
import sqlite3

# ----------------- SIZNING SOZLAMALARINGIZ -----------------
TOKEN = "8836705692:AAEZt8h7HzqhHl80qeIpry6x4cPCWCi-72g"
ADMIN_ID = 7013205343  # Sizning Telegram ID raqamingiz
# -----------------------------------------------------------

bot = telebot.TeleBot(TOKEN)

# Ma'lumotlar bazasini yaratish va sozlash
def init_db():
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    # Foydalanuvchilar
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, referred_by INTEGER)''')
    # Buyurtmalar
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, channel_link TEXT, cost INTEGER, total_req INTEGER, current_count INTEGER DEFAULT 0)''')
    # Bajarilgan vazifalar
    cursor.execute('''CREATE TABLE IF NOT EXISTS completed_tasks 
                      (user_id INTEGER, task_id INTEGER, PRIMARY KEY (user_id, task_id))''')
    conn.commit()
    conn.close()

init_db()

# Asosiy menyu klaviaturasi
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 Balans", "⚡️ Ball Ishlash")
    markup.row("🚀 Nakrutka Buyurtma", "👥 Takliflar (Referal)")
    if user_id == ADMIN_ID:
        markup.row("🛠 Admin Panel")
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referred_by = None
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != user_id:
                referred_by = ref_id
                # Taklif qilgan odamga bonus (10 ball)
                cursor.execute("UPDATE users SET balance = balance + 10 WHERE id = ?", (ref_id,))
                try:
                    bot.send_message(ref_id, f"⚡️ Havolangiz orqali yangi a'zo qo'shildi! Sizga +10 ball berildi.")
                except:
                    pass
                    
        cursor.execute("INSERT INTO users (id, balance, referred_by) VALUES (?, ?, ?)", (user_id, 0, referred_by))
        conn.commit()
    
    conn.close()
    bot.send_message(user_id, "👋 Salom! Mukammal Nakrutka (Obunachilar ko'paytirish) botiga xush kelibsiz.\nKanalizga haqiqiy va o'zbek obunachilarni qo'shish uchun ball to'plang!", reply_markup=main_menu(user_id))

@bot.message_handler(func=lambda msg: msg.text == "💰 Balans")
def check_balance(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    res = cursor.fetchone()
    balance = res[0] if res else 0
    conn.close()
    bot.send_message(user_id, f"💳 Sizning hisobingiz: *{balance} ball*\n\n💡 1 ta obunachi narxi = 5 ball.", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "👥 Takliflar (Referal)")
def referral_link(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    text = f"👥 *Do'stlarni taklif qilib ball ishlang!*\n\nSizning referal havolangiz:\n`{ref_link}`\n\nHavola orqali kirgan har bir do'stingiz uchun *10 ball* olasiz!"
    bot.send_message(user_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚡️ Ball Ishlash")
def earn_points(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    
    cursor.execute('''SELECT id, channel_link, channel_id FROM tasks 
                      WHERE current_count < total_req 
                      AND id NOT IN (SELECT task_id FROM completed_tasks WHERE user_id = ?) 
                      LIMIT 1''', (user_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        bot.send_message(user_id, "😔 Hozircha bajarish uchun kanallar tugadi. Keyinroq urinib ko'ring yoki do'stlaringizni taklif qiling!")
        return
        
    task_id, link, ch_id = task
    markup = types.InlineKeyboardMarkup()
    btn_link = types.InlineKeyboardButton("📢 Kanalga o'tish", url=link)
    btn_check = types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_{task_id}_{ch_id}")
    markup.add(btn_link)
    markup.add(btn_check)
    
    bot.send_message(user_id, "⚡️ Quyidagi kanalga a'zo bo'ling va pastdagi 'Tekshirish' tugmasini bosing (A'zolik uchun 5 ball beriladi):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def verify_subscription(call):
    user_id = call.from_user.id
    _, task_id, ch_id = call.data.split("_")
    
    try:
        member = bot.get_chat_member(ch_id, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            conn = sqlite3.connect('nakrutka_pro.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM completed_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
            if cursor.fetchone():
                bot.answer_callback_query(call.id, "Siz bu kanal uchun ball olgansiz!", show_alert=True)
                conn.close()
                return
                
            cursor.execute("UPDATE users SET balance = balance + 5 WHERE id = ?", (user_id,))
            cursor.execute("UPDATE tasks SET current_count = current_count + 1 WHERE id = ?", (task_id,))
            cursor.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)", (user_id, task_id))
            conn.commit()
            conn.close()
            
            bot.edit_message_text("✅ Ajoyib! Siz kanalga muvaffaqiyatli a'zo bo'ldingiz va hamyoningizga 5 ball qo'shildi.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz! Iltimos, a'zo bo'lib keyin tekshiring.", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ Xatolik: Bot ushbu kanalda admin emas yoki kanal ommaviy (public) emas.", show_alert=True)

@bot.message_handler(func=lambda msg: msg.text == "🚀 Nakrutka Buyurtma")
def order_subscribers(message):
    user_id = message.from_user.id
    msg_text = ("🚀 *Nakrutka buyurtma berish paneli*\n\n"
                "Kanalingizga odam qo'shish uchun quyidagi formatda xabar yuboring:\n"
                "`Kanal_ID Link Obunachilar_Soni`\n\n"
                "*Masalan:* `-1002456789123 https://t.me/shaxsiy_kanal 20`\n\n"
                "⚠️ *Diqqat:* Buyurtma berishdan oldin, ushbu botni kanalingizga **Admin** qilib qo'shishingiz shart, aks holda odamlar kirganini bot tekshira olmaydi!")
    bot.send_message(user_id, msg_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: len(msg.text.split()) == 3 and not msg.text.startswith('/'))
def process_order(message):
    user_id = message.from_user.id
    parts = message.text.split()
    ch_id, link, amount = parts[0], parts[1], parts[2]
    
    if not amount.isdigit():
        bot.send_message(user_id, "❌ Obunachilar soni faqat raqamlardan iborat bo'lishi kerak!")
        return
        
    amount = int(amount)
    required_points = amount * 5
    
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < required_points:
        bot.send_message(user_id, f"❌ Balans etarli emas. Sizga {required_points} ball kerak. Hozirgi balansingiz: {balance} ball.")
        conn.close()
        return
        
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (required_points, user_id))
    cursor.execute("INSERT INTO tasks (channel_id, channel_link, cost, total_req) VALUES (?, ?, ?, ?)", (ch_id, link, 5, amount))
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, f"✅ Buyurtmangiz muvaffaqiyatli qabul qilindi! {amount} ta obunachi tez orada qo'shila boshlaydi.")

@bot.message_handler(func=lambda msg: msg.text == "🛠 Admin Panel" and msg.from_user.id == ADMIN_ID)
def admin_panel(message):
    conn = sqlite3.connect('nakrutka_pro.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM tasks WHERE current_count < total_req")
    active_tasks = cursor.fetchone()[0]
    conn.close()
    
    text = f"🛠 *Asosiy Admin Panel*\n\n👥 Bot a'zolari jami: {total_users} ta\n🚀 Hozirda faol buyurtmalar: {active_tasks} ta"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

if __name__ == '__main__':
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
  
