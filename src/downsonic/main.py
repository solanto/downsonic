#!/usr/bin/env python

import sys
import libopensonic  # pyright: ignore[reportMissingTypeStubs]
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from netrc import netrc
import re
from sys import stderr
import logging
from libopensonic.media.media_types import Child
from tqdm import tqdm
from magic import Magic
from glob import glob

# 🟰 definitions

mime = Magic(mime=True)

if os.name == "nt":

    # mercy for w*ndows users
    def sanitize(string: str) -> str:
        """
        Edit text to be suitable for use in a windows path. Replaces invalid characters with `-`.

        :param string: input text
        :type string: str
        :return: edited text
        :rtype: str
        """
        return re.sub(r"/|\\|<|>|:|\"|\||\?|\*|\x00", "-", string)

else:

    def sanitize(string: str) -> str:
        """
        Edit text to be suitable for use in a *nix path. Replaces invalid characters with `-`.

        :param string: input text
        :type string: str
        :return: edited text
        :rtype: str
        """
        return re.sub(r"/|\\|:", "-", string)


def path(
    artist: str,
    album: str | None = None,
    song: str | None = None,
    extension: str | None = None,
) -> str:
    """
    Generate a `sanitize`d path for an artist directory, album directory, or song.

    For example, "5/3" from the album *Becoming an Entity*, by The Doozers:
    - `path("The Doozers")` → `"The Doozers"`
    - `path("The Doozers", "Becoming an Entity")` → `"The Doozers/Becoming an Entity"`
    - `path("The Doozers", "Becoming an Entity", "5/3", "mp3")` → `"The Doozers/Becoming an Entity/5-3.mp3"`

    :param artist: the name of an artist
    :type artist: str
    :param album: the name of said artist's album
    :type album: str | None
    :param song: the title of said album's song
    :type song: str | None
    :param extension: the desired file extension for the song
    :type song: str | None
    :return: a `sanitize`d path
    :rtype: str
    """

    result = sanitize(artist)

    if album:
        result += "/" + sanitize(album)

        if song:
            assert extension

            result += "/" + sanitize(song) + "." + extension

    return result


# ⚙️ configure arguments

argument_parser = argparse.ArgumentParser()

argument_parser.add_argument(
    "source",
    help="OpenSubsonic server to download music from; [http[s]://][host][:port], where port defaults to 80 for http, 443 for https, and 8080 when unspecified",
)
argument_parser.add_argument("destination", help="destination directory")
argument_parser.add_argument(
    "--netrc-file",
    help="path to a netrc file with login credentials; defaults to `~/.netrc`",
)
argument_parser.add_argument(
    "-u", "--user", help="username for server login; see help on `--password`"
)
argument_parser.add_argument(
    "-p",
    "--password",
    help="password for server login ⚠️ \0 avoid supplying your passwords through the terminal in plaintext, and instead consider using a netrc file",
)
argument_parser.add_argument(
    "-b",
    "--bitrate",
    type=int,
    help="target bitrate for transcoded files, in kbps; unspecified or `0` set no limit",
)
argument_parser.add_argument(
    "-F",
    "--format",
    help="audio format; navidrome servers, for example, support `mp3`, `flac`, `aac`, and `raw` (no transcoding)",
)
argument_parser.add_argument(
    "-e",
    "--extension",
    help="override the extension of all audio files; when unspecified, each file's extension will be inferred automatically",
)
argument_parser.add_argument(
    "-t",
    "--threads",
    help="maximum number of threads (and parallel network connections) to use while downloading",
    default=None,
)
argument_parser.add_argument(
    "-f",
    "--force",
    help="(re)download songs even if they're already in the destination directory",
    action="store_true",
)
argument_parser.add_argument(
    "-V",
    "--verbosity",
    action="count",
    default=0,
    help="how much logging to show; `-v` for critical errors (🛑), `-vv` for recoverable errors (⛔️), `-vvv` for warnings (⚠️ ), `-vvvv` for info (default), and `-vvvvv` for debug (🪲 )",
)
argument_parser.add_argument(
    "--non-interactive",
    action="store_true",
    help="don't show dynamic UI elements, like progress bars",
)

executable = sys.argv[0].split(os.path.sep)[-1]

argument_parser.usage = f"""{argument_parser.format_usage().split(": ")[1]}
examples:
  {executable} music.server.local ~/Music
  {executable} https://music.server.me ~/Music --netrc-file ~/.another-netrc
  {executable} https://music.server.me:1234 ~/Music -F mp3 -b 320"""

# 🪵 configure logging


class LevelFormatter(logging.Formatter):
    """
    A custom `logging.Formatter` extension that allows for individual formatting per log level.
    """

    def __init__(self, formats):
        super().__init__()
        self.formats = formats

    def format(self, record):
        # Get the appropriate format string for the current log level
        format_string = self.formats[record.levelno]

        # If a specific format is defined for the level, use it
        if format_string:
            self._style._fmt = format_string
        else:
            # Fallback to a default format if no specific format is found for the level
            self._style._fmt = self.formats["default"]

        return super().format(record)


