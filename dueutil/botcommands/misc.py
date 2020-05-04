import json
import os
import re
import subprocess
import math
import time
import random
from io import StringIO

import discord
import objgraph
import datetime

import generalconfig as gconf
import dueutil.permissions
from ..game.helpers import imagehelper
from ..permissions import Permission
from .. import commands, util, events, dbconn, loader
from ..game import customizations, awards, leaderboards, game
from ..game import emojis

# Import all game things. This is (bad) but is needed to fully use the eval command


@commands.command(permission=Permission.DISCORD_USER, args_pattern=None)
async def permissions(ctx, **_):
    """
    [CMD_KEY]permissions
    
    A check command for the permissions system.
    
    """

    permissions_report = ""
    for permission in dueutil.permissions.permissions:
        permissions_report += ("``" + permission.value[1] + "`` → "
                               + (":white_check_mark:" if dueutil.permissions.has_permission(ctx.author,
                                                                                             permission)
                                  else ":no_entry:") + "\n")
    await util.say(ctx.channel, permissions_report)


@commands.command(args_pattern="S*", hidden=True)
async def test(ctx, *args, **_):
    """A test command"""

    # print(args[0].__dict__)
    # args[0].save()
    # await imagehelper.test(ctx.channel)
    await util.say(ctx.channel, ("Yo!!! What up dis be my test command fo show.\n"
                                 "I got deedz args ```" + str(args) + "```!"))


@commands.command(args_pattern="RR", hidden=True)
async def add(ctx, first_number, second_number, **_):
    """
    [CMD_KEY]add (number) (number)
    
    One of the first test commands for Due2
    I keep it for sentimental reasons
    
    """

    result = first_number + second_number
    await util.say(ctx.channel, "Is " + str(result))


@commands.command()
async def wish(*_, **details):
    """
    [CMD_KEY]wish
    
    Does this increase the chance of a quest spawn?!
    
    Who knows?
    
    Me.
    
    """

    player = details["author"]
    player.quest_spawn_build_up += 0.005


@commands.command(permission=Permission.DUEUTIL_MOD, args_pattern="SSSSIP?")
async def uploadbg(ctx, icon, name, description, url, price, submitter=None, **details):
    """
    [CMD_KEY]uploadbg (a bunch of args)
    
    Takes:
      icon
      name
      desc
      url
      price
      
    in that order.
    
    NOTE: Make event/shitty backgrounds (xmas) etc **free** (so we can delete them)
    
    """

    if not (util.char_is_emoji(icon) or util.is_server_emoji(ctx.server, icon)):
        raise util.DueUtilException(ctx.channel, "Icon must be emoji available on this server!")

    if name != util.filter_string(name):
        raise util.DueUtilException(ctx.channel, "Invalid background name!")
    name = re.sub(' +', ' ', name)

    if name.lower() in customizations.backgrounds:
        raise util.DueUtilException(ctx.channel, "That background name has already been used!")

    if price < 0:
        raise util.DueUtilException(ctx.channel, "Cannot have a negative background price!")

    image = await imagehelper.load_image_url(url, raw=True)
    if image is None:
        raise util.DueUtilException(ctx.channel, "Failed to load image!")

    if not imagehelper.has_dimensions(image, (256, 299)):
        raise util.DueUtilException(ctx.channel, "Image must be ``256*299``!")

    image_name = name.lower().replace(' ', '_') + ".png"
    image.save('assets/backgrounds/' + image_name)

    try:
        backgrounds_file = open('assets/backgrounds/backgrounds.json', 'r+')
    except IOError:
        backgrounds_file = open('assets/backgrounds/backgrounds.json', 'w+')
    with backgrounds_file:
        try:
            backgrounds = json.load(backgrounds_file)
        except ValueError:
            backgrounds = {}
        backgrounds[name.lower()] = {"name": name, "icon": icon, "description": description, "image": image_name,
                                     "price": price}
        backgrounds_file.seek(0)
        backgrounds_file.truncate()
        json.dump(backgrounds, backgrounds_file, indent=4)

    customizations.backgrounds._load_backgrounds()

    await util.say(ctx.channel, ":white_check_mark: Background **" + name + "** has been uploaded!")
    await util.duelogger.info("**%s** added the background **%s**" % (details["author"].name_clean, name))

    if submitter is not None:
        await awards.give_award(ctx.channel, submitter, "BgAccepted", "Background Accepted!")


