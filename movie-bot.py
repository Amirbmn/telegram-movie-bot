import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
BOT_OWNER_ID = 530232458
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

# Helper function to calculate average rating
def calculate_average_rating(movie):
    ratings = movie.get("ratings", [])
    if not ratings:
        return 0
    return sum(ratings) / len(ratings)

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
    
    # Load movie data to display top-rated movies
    data = load_movie_data()
    
    # Calculate average ratings and get top 3
    movies_with_ratings = []
    for movie in data["movies"]:
        avg_rating = calculate_average_rating(movie)
        if avg_rating > 0:  # Only include movies with ratings
            movies_with_ratings.append((movie, avg_rating))
    
    # Sort by average rating (descending) and get top 3
    top_movies = sorted(movies_with_ratings, key=lambda x: x[1], reverse=True)[:3]
    
    # Create welcome message
    welcome_message = (
        f"🎬 Welcome to {BOT_USERNAME}!\n"
        f"Hello {user.first_name}, find and rate your favorite movies!\n\n"
    )
    
    # Add top-rated movies section
    if top_movies:
        welcome_message += "⭐ *Top Rated Movies*:\n"
        for i, (movie, avg_rating) in enumerate(top_movies, 1):
            stars = "⭐" * int(round(avg_rating))
            welcome_message += f"{i}. {movie['title']} {stars} ({avg_rating:.1f}/5)\n"
        welcome_message += "\n"
    else:
        welcome_message += "🌟 No rated movies yet. Be the first to rate!\n\n"
    
    # Add instructions
    welcome_message += (
        "🔍 *How to use*:\n"
        "• Use `/movie <movie_name>` to search for movies\n"
        "• Rate movies using the star buttons after downloading\n"
        "• Join our channel for full access\n\n"
    )
    
    if is_member:
        welcome_message += "✅ You're verified! Start searching with /movie"
    else:
        welcome_message += f"📢 Join {CHANNEL_USERNAME} and use /verify to get started"
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

# VERIFY command
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_member = await is_user_member(update, context)
    
    if is_member:
        await update.message.reply_text(
            f"✅ Verified! Welcome {user.first_name}!\n"
            "You can now use /movie <movie_name> to search for movies.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ You're not a member of {CHANNEL_USERNAME} yet.\n"
            "Please join our channel first, then use /verify again.",
            parse_mode="Markdown"
        )

# Create rating buttons
def create_rating_buttons(movie_title):
    keyboard = []
    row = []
    for i in range(1, 6):
        star_text = "⭐"*i
        row.append(InlineKeyboardButton(
            f"{star_text} {i}",
            callback_data=f"rate_{movie_title}_{i}"
        ))
    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# MOVIE command
async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.message.reply_text(
            f"🔒 Access restricted!\n"
            f"Join {CHANNEL_USERNAME} and use /verify to unlock movie access.",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Please specify a movie name!\n"
            "Usage: `/movie <movie_name>`",
            parse_mode="Markdown"
        )
        return

    movie_name = " ".join(context.args).lower()
    data = load_movie_data()
    
    # Find exact match
    movie = next((m for m in data["movies"] if m["title"].lower() == movie_name), None)

    if movie:
        # Show movie details with download links
        avg_rating = calculate_average_rating(movie)
        rating_count = len(movie.get("ratings", []))
        
        stars_display = "⭐" * int(round(avg_rating)) if avg_rating > 0 else "No ratings yet"
        
        text = (
            f"🎬 *{movie['title']}*\n"
            f"Rating: {stars_display} ({avg_rating:.1f}/5 from {rating_count} users)\n\n"
            f"📥 *Download Links*:\n"
        )
        
        for quality in movie["qualities"]:
            text += f"🔹 {quality['quality']}: {quality['url']}\n"
        
        text += "\n💫 Rate this movie below:"
        
        reply_markup = create_rating_buttons(movie['title'])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        return

    # Fuzzy matching for suggestions
    movie_titles = [m["title"].lower() for m in data["movies"]]
    close_matches = difflib.get_close_matches(movie_name, movie_titles, n=3, cutoff=0.4)
    
    # Substring matching for partial names
    substring_matches = [title for title in movie_titles if movie_name in title]
    
    # Combine and deduplicate matches
    all_matches = list(dict.fromkeys(substring_matches + close_matches))
    
    if all_matches:
        # Store suggestions for /confirm command
        context.user_data["suggestions"] = [
            next(m for m in data["movies"] if m["title"].lower() == match) 
            for match in all_matches
        ]
        
        suggestions = "\n".join(
            f"{i+1}. {next(m for m in data['movies'] if m['title'].lower() == match)['title']}"
            for i, match in enumerate(all_matches)
        )
        
        await update.message.reply_text(
            f"🔍 No exact match for '*{movie_name}*'\n\n"
            f"Did you mean:\n{suggestions}\n\n"
            f"Use `/confirm <number>` to select (e.g., `/confirm 1`)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ No movie found matching '*{movie_name}*'\n"
            "Please check the spelling or try a different title.",
            parse_mode="Markdown"
        )

