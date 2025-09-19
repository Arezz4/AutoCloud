import random
import string
import datetime
import glob
import os
import pyzipper
import time
import re
import logging
import configparser
from utils.colorlog import logger
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import ForumTopic
from gdrive.upload import upload_file_to_gdrive

config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.ini'))
parser = configparser.ConfigParser()
parser.read(config_path)

DEFAULT_PASSWORD = parser.get('general', 'DEFAULT_PASSWORD')
SEND_TO_TELEGRAM = parser.getboolean('general', 'SEND_TO_TELEGRAM', fallback=False)
DELETE_FILES_AFTER_UPLOAD = parser.getboolean('general', 'DELETE_FILES_AFTER_UPLOAD', fallback=True)

API_ID = parser.get('telegram', 'API_ID')
API_HASH = parser.get('telegram', 'API_HASH')
PHONE = parser.get('telegram', 'PHONE')
GROUP_ID = parser.getint('telegram', 'GROUP_ID')
ADMIN_ID = parser.getint('telegram', 'ADMIN_ID')

COLLECTED_FILES_DIR = 'data'
MEDIA_SUBFOLDER = os.path.join(COLLECTED_FILES_DIR, 'media')
LAST_BACKUP_FILE = os.path.join(COLLECTED_FILES_DIR, 'last_backup_id.txt')

os.makedirs(COLLECTED_FILES_DIR, exist_ok=True)
os.makedirs(MEDIA_SUBFOLDER, exist_ok=True)

client = TelegramClient('cloud_archive', API_ID, API_HASH)


def get_last_backup_id():
    """Read last backup message ID from file."""
    if os.path.exists(LAST_BACKUP_FILE):
        try:
            with open(LAST_BACKUP_FILE, 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None
    return None

def set_last_backup_id(msg_id):
    """Write last backup message ID to file."""
    try:
        with open(LAST_BACKUP_FILE, 'w') as f:
            f.write(str(msg_id))
    except Exception:
        logger.error('Failed to write last backup ID.')
        pass

async def generate_topic_grouped_chat_log(messages, chat_log_path, title="Telegram Archive Backup"):
    """
    Generate an HTML chat log grouped by topic, with collapsible sections.
    """
    html_header = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', Arial, sans-serif;
            background: linear-gradient(120deg, #e0e7ff 0%, #f5f7fa 100%);
            margin: 0;
            margin-inline: 12px;
            padding: 0;
            min-height: 100vh;
        }}
        .chat-container {{
            max-width: 900px;
            margin: 48px auto;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 6px 32px rgba(60,72,88,0.13);
            padding: 36px 32px 32px 32px;
            overflow: hidden;
        }}
        h2 {{
            text-align: center;
            font-weight: 600;
            color: #2a5885;
            margin-bottom: 32px;
            letter-spacing: 1px;
        }}
        .chat-log {{
            margin-top: 0;
        }}
        .topic-section {{
            margin-top: 40px;
            border-radius: 12px;
            background: #f7faff;
            box-shadow: 0 1px 4px rgba(60,72,88,0.07);
            padding: 0 0 12px 0;
        }}
        .topic-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #e3eaff;
            border-radius: 12px 12px 0 0;
            padding: 16px 24px;
            cursor: pointer;
            font-size: 1.15em;
            font-weight: 600;
            color: #2a5885;
            transition: background 0.2s;
        }}
        .topic-header:hover {{
            background: #d0e2ff;
        }}
        .topic-count {{
            background: #2a5885;
            color: #fff;
            border-radius: 8px;
            padding: 2px 10px;
            font-size: 0.95em;
            margin-left: 12px;
        }}
        .topic-content {{
            display: none;
            padding: 18px 24px 0 24px;
        }}
        .msg {{
            margin-bottom: 28px;
            padding-bottom: 12px;
            border-bottom: 1px solid #e3eaff;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(60,72,88,0.04);
            padding: 18px 18px 12px 18px;
            transition: box-shadow 0.2s;
        }}
        .msg:last-child {{
            border-bottom: none;
        }}
        .sender {{
            font-weight: 600;
            color: #2a5885;
            font-size: 1.08em;
        }}
        .date {{
            font-size: 0.93em;
            color: #7a8599;
            margin-left: 10px;
        }}
        .text {{
            margin: 10px 0 0 0;
            font-size: 1.07em;
            color: #222b45;
            line-height: 1.6;
            word-break: break-word;
        }}
        .media {{
            color: #d2691e;
            font-style: italic;
            margin-top: 10px;
        }}
        .media img {{
            max-width: 340px;
            max-height: 340px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(60,72,88,0.13);
            margin: 10px 0;
            display: block;
        }}
        .media a {{
            color: #2a5885;
            text-decoration: underline;
            font-weight: 500;
        }}
        @media (max-width: 600px) {{
            .chat-container {{ padding: 10px; }}
            .topic-header, .topic-content {{ padding: 10px; }}
            .msg {{ padding: 10px; }}
        }}
        .toggle-icon {{
            font-size: 1.2em;
            margin-left: 8px;
            transition: transform 0.2s;
        }}
        .topic-header.open .toggle-icon {{
            transform: rotate(90deg);
        }}
    </style>