@commands.command(permission=Permission.DUEUTIL_MOD, args_pattern="S")
async def testbg(ctx, url, **_):
    """
    [CMD_KEY]testbg (image url)

    Tests if a background is the correct dimensions.
    
    """

    image = await imagehelper.load_image_url(url)
    if image is None:
        raise util.DueUtilException(ctx.channel, "Failed to load image!")

    if not imagehelper.has_dimensions(image, (256, 299)):
        width, height = image.size
        await util.say(ctx.channel, (":thumbsdown: **That does not meet the requirements!**\n"
                                     + "The tested image had the dimensions ``" + str(width)
                                     + "*" + str(height) + "``!\n"
                                     + "It should be ``256*299``!"))
    else:
        await util.say(ctx.channel, (":thumbsup: **That looks good to me!**\n"
                                     + "P.s. I can't check for low quality images!"))


@commands.command(permission=Permission.DUEUTIL_MOD, args_pattern="S")
async def deletebg(ctx, background_to_delete, **details):
    """
    [CMD_KEY]deletebg (background name)
    
    Deletes a background.
    
    DO NOT DO THIS UNLESS THE BACKGROUND IS FREE
    
    """
    background_to_delete = background_to_delete.lower()
    if background_to_delete not in customizations.backgrounds:
        raise util.DueUtilException(ctx.channel, "Background not found!")
    if background_to_delete == "default":
        raise util.DueUtilException(ctx.channel, "Can't delete default background!")
    background = customizations.backgrounds[background_to_delete]

    try:
        with open('assets/backgrounds/backgrounds.json', 'r+') as backgrounds_file:
            backgrounds = json.load(backgrounds_file)
            if background_to_delete not in backgrounds:
                raise util.DueUtilException(ctx.channel, "You cannot delete this background!")
            del backgrounds[background_to_delete]
            backgrounds_file.seek(0)
            backgrounds_file.truncate()
            json.dump(backgrounds, backgrounds_file, indent=4)
    except IOError:
        raise util.DueUtilException(ctx.channel,
                                    "Only uploaded backgrounds can be deleted and there are no uploaded backgrounds!")
    os.remove("assets/backgrounds/" + background["image"])

    customizations.backgrounds._load_backgrounds()

    await util.say(ctx.channel, ":wastebasket: Background **" + background.name_clean + "** has been deleted!")
    await util.duelogger.info(
        "**%s** deleted the background **%s**" % (details["author"].name_clean, background.name_clean))


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="S")
async def bbeval(ctx, statement, **details):
    """
    For 1337 haxors only! Go away!
    """
    if not (ctx.author.id == "115269304705875969" or ctx.author.id == "261799488719552513"):
        util.logger.info(ctx.author.id + " tried to use the command: dueeval")
        util.logger.info("Arguments used with dueeval: \n%s" % statement)
    
    try:
        if statement.startswith("await"):
            result = await eval(statement.replace("await", '', 1))
        else:
            result = eval(statement)
        if result is not None:
            await util.say(ctx.channel, ":ferris_wheel: Eval...\n"
                                        "**Result** ```" + str(result) + "```")
    except Exception as eval_exception:
        await util.say(ctx.channel, (":cry: Could not evalucate!\n"
                                    + "``%s``" % eval_exception))


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="CC?B?", hidden=True)
async def generatecode(ctx, value, count=1, show=True, **details):
    """
    [CMD_KEY]generatecode ($$$) (amount)

    Generates the number of codes (amount) with price ($$$)
    """

    newcodes = ""
    with open("dueutil/game/configs/codes.json", "r+") as code_file:
        codes = json.load(code_file)

        for i in range(count):
            code = "DUEUTILPROMO_%i" % (random.uniform(1000000000, 9999999999))
            while codes.get(code):
                code = "DUEUTILPROMO_%i" % (random.uniform(1000000000, 9999999999))
            codes[code] = value
            if show:
                newcodes += "%s\n" % (code)

        code_file.seek(0)
        code_file.truncate()
        json.dump(codes, code_file, indent=4)
    
    if show:
        code_Embed = discord.Embed(title="New codes!", type="rich", colour=gconf.DUE_COLOUR)
        code_Embed.add_field(name="Codes:", value=newcodes)
        code_Embed.set_footer(text="These codes can only be used once! Use %sredeem (code) to redeem the prize!" % (details["cmd_key"]))
        await util.say(ctx.channel, embed=code_Embed)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="C?")
