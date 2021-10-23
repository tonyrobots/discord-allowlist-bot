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


if not os.getenv("env") == "dev":
    os.environ['http_proxy'] = os.environ.get('FIXIE_URL', '')
    os.environ['https_proxy'] = os.environ.get('FIXIE_URL', '')
else:
    from dotenv import load_dotenv
    load_dotenv() # uncomment on dev!

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

# listen for !allow command
@bot.command(brief='!allow <wallet address> to add your wallet address to the appropriate allow list.', usage="<wallet>", aliases=["add"], cog_name='General')
async def allow(message, arg):
    if message.author == bot.user:
        return

    # arg = "0xca3a1d145Bf23674BD762Fa1A87EfE14BcfEa852"
    wallet = validate_wallet(arg)

    if not wallet:
        await message.channel.send(f"Sorry, {arg} is not a valid wallet address. (Note: ENS names like 'example.eth' are not supported.)")
        return

    if check_eligibility(message.author):
        approved_role = check_eligibility(message.author)

        # print(f'writing to db ' + message.author.name + ' as role ' + approved_role)
        result_message = add_to_list(message.author, approved_role, wallet)
        # await message.channel.send('Hello, ' + message.author.name +'!' + ' You are added to the ' + approved_role + ' list.')
        await message.channel.send(f"Hello, {message.author.name}! {result_message}")

    else:
        print('not an approved role!')
        await message.channel.send(f"Hello, {message.author.name}! Sorry, you don't appear to be eligible. If you think this is an error, contact @gm")

# listen for !check command
@bot.command(brief='!check to check your current list status.', cog_name='General')
async def check(message):
    if message.author == bot.user:
        return

    my_list = check_eligibility(message.author)
    if user_not_in_list(message.author, my_list):
        await message.channel.send(f"Hello, {message.author.name}! Sorry, you don't appear to be on the '{my_list}' list. Use !allow <wallet address> to add yourself.")
    else:
        list_entry = get_list_entry(message.author)
        await message.channel.send(f'Hi, {message.author.name}! You are in list "{list_entry["listname"]}" with wallet {list_entry["wallet"]}')

#### helper functions

def check_eligibility(member): # returns top qualifying role for user
    approved_role = False
    for role in member.roles:
        if role.name in ALLOWED_ROLES:
            approved_role = role.name
    return approved_role

def add_to_list(member, list, wallet):
    list_entry = {"project": PROJECT_NAME, "username": member.name, "discordID":member.id, "listname": list, "wallet": wallet, "joinDate": member.joined_at, "currentDate": datetime.datetime.utcnow()}
    if user_not_in_list(member, list):
        # add user to list
        collection.insert_one(list_entry)
        return f'You are added to the {list} list with wallet: {wallet}.'    
    else:
        # user already exists, update previous record instead of adding
        old_record = collection.find_one_and_update({"project": PROJECT_NAME, "discordID": member.id, "listname": list}, {"$set": {"wallet": wallet}})
        if old_record['wallet'] == wallet:
            return f'You were already on the "{list}" list with that wallet address, so nothing has changed.'
        else:
            return f'You were already on the "{list}" list, but your record has been updated with the new wallet info: {wallet}'

def get_list_entry(member):
        myquery = { "discordID": member.id, "project": PROJECT_NAME, "listname":check_eligibility(member)  }
        list_entry = collection.find_one(myquery)
        return list_entry


def user_not_in_list(member,list):
    myquery = { "discordID": member.id, "listname": list, "project": PROJECT_NAME  } # only checking discord ID, should check id, list, project
    # print (f"found {collection.count_documents(myquery)} docs that match your discord ID {member.id}")
    return (collection.count_documents(myquery) == 0)
    

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

bot.run(TOKEN)
