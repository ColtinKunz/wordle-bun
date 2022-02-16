import discord
import sqlite3

from os import getenv
from emoji import demojize
from dotenv import load_dotenv
from typing import Dict, List, Tuple

from aux_lib import get_prefix, count_avg_stats, get_wordle_result, avg_message

intents = discord.Intents.default()
intents.members = True

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")
PREFIX = get_prefix("COMMAND_PREFIX")
PREFIX_LEN = len(PREFIX)

INIT_MSG = getenv("INIT_MESSAGE")
RESET_MSG = getenv("RESET_MESSAGE")


class BunClient(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        self.channels: Dict[int, int] = {}
        super().__init__(*args, **kwargs)

    async def on_ready(self) -> None:
        print(f"{client.user} has connected to Discord!")
        self.conn = sqlite3.connect("wordle.db")
        self.curs = self.conn.cursor()
        print("Connected to database!")

    async def on_message(self, message) -> None:
        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id
        msg_text = message.content

        # Init command
        if message.content == PREFIX + "init":
            self.set_channel(guild_id, channel_id)
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
            average_stats = self.get_average_stats(1)
            print(average_stats)

            if average_stats is None or average_stats["total"]["rounds"] == 0:
                await channel.send("You have no results uploaded yet.")
            else:
                average_message = (
                    avg_message(average_stats, "total")
                    + avg_message(average_stats, "easy")
                    + avg_message(average_stats, "hard")
                )

                await channel.send(average_message)

        elif command == "leaderboard":
            user_servers = self.curs.execute(
                f"""
                SELECT DISTINCT user_id, server_id
                FROM WordleResults
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

            async def _average_message(
                user_id: int, average: str, total: str, fails: str
            ) -> str:
                user = await self.fetch_user(user_id)
                return f"{user.display_name}: {average} - {total} rounds | Fails: {fails}\n"

            for user_server in user_servers:
                average_stats = self.get_average_stats(user_server[0])

                try:
                    ordered_stats.append(
                        (
                            user_server[0],
                            average_stats[option]["average_guesses"],
                            average_stats[option]["rounds"],
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

        elif command == "kill":
            await client.close()

    def set_channel(self, guild_id: int, channel_id: int) -> None:
        self.channels[guild_id] = channel_id

        self.delete_db()

        self.initialize_db()

    def initialize_db(self) -> None:
        self.curs.execute(
            """
            CREATE TABLE WordleResults(
                user_id         BIGINT      NOT NULL,
                game_num        INT         NOT NULL,
                guild_id        BIGINT      NOT NULL,
                num_guesses     INT         NOT NULL,
                hard_mode       BOOL        NOT NULL,
                PRIMARY KEY (user_id, game_num)
            );
            """
        )

        self.curs.execute(
            """
            CREATE TABLE UserStats(
                user_id         BIGINT PRIMARY KEY      NOT NULL,
                total_rounds    INT                     NOT NULL,
                total_guesses   INT                     NOT NULL,
                total_fails     INT                     NOT NULL,
                easy_rounds     INT                     NOT NULL,
                easy_guesses    INT                     NOT NULL,
                easy_fails      INT                     NOT NULL,
                hard_rounds     INT                     NOT NULL,
                hard_guesses    INT                     NOT NULL,
                hard_fails      INT                     NOT NULL
            );
            """
        )

        self.curs.execute(
            """
            INSERT INTO UserStats VALUES (1, 9, 8, 7, 6, 5, 4, 3, 2, 1);
            """
        )

        self.conn.commit()

    def delete_db(self) -> None:
        self.curs.execute(
            """
            DROP TABLE WordleResults;
            """
        )

        self.curs.execute(
            """
            DROP TABLE UserStats;
            """
        )

        self.conn.commit()

    def insert_wordle_result(
        self, msg_text: str, user_id: int, guild_id: int
    ) -> None:

        result = get_wordle_result(msg_text)

        if result is None:
            return

        self.curs.execute(
            """
            REPLACE INTO WordleResults (
                user_id,
                game_num,
                guild_id,
                num_guesses,
                hard_mode
            ) \
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """
        )
        self.conn.commit()

    def get_stats(self, user_id: int, mode: str) -> Tuple[int, int, int]:
        return self.curs.execute(
            f"""
            SELECT {mode}_rounds, {mode}_guesses, {mode}_fails
            FROM UserStats
            WHERE user_id = {user_id}
            """
        ).fetchone()

    def get_average_stats(self, user_id: int) -> Dict[str, Dict[str, str]]:
        total = self.get_stats(user_id, "total")
        print(type(total))

        easy = self.get_stats(user_id, "easy")

        hard = self.get_stats(user_id, "hard")

        average_dict = {
            "total": count_avg_stats(*total),
            "easy": count_avg_stats(*easy),
            "hard": count_avg_stats(*hard),
        }

        return average_dict


client = BunClient(intents=intents)

client.run(TOKEN)
