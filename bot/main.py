import os
from typing import Collection
from discord.ext import commands
import discord
import datetime
import re
import random
from discord.ext.commands.errors import BadArgument
from discord.permissions import Permissions
from discord.utils import get
import pymongo
from pymongo import MongoClient

import logging

logging.basicConfig(level=logging.INFO)

base_dir = os.path.dirname(__file__)

# What do I have to do to get these emoji to show up??!?
# SLOT_WIN = '<:LMaps_crown:902296702264950805>'
# SLOT_LOSS = ["<:LMaps_wiz_sad:902296702164287489>",
#              "<:LMaps_shield:902296702327877653>",
#              "<:LMaps_torch:902296702504034324>",
#              "<:LMaps_skel:902296702357229569>",
#              "<:LMaps_swords:902296702470463598>",
#              "<:LMaps_potion:902296702424350741>"]

SLOT_WIN = ":crown:"
SLOT_LOSS = [":skull_crossbones:", ":skull:", ":crescent_moon:", ":crossed_swords:", ":wolf:", ":black_cat:", ":bone:", ":dragon_face:", ":mushroom:",":coin:",":gem:", "🌞", "👹", "👻","👁️","🧝‍♂️","🧚‍♀️","🧙"]

if not os.getenv("env") == "dev":
    # PRODUCTION Settings
    os.environ['http_proxy'] = os.environ.get('FIXIE_URL', '')
    os.environ['https_proxy'] = os.environ.get('FIXIE_URL', '')
    TESTING = False
    SLOT_CHANCE = 1/10

    # SLOT_WIN = ":crossed_swords:"
    # SLOT_LOSS = [":dizzy_face:", ":face_with_spiral_eyes:",
    #              ":frowning2:", ":skull:"]

else:
    # DEV Settings
    from dotenv import load_dotenv
    load_dotenv() 
    TESTING = True
    SLOT_CHANCE = 1/4
    # SLOT_WIN = ":crossed_swords:"
    # SLOT_LOSS = [":dizzy_face:", ":face_with_spiral_eyes:", ":frowning2:", ":skull:"]

bot = commands.Bot(command_prefix="!")
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILDS = os.getenv("ALLOWED_DISCORD_GUILDS") # Not yet checked against
MONGO_URL = os.getenv("MONGO_URL")
ALLOWED_CHANNELS_SLOTS = ["oracle", "admin-test-channel"]  # only used by slotmachine
ALLOWED_CHANNELS_ALLOWLISTER = ["whitelist", "whitelist_private_booth",
                                "allowlist", "bots", "📝│allowlist", "📝│whitelist", "admin-test-channel"]  # only used by allow lister, not !slot
ENABLE_SLOT = False
ENABLE_ORACLE = True


def get_list_from_file(filename):
    with open(os.path.join(base_dir, filename), "r") as file:
        return file.read().splitlines()
    file.close()

if ENABLE_ORACLE:
    # Load oracle strings
    ORACLE_MESSAGES = get_list_from_file("oracle_messages.txt")
    print(f"Loaded {len(ORACLE_MESSAGES)} oracle messages from file.")

    # load sacrifices
    SACRIFICES = get_list_from_file("sacrifices.txt")
    print(f"Loaded {len(SACRIFICES)} sacrifices from file.")


# SLOT_WIN = discord.utils.get(bot.emojis, name="LMaps_crown")
# SLOT_LOSS = [
#     discord.utils.get(bot.emojis, name="LMaps_wiz_sad"),
#     discord.utils.get(bot.emojis, name="LMaps_wiz_angry"),
#     discord.utils.get(bot.emojis, name="LMaps_shield"),
#     discord.utils.get(bot.emojis, name="LMaps_torch"),
#     discord.utils.get(bot.emojis, name="LMaps_potion"),
#     discord.utils.get(bot.emojis, name="LMaps_skel"),
# ]

# print (bot.emojis)

ALLOWED_ROLES = ["Legendary Adventurer", "Epic Explorer", "Rare Seeker", "Uncommon Wanderer", "Friends", "Blerxers"]  # Wonder how to set via a config UI

cluster = MongoClient(MONGO_URL)
db = cluster["AllowList"]
if TESTING: 
    collection = db["AllowList_test"]
else:
    collection = db["AllowList_prod"]

