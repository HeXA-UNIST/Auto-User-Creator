import os
import discord
import sqlite3
from discord.ext import commands
from dotenv import load_dotenv
import subprocess
import random
import string
from datetime import datetime
import smtplib
from email.mime.text import MIMEText # Load environment variables
import re
import ssl
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
EMAIL_APP_KEY = os.getenv('EMAIL_KEY')
MAXIMUM_RETRY = 3
BOT_NAME = "HeXA user creator#2001"

bot = commands.Bot(command_prefix='/', intents=None)
client = discord.Client(intents=None)

# SQLite3 setup
conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (name TEXT, email TEXT PRIMARY KEY, created_at TEXT)''')
conn.commit()

def random_password():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))

def send_email(email_addr, uid, password):
    context = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL('smtp.daum.net', 465, context=context)
    smtp.login('apple0511h0511@daum.net', EMAIL_APP_KEY)
    msg = MIMEText('ID: {} \nPW: {}'.format(uid, password))
    msg['From'] = 'admin@hexa.pro'
    msg['Subject'] = 'HeXA 서버 계정 생성 안내'
    msg['To'] = email_addr
    smtp.sendmail('admin@hexa.pro', email_addr, msg.as_string())
    smtp.quit()
    
@bot.command("계정내놔")
async def hi(ctx):
    def check_instant_return(message):
        return message.author == ctx.author and not message.author.bot 

    # 1. Request and receive user email and person_name
    await ctx.send("Please provide your person name:")
    person_name = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
    person_name = person_name.content

    await ctx.send("Please provide your email:")
    try: 
        email_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
    except asyncio.TimeoutError:
        await ctx.send("Timeout")
        return
    
    email = email_msg.content

    # 2.1 Validate email
    retry = 0
    while not re.match(r'^([\w.-]+)@unist\.ac\.kr$', email) and retry < MAXIMUM_RETRY:
        await ctx.send("email must end with 'unist.ac.kr': {}".format(email))
        await ctx.send("Please provide your email:")
        try:
            email_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
        except asyncio.TimeoutError:
            await ctx.send("Timeout")
            return
        email = email_msg.content
        retry += 1
    if retry == MAXIMUM_RETRY:
        await ctx.send(f"Invalid format of email: {email}")
        return
    
    # 2.2 Check if email already exists in DB
    # c.execute("SELECT * FROM users WHERE email=?", (email,))
    # existing_user = c.fetchone()
    # if existing_user:
    #     await ctx.send(f"The user {email}({existing_user[0]}) is already enrolled.")
    #     return
    
    # 2.3 Extract the part before "@"
    splitter_i = email.find("@") # assert != -1
    username = email[:splitter_i]

    # 3.1 Create user on the server
    password = random_password()
    result = subprocess.run(['sudo', 'adduser', '--gecos', '', '--disabled-password', username], capture_output=True, text=True)
    if result.returncode != 0:
        await ctx.send(f"Error creating user: {result.stderr}")
        return
    
    # 3.2 Set the password for the user
    proc = subprocess.Popen(['passwd', username], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate(input=f"{password}\n{password}\n")
    if proc.returncode != 0:
        await ctx.send(f"Error setting password: {stderr}")
        return
    
    # 4. Insert user info into the database
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (person_name, email, current_time))
		
    # 5. Print user info
    send_email(email, username, password)
    await ctx.send(f"User {username}(owned by {person_name}) has been created on {current_time}!\nthe password was sent to {email}")

bot.run(TOKEN)
