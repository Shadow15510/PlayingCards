import discord
from discord.ext import commands
from PIL import Image
import os
from random import randint


CARD_WIDTH = 185
CARD_HEIGHT = 340
CARDS_PER_IMG = 6


def make_embed(fields, title, description, color=8421504, inline=False):
    embeds = []
    nb = len(fields) // 25 + 1
    index = 1
    while fields:
        embed = discord.Embed(title=f"{title} ({index}/{nb})", description=description, color=color)
        for field in fields[: 25]:
            embed.add_field(name=field[0], value=field[1], inline=inline)
        fields = fields[25: ]
        index += 1
        embeds.append(embed)
    return embeds


def shuffle_cards(nb):
    if nb == 78:
        cards_tmp = [i for i in range(78)]
    elif nb == 52:
        cards_tmp = [i for i in range(56) if (i % 14) != 11]
    elif nb == 32:
        cards_tmp = [i for i in range(56) if (i % 14) != 11 and (not (i % 14) or (i % 14) > 5)]

    cards = []
    for i in range(nb):
        cards.append(cards_tmp.pop(randint(0, nb - i - 1)))
    return cards


def generate_deck(*cards):
    tarotcards = Image.open("cards.gif")
    n = len(cards)
    sup_img = 1 if n % CARDS_PER_IMG else 0
    decks = [Image.new(mode="RGBA", size=(CARD_WIDTH * CARDS_PER_IMG, CARD_HEIGHT)) for _ in range(sup_img + n // CARDS_PER_IMG)]
    for index, card in enumerate(cards):
        x1 = CARD_WIDTH * (card % 14)
        y1 = (CARD_HEIGHT * (card // 14))

        img_card = tarotcards.crop((x1, y1, x1 + CARD_WIDTH, y1 + CARD_HEIGHT))
        decks[index // CARDS_PER_IMG].paste(img_card, ((index % CARDS_PER_IMG) * CARD_WIDTH, 0))

    return decks


async def send_deck(send_fn, title, cards, auto_sort=True):
    if auto_sort: decks = generate_deck(*sorted(cards))
    else: decks = generate_deck(*cards)
    await send_fn(f"**{title}**\n({len(decks)} image{('', 's')[len(decks) > 1]})")
    for deck in decks:
        deck.save(f"{title}.gif")
        await send_fn("", file=discord.File(f"{title}.gif"))
        os.remove(f"{title}.gif")


def get_cards_id(*cards):
    cards_id = []
    values = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "v", "c", "d", "r")

    for card in cards:
        card = card.lower()
        if card.endswith("pi"):
            cards_id.append(values.index(card[:-2]))
        elif card.endswith("co"):
            cards_id.append(values.index(card[:-2]) + 14)
        elif card.endswith("ca"):
            cards_id.append(values.index(card[:-2]) + 28)
        elif card.endswith("tr"):
            cards_id.append(values.index(card[:-2]) + 42)
        elif card.startswith("a"):
            cards_id.append(55 + int(card[1:]))
        elif card == "e":
            cards_id.append(77)
    
    return cards_id


async def public(ctx):
    if not ctx.guild:
        await ctx.send("*Erreur : ce message doit être public.*")
        return False
    else:
        return True


async def private(ctx):
    if ctx.guild:
        await ctx.send("*Erreur : ce message doit être privé.*")
        return False
    else:
        return True


class DefaultCommands(commands.Cog):
    def __init__(self, config):
        self.PREFIX = config["PREFIX"]
        self.players = []
        self.player_index = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 503720029456695306:
            await message.add_reaction("🖕")

    @commands.command(help="Affiche l'aide ou l'aide détaillée. Les arguments entre chevrons (`<>`) sont les arguments obligatoire, les arguments entre crochets (`[]`) sont les arguments facultatifs.", brief="Affiche ce panneau")
    async def aide(self, ctx, commande: str=None):

        def get_syntax(cmnd):
            syntax = f"`{self.PREFIX}{cmnd.name}"
            for arg in cmnd.clean_params:
                if "=" in str(cmnd.clean_params[arg]):
                    syntax+= f" [{arg}]"
                else:
                    syntax += f" <{arg}>"
            return syntax + "`"
            
        if commande:
            embed = discord.Embed(title="Aide détaillée", description="Informations complémentaires", color=8421504)
            cmnd_data = {cmnd.name: cmnd for cmnd in self.get_commands()}

            if commande in cmnd_data:
                cmnd = cmnd_data[commande]
                embed.add_field(name="Syntaxe", value=get_syntax(cmnd), inline=True)
                embed.add_field(name="Description", value=cmnd.help, inline=True)
            else:
                embed.add_field(name="Erreur : commande inconnue", value=f"Entrez `{self.PREFIX}aide` pour avoir la liste des commandes.")
            
            await ctx.send(embed=embed)

        else:
            fields = []
            for cmnd in self.get_commands():
                fields.append((cmnd.brief, get_syntax(cmnd)))
            
            for embed in make_embed(fields, "Rubique d'aide", f"Entrez : `{self.PREFIX}aide <commande>` pour plus d'informations."):
                await ctx.send(embed=embed)

    def get_player_from_id(self, player_id, check_turn=False):
        for index, player in enumerate(self.players):
            if player_id == player.user_id:
                if not check_turn: return player
                elif self.player_index == index: return player
        return None

    def get_player_from_name(self, player_name, check_turn=False):
        for index, player in enumerate(self.players):
            if player_name == player.user_name:
                if not check_turn: return player
                elif self.player_index == index: return player
        return None


class DefaultPlayer:
    def __init__(self, user_id, user_name, send, cards=[]):
        self.user_id = user_id
        self.user_name = user_name
        self.send = send

        if self.cards: self.cards = cards
        else: self.cards = []

    def clean_deck(self):
        self.cards = []

    async def send_private_deck(self):
        decks = generate_deck(*sorted(self.cards))
        await self.send(f"**Votre main ({self.user_name})**\n({len(decks)} image{('', 's')[len(decks) > 1]})")

        for deck in decks:
            deck.save(f"{self.user_id}.gif")
            await self.send("", file=discord.File(f"{self.user_id}.gif"))
            os.remove(f"{self.user_id}.gif")

    async def send_public_deck(self, ctx):
        await send_deck(ctx.send, f"La main de {self.user_name}", self.cards)

    def select_card_by_color(self, color_id):
        return [i for i in self.cards if (i // 14) == color_id]

    def select_card_by_value(self, value_id):
        return [i for i in self.cards if (i % 14) == value_id]

