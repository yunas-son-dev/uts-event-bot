# bot.py
import discord
from discord.ext import commands
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ------------------------------
# Environment Variables
# ------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = "users"
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

AIRTABLE_ENDPOINT = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

# ------------------------------
# Bot Setup
# ------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------
# Constants
# ------------------------------
UNVERIFIED_ROLE = "Unverified"
UTS_ROLE = "Student/Alumni"

# Predefined majors with abbreviations
MAJORS = {
    "Data Science": "DS",
    "MBA": "MBA",
    "Mechanical and Mechatronic Engineering": "MME",
    "Computer Science": "CS",
    "Systems Design and Analysis": "SDA",
    "Cybersecurity and Networking": "CSN",
    "Games, Graphics and Multimedia": "GGM",
    "Information Technology": "IT",
    "Artificial Intelligence": "AI",
    "Business Information Systems Management": "BISM",
    "Data Analytics": "DA",
    "Enterprise Systems Development": "ESD",
    "Interaction Design": "ID",
    "Networking and Cybersecurity": "NC"
}

# Temporary user data during DM registration
user_data = {}

# ------------------------------
# Helper Functions
# ------------------------------
def studentid_exists(studentid):
    """Check if StudentID already exists in Airtable"""
    params = {"filterByFormula": f"{{studentid}}='{studentid}'"}
    resp = requests.get(AIRTABLE_ENDPOINT, headers=HEADERS, params=params)
    if resp.status_code == 200:
        data = resp.json()
        return len(data["records"]) > 0
    return False

def add_user_to_airtable(discord_id, name, major, studentid, status):
    """Add verified user to Airtable"""
    data = {
        "fields": {
            "discord_id": str(discord_id),
            "name": name,
            "major": major,
            "studentid": studentid,
            "status": status
        }
    }
    requests.post(AIRTABLE_ENDPOINT, headers=HEADERS, json=data)

def format_nickname(name, major, status):
    """Format nickname after verification"""
    major_abbr = MAJORS.get(major, major)
    return f"{name} | {major_abbr} | {status}"

async def send_admin_alert(member, airtable_link):
    """Send alert to admin channel"""
    channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if channel:
        await channel.send(
            f"✅ {member.mention} has been verified and added.\nAirtable Link: {airtable_link}"
        )

# ------------------------------
# Events
# ------------------------------
@bot.event
async def on_member_join(member):
    """Automatically assign Unverified role on join"""
    role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE)
    if role:
        await member.add_roles(role)
        try:
            await member.send(
                "Welcome! Please provide your information for verification.\n"
                "Reply in the following format:\n"
                "`Name, Major, Status(재학생/졸업생), StudentID`"
            )
        except:
            print(f"Could not DM {member.name}")

@bot.event
async def on_message(message):
    """Handle DM messages for verification"""
    if message.author == bot.user:
        return

    # Only process DMs
    if isinstance(message.channel, discord.DMChannel):
        try:
            # Parse user input
            name, major, status, studentid = [x.strip() for x in message.content.split(",")]
        except:
            await message.channel.send(
                "Invalid format. Please send as: Name, Major, Status(재학생/졸업생), StudentID"
            )
            return

        # Validate major
        if major not in MAJORS:
            await message.channel.send(f"Invalid major. Choose from: {', '.join(MAJORS.keys())}")
            return

        # Validate StudentID format
        if not studentid.isdigit() or len(studentid) != 8:
            await message.channel.send("Please submit valid StudentID.")
            return

        # Check duplication
        if studentid_exists(studentid):
            await message.channel.send("This StudentID is already registered.")
            return

        # Save to Airtable
        add_user_to_airtable(message.author.id, name, major, studentid, status)

        # Update guild nickname and role
        for guild in bot.guilds:
            member = guild.get_member(message.author.id)
            if member:
                nickname = format_nickname(name, major, status)
                await member.edit(nick=nickname)

                # Remove Unverified role
                unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE)
                if unverified_role in member.roles:
                    await member.remove_roles(unverified_role)

                # Add UTS Student role
                uts_role = discord.utils.get(guild.roles, name=UTS_ROLE)
                if uts_role:
                    await member.add_roles(uts_role)

        # DM confirmation
        await message.channel.send("✅ Your registration is complete! Welcome to the server.")

        # Admin alert
        airtable_link = f"https://airtable.com/{AIRTABLE_BASE_ID}/tbl{AIRTABLE_TABLE_NAME}"
        await send_admin_alert(message.author, airtable_link)

    await bot.process_commands(message)

# ------------------------------
# Run Bot
# ------------------------------
bot.run(DISCORD_TOKEN)
