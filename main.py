import discord
import sqlite3

from os import getenv
from emoji import demojize
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple, Union

from aux_lib import get_prefix

intents = discord.Intents.default()
intents.members = True

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")
PREFIX = get_prefix("COMMAND_PREFIX")
PREFIX_LEN = len(PREFIX)

INIT_MSG = getenv("INIT_MESSAGE")
RESET_MSG = getenv("RESET_MESSAGE")


class WordleResult:
    def __init__(
        self,
        game_num: int,
        num_guesses: int,
        square_lines: List[List[str]],
        is_hard_mode: bool,
    ):
        self.game_num = game_num
        self.num_guesses = num_guesses
        self.square_lines = square_lines
        self.is_hard_mode = is_hard_mode


class BunClient(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        self.channels: Dict[int, int] = {}
        super().__init__(*args, **kwargs)

    async def on_ready(self) -> None:
        print(f"{client.user} has connected to Discord!")
        self.conn = sqlite3.connect("wordle.db")
        print("Connected to database!")

    async def on_message(self, message) -> None:
        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id
        msg_text = message.content

        # Init command
        if message.content == PREFIX + "init":
            self.initialize_bot(guild_id, channel_id)
            await client.get_channel(channel_id).send(INIT_MSG)
            return

        # Check if message is in bot channel
        if channel_id == self.channels[guild_id]:
            channel = client.get_channel(channel_id)
        else:
            return

        # Wordle score check if message isn't a command
        if message.content[:PREFIX_LEN] != PREFIX:
            self.insert_wordle_result(msg_text, user_id, guild_id)
            return

        # Command parse
        split_words = msg_text.split()
        command = split_words[0][PREFIX_LEN:]
        print(command)

        if command == "reset":
            messages = await channel.history(limit=None).flatten()
            messages.reverse()

            for message in messages:
                self.insert_wordle_result(
                    message.content, message.author.id, message.guild.id
                )

            await channel.send(RESET_MSG)

        elif command == "mystats":
            average_stats = self.get_average_stats(user_id, guild_id)

            if (
                average_stats is None
                or average_stats["all"]["total_guesses"] == 0
            ):
                await channel.send("You have no results uploaded yet.")
            else:
                average_message = (
                    f'{average_stats["all"]["average_guesses"]}'
                    + f' - {average_stats["all"]["total_guesses"]} rounds'
                    + f' | Fails: {average_stats["all"]["fails"]}\n'
                )

                try:
                    average_message += (
                        f'{average_stats["hard"]["average_guesses"]}'
                        + f' - {average_stats["hard"]["total_guesses"]} hard rounds'
                        + f' | Fails: {average_stats["hard"]["fails"]}\n'
                    )
                except KeyError:
                    pass

                try:
                    average_message += (
                        f'{average_stats["easy"]["average_guesses"]}'
                        + f' - {average_stats["easy"]["total_guesses"]} easy rounds'
                        + f' | Fails: {average_stats["easy"]["fails"]}\n'
                    )
                except KeyError:
                    pass

                await channel.send(average_message)

        elif command == "leaderboard":
            user_servers = self.conn.execute(
                f"""
                SELECT DISTINCT user_id, server_id
                FROM WordleResult
                WHERE server_id = "{guild_id}"
                """
            ).fetchall()

            print(user_servers)

            ordered_stats = []

            if len(split_words) > 1:
                option = split_words[1]
            else:
                option = "all"

            leaderboard_message = (
                f"Top 5: {option.capitalize()}\n"
                + "-----------------------------------\n"
            )

            async def _average_message(user_id: int, average, total, fails):
                user = await self.fetch_user(user_id)
                return f"{user.display_name}: {average} - {total} rounds | Fails: {fails}\n"

            for user_server in user_servers:
                average_stats = self.get_average_stats(
                    user_server[0], user_server[1]
                )

                try:
                    ordered_stats.append(
                        (
                            user_server[0],
                            average_stats[option]["average_guesses"],
                            average_stats[option]["total_guesses"],
                            average_stats[option]["fails"],
                        )
                    )
                except KeyError:
                    pass

            ordered_stats.sort(key=lambda a: (a[1], a[3], a[2]))
            top5 = ordered_stats[:5]

            for top in top5:
                leaderboard_message += await _average_message(*top)

            await channel.send(leaderboard_message)

        elif command == "channels":
            print(self.channels.items())

        elif command == "kill":
            await client.close()

    def initialize_bot(self, guild_id: int, channel_id: int) -> None:
        self.channels[guild_id] = channel_id

        try:
            self.delete_db()

        except sqlite3.OperationalError:
            pass

        self.initialize_db()

    def get_average_stats(self, user_id: int, guild_id: int):
        sum_guesses = 0
        easy_sum_guesses = 0
        easy_count = 0
        hard_sum_guesses = 0
        hard_count = 0
        fails = 0
        easy_fails = 0
        hard_fails = 0

        results = self.get_stats(user_id, guild_id)

        if len(results) == 0:
            return None

        for result in results:
            if result[0] > 0:
                guesses = int(result[0])
                sum_guesses += guesses
                if result[1] == 1:
                    hard_sum_guesses += guesses
                    hard_count += 1
                else:
                    easy_sum_guesses += guesses
                    easy_count += 1
            else:
                fails += 1
                if result[1] == 1:
                    hard_fails += 1
                else:
                    easy_fails += 1

        average_dict = {
            "all": {
                "total_guesses": len(results),
                "average_guesses": (
                    f"{sum_guesses/(len(results) - fails):.2f}"
                    if (len(results) - fails > 0)
                    else "Infinity"
                ),
                "fails": fails,
            }
        }

        if hard_count > 0:
            average_dict["hard"] = {
                "total_guesses": hard_count,
                "average_guesses": (
                    f"{hard_sum_guesses/(hard_count - hard_fails):.2f}"
                    if hard_count - hard_fails > 0
                    else "Infinity"
                ),
                "fails": hard_fails,
            }

        if easy_count > 0:
            average_dict["easy"] = {
                "total_guesses": easy_count,
                "average_guesses": (
                    f"{easy_sum_guesses/(easy_count - easy_fails):.2f}"
                    if easy_count - easy_fails > 0
                    else "Infinity"
                ),
                "fails": easy_fails,
            }

        return average_dict

    def insert_wordle_result(
        self, msg_text: str, user_id: int, guild_id: int
    ) -> None:

        result = self.get_wordle_result(msg_text)

        if result is not None:
            self.conn.execute(
                f"""
                REPLACE INTO WordleResult (
                    user_id,
                    server_id,
                    game_num,
                    num_guesses,
                    hard_mode
                ) \
                VALUES (
                    {user_id},
                    {guild_id},
                    {result.game_num},
                    {result.num_guesses if result.num_guesses is not None else "NULL"},
                    {result.is_hard_mode}
                )
            """
            )
            self.conn.commit()

    def initialize_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE WordleResult(
                id              INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE        NOT NULL,
                user_id         CHAR(17)                                        NOT NULL,
                server_id       CHAR(17)                                        NOT NULL,
                game_num        INT                                             NOT NULL,
                num_guesses     INT                                             NOT NULL,
                hard_mode       INT                                             NOT NULL
            );
            """
        )
        self.conn.execute(
            """
            CREATE UNIQUE INDEX unique_cons
            ON WordleResult(
                user_id, server_id, game_num
            );
            """
        )
        self.conn.commit()

    def delete_db(self) -> None:
        self.conn.execute(
            """
            DROP TABLE WordleResult;
            """
        )

        self.conn.commit()

    def get_stats(self, user_id: int, guild_id: int) -> List[Tuple[int, int]]:
        return self.conn.execute(
            f"""
            SELECT num_guesses, hard_mode
            FROM WordleResult
            WHERE user_id = "{user_id}" AND server_id = "{guild_id}"
            """
        ).fetchall()

    def get_wordle_result(self, msg_text: str) -> Optional[WordleResult]:
        # Wordle, number of wordle game, results, squares
        message_list = msg_text.split()

        if len(message_list) == 0:
            return None

        # if message[0] != "Wordle" or type(game_num) != int and

        is_wordle = message_list.pop(0) == "Wordle"

        if not is_wordle:
            return None

        game_num = int(message_list.pop(0))

        results = message_list.pop(0)
        num_guesses = int(results[0]) if results[0] != "X" else 0
        is_hard_mode = len(results) == 4 and results[3] == "*"

        square_lines = []
        for square_line in message_list:
            squares = demojize(square_line).split(":")
            squares = [i for i in squares if i != ""]

            line = []
            for square in squares:
                if square == "green_square" or square == "orange_square":
                    line.append("good")
                elif square == "yellow_square" or square == "blue_square":
                    line.append("close")
                else:
                    line.append("no")

            square_lines.append(line)

        return WordleResult(game_num, num_guesses, square_lines, is_hard_mode)


client = BunClient(intents=intents)

client.run(TOKEN)