# project_name = "CF Test"

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game('Accepting wallet addresses'))
    f'{bot.user} is connected to the following server(s):\n'

    for guild in bot.guilds:
        # if guild.name == GUILD:
        #     break
        print(
            f'{guild.name}(id: {guild.id})'
        )
        # print (guild.emojis)
        SLOT_WIN = discord.utils.get(guild.emojis, name="LMaps_crown")


        await guild.me.edit(nick="Legend Maps Allowlist Bot") # Give it a cute nickname, can set this up custom per server TODO



### command listeners

# listen for !allow command
@bot.command(brief='!allow <wallet address> to add your wallet address to the appropriate allow list.', usage="<wallet>", aliases=["add"], cog_name='General')
async def allow(message, arg):
    #only allow in defined channel(s)
    if not is_allowed_channel(message, ALLOWED_CHANNELS_ALLOWLISTER):
        await wrong_channel_message(message, ALLOWED_CHANNELS_ALLOWLISTER)
        return

    if message.author == bot.user:
        return

    wallet = validate_wallet(arg)

    if not wallet:
        await message.reply(f"Sorry, {arg} is not a valid wallet address. (Note: ENS names like 'example.eth' are not supported.)")
        return

    if check_eligibility(message.author):
        approved_role = check_eligibility(message.author)

        # print(f'writing to db ' + message.author.name + ' as role ' + approved_role)
        result_message = add_to_list(message.author, approved_role, wallet, message.guild.name)
        # await message.channel.send('Hello, ' + message.author.name +'!' + ' You are added to the ' + approved_role + ' list.')
        await message.reply(f"Hey, {message.author.nick or message.author.name}! {result_message}")

    else:
        # print('not an approved role!')
        await message.reply(f"Sorry, {message.author.nick or message.author.name}! You don't seem to have a role eligible for the allow list. Try !roles to see eligible roles.")

# listen for !check command
@bot.command(brief='!check to check your current list status.', cog_name='General')
async def check(message):
    #only allow in defined channel(s)
    # if not is_allowed_channel(message, ALLOWED_CHANNELS_ALLOWLISTER):
    #     await wrong_channel_message(message,ALLOWED_CHANNELS_ALLOWLISTER)
    #     return
    
    if message.author == bot.user:
        return

    my_list = check_eligibility(message.author)

    if not my_list:
        promo_msg=""
        # if ENABLE_ORACLE:
        #     promo_msg = "And make a !sacrifice to the Oracle in the #oracle channel for a chance to be granted a WL spot."
        await message.reply(f"Sorry, {message.author.nick or message.author.name}. You don't seem to have a role eligible for the allow list. Try !roles to see eligible roles. {promo_msg}")
        return

    if user_not_in_list(message.author, my_list, message.guild.name):
        await message.reply(f"Hello, {message.author.nick or message.author.name}! You are eligible for the '{my_list}' list, but haven't added your wallet address yet. Use !allow <wallet address> to add yourself.")
    else:
        list_entry = get_list_entry(message)
        await message.reply(f'Hi, {message.author.nick or message.author.name}! You are in list "{list_entry["listname"]}" with wallet {list_entry["wallet"]}')

# checkid <discord userid>
# listen for !checkid command
@bot.command(brief='!checkid <discord user id> to check the status of a user by id (admin only).')
# must have manage_guild (server) perms to do count command
@commands.has_permissions(manage_guild=True)
async def checkid(message, arg=0):
    # #only allow in defined channel(s)
    # if not is_allowed_channel(message, ALLOWED_CHANNELS_ALLOWLISTER):
    #     await wrong_channel_message(message, ALLOWED_CHANNELS_ALLOWLISTER)
    #     return
    if message.author == bot.user:
        return

    #is arg a real user id?
    try:
        arg = int(arg)
    except:
        await message.reply("That's not a valid user id format.")
        return

    try:
        user = await bot.fetch_user(arg)
        # check id
        list_entry = get_any_list_entry(user, message.guild.name)
        if (list_entry):
            # return list entries
            await message.reply(f'User {list_entry["username"]} is in list "{list_entry["listname"]}" with wallet {list_entry["wallet"]}')
        else:
            # sorry you are not in the list
            await message.reply(f"That ID is not on the list.")
    except:
        await message.reply("That's not a valid user id.")


# listen for !roles command
@bot.command(brief='!roles to see allow-listed Discord roles', cog_name='General')
async def roles(message):
    rolesStr = "Allowed Roles: \n"

    for role in get_eligible_guild_roles(message.guild):
        rolesStr += f"\t{role}\n"
    await message.channel.send(rolesStr)

