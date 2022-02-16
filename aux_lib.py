from os import getenv
from emoji import demojize
from typing import Dict, List, Optional


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


def get_prefix(env_name: str) -> str:
    PREFIX = getenv(env_name)

    if PREFIX is None:
        return ""

    return PREFIX


def count_avg_stats(rounds: int, guesses: int, fails: int) -> Dict[str, str]:
    result = dict()

    result["rounds"] = str(rounds)
    result["average_guesses"] = (
        f"{guesses / (rounds - fails):.2f}" if rounds > fails else "-1"
    )
    result["fails"] = str(fails)

    return result


def avg_message(avg_stats, mode: str) -> str:
    return f'{avg_stats[mode]["average_guesses"]} - {avg_stats[mode]["rounds"]} {mode} rounds | Fails: {avg_stats[mode]["fails"]}\n'


def get_wordle_result(msg_text: str) -> Optional[WordleResult]:
    # Wordle, number of wordle game, results, squares
    split_msg = msg_text.split()

    if len(split_msg) < 3 or split_msg[0] != "Wordle":
        return None

    game_num = int(split_msg[1])
    result = split_msg[2]

    num_guesses = 0 if result[0] == "X" else int(result[0])
    is_hard_mode = len(result) == 4 and result[3] == "*"

    square_lines = []
    for square_line in split_msg[:]:
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
