import os, subprocess, random, string, re
import smtplib, ssl
from email.mime.text import MIMEText
import sqlite3
import discord, asyncio
import data
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = data.DISCORD_TOKEN
EMAIL_APP_KEY = data.EMAIL_KEY
MAXIMUM_RETRY = 3
BOT_NAME = data.BOT_NAME
TARGET_CHANNEL_ID = data.TARGET_CHANNEL_ID

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
    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context)
    smtp.login(data.SENDER_EMAIL, EMAIL_APP_KEY)
    msg = MIMEText('ID: {} \nPW: {}'.format(uid, password))
    msg['From'] = data.SENDER_EMAIL
    msg['Subject'] = 'HeXA 서버 계정 생성 안내'
    msg['To'] = email_addr
    smtp.sendmail(data.SENDER_EMAIL, email_addr, msg.as_string())
    smtp.quit()
    
def load_users_from_passwd():
    passwd_file = open('/etc/passwd', 'r')
    passwd_lines = passwd_file.readlines()
    passwd_file.close()
    
    user_list = []
    
    for line in passwd_lines:
        fields = line.strip().split(':')
        user_list.append(fields[0])
        
    return user_list
    
def check_username(user_name:str) -> bool:
    if not user_name[0].isalpha():
        return False
    if not user_name.isalnum():
        return False
    return True


@bot.command("계정주세요")
async def hi(ctx):
    try:
        def check_instant_return(message):
            return message.author == ctx.author and not message.author.bot 

        try: 
            # 2-1. Request and receive person_name
            await ctx.send("Please provide your person name:")
            person_name = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
            person_name = person_name.content
            retry = 0
            while not re.match(r'^[가-힣]{2,4}$', person_name) and retry < MAXIMUM_RETRY:
                await ctx.send("Name must be in Korean: {}".format(person_name))
                await ctx.send("Please provide your person name:")
                person_name = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
                person_name = person_name.content
                retry += 1
            
            # 2-2-1. Request and receive user email
            await ctx.send("Please provide your UNIST email:")
            email_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
            email = email_msg.content

            # 2-2-2. Validate email
            retry = 0
            while not re.match(r'^([\w.-]+)@unist\.ac\.kr$', email) and retry < MAXIMUM_RETRY:
                await ctx.send("Email must end with 'unist.ac.kr': {}".format(email))
                await ctx.send("Please provide your email:")

                email_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
                email = email_msg.content
                
                retry += 1
                
            if retry == MAXIMUM_RETRY:
                await ctx.send(f"Invalid format of email: {email}")
                return
            
            # 2-2-3. Check if email already exists in DB
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            existing_user = c.fetchone()
            if existing_user:
                await ctx.send(f"The user {email}({existing_user[0]}) is already enrolled.")
                return
            
            # 2-3-1. Request and receive username
            await ctx.send("Please provide your username for using in the server:")
            username_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
            username = username_msg.content
            
            # 2-3-2. Validate username
            user_list = load_users_from_passwd()

            retry = 0
            while retry < MAXIMUM_RETRY and (username in user_list or not check_username(username)):
                await ctx.send(f"Cannot generate user with username \"{username}\"")
                
                username_msg = await bot.wait_for('message', timeout=60.0, check=check_instant_return)
                username = username_msg.content
                
                retry += 1
                
            if retry == MAXIMUM_RETRY:
                await ctx.send(f"Invalid username: {username}")
                return

        except asyncio.TimeoutError:
            await ctx.send("Timeout")
            return
          
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
        
        # After successfully creating the user and inserting into the DB
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        await target_channel.send(f"User {username}(owned by {person_name} / {email}) has been created on {current_time}.")
    except Exception as e:
        print(e)
        
bot.run(TOKEN)
