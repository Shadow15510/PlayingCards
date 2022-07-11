import discord
from discord.ext import commands
import json
import os

from games.tarot import Tarot


with open("config.json", "r") as file:
    config = json.load(file)

if not "saves" in os.listdir():
    os.mkdir("saves")

playing_cards = commands.Bot(command_prefix=config["PREFIX"], strip_after_prefix=True)


@playing_cards.event
async def on_ready():
    game = 0
    games_list, index = [], 1
    for value in os.listdir('games'):
        if value != "__pycache__":
            games_list.append(f"{index}. {value.split('.')[0].title()}")
            index += 1
            
    games_str = "\n".join(games_list)
    while not game:
        print(f"Quel jeu charger ?\n{games_str}")
        game = input("> ")
        try: game = int(game)
        except: game = 0
        if not (1 <= game <= len(games_list)): game = 0

    print(f"Chargement du jeu :{games_list[game - 1].split('.')[1]}")

    if game == 1:
        playing_cards.add_cog(Tarot(config, playing_cards))

    activity = discord.Activity(type=discord.ActivityType.playing, name=f"{games_list[game - 1].split('.')[1]} │ {config['PREFIX']}aide")
    await playing_cards.change_presence(activity=activity)
    print("Connecté")

playing_cards.run(config["TOKEN"])


# 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, V, C, D, R
# co, pi, ca, tr
# A1 - A21 E