import os
from typing import Collection
from discord.ext import commands
import discord
import datetime
import re
import pymongo
from pymongo import MongoClient

import logging

logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv

load_dotenv() # uncomment on dev!

if not os.getenv("env") == "dev":
    os.environ['http_proxy'] = os.environ.get('FIXIE_URL', '')
    os.environ['https_proxy'] = os.environ.get('FIXIE_URL', '')

bot = commands.Bot(command_prefix="!")
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD")
MONGO_URL = os.getenv("MONGO_URL")
TESTING = True

PROJECT_NAME = "CF Test"
ALLOWED_ROLES = ["Friends", "Blerxers"] # Wonder how to set via a config UI

cluster = MongoClient(MONGO_URL)
db = cluster["AllowList"]
if TESTING: 
    collection = db["AllowList_test"]
else:
    collection = db["AllowList_prod"]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    for guild in bot.guilds:
        if guild.name == GUILD:
            break

    print(
        f'{bot.user} is connected to the following server:\n'
        f'{guild.name}(id: {guild.id})'
    )


### command listeners

#listen for !help command
# @bot.command()
#     await message.channel.send('use !check to check your current list status, and !allow <wallet address> to add yourself to the allow list. (Note: ENS names like example.eth are not accepted.')

# listen for !allow command
@bot.command()
async def allow(message, arg):
    if message.author == bot.user:
        return

    # arg = "0xca3a1d145Bf23674BD762Fa1A87EfE14BcfEa852"
    wallet = validate_wallet(arg)

    if not wallet:
        await message.channel.send("that's not a valid wallet address")
        return

    if check_eligibility(message.author):
        approved_role = check_eligibility(message.author)

        # print(f'writing to db ' + message.author.name + ' as role ' + approved_role)
        result_message = add_to_list(message.author, approved_role, wallet)
        # await message.channel.send('Hello, ' + message.author.name +'!' + ' You are added to the ' + approved_role + ' list.')
        await message.channel.send('Hello, ' + message.author.name +'! ' + result_message)

    else:
        print('not an approved role!')
        await message.channel.send('Hello, ' + message.author.name +'! ' + "Sorry, you don't appear to be eligible. If you think this is an error, contact @gm")

# listen for !check command
@bot.command()
async def check(message):
    if message.author == bot.user:
        return

    if user_not_in_list(message.author):
        await message.channel.send('Hello, ' + message.author.name +'! ' + "Sorry, you don't appear to be on the list. Use !allow <wallet address> to add yourself.")
    else:
        list_entry = get_list_entry(message.author)
        await message.channel.send('Hi, ' + message.author.name +'! You are in list ' + list_entry["listname"] )


#### helper functions

def check_eligibility(member): # returns top qualifying role for user
    approved_role = False
    for role in member.roles:
        if role.name in ALLOWED_ROLES:
            approved_role = role.name
    return approved_role

def add_to_list(member, list, wallet):
    list_entry = {"project": PROJECT_NAME, "username": member.name, "discordID":member.id, "listname": list, "wallet": wallet, "joinDate": member.joined_at, "currentDate": datetime.datetime.utcnow()}
    if user_not_in_list(member):
        # add user to list
        collection.insert_one(list_entry)
        return f'You are added to the {list} list.'    
    else:
        # user already exists, update previous record instead of adding
        # collection.find_one_and_update({project:})
        return 'You were already listed, but your record has been NOT YET updated with the new wallet info'

def get_list_entry(member):
        myquery = { "discordID": member.id, "project": PROJECT_NAME, "listname":check_eligibility(member)  }
        list_entry = collection.find_one(myquery)
        return list_entry


def user_not_in_list(member):
    myquery = { "discordID": member.id } # only checking discord ID, should check id, list, project
    # print (f"found {collection.count_documents(myquery)} docs that match your discord ID {member.id}")
    return (collection.count_documents(myquery) == 0)
    

def validate_wallet(wallet = ""):
    p = re.compile("0x[a-fA-F0-9]{40}")
    # wallet = wallet.strip()
    address = p.search(wallet)
    # return EthereumAddress(wallet)
    # return /^0x[a-fA-F0-9]{40}$/
    print(f"checking wallet {wallet}, found {address}")
    return address

bot.run(TOKEN)
