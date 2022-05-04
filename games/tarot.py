import json
from lib_playingcards import *


class Tarot(DefaultCommands):
    def __init__(self, config, bot):
        # Constantes
        self.config = config
        self.PREFIX = config["PREFIX"]
        self.bot = bot
        self.CARDS_BY_DESC = []
        for i in range(76, 55, -1): self.CARDS_BY_DESC.append(i)
        for i in range(13, -1, -1):
            for j in range(4): self.CARDS_BY_DESC.append(i + 14 * j)
        self.CARDS_BY_DESC.append(77)
        
        # Joueurs
        self.players = []
        self.player_index = 0
        self.giver_index = 0
        self.first_giver_index = 0
        self.taker_index = 0
        self.first_index = 0
        self.leader_index = -1
        self.player_excuse_index = -1
        self.taker_bonus = 0
        self.defense_bonus = 0
        
        # Cartes
        self.cards = shuffle_cards(78)
        self.taker_tricks = []
        self.defense_tricks = []
        self.table = []
        self.ref_card = -1

        # Indicateurs et fonction de message
        self.game_phase = 0
        self.trick_index = 0
        self.guild_send = None
        self.old_table = []

        self.auction = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 969872133998116944 and message.guild and self.game_phase == 4 and ("Table" in message.content or message.attachments):
            self.old_table.append(message)

    async def _init_game(self, ctx):
        async def init_players_decks():
            def petit_sec(player):
                for i in range(57, 78):
                    if i in player.cards: return False
                return True
            
            self.cards = shuffle_cards(78)

            for player in self.players:
                player.clean_deck()
                player.clean_auction()
                player.cards = self.cards[:18]
                self.cards = self.cards[18:]
                
                if 56 in player.cards and petit_sec(player):
                    await ctx.send(f"{player.user_name} avait un Petit sec. Re-distribution des cartes.")
                    await init_players_decks()
        self.game_phase = 1

        # Distribution des cartes
        await ctx.send("__Distribution des cartes.__")
        await init_players_decks()
        for player in self.players:
            await player.send_private_deck()

        # Début des enchères
        self.game_phase += 1
        await ctx.send(f"__Enchères__\nC'est à {self.players[self.player_index].user_name} de dire son enchère.")

    @commands.command(help="Permet de voir sa main. Les carte sont envoyées sous forme d'image en message privée (Le temps d'attente est d'environ 2 secondes).", brief="Voir sa main.")
    async def main(self, ctx):
        player = self.get_player_from_id(ctx.author.id)
        if not player: await ctx.send("*Erreur : vous n'êtes pas un joueur enregistré.*") ; return
        if not self.game_phase: await ctx.send("*Erreur : la partie n'est pas encore commencée.*") ; return
        await player.send_private_deck()


    @commands.command(name="poignée", help="Permet de déclarer une poignée de 10, 13 ou 15 atouts. Une poignée non déclarée n'est pas prise en compte dans les points. Déclarer une poignée affiche vos atouts au reste de la table.", brief="Déclarer une poignée.")
    @commands.check(public)
    async def poignee(self, ctx):
        player = self.get_player_from_id(ctx.author.id, check_turn=True)
        if not player: await ctx.send("*Erreur : vous n'êtes pas un joueur enregistré ou ce n'est pas votre tour.*") ; return
        if not self.game_phase in (2, 3): await ctx.send("*Erreur : ce n'est pas le moment d'annoncer une poignée.*") ; return

        def delete_trump(trumps, size):
            if len(trumps) <= size: return trumps
            else:
                if 56 in trumps and len(trumps) >= (size + 1): trumps.remove(56)
                if 76 in trumps and len(trumps) >= (size + 1): trumps.remove(76)
                if 77 in trumps and len(trumps) >= (size + 1): trumps.remove(77)

            return trumps[:size]


        trumps = player.select_trump_cards()
        nb_trump = len(trumps)
        
        if nb_trump >= 15:
            if player.index == self.taker_index: self.taker_bonus += 40
            else: self.defense_bonus += 40
            await send_deck(ctx.send, f"{player.user_name} déclare une poignée de 15.", delete_trump(trumps, 15))
        
        elif nb_trump >= 13:
            if player.index == self.taker_index: self.taker_bonus += 30
            else: self.defense_bonus += 30
            await send_deck(ctx.send, f"{player.user_name} déclare une poignée de 13.", delete_trump(trumps, 13))

        elif nb_trump >= 10:
            if player.index == self.taker_index: self.taker_bonus += 20
            else: self.defense_bonus += 20
            await send_deck(ctx.send, f"{player.user_name} déclare une poignée de 10.", delete_trump(trumps, 10))

        else: await ctx.send("*Erreur : il faut avoir au moins 10 atouts pour déclarer une poignée.*")

    @commands.command(help="Permet de rejoindre une partie.", brief="Rejoindre une partie.")
    @commands.check(public)
    async def rejoindre(self, ctx): # phase : 0
        player = self.get_player_from_id(ctx.author.id)
        if player: await ctx.send("*Erreur : vous avez déjà rejoint la partie.*") ; return
        if self.game_phase: await ctx.send("*Erreur : une partie est déjà commencée.*") ; return

        if ctx.author.nick: name = ctx.author.nick
        else: name = ctx.author.name
        self.players.append(Player(ctx.author.id, name, ctx.author.send, len(self.players)))

        await ctx.send(f"{name} a rejoint la partie.")
        await self.players[-1].send("Bienvenue, une partie de Tarot est en train de commencer.")

        if not self.guild_send: self.guild_send = ctx.send

    @commands.command(help="Déclare la partie comme commencée. Cela bloque les nouveaux arrivants et initialise le jeu.", brief="Commencer la partie.")
    @commands.check(public)
    async def commencer(self, ctx): # phase : 1
        if len(self.players) < 4: await ctx.send(f"*Erreur : il n'y a pas assez de joueurs ({len(self.players)} / 4).*") ; return
        elif len(self.players) > 4: await ctx.send(f"*Erreurs : il y a trop de joueurs. Les derniers arrivés ({', '.join([i.user_name for i in self.players[4:]])}) seront ignorés.*")
        if self.game_phase: await ctx.send("*Erreur : une partie est déjà commencée.*")
        
        # Déclaration de la partie comme commencée
        await ctx.send("La partie commence.")

        # Détermination du donneur
        await ctx.send("__Détermination du donneur.__")
        for i, player in enumerate(self.players):
            player.cards.append(self.cards.pop(randint(0, 77 - i)))
            await player.send_public_deck(ctx)

        self.giver_index = 0
        max_tmp = self.CARDS_BY_DESC.index(self.players[0].cards[0])
        for index, player in enumerate(self.players):
            card_index = self.CARDS_BY_DESC.index(player.cards[0])
            if player.cards[0] != 77 and card_index < max_tmp:
                self.giver_index = index
                max_tmp = card_index

        await ctx.send(f"{self.players[self.giver_index].user_name} est le⋅a donneur⋅euse. Les joueurs sont disposés dans l'ordre suivant :\n - " + "\n - ".join([player.user_name for player in self.players]))
        self.player_index = (self.giver_index + 1) % 4
        self.first_giver_index = self.giver_index

        # Initialisation des mains
        await self._init_game(ctx)

    @commands.command(name="enchère", help="Détermine le type d'enchère. Il existe 4 types d'enchères : prise, garde, garde sans et garde contre. À son tour le joueur peut aussi choisir de passer. Le joueur peut ajouer 'chelem' à la fin de son enchère pour annoncer un Chelem.", brief="Annoncer son enchère.")
    @commands.check(public)
    async def enchere(self, ctx, *type_enchere: str): # phase : 2
        player = self.get_player_from_id(ctx.author.id, check_turn=True)
        if not player: await ctx.send("*Erreur : vous n'êtes pas un joueur enregistré ou ce n'est pas votre tour.*") ; return
        if self.game_phase != 2: await ctx.send("*Erreur : ce n'est pas le moment des enchères.*") ; return

        type_enchere = " ".join(type_enchere).lower()

        if "passe" in type_enchere: # 0
            await ctx.send(f"{player.user_name} passe son tour.")

        elif "prise" in type_enchere or "prend" in type_enchere: # 1
            if self.players[(self.player_index - 1) % 4].auction < 1:
                player.auction = 1
                await ctx.send(f"{player.user_name} prend.")
            else:
                await ctx.send(f"{player.user_name} ne peut pas prendre car {self.players[(self.player_index - 1) % 4].user_name} a déjà fait une enchère plus forte.")
                return

        elif "garde sans" in type_enchere: # 3
            if self.players[(self.player_index - 1) % 4].auction < 3:
                player.auction = 3
                await ctx.send(f"{player.user_name} garde sans le Chien.")
            else:
                await ctx.send(f"{player.user_name} ne peut pas prendre car {self.players[(self.player_index - 1) % 4].user_name} a déjà fait une enchère plus forte.")
                return

        elif "garde contre" in type_enchere: # 4
            if self.players[(self.player_index - 1) % 4].auction < 4:
                player.auction = 4
                await ctx.send(f"{player.user_name} garde contre le Chien.")
            else:
                await ctx.send(f"{player.user_name} ne peut pas prendre car {self.players[(self.player_index - 1) % 4].user_name} a déjà fait une enchère plus forte.")
                return

        elif "garde" in type_enchere: # 2
            if self.players[(self.player_index - 1) % 4].auction < 2:
                player.auction = 2
                await ctx.send(f"{player.user_name} garde.")
            else:
                await ctx.send(f"{player.user_name} ne peut pas prendre car {self.players[(self.player_index - 1) % 4].user_name} a déjà fait une enchère plus forte.")
                return

        else:
            await ctx.send(f"*Erreur : le type d'enchère : '{type_enchere}' n'est pas reconnu.*")
            return

        if "chelem" in type_enchere:
            player.chelem = 1
            await ctx.send(f"{player.user_name} annonce un Chelem.")

        self.player_index = (self.player_index + 1) % 4

        if self.player_index == (self.giver_index + 1) % 4:
            if sum([i.auction for i in self.players]):
                player = self.players[0]
                for index, i in enumerate(self.players):
                    if i.auction > player.auction or player.chelem:
                        player = i
                        self.player_index = index

                await ctx.send(f"Fin des enchères. {player.user_name} est le⋅a preneur⋅euse.")
                self.taker_index = self.player_index
                self.auction = player.auction

                if self.auction in (3, 4):
                    if self.auction == 3: self.taker_tricks = self.cards.copy()
                    elif self.auction == 4: self.defense_tricks = self.cards.copy()
                    self.cards.clear()
                    self.game_phase += 2
                    await ctx.send()
                else:
                    await send_deck(ctx.send, "Cartes du Chien", self.cards)
                    player.cards += self.cards[:]
                    self.cards.clear()

                    self.game_phase += 1
                    await ctx.send(f"__Écart__\n{player.user_name} doit écarter six cartes de son jeu.")
                    await player.send("Vous devez écarter six cartes de votre jeu.")
                    await player.send_private_deck()

            else:
                await ctx.send("Aucune enchère n'a été prise : re-distribution des cartes.")

                for i in self.players:
                    i.cards.clear()
                self.cards = shuffle_cards(78)
                self.game_phase = 0
                await self.commencer(ctx)
        else:
            await ctx.send(f"C'est à {self.players[self.player_index].user_name} de dire son enchère.")

    @commands.command(name="écarte", aliases=["écarter"], help="Une fois l'enchère prise, le joueur peut être amené à écarter six cartes de son jeu.", brief="Écarter les six cartes.")
    @commands.check(private)
    async def ecarte(self, ctx, *cartes): # phase : 3
        player = self.get_player_from_id(ctx.author.id, check_turn=True)
        if not player: await ctx.send("*Erreur : vous n'êtes pas un joueur enregistré ou ce n'est pas votre tour.*") ; return
        if self.game_phase != 3: await ctx.send("*Erreur : ce n'est pas le moment d'écarter des cartes.*") ; return

        cards_id = get_cards_id(*cartes)
        if len(cards_id) != 6: await player.send("*Erreur : vous devez écarter six cartes.*") ; return
        for index, i in enumerate(cards_id):
            if not i in player.cards:
                await player.send(f"*Erreur : vous ne possédez pas cette carte : '{cartes[i]}'.*")
                return
            if (i % 14 == 13) or i in (56, 76, 77):
                await player.send("*Erreur : vous ne pouvez pas donner de Roi ou de Bouts.*")
                return
            if cards_id.count(i) != 1:
                await player.send("*Erreur : vous ne pouvez pas donner deux fois la même carte.*")
                return

        for i in range(6):
            player.cards.remove(cards_id[i])
            self.taker_tricks.append(cards_id[i])

        await player.send_private_deck()
        self.player_index = (self.giver_index - 1) % 4
        self.first_index = self.player_index
        await self.guild_send(f"{player.user_name} a donné six cartes valides.\nC'est à {self.players[self.player_index].user_name} de poser une carte.")

        self.trick_index = 0
        self.game_phase += 1

    @commands.command(aliases=["poser"], help="Poser une carte sur la table.\nLes cartes sont repérées par leur valeur (1 - R) suivi de leur couleur (pi, co, ca, tr). Pour les atouts, indiquez seulement A suivi de la valeur. E pour jouer l'Excuse.", brief="Poser une carte.")
    @commands.check(public)
    async def pose(self, ctx, carte: str): # phase : 4
        player = self.get_player_from_id(ctx.author.id, check_turn=True)
        if not player: await ctx.send("*Erreur : vous n'êtes pas un joueur enregistré ou ce n'est pas votre tour.*") ; return
        if self.game_phase != 4: await ctx.send("*Erreur : ce n'est pas le moment de poser une carte.*") ; return

        # Vérification de la carte
        card_id = get_cards_id(carte)[0]
        if not card_id in player.cards:
            await ctx.send("*Erreur : vous ne possédez pas cette carte.*")
            return 

        # Établissement de la carte de référence
        if self.ref_card == -1:
            if card_id != 77:
                self.ref_card = card_id
                self.leader_index = self.player_index
        
        # Vérification de la validité de la carte
        else:
            max_trump = 0
            for i in self.table:
                if (56 <= i[0] <= 76) and i[0] > max_trump: max_trump = i[0]

            # si c'est de l'atout demandé, que la carte posée est en sous-coupe alors que le joueur peut surcouper
            if self.ref_card >= 56 and card_id < max_trump and player.select_trump_cards(max_trump):
                await ctx.send("*Erreur : vous devez surcouper.*")
                return

            # si la couleur ne correspond pas
            elif self.ref_card < 56 and self.ref_card // 14 != card_id // 14: 
                # si le joueur a la couleur demandée
                if player.select_card_by_color(self.ref_card // 14):
                    await ctx.send("*Erreur : vous devez jouer la couleur demandée.*")
                    return

                # si le joueur n'a pas la couleur mais a de l'atout
                elif player.select_trump_cards():
                    # si la carte posée n'est pas de l'atout
                    if card_id < 56:
                        await ctx.send("*Erreur : vous devez couper.*")
                        return

                    # si la carte posée est un atout trop petit
                    elif (card_id < max_trump) and player.select_trump_cards(max_trump):
                        await ctx.send("*Erreur : vous devez surcouper.*")
                        return

        # Mise à jour du leader de la levée
        leader_card = get_leader_card(self.table, self.leader_index)
        if leader_card != -1 and self.CARDS_BY_DESC.index(card_id) < self.CARDS_BY_DESC.index(leader_card):
            self.leader_index = self.player_index

        player.cards.remove(card_id)
        self.table.append((card_id, self.player_index))
        if self.old_table:
            for i in self.old_table: await i.delete()
            self.old_table.clear()
        await send_deck(ctx.send, "Table", [i[0] for i in self.table], False)

        self.player_index = (self.player_index + 1) % 4

        # Si les 4 joueurs ont joués
        if self.player_index == self.first_index:
            await ctx.send(f"Fin de la levée. C'est {self.players[self.leader_index].user_name} qui remporte la levée.")
            
            for i in self.table:
                if i[0] == 77: self.player_excuse_index = i[1]
                if i[0] == 56 and self.trick_index == 18:
                    if i[1] == self.taker_index: self.taker_bonus += 10 * (1, 2, 4, 6)[self.auction]
                    else: self.defense_bonus += 10
        
            if self.leader_index == self.taker_index:
                for i in self.table: self.taker_tricks.append(i[0])
            else:
                for i in self.table: self.defense_tricks.append(i[0])

            self.table.clear()
            self.first_index = self.leader_index
            self.trick_index += 1
            self.leader_index = -1
            self.ref_card = -1


            # Fin de la donne : compte temporaire des points
            if self.trick_index == 18:
                self.game_phase += 1 # self.game_phase = 5
                msg = "Les levées sont terminées.\n__Comptage des points__\n"
                
                # l'Excuse revient dans son camp
                if self.player_excuse_index != -1:
                    if self.player_excuse_index == self.taker_index:
                        if 77 in self.defense_tricks:
                            low_value_card = get_low_value_card(self.taker_tricks)
                            self.defense_tricks.append(low_value_card)
                            self.defense_tricks.remove(77)
                            self.taker_tricks.append(77)
                            self.taker_tricks.remove(low_value_card)
                    else:
                        if 77 in self.taker_tricks:
                            low_value_card = get_low_value_card(self.defense_tricks)
                            self.taker_tricks.append(low_value_card)
                            self.taker_tricks.remove(77)

                            self.defense_tricks.append(77)
                            self.defense_tricks.remove(low_value_card)                   

                points, minimum = points_counter(self.taker_tricks)
                chelem_points, chelem_defense = get_chelem_points(self.taker_tricks, self.defense_tricks, self.players, self.taker_index)

                if points >= minimum:
                    msg += "C'est le⋅a preneur⋅euse qui marque.\n"
                    
                    points = (25 + (points - minimum)) * (1, 2, 4, 6)[self.auction]
                    if not chelem_defense: points += chelem_points
                    points += self.taker_bonus
                    points -= self.defense_bonus 
                    
                    points = int(points)
                    for index, player in enumerate(self.players):
                        if index == self.taker_index:
                            msg += f" - {player.user_name} : +{3 * points} points (preneur)\n"
                            player.points.append(3 * points)
                        else:
                            msg += f" - {player.user_name} : -{points} points (défense)\n"
                            player.points.append(-points)

                else:
                    msg += "C'est la défense qui marque\n"

                    points = 25 + (minimum - points)
                    if chelem_defense: points += chelem_points
                    points -= self.taker_bonus
                    points += self.defense_bonus

                    points = int(points)
                    for index, player in enumerate(self.players):
                        if index == self.taker_index:
                            msg += f" - {player.user_name} : -{3 * points} points (preneur)\n"
                            player.points.append(-3 * points)
                        else:
                            msg += f" - {player.user_name} : +{points} points (défense)\n"
                            player.points.append(points)
                await ctx.send(msg)
                await ctx.send(generate_result_table(self.players))

                self.giver_index = (self.giver_index + 1) % 4
                self.player_index = (self.giver_index + 1) % 4
                if self.giver_index == self.first_giver_index:
                    await ctx.send(f"Fin de la partie :\n{generate_result_table(self.players)}")
                    self.__init__(self.config)
                else:
                    await ctx.send(f"Donne suivante. C'est {self.players[self.giver_index].user_name} qui donne.")
                    await self._init_game(ctx)
            
            # levée suivante
            else:

                for i in self.players: await i.send_private_deck()
                self.player_index = self.first_index
                await ctx.send(f"Nouvelle levée. C'est au tour de {self.players[self.player_index].user_name} de poser une carte.")                
        
        # joueur suivant
        else:
            await ctx.send(f"C'est au tour de {self.players[self.player_index].user_name} de poser une carte.")

    @commands.command(aliases=["sauvegarder"], help="Sauvegarde la partie en cours.", brief="Sauvegarde la partie en cours.")
    async def sauvegarde(self, ctx, nom: str):
        with open(f"saves/[TAROT]{nom}.json", "w") as file:
            file.write(json.dumps(
                {
                    "guild_id": ctx.guild.id,
                    "players": [i.export() for i in self.players],
                    "players_vars": [self.player_index, self.giver_index, self.first_giver_index, self.taker_index, self.first_index, self.leader_index, self.player_excuse_index, self.taker_bonus, self.defense_bonus],
                    "cards": [self.cards, self.taker_tricks, self.defense_tricks, self.table, self.ref_card],
                    "misc": [self.game_phase, self.trick_index, self.old_table, self.auction]
                }))
        await ctx.send("Partie sauvegardée.")

    @commands.command(aliases=["charger"], help="Charge la partie demandée.", brief="Charge la partie demandée.")
    async def charge(self, ctx, nom: str):
        with open(f"saves/[TAROT]{nom}.json", "r") as file:
            data = json.loads(file.read())

        self.__init__(self.config, self.bot)

        guild = self.bot.get_guild(data["guild_id"])
        self.guild_send = ctx.send
        for i in data["players"]:
            member = await guild.fetch_member(i[0])
            i[2] = member.send
            self.players.append(Player(*i))

        self.player_index = data["players_vars"][0]
        self.giver_index = data["players_vars"][1]
        self.first_giver_index = data["players_vars"][2]
        self.taker_index = data["players_vars"][3]
        self.first_index = data["players_vars"][4]
        self.leader_index = data["players_vars"][5]
        self.player_excuse_index = data["players_vars"][6]
        self.taker_bonus = data["players_vars"][7]
        self.defense_bonus = data["players_vars"][8]
        
        self.cards = data["cards"][0]
        self.taker_tricks = data["cards"][1]
        self.defense_tricks = data["cards"][2]
        self.table = data["cards"][3]
        self.ref_card = data["cards"][4]

        self.game_phase = data["misc"][0]
        self.trick_index = data["misc"][1]
        self.old_table = data["misc"][2]
        self.auction = data["misc"][3]

        await ctx.send("Partie chargée.")
        if self.game_phase == 0:
            await ctx.send("La partie n'est pas encore commencée.")
        elif self.game_phase == 1:
            await ctx.send("La partie vient de commencer.")
        elif self.game_phase == 2:
            await ctx.send(f"C'est à {self.players[self.player_index].user_name} de dire son enchère.")
        elif self.game_phase == 3:
            await ctx.send(f"{self.players[self.player_index].user_name} doit écarter six cartes de son jeu.")
        elif self.game_phase == 4:
            await ctx.send(f"C'est à de {self.players[self.player_index].user_name} de poser une carte.")

        if self.game_phase:
            for i in self.players: await i.send_private_deck()
            if self.game_phase == 4: await send_deck(ctx, "Table", self.table, False)




class Player(DefaultPlayer):
    def __init__(self, user_id, user_name, send, index, cards=[], points=[]):
        self.user_id = user_id
        self.user_name = user_name
        self.send = send
        self.index = index

        if cards: self.cards = cards
        else: self.cards = []

        if points: self.points = points
        else: self.points = []

        self.auction = 0
        self.chelem = 0
        self.bonus = 0

    def clean_auction(self):
        self.auction = 0

    def select_trump_cards(self, min_value=56):
        if not (56 <= min_value <= 76): min_value = 56
        return [i for i in self.cards if (min_value <= i < 77)]

    def export(self):
        return [self.user_id, self.user_name, None, self.index, self.cards, self.points]

    def convert_points(self):
        if len(self.points) == 4: self.points.append(sum(self.points))        
        pts = []
        for index in range(5):
            if index < len(self.points):
                value = self.points[index]
                if value < 0: pts.append(str(value))
                else: pts.append("+" + str(value))
            else: pts.append("-")

        max_length = max([len(i) for i in pts])
        max_length = max(max_length, len(self.user_name))
        
        self.user_name += " " * (max_length - len(self.user_name))
        for i in range(len(pts)):
            pts[i] += " " * (1 + max_length - len(pts[i]))

        return pts, max_length


def get_leader_card(table, leader_index):
    for i in table:
        if i[1] == leader_index:
            return i[0]
    return -1


def get_low_value_card(cards):
    for i in cards:
        if i < 56 and (i % 14) < 10: return i

def get_chelem_points(taker_tricks, defense_tricks, players, taker_index):
    def get_chelem_player(players):
        for index, player in enumerate(players):
            if player.chelem: return index
        return -1

    chelem_index = get_chelem_player(players)

    # si le⋅a preneur⋅euse a fait un Chelem
    if not defense_tricks:
        if chelem_index == taker_index: return 400, False # annoncé
        elif chelem_index == -1: return 200, False        # non annoncé
    elif chelem_index == taker_index : return -200, False # annoncé, non réalisé

    # Si la défense à fait un Chelem
    if not taker_tricks:
        return 0, True

    return 0, False


def points_counter(cards):
    points, oulder = 0, 0
    for i in cards:
        if i in (56, 76, 77):points += 4.5 ; oulder += 1
        elif (i % 14) == 13: points += 4.5
        elif (i % 14) == 12: points += 3.5
        elif (i % 14) == 11: points += 2.5
        elif (i % 14) == 10: points += 1.5
        else: points += 0.5
    return points, (56, 51, 41, 36)[oulder]


def generate_result_table(players):
    width = 24
    width_players = []
    for i in players:
        i.pts, i.max_length = i.convert_points()
        width += i.max_length

    tmp = 12 * " " + "┌"
    for i in players:
        tmp += (i.max_length + 2) *  "─" + "┬"
    lines = [tmp[:-1] + "┐"]

    tmp = 12 * " " + "│ "
    for i in players:
        tmp += f"{i.user_name} │ "
    lines.append(tmp)

    tmp = "┌" + 11 * "─" + "┼"
    for i in players:
        tmp += (i.max_length + 2) *  "─" + "┼"
    lines.append(tmp[:-1] + "┤")

    for j in range(4):
        tmp = f"│ Donne n°{j + 1} │ "
        for i in players:
            tmp += i.pts[j] + "│ "
        lines.append(tmp)

        tmp = "├" + 11 * "─" + "┼"
        for i in players:
            tmp += (i.max_length + 2) *  "─" + "┼"
        lines.append(tmp[:-1] + "┤")

    tmp = f"│ Total     │ "
    for i in players:
        tmp += i.pts[4] + "│ "
    lines.append(tmp)

    tmp = "└" + 11 * "─" + "┴"
    for i in players:
        tmp += (i.max_length + 2) * "─" + "┴"
    lines.append(tmp[:-1] + "┘")

    return "```\n" + "\n".join(lines) + "\n```"