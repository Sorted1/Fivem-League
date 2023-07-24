import discord
from datetime import datetime
from discord.ext import commands
import sqlite3

ADMINROLE = "Your Admin Role Name"
REGISTERED_ROLE_NAME = "Registered"
IDSX = "DISCORD SERVER ID"

intents = discord.Intents.all()
intents.members = True
intents.messages = True
bot = discord.Client(intents=intents)

bot = commands.Bot(command_prefix='!', intents=intents)

conn = sqlite3.connect('elo_data.db')
cursor = conn.cursor()

elo_scores = {}
queues = {}


cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    elo INTEGER
                  )''')
conn.commit()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await load_reg_users()

async def load_reg_users():
    cursor.execute('SELECT * FROM users')
    users_data = cursor.fetchall()
    for user_data in users_data:
        user_id, username, elo = user_data
        elo_scores[user_id] = elo
        user = bot.get_user(user_id)
        if user:
            new_nickname = f"[{elo}] {username}"
            guild = bot.get_guild(IDSX)
            member = guild.get_member(user_id)
            if member:
                try:
                    await member.edit(nick=new_nickname)
                except discord.Forbidden:
                    pass 

def has_admin_role():
    async def predicate(ctx):
        if ctx.author is None:
            return False
        admin_role = discord.utils.get(ctx.guild.roles, name=ADMINROLE)
        if admin_role is None:
            return False
        return admin_role in ctx.author.roles
    return commands.check(predicate)

@bot.command()
async def leaderboard(ctx):
    cursor.execute('SELECT * FROM users ORDER BY elo DESC LIMIT 10')
    top_users = cursor.fetchall()

    leaderboard_description = "```"
    for index, user in enumerate(top_users, 1):
        user_info = f"{user[1]} - Elo: {user[2]}\n"
        leaderboard_description += f"{index}. {user_info}"
    leaderboard_description += "```"

    embed = discord.Embed(title="Leaderboard - Top 10 Users", description=leaderboard_description, color=discord.Color.gold())
    await ctx.send(embed=embed)
    
@bot.event
async def on_disconnect():
    cursor.close()
    conn.close()

@bot.command()
async def register(ctx):
    author = ctx.author
    if author.id not in elo_scores:
        cursor.execute('INSERT INTO users (user_id, username, elo) VALUES (?, ?, ?)',
                       (author.id, author.name, 0))
        conn.commit()
        new_nickname = f"[0] {author.name}"
        try:
            await author.edit(nick=new_nickname)
        except discord.Forbidden:
            pass  # Handle if the bot lacks permission to change nicknames

        # Give the user the "registered" role
        registered_role = discord.utils.get(ctx.guild.roles, name=REGISTERED_ROLE_NAME)
        if registered_role:
            await author.add_roles(registered_role)

        elo_scores[author.id] = 0
        await ctx.send(f'{author.mention} has been registered with 0 Elo score and nickname set to {new_nickname}.')
    else:
        await ctx.send(f'{author.mention} is already registered with {elo_scores[author.id]} Elo score.')


@bot.command()
async def j(ctx):
    author = ctx.author
    channel = ctx.channel

    if channel.id not in queues:
        queues[channel.id] = []

    if author.id in queues[channel.id]:
        await ctx.send(f'{author.mention} is already in the queue.')
    else:
        queues[channel.id].append(author.id)
        await ctx.send(f'{author.mention} has joined the queue in this channel. Queue size: {len(queues[channel.id])}')
        if len(queues[channel.id]) == 2:
            await start_competition(ctx, channel)

@bot.command()
async def l(ctx):
    author = ctx.author
    channel = ctx.channel

    if channel.id not in queues:
        queues[channel.id] = []

    if author.id in queues[channel.id]:
        queues[channel.id].remove(author.id)
        await ctx.send(f'{author.mention} has left the queue in this channel. Queue size: {len(queues[channel.id])}')
    else:
        await ctx.send(f'{author.mention} is not in the queue in this channel.')

ranks = [
    {"name": "Legend", "elo_threshold": 1000, "win_points": 25, "lose_points": 40},
    {"name": "Elite", "elo_threshold": 500, "win_points": 20, "lose_points": 35},
    {"name": "Platinum", "elo_threshold": 400, "win_points": 20, "lose_points": 30},
    {"name": "Gold", "elo_threshold": 300, "win_points": 20, "lose_points": 25},
    {"name": "Silver", "elo_threshold": 200, "win_points": 15, "lose_points": 15},
    {"name": "Bronze", "elo_threshold": 150, "win_points": 10, "lose_points": 5},
    {"name": "Intermediate", "elo_threshold": 100, "win_points": 10, "lose_points": 5},
    {"name": "Amateur", "elo_threshold": 50, "win_points": 10, "lose_points": 0},
    {"name": "Registered", "elo_threshold": 0, "win_points": 5, "lose_points": 0},
]

async def start_competition(ctx, channel):
    user1_id = queues[channel.id][0]
    user2_id = queues[channel.id][1]
    queues[channel.id].clear()

    user1 = bot.get_user(user1_id)
    user2 = bot.get_user(user2_id)

    if user1 and user2:
        current_time = datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p')
        team1_elo = elo_scores[user1_id]
        team2_elo = elo_scores[user2_id]

        team1_points = next((rank["win_points"] for rank in ranks if team1_elo >= rank["elo_threshold"]), 0)
        team2_points = next((rank["win_points"] for rank in ranks if team2_elo >= rank["elo_threshold"]), 0)

        team1_info = f"{user1.mention} - `{team1_elo} (W: +{team1_points}, L: -{team1_points})`"
        team2_info = f"{user2.mention} - `{team2_elo} (W: +{team2_points}, L: -{team2_points})`"

        embed = discord.Embed(title="Fivem League | Match Started!", color=discord.Color.dark_blue())
        embed.add_field(name="Match Information:", value=f"```\n"
                                                         f"**Creation Time**: `{current_time}`\n"
                                                         f"**Matchmaking Lobby**: `{channel.name}`\n"
                                                         f"```")
        embed.add_field(name="Team 1", value=team1_info, inline=False)
        embed.add_field(name="Team 2", value=team2_info, inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send("One or both users have left the server or are not registered.")

def update_user_elo(user_id, new_elo):
    cursor.execute('UPDATE users SET elo = ? WHERE user_id = ?', (new_elo, user_id))
    conn.commit()

@bot.command()
@has_admin_role()
async def win(ctx, user: discord.Member):
    user = ctx.guild.get_member(user.id)  # Fetch the member object instead of user object
    if user and user.id in elo_scores:
        for rank in ranks:
            if elo_scores[user.id] >= rank["elo_threshold"]:
                elo_scores[user.id] += rank["win_points"]
                update_user_elo(user.id, elo_scores[user.id])
                role = discord.utils.get(ctx.guild.roles, name=rank["name"])
                if role:
                    await user.add_roles(role)
                await ctx.send(f'{user.mention} has won the competition! New Elo score: {elo_scores[user.id]}')
                break
    else:
        await ctx.send(f'{user.mention} is not registered. Use !register to register first.')

@bot.command()
@has_admin_role()
async def lose(ctx, user: discord.Member):
    user = ctx.guild.get_member(user.id)  # Fetch the member object instead of user object
    if user and user.id in elo_scores:
        for rank in ranks:
            if elo_scores[user.id] >= rank["elo_threshold"]:
                elo_scores[user.id] -= rank["lose_points"]
                update_user_elo(user.id, elo_scores[user.id])
                role = discord.utils.get(ctx.guild.roles, name=rank["name"])
                if role:
                    await user.add_roles(role)
                await ctx.send(f'{user.mention} has lost the competition! New Elo score: {elo_scores[user.id]}')
                break
    else:
        await ctx.send(f'{user.mention} is not registered. Use !register to register first.')

@bot.command()
@has_admin_role()
async def wipe(ctx, user: discord.Member):
    user = ctx.guild.get_member(user.id)
    if user and user.id in elo_scores:
        elo_scores[user.id] = 0  # Reset Elo score to 0
        update_user_elo(user.id, elo_scores[user.id])
        await ctx.send(f'{user.mention} has been wiped. New Elo score: {elo_scores[user.id]}')
    else:
        await ctx.send(f'{user.mention} is not registered. Use !register to register first.')




        
bot.run('')
