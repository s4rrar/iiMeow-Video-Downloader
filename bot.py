import os
import telebot
import yt_dlp
import threading
from queue import Queue
from urllib.parse import urlparse, parse_qs
import math
import subprocess
from datetime import datetime

# Configuration
API_TOKEN = "<YOUR_BOT_API_TOKEN>"
MAX_TELEGRAM_SIZE = 50 * 1024 * 1024  # 50 MB in bytes
MAX_FILE_SIZE = 1.9 * 1024 * 1024 * 1024  # 1.9 GB in bytes
MAX_CONCURRENT_DOWNLOADS = 5  # Maximum concurrent downloads
MAX_QUEUE_SIZE = 50  # Maximum number of users in queue

# Thread-safe queues and tracking
download_queue = Queue()
waiting_queue = Queue(maxsize=MAX_QUEUE_SIZE)
user_downloads = {}  # Stores (message_id, cancel_event) tuple
download_lock = threading.Lock()
queue_lock = threading.Lock()

bot = telebot.TeleBot(API_TOKEN)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")
    print("Bot started...")
    print("Ch: @darks1ders")
    print("Dev: @s4rrar")


def check_file_size(url):
    """Check if the file size is within limits before downloading"""
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("filesize"):
                return info["filesize"] <= MAX_FILE_SIZE
            # If filesize not available, check formatted size
            formats = info.get("formats", [])
            max_size = 0
            for f in formats:
                if f.get("filesize"):
                    max_size = max(max_size, f["filesize"])
            return max_size <= MAX_FILE_SIZE
    except:
        return True  # If size check fails, allow download attempt


def process_waiting_queue():
    """Process users in waiting queue when a slot becomes available"""
    with queue_lock:
        if not waiting_queue.empty() and len(user_downloads) < MAX_CONCURRENT_DOWNLOADS:
            try:
                task = waiting_queue.get_nowait()
                user_id, message, url, is_audio, cancel_event = task

                # Notify user their download is starting
                bot.edit_message_text(
                    "Your turn has arrived! Starting download... 🔄",
                    message.chat.id,
                    message.message_id,
                )

                # Add to active downloads
                with download_lock:
                    user_downloads[user_id] = (message.message_id, cancel_event)

                # Add to download queue
                download_queue.put(task)

                return True
            except:
                return False
    return False


def extract_video_id(url):
    """Extract the video ID from a YouTube URL, ignoring playlist parameters"""
    parsed_url = urlparse(url)
    if parsed_url.hostname in ("www.youtube.com", "youtube.com", "youtu.be"):
        if parsed_url.hostname in ("www.youtube.com", "youtube.com"):
            video_id = parse_qs(parsed_url.query).get("v", [None])[0]
        else:  # youtu.be
            video_id = parsed_url.path[1:]
        return video_id
    return None