# CONFIRM command
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.message.reply_text(
            f"🔒 Access restricted!\n"
            f"Join {CHANNEL_USERNAME} and use /verify first.",
            parse_mode="Markdown"
        )
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "⚠️ Please specify a valid number!\n"
            "Usage: `/confirm <number>`",
            parse_mode="Markdown"
        )
        return

    suggestion_index = int(context.args[0]) - 1
    suggestions = context.user_data.get("suggestions", [])

    if not suggestions or suggestion_index < 0 or suggestion_index >= len(suggestions):
        await update.message.reply_text(
            "❌ Invalid selection or no suggestions available.\n"
            "Please use `/movie <movie_name>` to search again.",
            parse_mode="Markdown"
        )
        return

    movie = suggestions[suggestion_index]
    avg_rating = calculate_average_rating(movie)
    rating_count = len(movie.get("ratings", []))
    
    stars_display = "⭐" * int(round(avg_rating)) if avg_rating > 0 else "No ratings yet"
    
    text = (
        f"🎬 *{movie['title']}*\n"
        f"Rating: {stars_display} ({avg_rating:.1f}/5 from {rating_count} users)\n\n"
        f"📥 *Download Links*:\n"
    )
    
    for quality in movie["qualities"]:
        text += f"🔹 {quality['quality']}: {quality['url']}\n"
    
    text += "\n💫 Rate this movie below:"
    
    reply_markup = create_rating_buttons(movie['title'])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    
    # Clear suggestions after confirmation
    context.user_data["suggestions"] = []

# Handle rating button callbacks
async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: rate_movie_title_rating
    callback_parts = query.data.split("_", 2)
    if len(callback_parts) != 3 or callback_parts[0] != "rate":
        await query.edit_message_text("❌ Invalid rating data.")
        return
    
    movie_title = callback_parts[1]
    rating = int(callback_parts[2])
    user_id = update.effective_user.id
    
    # Load data and find movie
    data = load_movie_data()
    movie = next((m for m in data["movies"] if m["title"] == movie_title), None)
    
    if not movie:
        await query.edit_message_text("❌ Movie not found.")
        return
    
    # Initialize ratings list if not exists
    if "ratings" not in movie:
        movie["ratings"] = []
    if "user_ratings" not in movie:
        movie["user_ratings"] = {}
    
    # Check if user already rated this movie
    if str(user_id) in movie["user_ratings"]:
        # Update existing rating
        old_rating = movie["user_ratings"][str(user_id)]
        movie["ratings"].remove(old_rating)
        movie["ratings"].append(rating)
        movie["user_ratings"][str(user_id)] = rating
        action = "updated"
    else:
        # Add new rating
        movie["ratings"].append(rating)
        movie["user_ratings"][str(user_id)] = rating
        action = "added"
    
    # Save data
    save_movie_data(data)
    
    # Calculate new average
    avg_rating = calculate_average_rating(movie)
    rating_count = len(movie["ratings"])
    stars_display = "⭐" * rating
    
    await query.edit_message_text(
        f"✅ Rating {action}!\n\n"
        f"🎬 *{movie['title']}*\n"
        f"Your rating: {stars_display} ({rating}/5)\n"
        f"Average rating: ⭐ {avg_rating:.1f}/5 from {rating_count} users\n\n"
        f"Thank you for rating! 🎭",
        parse_mode="Markdown"
    )

# ADDMOVIE command (Owner only)
async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("⛔ This command is restricted to the bot owner.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Invalid format!\n"
            "Usage: `/addmovie <movie_name> <quality1>:<url1> [<quality2>:<url2> ...]`",
            parse_mode="Markdown"
        )
        return

    movie_name = context.args[0]
    qualities = []

    for entry in context.args[1:]:
        if ":" not in entry:
            await update.message.reply_text(f"❌ Invalid format: `{entry}`\nUse: quality:url", parse_mode="Markdown")
            return
        
        quality, url = entry.split(":", 1)
        if not url.startswith(("http://", "https://")):
            await update.message.reply_text(f"❌ Invalid URL: `{url}`", parse_mode="Markdown")
            return
        
        qualities.append({"quality": quality, "url": url})

    data = load_movie_data()
    
    # Check if movie already exists
    existing_movie = next((m for m in data["movies"] if m["title"].lower() == movie_name.lower()), None)
    
    if existing_movie:
        # Add qualities to existing movie
        existing_movie["qualities"].extend(qualities)
        await update.message.reply_text(f"✅ Updated movie '*{movie_name}*' with new qualities.", parse_mode="Markdown")
    else:
        # Create new movie
        new_movie = {
            "title": movie_name,
            "qualities": qualities,
            "ratings": [],
            "user_ratings": {}
        }
        data["movies"].append(new_movie)
        await update.message.reply_text(f"✅ Added new movie '*{movie_name}*' successfully!", parse_mode="Markdown")

    save_movie_data(data)

# Main function
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("movie", movie))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("addmovie", add_movie))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern="^rate_"))

    logger.info("🎬 Movie Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()