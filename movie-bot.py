import json
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
import difflib

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7863260940:AAGK7fCM8r7XZB1V-xS93Pz7cULEvzDotec"
CHANNEL_USERNAME = "@amiramovie"
BOT_USERNAME = "@AmirrrrrrrrrrMovieeeeeeeeeeBot"
BOT_OWNER_ID = 530232458  # Integer for consistency
MOVIE_DATA_FILE = "movies.json"

# JSON Functions
def load_movie_data():
    try:
        with open(MOVIE_DATA_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"movies": []}

def save_movie_data(data):
    try:
        with open(MOVIE_DATA_FILE, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logger.error(f"Error saving movie data: {e}")

# Channel Membership Check
async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        user_id = update.effective_user.id
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.warning(f"Membership check failed: {e}")
        return False

# START command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_member = await is_user_member(update, context)
    
    # Load movie data to display favorites
    data = load_movie_data()
    # Sort movies by rating (descending) and get top 3
    top_movies = sorted(data["movies"], key=lambda x: x.get("rating", 0), reverse=True)[:3]
    
    # Favorites section
    favorites_text = "🌟 *Top Favorite Movies*:\n"
    if top_movies:
        for i, movie in enumerate(top_movies, 1):
            rating = movie.get("rating", 0)
            favorites_text += f"{i}. {movie['title']} (Popularity: {rating})\n"
    else:
        favorites_text += "No popular movies yet. Start searching to build the list!\n"
    
    # Navigation section
    navigation_text = (
        "\n🔍 *Find Your Movie*:\n"
        f"- Use `/movie <movie_name>` to search for a movie.\n"
        f"- If suggestions appear, use `/confirm <number>` to select one.\n"
        f"- Join our channel {CHANNEL_USERNAME} and use `/verify` to unlock access."
    )
    
    # Combine sections
    welcome_message = (
        f"👋 Hello, {user.first_name}!\n"
        f"Welcome to {BOT_USERNAME}, your movie link bot!\n\n"
        f"{favorites_text}\n{navigation_text}"
    )
    
    if is_member:
        welcome_message += "\nYou're a member! Start searching with /movie."
    else:
        welcome_message += f"\nPlease join {CHANNEL_USERNAME} and use /verify to unlock full access."
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

# VERIFY command
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_member = await is_user_member(update, context)
    if is_member:
        await update.message.reply_text(
            f"✅ Verified! Welcome, {user.first_name}.\n"
            "Now you can use /movie <movie_name> to get movie links."
        )
    else:
        await update.message.reply_text(
            f"❌ You're not a member of {CHANNEL_USERNAME}.\n"
            "Please join and then use /verify again."
        )

# MOVIE command
async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.message.reply_text(
            f"🔒 Please join {CHANNEL_USERNAME} to access movie links.\n"
            "Then use /verify to unlock access."
        )
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /movie <movie_name>")
        return

    movie_name = " ".join(context.args).lower()
    data = load_movie_data()
    movie = next((m for m in data["movies"] if m["title"].lower() == movie_name), None)

    if movie:
        # Increment rating
        movie["rating"] = movie.get("rating", 0) + 1
        save_movie_data(data)
        
        text = f"🎬 *{movie['title']}* Download Links:\n\n"
        for q in movie["qualities"]:
            text += f"🔹 {q['quality']}: {q['url']}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # Fuzzy matching for suggestions
    movie_titles = [m["title"].lower() for m in data["movies"]]
    # Lower cutoff to capture more partial matches
    close_matches = difflib.get_close_matches(movie_name, movie_titles, n=3, cutoff=0.4)
    
    # Additional substring matching for partial names
    substring_matches = [title for title in movie_titles if movie_name in title]
    # Combine and deduplicate matches, prioritizing substring matches
    all_matches = list(dict.fromkeys(substring_matches + close_matches))
    
    if all_matches:
        # Store suggestions in user context for /confirm
        context.user_data["suggestions"] = [
            data["movies"][movie_titles.index(match)] for match in all_matches
        ]
        suggestions = "\n".join(
            f"{i+1}. {data['movies'][movie_titles.index(match)]['title']}"
            for i, match in enumerate(all_matches)
        )
        await update.message.reply_text(
            f"❌ No movie found with the exact name '{movie_name}'.\n"
            f"Did you mean one of these?\n{suggestions}\n\n"
            f"Use /confirm <number> to select a movie (e.g., /confirm 1)."
        )
    else:
        await update.message.reply_text(
            f"❌ No movie found with the name '{movie_name}'.\n"
            "Check the spelling or try another movie."
        )

# CONFIRM command
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.message.reply_text(
            f"🔒 Please join {CHANNEL_USERNAME} to access movie links.\n"
            "Then use /verify to unlock access."
        )
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Usage: /confirm <number>")
        return

    suggestion_index = int(context.args[0]) - 1
    suggestions = context.user_data.get("suggestions", [])

    if not suggestions or suggestion_index < 0 or suggestion_index >= len(suggestions):
        await update.message.reply_text(
            "❌ Invalid selection. Please use /movie <movie_name> to search again."
        )
        return

    movie = suggestions[suggestion_index]
    # Increment rating
    for m in load_movie_data()["movies"]:
        if m["title"].lower() == movie["title"].lower():
            m["rating"] = m.get("rating", 0) + 1
            break
    save_movie_data(load_movie_data())
    
    text = f"🎬 *{movie['title']}* Download Links:\n\n"
    for q in movie["qualities"]:
        text += f"🔹 {q['quality']}: {q['url']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")
    # Clear suggestions after confirmation
    context.user_data["suggestions"] = []

# ADDMOVIE command
async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("⛔ Only the bot owner can use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /addmovie <movie_name> <quality1>:<url1> [<quality2>:<url2> ...]")
        return

    movie_name = context.args[0]
    qualities = []

    for entry in context.args[1:]:
        if ":" not in entry:
            await update.message.reply_text(f"❌ Invalid format: {entry}. Use quality:url")
            return
        quality, url = entry.split(":", 1)
        if not url.startswith(("http://", "https://")):
            await update.message.reply_text(f"❌ Invalid URL: {url}")
            return
        qualities.append({"quality": quality, "url": url})

    data = load_movie_data()
    for movie in data["movies"]:
        if movie["title"].lower() == movie_name.lower():
            movie["qualities"].extend(qualities)
            break
    else:
        # Initialize new movie with rating=0
        data["movies"].append({"title": movie_name, "qualities": qualities, "rating": 0})

    save_movie_data(data)
    await update.message.reply_text(f"✅ Movie '{movie_name}' added/updated.")

# Main function
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("movie", movie))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("addmovie", add_movie))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()