async def codes(ctx, page=1, **details):
    """
    [CMD_KEY]codes

    Shows remaining codes
    """

    page = page - 1
    codelist=""
    with open("dueutil/game/configs/codes.json", "r+") as code_file:
        codes = json.load(code_file)
        codes = list(codes)
        if page != 0 and page * 30 >= len(codes):
            raise util.DueUtilException(ctx.channel, "Page not found")

        for index in range(len(codes) - 1 - (30 * page), -1, -1):
            code_name = codes[index]
            codelist += "%s\n" % (code_name)
            if len(codelist) == 720:
                break

    code_Embed = discord.Embed(title="New codes!", type="rich", colour=gconf.DUE_COLOUR)
    code_Embed.add_field(name="Codes:", value="%s" % (codelist if len(codelist) != 0 else "No code to display!"))
    code_Embed.set_footer(text="These codes can only be used once! Use %sredeem (code) to redeem the prize!" % (details["cmd_key"]))
    await util.say(ctx.channel, embed=code_Embed)


@commands.command(args_pattern="S")
async def redeem(ctx, code, **details):
    """
    [CMD_KEY]redeem (code)

    Redeem your code
    """

    with open("dueutil/game/configs/codes.json", "r+") as code_file:
        try:
            codes = json.load(code_file)
        except ValueError:
            codes = {}

        if not codes.get(code):
            code_file.close()
            raise util.DueUtilException(ctx.channel, "Code does not exist!")
        
        user = details["author"]
        money = codes[code]

        del codes[code]
        user.money += money
        user.save()
        
        code_file.seek(0)
        code_file.truncate()
        json.dump(codes, code_file, indent=4)
        code_file.close()

        await util.say(ctx.channel, "You successfully reclaimed **%s** !!" % (util.format_money(money)))

@commands.command(permission=Permission.DUEUTIL_OWNER, args_pattern="PS")
async def sudo(ctx, victim, command, **_):
    """
    [CMD_KEY]sudo victim command
    
    Infect a victims mind to make them run any command you like!
    """
    if not (ctx.author.id == "115269304705875969" or ctx.author.id == "261799488719552513"):
        util.logger.info(ctx.author.id + " used the command: sudo\nUsing command: %s" % command)
        if (victim.id == "115269304705875969" or victim.id == "261799488719552513"):
            raise util.DueUtilException(ctx.channel, "You cannot sudo DeveloperAnonymous or Firescoutt")

    try:
        ctx.author = ctx.server.get_member(victim.id)
        if ctx.author is None:
            # This may not fix all places where author is used.
            ctx.author = victim.to_member()
            ctx.author.server = ctx.server  # Lie about what server they're on.
        ctx.content = command
        await util.say(ctx.channel, ":smiling_imp: Sudoing **" + victim.name_clean + "**!")
        await events.command_event(ctx)
    except util.DueUtilException as command_failed:
        raise util.DueUtilException(ctx.channel, 'Sudo failed! "%s"' % command_failed.message)
        

@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="PC")
async def setpermlevel(ctx, player, level, **_):
    if not (ctx.author.id == "115269304705875969" or ctx.author.id == "261799488719552513"):
        util.logger.info(ctx.author.id + " used the command: setpermlevel\n")
        if (player.id == "115269304705875969" or player.id == "261799488719552513"):
            raise util.DueUtilException(ctx.channel, "You cannot change the permissions for DeveloperAnonymous or Firescoutt")
    member = discord.Member(user={"id": player.id})
    permission_index = level - 1
    permission_list = dueutil.permissions.permissions
    if permission_index < len(permission_list):
            permission = permission_list[permission_index]
            dueutil.permissions.give_permission(member, permission)
            await util.say(ctx.channel,
                        "**" + player.name_clean + "** permission level set to ``" + permission.value[1] + "``.")
            if permission == Permission.DUEUTIL_MOD:
                await awards.give_award(ctx.channel, player, "Mod", "Become an mod!")
                await util.duelogger.info("**%s** is now a DueUtil mod!" % player.name_clean)
            elif "Mod" in player.awards:
                player.awards.remove("Mod")
            if permission == Permission.DUEUTIL_ADMIN:
                await awards.give_award(ctx.channel, player, "Admin", "Become an admin!")
                await util.duelogger.info("**%s** is now a DueUtil admin!" % player.name_clean)
            elif "Admin" in player.awards:
                player.awards.remove("Admin")
    else:
        raise util.DueUtilException(ctx.channel, "Permission not found")


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="P", aliases=["giveban"])
async def ban(ctx, player, **_):
    if (player.id == "115269304705875969" or (player.id == "261799488719552513")):
        raise util.DueUtilException(ctx.channel, "You cannot ban DeveloperAnonymous or Firescoutt")
    dueutil.permissions.give_permission(player.to_member(), Permission.BANNED)
    await util.say(ctx.channel, emojis.MACBAN+" **" + player.name_clean + "** banned!")
    await util.duelogger.concern("**%s** has been banned!" % player.name_clean)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="P", aliases=["pardon"])
