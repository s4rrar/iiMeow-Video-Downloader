# 🐈 iiMeow Video Downloader Bot

## Overview
A Telegram bot that allows users to download YouTube videos and audio with simple commands.

![iiMeowBot](https://github.com/user-attachments/assets/dc33e2f1-115d-479a-a071-240a1c426d86)

## Features
- Download YouTube videos as MP4
- Download YouTube audio as MP3
- File size limit of 1.9 GB
- Simple, user-friendly interface

## Prerequisites
- Python 3.8+
- FFmpeg
- Libraries: 
  - telebot
  - yt_dlp
  - threading
  - Queue

## Installation
```bash
git clone https://github.com/s4rrar/iiMeow-Video-Downloader.git
cd iiMeow-Video-Downloader
pip install telebot yt_dlp threading Queue
sudo apt install ffmpeg -y
python bot.py
```

## Configuration
1. Replace `<YOUR_BOT_API_TOKEN>` with your Telegram Bot Token
2. Adjust `MAX_FILE_SIZE` if needed

## Usage
- `/audio [YouTube URL]`: Download audio
- `/video [YouTube URL]`: Download video

## Channels
- Telegram Channel: [@darks1ders](https://t.me/darks1ders)
- Developer: [@s4rrar](https://t.me/s4rrar)