# listen for !count command
@bot.command(brief='!count to see current allowlist count', cog_name='General')
@commands.has_permissions(manage_guild=True) # must have manage_guild (server) perms to do count command
async def count(message, arg=""):
    project_name = message.guild.name #should check to see if in allowed guilds
    doc_count = collection.count_documents({"project": project_name})
    respString = (f"There are currently {doc_count} addresses on the allowlist.\n")
    if arg=="v" or arg=="verbose":
        for role in get_eligible_guild_roles(message.guild):
            role_count = collection.count_documents({"project": project_name, "listname": role})
            respString += f"{role}: {role_count}\n"

    await message.channel.send(respString)

# listen for !info command


@bot.command(hidden=True)
# must have manage_guild (server) perms to do this command
@commands.has_permissions(manage_guild=True)
async def info(message):
    await message.channel.send(f"`slot odds: {SLOT_CHANCE} `")


if ENABLE_ORACLE:
    slot_result = ["", "", ""]
    # listen for !sacrifice command
    @bot.command(brief='make a !sacrifice to the oracle, and she may reward you with wealth or wisdom')
    async def sacrifice(message):
        # exit command if not an allowed channel.
        #only allow in defined channel(s)
        if not is_allowed_channel(message, ALLOWED_CHANNELS_SLOTS):
            await wrong_channel_message(message, ALLOWED_CHANNELS_SLOTS)
            return
        # do the regular sacrifice oracle message thing
        # await message.reply(f"You make your sacrifice to the Oracle, and a disembodied voice emerges from the shadows to say:\n `{random.choice(ORACLE_MESSAGES)}`")    
        oracle_reply = f"You lay {random.choice(SACRIFICES)} upon the altar, and a swirling vision forms before you...\n"

        if slot_win(message):
            # await message.reply(f"Suddenly, you hear a great and distant rumbling, and a searing light fills your eyes. You heart fills with radiance -- you have been *blessed* by the gods!")
            oracle_reply += f"{SLOT_WIN}   {SLOT_WIN}   {SLOT_WIN}\n"
            # oracle_reply += f"`{random.choice(ORACLE_MESSAGES)}`"
            oracle_reply += f"Suddenly, you hear a great and distant rumbling, and a searing light fills your eyes. A voice from the shadows booms:\n `YOU HAVE BEEN CHOSEN FOR MY BLESSING.`\n"
            
            # set member role to Blessed
            # TODO clean this up!
            winner_role1 = get(message.guild.roles, name="Blessed")
            await message.author.add_roles(winner_role1)
            oracle_reply += (f"Congratulations! You now have the 'Blessed' role.")

            # # only give uncommon wanderer if they don't have a higher role. Really gotta generalize this!
            # if check_eligibility(message.author):
            #     oracle_reply += (
            #         f"Congratulations! You already had an eligible role, so we'll just call you 'blessed.' ")
            #     await message.author.add_roles(winner_role1)
            # else:
            #     winner_role2 = get(message.guild.roles,
            #                        name="Uncommon Wanderer")
            #     await message.author.add_roles(winner_role1, winner_role2)

            #     oracle_reply += (
            #         f"Congratulations! You are now a {winner_role2}, and can now add yourself in the whitelist channel with command !allow <wallet address>.")
        else:
            # output loser images
            for i in range(2):
                slot_result[i] = random.choice(SLOT_LOSS)
            oracle_reply += f"{slot_result[0]}   {slot_result[1]}\n"
            oracle_reply += f"As you puzzle over its meaning, a disembodied voice emerges from the shadows to say:\n `{random.choice(ORACLE_MESSAGES)}`"
        
        await message.reply(oracle_reply)