async def unban(ctx, player, **_):
    member = player.to_member()
    if not dueutil.permissions.has_special_permission(member, Permission.BANNED):
        await util.say(ctx.channel, "**%s** is not banned..." % player.name_clean)
        return
    dueutil.permissions.give_permission(member, Permission.PLAYER)
    await util.say(ctx.channel, ":unicorn: **" + player.name_clean + "** has been unbanned!")
    await util.duelogger.info("**%s** has been unbanned" % player.name_clean)

@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None, hidden=True)
async def bans(ctx, **_):
    bans_embed = discord.Embed(title="Ban list", type="rich", color=gconf.DUE_COLOUR)
    stringe = ""
    for k, v in dueutil.permissions.special_permissions.items():
        if v == "banned":
            stringe += "<@%s> (%s)\n" % (k,k)
    bans_embed.add_field(name="There is what I collected about bad people:", value=stringe or "Nobody is banned!")

    await util.say(ctx.channel, embed=bans_embed)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="P")
async def toggledonor(ctx, player, **_):
    player.donor = not player.donor
    if player.donor:
        await util.say(ctx.channel, "**%s** is now a donor!" % player.name_clean)
    else:
        await util.say(ctx.channel, "**%s** is no longer donor" % player.name_clean)


@commands.command(permission=Permission.DUEUTIL_OWNER, args_pattern=None)
async def relaodbot(ctx, **_):
    await util.say(ctx.channel, ":ferris_wheel: Reloading BattleBanana modules!")
    await util.duelogger.concern("BattleBanana Reloading!")
    loader.reload_modules(packages=loader.COMMANDS)
    raise util.DueReloadException(ctx.channel)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="IP*")
async def givecash(ctx, amount, *players, **_):
    toSend = ""
    for player in players:
        player.money += amount
        amount_str = util.format_number(abs(amount), money=True, full_precision=True)
        if amount >= 0:
            toSend += "Added ``" + amount_str + "`` to **" + player.get_name_possession_clean() + "** account!\n"
        else:
            toSend += "Subtracted ``" + amount_str + "`` from **" + player.get_name_possession_clean() + "** account!\n"
        player.save()

    await util.say(ctx.channel, toSend)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="PI")
async def setcash(ctx, player, amount, **_):
    player.money = amount
    amount_str = util.format_number(amount, money=True, full_precision=True)
    await util.say(ctx.channel, "Set **%s** balance to ``%s``" % (player.get_name_possession_clean(), amount_str))

@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="PI")
async def setprestige(ctx, player, prestige, **details):
    player.prestige_level = prestige
    player.save()
    await util.say(ctx.channel, "Set prestige to **%s** for **%s**" % (prestige, player.get_name_possession_clean()))


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="PS")
async def giveaward(ctx, player, award_id, **_):
    if awards.get_award(award_id) is not None:
        await awards.give_award(ctx.channel, player, award_id)
    else:
        raise util.DueUtilException(ctx.channel, "Award not found!")


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern="PR")
async def giveexp(ctx, player, exp, **_):
    # (attack + strg + accy) * 100
    if exp < 0.1:
        raise util.DueUtilException(ctx.channel, "The minimum exp that can be given is 0.1!")
    increase_stat = exp/300
    player.progress(increase_stat, increase_stat, increase_stat,
                    max_exp=math.inf, max_attr=math.inf)
    await util.say(ctx.channel, "**%s** has been given **%s** exp!"
                   % (player.name_clean, util.format_number(exp, full_precision=True)))
    await game.check_for_level_up(ctx, player)
    player.save()


