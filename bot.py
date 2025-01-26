import os
import telebot
import yt_dlp

# Configuration
API_TOKEN = '<YOUR_BOT_API_TOKEN>'
MAX_FILE_SIZE = 1.9 * 1024 * 1024 * 1024  # 1.9 GB in bytes

bot = telebot.TeleBot(API_TOKEN)
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Bot started...")
    print("Ch: @darks1ders")
    print("Dev: @s4rrar")
    
def download_youtube_content(url, is_audio=False):
    """
    Download YouTube content with file size check and error handling
    
    Args:
        url (str): YouTube video URL
        is_audio (bool): Whether to download audio or video
    
    Returns:
        str or None: Path to downloaded file or None if download fails
    """
    try:
        # Check URL validity first
        if not url.startswith(('http://', 'https://')):
            return None

        # Retrieve file info to check size
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            filesize = info_dict.get('filesize', None) or info_dict.get('filesize_approx', None)

            if filesize and filesize > MAX_FILE_SIZE:
                return None

        # Download configurations
        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': '%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': '%(title)s.%(ext)s',
                'merge_output_format': 'mp4',
            }

        # Download the content
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Get the downloaded filename
        info_dict = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info_dict)
        filename = filename.replace(filename.split('.')[-1], 'mp3' if is_audio else 'mp4')
        clear_screen()
        return filename
    except Exception as e:
        print(f"Error downloading: {e}")
        return None

@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    """Welcome message with bot instructions"""
    welcome_text = """
Hi there! I'm iiMeow Video Downloader 🐈

I can help you download YouTube videos and audio:
• /audio [YouTube URL] - Download audio
• /video [YouTube URL] - Download video

Examples:
/audio https://youtube.com/iiMeowVideoExample
/video https://youtube.com/iiMeowVideoExample

Follow our channels on Telegram:
» @darks1ders
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.text.startswith(('/audio', '/video')))
def handle_download(message):
    """Handle audio and video download requests"""
    try:
        # Extract URL from message
        command, url = message.text.split(maxsplit=1)
        is_audio = command == '/audio'

        # Send initial processing message
        processing_msg = bot.reply_to(message, "Processing your request... 🔄")

        # Download the content
        filename = download_youtube_content(url, is_audio)

        if filename and os.path.exists(filename):
            # Open the file and send it
            with open(filename, 'rb') as file:
                if is_audio:
                    bot.send_audio(message.chat.id, file)
                else:
                    bot.send_video(message.chat.id, file)

            # Delete the local file after sending
            os.remove(filename)
            bot.delete_message(message.chat.id, processing_msg.message_id)
        else:
            bot.edit_message_text(
                "❌ Download failed. Possible reasons:\n"
                "• Invalid URL\n"
                "• File size exceeds 1.9 GB\n"
                "• Network issues",
                message.chat.id, 
                processing_msg.message_id
            )
        clear_screen()
    except ValueError:
        bot.reply_to(message, "❌ Please provide a valid YouTube URL after the command.")
    except Exception as e:
        bot.reply_to(message, f"An unexpected error occurred: {e}")

# Start the bot
clear_screen()
bot.infinity_polling()