</head>
<body>
<div class="chat-container">
<h2>{title}</h2>
<div class="chat-log">
'''
    html_footer = '''</div></div></body></html>'''
    collapsible_script = '''<script>
function toggleTopic(id) {
  var header = document.getElementById('header_' + id);
  var content = document.getElementById(id);
  if (content.style.display === "none" || content.style.display === "") {
    content.style.display = "block";
    header.classList.add('open');
  } else {
    content.style.display = "none";
    header.classList.remove('open');
  }
}
</script>'''
    # Fetch topics
    topic_map = {}
    try:
        topics_result = await client(GetForumTopicsRequest(GROUP_ID, offset_date=None, offset_id=0, offset_topic=0, limit=100))
        for topic in getattr(topics_result, 'topics', []):
            if isinstance(topic, ForumTopic):
                topic_map[topic.id] = topic.title
    except Exception:
        topic_map = {}
    # Collect messages by topic root message id and topic name
    topic_root_map = {}
    all_messages = []
    for message in messages:
        topic_name = getattr(getattr(message, 'action', None), 'title', None)
        if topic_name:
            topic_root_map[message.id] = topic_name
        sender = await message.get_sender()
        sender_name = sender.first_name if sender and hasattr(sender, 'first_name') else str(message.sender_id)
        date_str = message.date.strftime('%Y-%m-%d %H:%M:%S')
        all_messages.append((message, sender_name, date_str))
    # Group messages by topic
    topic_messages = {}
    msg_id_map = {msg.id: msg for (msg, _, _) in all_messages}
    for message, sender_name, date_str in all_messages:
        current = message
        topic_name = None
        visited = set()
        while current:
            if current.id in topic_root_map:
                topic_name = topic_root_map[current.id]
                break
            reply_to = getattr(current, 'reply_to', None)
            reply_to_msg_id = getattr(reply_to, 'reply_to_msg_id', None) if reply_to else None
            if reply_to_msg_id and reply_to_msg_id in msg_id_map and reply_to_msg_id not in visited:
                visited.add(reply_to_msg_id)
                current = msg_id_map[reply_to_msg_id]
            else:
                current = None
        if not topic_name:
            topic_name = 'General'
        if topic_name not in topic_messages:
            topic_messages[topic_name] = []
        msg_dict = {
            'sender_name': sender_name,
            'date_str': date_str,
            'text': message.text if message.text else None,
            'photo': f"media/photo_{message.id}.jpg" if message.photo else None,
            'document': f"media/{message.file.name}" if message.document and message.file and message.file.name else (f"media/document_{message.id}" if message.document else None)
        }
        topic_messages[topic_name].append(msg_dict)
    grouped_msgs = defaultdict(list)
    for topic_name, msgs in topic_messages.items():
        for msg in msgs:
            grouped_msgs[topic_name].append(msg)
    with open(chat_log_path, 'w', encoding='utf-8') as f:
        f.write(html_header)
        f.write(collapsible_script)
        topic_counter = 0
        for topic_name, msgs in grouped_msgs.items():
            topic_div_id = f"topic_{topic_counter}"
            msg_count = len(msgs)
            # Topic section with modern style
            f.write(f'<div class="topic-section">')
            f.write(f'<div class="topic-header" id="header_{topic_div_id}" onclick="toggleTopic(\'{topic_div_id}\')">')
            f.write(f'<div>')
            f.write(f'<span>{topic_name}</span>')
            f.write(f'<span class="topic-count">{msg_count}</span>')
            f.write(f'</div>')
            f.write(f'<span class="toggle-icon">&#9654;</span>')
            f.write(f'</div>')
            f.write(f'<div class="topic-content" id="{topic_div_id}">')
            for msg in msgs:
                f.write('<div class="msg">')
                f.write(f'<span class="sender">{msg["sender_name"]}</span>')
                f.write(f'<span class="date">{msg["date_str"]}</span>')
                if msg['text']:
                    def make_links_clickable(text):
                        url_pattern = r'(https?://\S+|www\.\S+)'  # Match http/https/www URLs
                        return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)
                    safe_text = make_links_clickable(msg["text"])
                    f.write(f'<div class="text">{safe_text}</div>')
                if msg['photo']:
                    img_src = msg["photo"]
                    f.write(f'<div class="media"><img src="{img_src}" alt="Photo" /></div>')
                if msg['document']:
                    doc_url = msg["document"]
                    doc_path = os.path.join(COLLECTED_FILES_DIR, doc_url)
                    if not os.path.splitext(doc_url)[1]:
                        matches = glob.glob(doc_path + '.*')
                        if matches:
                            doc_url = os.path.relpath(matches[0], COLLECTED_FILES_DIR)
                    doc_name = os.path.basename(doc_url)
                    f.write(f'<div class="media">[<a href="{doc_url}" target="_blank">{doc_name}</a>]</div>')
                f.write('</div>')
            f.write('</div></div>')
            topic_counter += 1
        f.write(html_footer)

async def zip_files(messages, chat_log_path, zip_file_path, password):
    """
    Create a password-protected zip file containing the chat log and all media files.
    """
    with pyzipper.AESZipFile(zip_file_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES, compresslevel=9) as zipf:
        zipf.setpassword(password.encode())
        zipf.write(chat_log_path, 'chat_log.html')
        logger.info('chat_log.html added to zip.')
        for message in messages:
            if message.photo:
                fname = f"photo_{message.id}.jpg"
                fpath = os.path.join(MEDIA_SUBFOLDER, fname)
                if os.path.exists(fpath):
                    zipf.write(fpath, os.path.join('media', fname))
                    logger.info(f'Added photo to zip: {fname}')
            if message.document:
                fname = message.file.name or f"document_{message.id}"
                fpath = os.path.join(MEDIA_SUBFOLDER, fname)
                if not os.path.exists(fpath):
                    matches = glob.glob(os.path.join(MEDIA_SUBFOLDER, f"document_{message.id}.*"))
                    if matches:
                        fpath = matches[0]
                        fname = os.path.basename(fpath)
                if os.path.exists(fpath):
                    zipf.write(fpath, os.path.join('media', fname))
                    logger.info(f'Added document to zip: {fname}')

async def fetch_messages(group_id, min_id=None):
    """
    Fetch messages from a group. If min_id is provided, only fetch messages newer than min_id.
    """
    messages = []
    if min_id:
        async for message in client.iter_messages(group_id, min_id=min_id):
            messages.append(message)
    else:
        async for message in client.iter_messages(group_id):
            messages.append(message)
    return messages

async def save_all_media(messages):
    """
    Download all media (photos/documents) from a list of messages.
    """
    for message in messages:
        if message.photo or message.document:
            try:
                await save_media(message)
                logger.info(f'Saved media for message {message.id}.')
            except Exception as e:
                logger.error(f'Failed to save media for message {message.id}: {e}')

async def backup_and_send(event, messages, zip_prefix, chat_log_title, update_last_backup=False):
    """
    Generate chat log, zip files, send to admin, update backup state, and clean up.
    """
    chat_log_path = os.path.join(COLLECTED_FILES_DIR, 'chat_log.html')
    await generate_topic_grouped_chat_log(messages, chat_log_path, title=chat_log_title)
    logger.info(f'chat_log.html generated at {chat_log_path}')
    date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_file_path = os.path.join(COLLECTED_FILES_DIR, f'{zip_prefix}_{date_str}.zip')
    password = DEFAULT_PASSWORD
    PASSWORD_RANDOMLY_GENERATED = False
    if password == '0':
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        PASSWORD_RANDOMLY_GENERATED = True
    logger.info(f'Creating zip file: {zip_file_path}')
    await zip_files(messages, chat_log_path, zip_file_path, password)
    await event.respond(f'Backup complete. Uploading the file...\nPassword: {password if PASSWORD_RANDOMLY_GENERATED else "(default)"}')
    if SEND_TO_TELEGRAM:
        try:
            await client.send_file(ADMIN_ID, zip_file_path)
            logger.info(f'{zip_prefix} zip sent to admin.')
        except Exception as e:
            logger.error(f'Error sending {zip_prefix} zip: {e}')
            await event.respond(f'Failed to send {zip_prefix} zip.')
    # Upload to Google Drive before deleting
    try:
        gdrive_file_id = upload_file_to_gdrive(zip_file_path)
        logger.info(f'Uploaded zip to Google Drive, file id: {gdrive_file_id}')
        await event.respond(f'+ Backup uploaded to Google Drive.\nhttps://drive.google.com/file/d/{gdrive_file_id}/view')
    except Exception as e:
        logger.error(f'Error uploading to Google Drive: {e}')
        await event.respond(f'Failed to upload backup to Google Drive: {e}')
    # Wait briefly to ensure all file handles are released
    time.sleep(0.5)
    
    cleanup_collected_files(LAST_BACKUP_FILE, logger, after=zip_prefix)

    if update_last_backup and messages:
        set_last_backup_id(messages[0].id)
        logger.info(f'Updated last backup ID to {messages[0].id}')

@client.on(events.NewMessage(pattern='/backup_now'))
async def handler(event):
    """
    Handle /backup_now command: full backup of all messages/media.
    """
    if event.is_private and event.sender_id == ADMIN_ID:
        try:
            await event.message.mark_read()
        except Exception as e:
            logger.error(f'Could not mark /backup_now message as read: {e}')
        await event.respond('Starting backup...')
        logger.info('Handler triggered for /backup_now')
        messages = await fetch_messages(GROUP_ID)
        await save_all_media(messages)
        await backup_and_send(event, messages, 'archive_backup', 'Telegram Archive Backup')
        if messages:
            set_last_backup_id(messages[0].id)
            logger.info(f'Updated last backup ID to {messages[0].id} (full backup)')
    else:
        await event.respond('Unauthorized or not in private chat.')

@client.on(events.NewMessage(pattern='/backup_sync'))
async def sync_handler(event):
    """
    Handle /backup_sync command: incremental backup of new messages/media since last backup.
    """
    if event.is_private and event.sender_id == ADMIN_ID:
        logger.info('Received /backup_sync command from admin.')
        try:
            await event.message.mark_read()
            logger.info('Marked /backup_sync message as read.')
        except Exception as e:
            logger.error(f'Could not mark /backup_sync message as read: {e}')
        await event.respond('Starting incremental backup...')
        last_id = get_last_backup_id()
        logger.info(f'Last backup message ID: {last_id}')
        messages = await fetch_messages(GROUP_ID, min_id=(last_id or 0))
        logger.info(f'Found {len(messages)} new messages since last backup.')
        if messages:
            logger.info(f'New message IDs: {[m.id for m in messages]}')
        if not messages:
            logger.info('No new messages to backup.')
            await event.respond('No new messages since last backup.')
            return
        await save_all_media(messages)
        await backup_and_send(event, messages, 'archive_sync', 'Telegram Archive Backup (Incremental)', update_last_backup=True)
    else:
        await event.respond('Unauthorized or not in private chat.')

async def save_media(message):
    """
    Download a single media file (photo or document) from a message.
    """
    if message.photo:
        file_path = os.path.join(MEDIA_SUBFOLDER, f"photo_{message.id}.jpg")
        await client.download_media(message, file_path)
    elif message.document:
        file_name = message.file.name or f"document_{message.id}"
        file_path = os.path.join(MEDIA_SUBFOLDER, file_name)
        await client.download_media(message, file_path)

def cleanup_collected_files(last_backup_file, logger, after='backup'):
    """
    Remove all files and directories in COLLECTED_FILES_DIR except the zip file and last_backup_id.txt.
    """
    if DELETE_FILES_AFTER_UPLOAD:
        # Delete all files except last_backup_file
        for root, dirs, files in os.walk(COLLECTED_FILES_DIR, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                if file_path != last_backup_file:
                    try:
                        os.remove(file_path)
                        logger.info(f'Removed file after {after}: {file_path}')
                    except Exception as e:
                        logger.error(f'Error removing file {file_path}: {e}')
            for name in dirs:
                dir_path = os.path.join(root, name)
                try:
                    os.rmdir(dir_path)
                    logger.info(f'Removed directory after {after}: {dir_path}')
                except Exception as e:
                    logger.error(f'Error removing directory {dir_path}: {e}')
    else:
        # Only delete the media folder and chat_log.html
        chat_log_path = os.path.join(COLLECTED_FILES_DIR, 'chat_log.html')
        if os.path.exists(chat_log_path):
            try:
                os.remove(chat_log_path)
                logger.info(f'Removed chat log: {chat_log_path}')
            except Exception as e:
                logger.error(f'Error removing chat log {chat_log_path}: {e}')
        if os.path.exists(MEDIA_SUBFOLDER):
            for root, dirs, files in os.walk(MEDIA_SUBFOLDER, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        os.remove(file_path)
                        logger.info(f'Removed media file: {file_path}')
                    except Exception as e:
                        logger.error(f'Error removing media file {file_path}: {e}')
                for name in dirs:
                    dir_path = os.path.join(root, name)
                    try:
                        os.rmdir(dir_path)
                        logger.info(f'Removed media subdir: {dir_path}')
                    except Exception as e:
                        logger.error(f'Error removing media subdir {dir_path}: {e}')
            try:
                os.rmdir(MEDIA_SUBFOLDER)
                logger.info(f'Removed media folder: {MEDIA_SUBFOLDER}')
            except Exception as e:
                logger.error(f'Error removing media folder {MEDIA_SUBFOLDER}: {e}')


if __name__ == '__main__':
    client.start(phone=PHONE)
    print('Telegram backup bot running...')
    client.run_until_disconnected()