def get_clean_video_url(url):
    """Convert any YouTube URL to a clean video-only URL"""
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def get_media_duration(filename):
    """Get media duration using ffprobe"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filename,
    ]
    try:
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except:
        return None


def split_audio(input_file, max_size=MAX_TELEGRAM_SIZE):
    """Split an audio file into parts that fit within Telegram's size limit"""
    if not os.path.exists(input_file):
        return []

    file_size = os.path.getsize(input_file)
    if file_size <= max_size:
        return [input_file]

    duration = get_media_duration(input_file)
    if not duration:
        return []

    # Calculate number of parts needed with conservative sizing
    safe_max_size = 45 * 1024 * 1024  # 45MB
    num_parts = math.ceil(file_size / safe_max_size)
    segment_duration = duration / num_parts

    output_files = []
    for i in range(num_parts):
        start_time = i * segment_duration
        output_file = f"{input_file[:-4]}_part{i+1}.mp3"

        cmd = [
            "ffmpeg",
            "-i",
            input_file,
            "-ss",
            str(start_time),
            "-t",
            str(segment_duration),
            "-c:a",
            "libmp3lame",  # Use MP3 codec
            "-b:a",
            "192k",  # Set audio bitrate
            output_file,
            "-y",
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                if os.path.getsize(output_file) > safe_max_size:
                    # If still too large, try again with lower bitrate
                    cmd[5] = "128k"  # Reduce audio bitrate
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if (
                    os.path.exists(output_file)
                    and os.path.getsize(output_file) <= MAX_TELEGRAM_SIZE
                ):
                    output_files.append(output_file)
                else:
                    os.remove(output_file)  # Clean up failed attempt
        except Exception as e:
            print(f"Error splitting audio: {e}")
            if os.path.exists(output_file):
                os.remove(output_file)

    return output_files


def split_video(input_file, max_size=MAX_TELEGRAM_SIZE):
    """Split a video file into parts that fit within Telegram's size limit"""
    if not os.path.exists(input_file):
        return []

    file_size = os.path.getsize(input_file)
    if file_size <= max_size:
        return [input_file]

    duration = get_media_duration(input_file)
    if not duration:
        return []

    safe_max_size = 45 * 1024 * 1024  # 45MB
    num_parts = math.ceil(file_size / safe_max_size)
    segment_duration = duration / num_parts

    output_files = []
    for i in range(num_parts):
        start_time = i * segment_duration
        output_file = f"{input_file[:-4]}_part{i+1}.mp4"

        cmd = [
            "ffmpeg",
            "-i",
            input_file,
            "-ss",
            str(start_time),
            "-t",
            str(segment_duration),
            "-c:v",
            "libx264",
            "-b:v",
            "1500k",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-max_muxing_queue_size",
            "1024",
            output_file,
            "-y",
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                if os.path.getsize(output_file) > safe_max_size:
                    cmd[8] = "750k"  # Reduce video bitrate
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if (
                    os.path.exists(output_file)
                    and os.path.getsize(output_file) <= MAX_TELEGRAM_SIZE
                ):
                    output_files.append(output_file)
                else:
                    os.remove(output_file)
        except Exception as e:
            print(f"Error splitting video: {e}")
            if os.path.exists(output_file):
                os.remove(output_file)

    return output_files


def download_youtube_content(url, is_audio=False, cancel_event=None):
    """Download YouTube content with progress updates and cancellation support"""
    try:
        if not url.startswith(("http://", "https://")):
            return None

        # Download configurations
        if is_audio:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "%(title)s.%(ext)s",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        else:
            ydl_opts = {
                "format": "best[ext=mp4]/best",  # Simplified format selection
                "outtmpl": "%(title)s.%(ext)s",
            }

        if cancel_event and cancel_event.is_set():
            return None

        # Download the content
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Get the downloaded filename
        info_dict = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info_dict)
        filename = filename.replace(
            filename.split(".")[-1], "mp3" if is_audio else "mp4"
        )
        clear_screen()
        return filename
    except Exception as e:
        print(f"Error downloading: {e}")
        return None


def download_worker():
    """Background worker to process download queue"""
    while True:
        task = download_queue.get()

        try:
            user_id, message, url, is_audio, cancel_event = task

            # Check file size before downloading
            if not check_file_size(url):
                bot.edit_message_text(
                    "❌ File size exceeds 1.9GB limit. Please choose a smaller video.",
                    message.chat.id,
                    message.message_id,
                )
                continue

            original_url = url
            url = get_clean_video_url(url)
            if original_url != url:
                bot.edit_message_text(
                    "📋 Playlist detected, downloading single video...",
                    message.chat.id,
                    message.message_id,
                )

            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", "Unknown Title")

                bot.edit_message_text(
                    f"⏳ Downloading: {video_title}...",
                    message.chat.id,
                    message.message_id,
                )

            if cancel_event.is_set():
                bot.edit_message_text(
                    "❌ Download cancelled.", message.chat.id, message.message_id
                )
                continue

            filename = download_youtube_content(url, is_audio, cancel_event)

            if cancel_event.is_set():
                if filename and os.path.exists(filename):
                    os.remove(filename)
                bot.edit_message_text(
                    "❌ Download cancelled.", message.chat.id, message.message_id
                )
            elif filename and os.path.exists(filename):
                try:
                    file_size = os.path.getsize(filename)

                    if file_size > MAX_TELEGRAM_SIZE:
                        bot.edit_message_text(
                            f"📦 File is too large for Telegram. Splitting into parts...\n⏳ Please be patient, it may take time.",
                            message.chat.id,
                            message.message_id,
                        )

                        # Choose appropriate splitting function based on content type
                        parts = (
                            split_audio(filename) if is_audio else split_video(filename)
                        )
                        total_parts = len(parts)

                        if total_parts == 0:
                            bot.edit_message_text(
                                f"❌ Error splitting {'audio' if is_audio else 'video'}. File might be corrupted.",
                                message.chat.id,
                                message.message_id,
                            )
                            if os.path.exists(filename):
                                os.remove(filename)
                            return

                        for i, part in enumerate(parts, 1):
                            if cancel_event.is_set():
                                break

                            bot.edit_message_text(
                                f"📤 Sending part {i}/{total_parts}...",
                                message.chat.id,
                                message.message_id,
                            )

                            with open(part, "rb") as file:
                                caption = f"{video_title} - Part {i}/{total_parts}"
                                if is_audio:
                                    bot.send_audio(
                                        message.chat.id, file, caption=caption
                                    )
                                else:
                                    bot.send_video(
                                        message.chat.id, file, caption=caption
                                    )

                            os.remove(part)

                        os.remove(filename)

                        if not cancel_event.is_set():
                            bot.edit_message_text(
                                f"✅ Download completed: {video_title}\nSent in {total_parts} parts",
                                message.chat.id,
                                message.message_id,
                            )
                    else:
                        with open(filename, "rb") as file:
                            if is_audio:
                                bot.send_audio(
                                    message.chat.id, file, caption=video_title
                                )
                            else:
                                bot.send_video(
                                    message.chat.id, file, caption=video_title
                                )

                        os.remove(filename)
                        bot.edit_message_text(
                            f"✅ Download completed: {video_title}",
                            message.chat.id,
                            message.message_id,
                        )
                except Exception as send_error:
                    bot.edit_message_text(
                        f"❌ Error sending file: {send_error}",
                        message.chat.id,
                        message.message_id,
                    )
                    if os.path.exists(filename):
                        os.remove(filename)
            else:
                bot.edit_message_text(
                    "❌ Download failed. Possible reasons:\n"
                    "• Invalid URL\n"
                    "• Network issues\n"
                    "• Video unavailable",
                    message.chat.id,
                    message.message_id,
                )
        except Exception as e:
            bot.reply_to(message, f"An unexpected error occurred: {e}")
        finally:
            with download_lock:
                if user_id in user_downloads:
                    user_downloads.pop(user_id, None)

            download_queue.task_done()

            # Process next user in waiting queue
            process_waiting_queue()


@bot.message_handler(commands=["queue"])
def check_queue_position(message):
    """Allow users to check their position in the queue"""
    user_id = message.from_user.id

    # Check if user is in active downloads
    if user_id in user_downloads:
        bot.reply_to(message, "Your download is currently in progress! ⏳")
        return

    # Check waiting queue
    position = 1
    found = False
    temp_queue = Queue()

    while not waiting_queue.empty():
        task = waiting_queue.get()
        if task[0] == user_id:
            found = True
        temp_queue.put(task)
        if not found:
            position += 1

    # Restore queue
    while not temp_queue.empty():
        waiting_queue.put(temp_queue.get())

    if found:
        bot.reply_to(
            message, f"You are position #{position} in the queue. Please wait... ⌛"
        )
    else:
        bot.reply_to(message, "You are not currently in the queue.")


@bot.message_handler(commands=["cancel"])
def cancel_download(message):
    """Handle download cancellation requests"""
    user_id = message.from_user.id

    with download_lock:
        if user_id not in user_downloads:
            bot.reply_to(message, "❌ You don't have any active downloads to cancel.")
            return

        message_id, cancel_event = user_downloads[user_id]
        cancel_event.set()
        bot.reply_to(message, "🛑 Cancelling your download...")


@bot.message_handler(commands=["help", "start"])
def send_welcome(message):
    """Welcome message with bot instructions"""
    welcome_text = """
Hi there! I'm iiMeow Video Downloader 🐈

I can help you download YouTube videos and audio:
• /audio [YouTube URL] - Download audio
• /video [YouTube URL] - Download video
• /cancel - Cancel your current download
• /queue - Check your position in queue

Note: 
- Large videos will be split into parts due to Telegram's size limit
- Maximum file size: 1.9GB
- If the system is busy, you'll be placed in a queue

Examples:
/audio https://youtube.com/iiMeowVideoExample
/video https://youtube.com/iiMeowVideoExample

Follow our channels on Telegram:
» @darks1ders
"""
    bot.reply_to(message, welcome_text)


@bot.message_handler(func=lambda message: message.text.startswith(("/audio", "/video")))
def handle_download(message):
    """Handle audio and video download requests"""
    try:
        command, url = message.text.split(maxsplit=1)
        is_audio = command == "/audio"
        user_id = message.from_user.id

        # Check for ongoing downloads
        with download_lock:
            if user_id in user_downloads:
                bot.reply_to(
                    message,
                    "❌ You already have a download in progress. Use /cancel to stop it.",
                )
                return

        # Create cancellation event and processing message
        cancel_event = threading.Event()
        processing_msg = bot.reply_to(message, "Processing your request... 🔄")

        # Check if there's room for immediate processing
        with download_lock:
            if len(user_downloads) < MAX_CONCURRENT_DOWNLOADS:
                user_downloads[user_id] = (processing_msg.message_id, cancel_event)
                download_queue.put(
                    (user_id, processing_msg, url, is_audio, cancel_event)
                )
            else:
                # Try to add to waiting queue
                try:
                    waiting_queue.put_nowait(
                        (user_id, processing_msg, url, is_audio, cancel_event)
                    )
                    queue_position = waiting_queue.qsize()
                    bot.edit_message_text(
                        f"Queue is full. You are position #{queue_position} in line.\n"
                        f"Use /queue to check your position.\n"
                        f"Your download will start automatically when it's your turn.",
                        processing_msg.chat.id,
                        processing_msg.message_id,
                    )
                except Queue.Full:
                    bot.edit_message_text(
                        "❌ Sorry, the waiting queue is full. Please try again later.",
                        processing_msg.chat.id,
                        processing_msg.message_id,
                    )

    except ValueError:
        bot.reply_to(
            message, "❌ Please provide a valid YouTube URL after the command."
        )
    except Exception as e:
        bot.reply_to(message, f"An unexpected error occurred: {e}")


# Start download workers
for _ in range(MAX_CONCURRENT_DOWNLOADS):
    worker_thread = threading.Thread(target=download_worker, daemon=True)
    worker_thread.start()

# Start the bot
if __name__ == "__main__":
    clear_screen()
    bot.infinity_polling()