if ENABLE_SLOT: 
    #### Slot Machine stuff, needs some clean-up
    slot_result = ["","",""]

    # listen for !slot command
    @bot.command(brief='!slot to try your luck (only in the slot-machine channel)')
    async def slot(message):
        # exit command if not an allowed channel.
        #only allow in defined channel(s)
        if not is_allowed_channel(message, ALLOWED_CHANNELS_SLOTS):
            await wrong_channel_message(message, ALLOWED_CHANNELS_SLOTS)
            return

        if slot_win(message):
            await message.reply(f"{SLOT_WIN}  {SLOT_WIN}  {SLOT_WIN} -- Winner Winner Chicken Dinner!")
            # set member role to Lucky Devil

            # TODO clean this up!
            winner_role1 = get(message.guild.roles, name="Lucky Devil")

            # only give uncommon wanderer if they don't have a higher role. Really gotta generalize this!
            if check_eligibility(message.author):
                await message.reply(f"You already had an eligible role, so we'll just call you a lucky devil :)")
                await message.author.add_roles(winner_role1)
            else:
                winner_role2 = get(message.guild.roles, name="Uncommon Wanderer")
                await message.author.add_roles(winner_role1, winner_role2)

                await message.reply(f"You are now a {winner_role2}, and can now add yourself in the whitelist channel with command !allow <wallet address>.")

        else:
            wins = random.randint(0,2)
            for i in range(3):
                if (random.random() < (wins/3) ):
                    slot_result[i] = SLOT_WIN
                    wins -= 1
                else:
                    slot_result[i] = random.choice(SLOT_LOSS)
            await message.reply(f"{slot_result[0]}  {slot_result[1]}  {slot_result[2]}  -- Sorry, you didn't win.")


    # # listen for !export command
    # @bot.command(brief='!export current allowlist as CSV', cog_name='Admin')
    # @commands.has_permissions(manage_guild=True)
    # async def export(message):
    #     doc_count = collection.count_documents({"project": PROJECT_NAME})
    #     await message.channel.send(f"There are currently {doc_count} addresses on the allowlist.")


#### helper functions

def check_eligibility(member): # returns top qualifying role for user
    approved_role = False
    for role in member.roles:
        if role.name in ALLOWED_ROLES:
            approved_role = role.name
    return approved_role

def add_to_list(member, list, wallet, project):
    project_name = project  # should check to see if in allowed guilds

    list_entry = {"project": project_name, "username": member.name, "discordID":member.id, "listname": list, "wallet": wallet, "joinDate": member.joined_at, "currentDate": datetime.datetime.utcnow()}
    if user_not_in_list(member, list, project_name):
        # add user to list
        collection.insert_one(list_entry)
        return f'You are added to the {list} list with wallet: {wallet}.'    
    else:
        # user already exists, update previous record instead of adding
        old_record = collection.find_one_and_update({"project": project_name, "discordID": member.id, "listname": list}, {"$set": {"wallet": wallet}})
        if old_record['wallet'] == wallet:
            return f'You were already on the "{list}" list with that wallet address, so nothing has changed.'
        else:
            return f'You were already on the "{list}" list, but your record has been updated with the new wallet info: {wallet}'

def get_list_entry(message):
    project_name = message.guild.name  # should check to see if in allowed guilds
    myquery = { "discordID": message.author.id, "project": project_name, "listname":check_eligibility(message.author)  }
    list_entry = collection.find_one(myquery)
    return list_entry

def get_any_list_entry(user, project_name):
    myquery = {"discordID": user.id, "project": project_name}
    list_entries = collection.find_one(myquery)
    return list_entries

def user_not_in_list(member, list, project):
    project_name = project  # should check to see if in allowed guilds
    myquery = { "discordID": member.id, "listname": list, "project": project_name  } 
    return (collection.count_documents(myquery) == 0)

def get_eligible_guild_roles(guild):
    my_roles=[]
    for role in guild.roles:
        # if role in message.guild.roles:
        if role.name in ALLOWED_ROLES:
            my_roles.insert(0,role.name)
    return my_roles

# def export_csv(query='{"project": PROJECT_NAME}'):

def slot_win(message):
    if random.random() < SLOT_CHANCE: 
        return True
    else:
        return False

def validate_wallet(wallet = ""):
    p = re.compile("0x[a-fA-F0-9]{40}")
    # wallet = wallet.strip()
    address = p.search(wallet)
    # return EthereumAddress(wallet)
    # return /^0x[a-fA-F0-9]{40}$/
    print(f"checking wallet {wallet}, found {address}")
    if address:
        return address.string
    else:
        return False

def is_allowed_channel(message, allowed_channels):
    if allowed_channels and message.channel.name not in allowed_channels:
        return False
    else:
        return True

def filter_channels(message, channels):
    filtered_channels = []
    for channel in message.guild.text_channels:
        print(channel)
        if channel in channels:
            filtered_channels.append(channel)

    return filtered_channels

async def wrong_channel_message(message,allowed_channels):
    # filtered_allowed_channels = filter_channels(message, allowed_channels)
    # await message.reply("You can only do that in the following channels: " + ', '.join(filtered_allowed_channels))
    await message.reply("Sorry, you can't do that in this channel.")


# def user_is_admin(member):
#     return member.hasPermissions(manage_guild=True)

bot.run(TOKEN)
