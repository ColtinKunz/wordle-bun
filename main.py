import discord
import sqlite3

from os import getenv
from emoji import demojize
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.members = True

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")


class WordleResult:
    def __init__(self, wordle_num, user, num_guesses):
        self.num_guesses = num_guesses
        self.user = user
        self.wordle_num = wordle_num


class BunClient(discord.Client):
    def __init__(self, *args, **kwargs):
        self.channel = {}
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print(f"{client.user} has connected to Discord!")
        self.conn = sqlite3.connect("wordle.db")
        print("Connected to database!")

    async def on_message(self, message):
        if message.content[0] == "!":
            split_words = message.content.split()
            command = split_words[0]
            if command == "!init":
                self.channel[message.guild.id] = self.get_initial_channel(
                    message
                )
                self.initialize_db()
            elif command == "!reset":
                try:
                    self.delete_db()
                except sqlite3.OperationalError:
                    pass
                self.initialize_db()
                self.channel[message.guild.id] = self.get_initial_channel(
                    message
                )
                messages = (
                    await self.channel[message.guild.id]
                    .history(limit=None)
                    .flatten()
                )
                messages.reverse()
                for message in messages:
                    self.insert_wordle_result(message)
                await self.channel[message.guild.id].send(
                    "Database reset and channel set!"
                )
            elif command == "!mystats":
                average_stats = self.get_average_stats(
                    message.author.id, message.guild.id
                )
                if (
                    average_stats is None
                    or average_stats["all"]["total_guesses"] == 0
                ):
                    await self.channel[message.guild.id].send(
                        "You have no results uploaded yet."
                    )
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

                    await self.channel[message.guild.id].send(average_message)
            elif command == "!leaderboard":
                user_servers = self.conn.execute(
                    """
                    SELECT DISTINCT user_id, server_id
                    FROM WordleResult
                    """
                ).fetchall()

                ordered_stats = []

                if len(split_words) > 1:
                    option = split_words[1]
                else:
                    option = "all"

                leaderboard_message = (
                    f"Top 5: {option.capitalize()}\n"
                    + "-----------------------------------\n"
                )

                async def _average_message(user_id, average, total, fails):
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

                await self.channel[message.guild.id].send(leaderboard_message)

        else:
            self.insert_wordle_result(message)

    def get_average_stats(self, user_id, guild_id):
        sum_guesses = 0
        easy_sum_guesses = 0
        total_easy = 0
        hard_sum_guesses = 0
        total_hard = 0
        results = self.get_stats(user_id, guild_id)
        fails = 0
        easy_fails = 0
        hard_fails = 0
        for result in results:
            if result[1] is not None:
                guesses = int(result[1])
                sum_guesses += guesses
                if result[2] == 1:
                    hard_sum_guesses += guesses
                    total_hard += 1
                else:
                    easy_sum_guesses += guesses
                    total_easy += 1
            else:
                fails += 1
                if result[2] == 1:
                    hard_fails += 1
                else:
                    easy_fails += 1
        if len(results) == 0:
            return None

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

        if total_hard > 0:
            average_dict["hard"] = {
                "total_guesses": total_hard,
                "average_guesses": (
                    f"{hard_sum_guesses/(total_hard-hard_fails):.2f}"
                    if total_hard - hard_fails > 0
                    else "Infinity"
                ),
                "fails": hard_fails,
            }
        if total_easy > 0:
            average_dict["easy"] = {
                "total_guesses": total_easy,
                "average_guesses": (
                    f"{easy_sum_guesses/(total_easy - easy_fails):.2f}"
                    if total_easy - easy_fails > 0
                    else "Infinity"
                ),
                "fails": easy_fails,
            }

        return average_dict

    def insert_wordle_result(self, message):
        result = self.get_wordle_result(message.content)
        if (
            message.channel == self.channel[message.guild.id]
            and result is not None
        ):
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
                    {message.author.id},
                    {message.guild.id},
                    {result["game_num"]},
                    {result["num_guesses"] if result["num_guesses"] is not None else "NULL"},
                    {result["is_hard_mode"]}
                )
            """
            )
            self.conn.commit()

    def get_initial_channel(self, message):
        return message.channel

    def initialize_db(self):
        self.conn.execute(
            """
            CREATE TABLE WordleResult(
                id              INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE        NOT NULL,
                user_id         CHAR(17)                                        NOT NULL,
                server_id       CHAR(17)                                        NOT NULL,
                game_num        INT                                             NOT NULL,
                num_guesses     CHAR(1),
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

    def delete_db(self):
        self.conn.execute(
            """
            DROP TABLE WordleResult;
            """
        )
        self.conn.commit()

    def get_stats(self, user_id, server_id):
        return self.conn.execute(
            f"""
            SELECT game_num, num_guesses, hard_mode
            FROM WordleResult
            WHERE user_id="{user_id}" AND server_id="{server_id}"
            """
        ).fetchall()

    def get_wordle_result(self, message):
        # Wordle, number of wordle game, results, squares
        message_list = message.split()

        if len(message_list) == 0:
            return None

        # if message[0] != "Wordle" or type(game_num) != int and

        is_wordle = message_list.pop(0) == "Wordle"

        if not is_wordle:
            return None

        game_num = message_list.pop(0)

        results = message_list.pop(0)
        num_guesses = int(results[0]) if results[0] != "X" else None
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

        return {
            "game_num": game_num,
            "num_guesses": num_guesses,
            "square_lines": square_lines,
            "is_hard_mode": is_hard_mode,
        }


client = BunClient(intents=intents)


client.run(TOKEN)
