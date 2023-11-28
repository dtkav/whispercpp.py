from whispercpp import Whisper
import click
from pprint import pprint
from rich.console import Console
from rich.theme import Theme
from datetime import timedelta
import json


import os
import pickle
from functools import wraps

w = Whisper('large')


def to_timestamp(t):
    return timedelta(seconds=t//100)
    sec = int(t/100);
    msec = int(t - sec*100);
    minutes = int(sec/60);
    sec = int(sec - minutes*60);
    return f"00:{minutes:02}:{sec:02}" #.{msec}"



def cache_output(file_path):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a unique key based on the function name and input arguments
            key = f"{func.__name__}_{pickle.dumps(args)}_{pickle.dumps(kwargs)}"
            
            # Check if the cache file exists
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    try:
                        cache = pickle.load(file)
                        if key in cache:
                            return cache[key]
                    except (EOFError, pickle.UnpicklingError):
                        pass
            
            # Call the function and cache the output
            output = func(*args, **kwargs)
            
            # Update the cache file
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    try:
                        cache = pickle.load(file)
                    except (EOFError, pickle.UnpicklingError):
                        cache = {}
            else:
                cache = {}
            
            cache[key] = output
            
            with open(file_path, 'wb') as file:
                pickle.dump(cache, file)
            
            return output
        
        return wrapper
    
    return decorator



# Function to map a number to a color based on your criteria
def map_number_to_color(number):
    if number > 0.8:
        return "high_color"
    elif number <= 0.2:
        return "low_color"
    else:
        return "mid_color"

def map_number_to_highlighter(number):
    if number > 0.6:
        return None
    if number <= 0.2:
        return "red"
    else:
        return "yellow"


@cache_output("cache.json")
def do(fname):
    result = w.transcribe(fname)
    return w.get_probs(result)


def print_segments(console, segments):
    for t0, t1, tokens in segments:
        console.print(to_timestamp(t0), end=" - ")
        console.print(to_timestamp(t1), end="\t")
        for token_text, token_p in tokens[:-1]:
            token_text = token_text.replace("[_BEG_]", "")
            color_name = map_number_to_color(token_p)
            console.print(f"[{color_name}]{token_text}[/]", end="")
        console.print("")

def print_tokens(segments):

    for t0, t1, tokens in segments:
        segment_text = "".join([token_text for token_text, token_p in tokens])
        words = segment_text.split(" ")
        print(to_timestamp(t0), end=" - ")
        print(to_timestamp(t1), end="\t")
        token_p_min = 1.0
        token_run = ""
        for token_text, token_p in tokens[:-1]:
            token_text = token_text.replace("[_BEG_]", "")
            if " " in token_text:
                t0, t1 = token_text.split(" ")
                token_run += t0
                print(token_run, f"{{{token_p_min:.2f}}}", end=" ")
                token_run = t1
                token_p_min = token_p
            else:
                token_run += token_text
                token_p_min = min(token_p_min, token_p)
        print("")


def print_audio_player_format(filename, console, segments):

    print("```audio-player")
    print(f"[[{filename}]]")
    for t0, t1, tokens in segments:
        segment_text = "".join([token_text for token_text, token_p in tokens])
        words = segment_text.split(" ")
        console.print(to_timestamp(t0), end=" --- ")
        token_p_min = 1.0
        token_run = ""
        for token_text, token_p in tokens[:-1]:
            token_text = token_text.replace("[_BEG_]", "")
            if " " in token_text:
                t0, t1 = token_text.split(" ")
                token_run += t0
                color_name = map_number_to_color(token_p_min)
                console.print(f"[{color_name}]{token_run}[/]", end=" ")
                token_run = t1
                token_p_min = token_p
            else:
                token_run += token_text
                token_p_min = min(token_p_min, token_p)
        console.print("")
    print("```")


def print_words(console, segments):

    for t0, t1, tokens in segments:
        segment_text = "".join([token_text for token_text, token_p in tokens])
        words = segment_text.split(" ")
        console.print(to_timestamp(t0), end=" - ")
        console.print(to_timestamp(t1), end="\t")
        token_p_min = 1.0
        token_run = ""
        for token_text, token_p in tokens[:-1]:
            token_text = token_text.replace("[_BEG_]", "")
            if " " in token_text:
                t0, t1 = token_text.split(" ")
                token_run += t0
                color_name = map_number_to_color(token_p_min)
                console.print(f"[{color_name}]{token_run}[/]", end=" ")
                token_run = t1
                token_p_min = token_p
            else:
                token_run += token_text
                token_p_min = min(token_p_min, token_p)
        console.print("")


def print_html(segments):
    for t0, t1, tokens in segments:
        print("<p>")
        segment_text = "".join([token_text for token_text, token_p in tokens])
        words = segment_text.split(" ")
        print(to_timestamp(t0), end=" - ")
        print(to_timestamp(t1), end="\t")
        token_p_min = 1.0
        token_run = ""
        for token_text, token_p in tokens[:-1]:
            token_text = token_text.replace("[_BEG_]", "")
            if " " in token_text:
                t0, t1 = token_text.split(" ")
                token_run += t0
                color_name = map_number_to_highlighter(token_p_min)
                if color_name is None:
                    print(token_run)
                else:
                    print(f"""<mark class="{color_name}">{token_run}</mark>""")
                token_run = t1
                token_p_min = token_p
            else:
                token_run += token_text
                token_p_min = min(token_p_min, token_p)
        print("</p>")


@click.command()
@click.argument('filename')
@click.option('--raw', is_flag=True)
@click.option('--words', is_flag=True)
@click.option('--audio-player', is_flag=True)
@click.option('--html', is_flag=True)
def process_audio(filename, raw, words, audio_player, html):
    click.echo(f"Processing audio file: {filename}")
    segments = do(filename)

    # Define the gradient colors for your criteria
    theme = Theme({
        "high_color": "green",
        "mid_color": "yellow",
        "low_color": "red",
    })
    console = Console(theme=theme)
    if words:
        print_words(console, segments)
    elif html:
        print_html(segments)
    elif audio_player:
        print_audio_player_format(filename, console, segments)
    elif raw:
        print_tokens(segments)
    else:
        print_segments(console, segments)


if __name__ == '__main__':
    process_audio()