streamHandler = logging.StreamHandler()

streamHandler.setFormatter(
    LevelFormatter(
        {
            logging.DEBUG: "🪲  %(module)s:%(lineno)d · %(message)s",
            logging.INFO: "%(message)s",
            logging.WARNING: "⚠️  %(message)s",
            logging.ERROR: "⛔️  %(message)s",
            logging.CRITICAL: "🛑 %(message)s",
            "default": "%(message)s",
        }
    )
)

logging.root.addHandler(streamHandler)


def run():
    """
    Main functionality.
    """

    meter: tqdm | None = None

    # 📖 parse & validate arguments

    arguments = argument_parser.parse_args()

    logging.root.setLevel(
        max(6 - arguments.verbosity, 1) * 10 if arguments.verbosity else 20,
    )

    if arguments.threads and not arguments.threads.isdigit():
        logging.critical("invalid number of threads")
        exit(1)

    try:
        authenticator = netrc(arguments.netrc_file).authenticators(arguments.source)

        if not authenticator:
            raise KeyError()

        user, _, password = authenticator
    except (FileNotFoundError, KeyError):
        if not arguments.user or not arguments.password:
            logging.critical(
                "unable to get user and password from netrc file or arguments"
            )
            exit(1)

        user = arguments.user
        password = arguments.password

    url = re.search(
        r"^(?:(https?):\/\/)?((?!.+:\/{0,2}$).+?)(?::(\d+))?$", arguments.source
    )

    if not url or not url[2]:
        logging.critical("unable to parse url")
        exit(1)

    protocol, host, port_string = url.groups()

    # parse explicit port or infer from protocol
    port = (
        int(port_string)
        if port_string
        else 443 if protocol == "https" else 80 if protocol == "http" else 8080
    )

    # parse explicit procotol or infer from port
    protocol = protocol if protocol else "https" if port == 443 else "http"

    threads = int(arguments.threads) if arguments.threads else None

    if not os.path.isdir(arguments.destination):
        logging.critical("destination folder does not exist")
        exit(1)

    # ⚓️ initialize opensubsonic client & helpers

    client = libopensonic.Connection(protocol + "://" + host, user, password, port)

    def write_song(song: Child):
        """
        From OpenSubsonic data about a song, download the song to its appropriate directory.

        :param song: OpenSubsonic song data
        :type song: Child
        """

        if meter and logging.root.level <= logging.INFO:
            meter.write(song.title, stderr)

        content = client.stream(song.id, arguments.bitrate, arguments.format).content

        if arguments.extension:
            extension = arguments.extension
        else:  # infer extension from mimetype
            mime_type = mime.from_buffer(content)

            extension = (
                "mp3"
                if mime_type == "audio/mpeg"
                else (
                    "m4a"
                    if re.match(r"^audio\/(.*\W)?aac(\W.*)?$", mime_type)
                    else "flac"
                )
            )

        song_path = (
            path(song.artist, song.album, song.title, extension)
            if song.artist
            else sanitize(song.title)
        )

        with open(song_path, "wb") as file:
            file.write(content)

    # 📂 work in destination directory

    os.chdir(arguments.destination)

    # 🗄️ prepare subdirectories

    indexes = client.get_indexes().index

    if not indexes:
        logging.warning("server returned no indexes")
        exit(0)

    all_songs = []

    for index in indexes:
        if index.artist:
            for artist in index.artist:
                os.makedirs(path(artist.name), exist_ok=True)

                albums: list[Child] | None = client.get_music_directory(artist.id).child

                if albums:
                    for album in albums:
                        os.makedirs(path(artist.name, album.title), exist_ok=True)

                        songs = client.get_music_directory(album.id).child

                        if songs:
                            for song in songs:
                                song_path = (
                                    path(song.artist, song.album, song.title, "*")
                                    if song.artist
                                    else sanitize(song.title)
                                )

                                if arguments.force or not glob(song_path):
                                    all_songs.append(song)

    # ⬇️ download songs

    with ThreadPoolExecutor(threads) as executor:
        futures = [executor.submit(write_song, song) for song in all_songs]

        if logging.root.level <= logging.INFO:
            meter = tqdm(as_completed(futures), total=len(futures))
            meter.write("🎺 downloading songs:", stderr)

            results = []

            for future in meter:
                results.append(future.result())


def main():
    """A wrapper for `run` that catches `KeyboardInterrupt` exceptions."""

    try:
        run()
    except KeyboardInterrupt:
        logging.critical(
            "interrupted; you may need to interrupt again to stop all threads"
        )


if __name__ == "__main__":
    main()