@commands.command(permission=Permission.DUEUTIL_MOD, args_pattern=None)
async def updateleaderboard(ctx, **_):
    leaderboards.last_leaderboard_update = 0
    await leaderboards.update_leaderboards(ctx)
    await util.say(ctx.channel, ":ferris_wheel: Updating leaderboard!")


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None)
async def updatebot(ctx, **_):
    """
    [CMD_KEY]updatebot
    
    Updates BattleBanana
    
    """

    try:
        update_result = subprocess.check_output(['bash', 'update_script.sh'])
    except subprocess.CalledProcessError as updateexc:
        update_result = updateexc.output
    update_result = update_result.decode("utf-8")
    if len(update_result.strip()) == 0:
        update_result = "No output."
    update_embed = discord.Embed(title=":gear: Updating BattleBanana!", type="rich", color=gconf.DUE_COLOUR)
    update_embed.description = "Pulling lastest version from **github**!"
    update_embed.add_field(name='Changes', value='```' + update_result + '```', inline=False)
    await util.say(ctx.channel, embed=update_embed)
    update_result = update_result.strip()
    if not (update_result.endswith("is up to date.") or update_result.endswith("up-to-date.")):
        await util.duelogger.concern("BattleBanana updating!")
        os._exit(1)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None)
async def stopbot(ctx, **_):
    await util.say(ctx.channel, ":wave: Stopping BattleBanana!")
    await util.duelogger.concern("BattleBanana shutting down!")
    for client in util.shard_clients:
        await client.change_presence(game=discord.Game(name="restarting"), status=discord.Status.idle, afk=True)
    os._exit(0)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None)
async def restartbot(ctx, **_):
    await util.say(ctx.channel, ":ferris_wheel: Restarting BattleBanana!")
    await util.duelogger.concern("BattleBanana restarting!!")
    for client in util.shard_clients:
        await client.change_presence(game=discord.Game(name="restarting"), status=discord.Status.idle, afk=True)
    os._exit(1)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None)
async def meminfo(ctx, **_):
    mem_info = StringIO()
    objgraph.show_most_common_types(file=mem_info)
    await util.say(ctx.channel, "```%s```" % mem_info.getvalue())
    mem_info = StringIO()
    objgraph.show_growth(file=mem_info)
    await util.say(ctx.channel, "```%s```" % mem_info.getvalue())

@commands.command(args_pattern=None)
async def ping(ctx,**_):
    """
    [CMD_KEY]ping
    pong! Gives you the response time.
    """
    message = await util.say(ctx.channel, ":ping_pong:")

    apims = round((message.timestamp - ctx.timestamp).total_seconds() * 1000)

    t1 = time.time()
    dbconn.conn().command("ping")
    t2 = time.time()
    dbms = round((t2 - t1) * 1000)
    
    embed = discord.Embed(title=":ping_pong: Pong!", type="rich", colour=gconf.DUE_COLOUR)
    embed.add_field(name="Bot Latency:", value="``%sms``" % (apims))
    embed.add_field(name="Database Latency:", value="``%sms``" % (dbms), inline=False)

    await util.edit_message(message, embed=embed)
    
@commands.command(args_pattern=None, hidden=True)
async def pong(ctx,**_):
    """
    [CMD_KEY]pong
    pong! Gives you the response time.
    """
    message = await util.say(ctx.channel, ":ping_pong:")

    apims = round((message.timestamp - ctx.timestamp).total_seconds() * 1000)

    t1 = time.time()
    dbconn.conn().command("ping")
    t2 = time.time()
    dbms = round((t2 - t1) * 1000)
    
    embed = discord.Embed(title=":ping_pong: Ping!", type="rich", colour=gconf.DUE_COLOUR)
    embed.add_field(name="Database Latency:", value="``%sms``" % (dbms))
    embed.add_field(name="Bot Latency:", value="``%sms``" % (apims), inline=False)

    await util.edit_message(message, embed=embed)


@commands.command(args_pattern=None)
async def vote(ctx, **details):
    """
    Obtain ¤50'000 for voting on Discord Bot List
    """
    
    Embed = discord.Embed(title="Vote for your favorite Discord Bot", type="rich", colour=gconf.DUE_COLOUR)
    Embed.add_field(name="Vote:", value="[Discord Bot list](https://discordbots.org/bot/464601463440801792/vote)\n"
                                        "[Bot On Discord](https://bots.ondiscord.xyz/bots/464601463440801792)")
    Embed.set_footer(text="You will receive your reward shortly after voting!")

    await util.say(ctx.channel, embed=Embed)


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None, hidden=True)
async def cleartopdogs(ctx, **details):
    await util.say(ctx.channel, ":arrows_counterclockwise: Removing every active topdog!")
    for id, v in sorted(game.players.players.items()):
        if 'TopDog' in v.awards:
            v.awards.remove("TopDog")
            v.save()
    
    await util.say(ctx.channel, "Scan is done! ")


@commands.command(permission=Permission.DUEUTIL_ADMIN, args_pattern=None, hidden=True)
async def hello(ctx, **_):
    await util.say(ctx.channel, "hello world!")