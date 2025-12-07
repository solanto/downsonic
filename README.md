# downsonic

downsonic is a little command-line utility made to help download all of a user's music from an OpenSubsonic server.

downsonic is meant to fill a similar niche to rsync; it keeps it simple as a transfer utility. It's not as intelligent as rsync—no delta-transfers here—but music libraries tend not to be edited, only added to.

What sets downsonic apart from rsync for music is that, in working with the OpenSubsonic API, you have the option to transcode your music before downloading it. This can save you considerable space if you'd just like a good-enough copy of your music for the occasional offline listen.

## installing

On pipx systems:

```bash
pipx install downsonic
```

On pip systems, for global installation:

```bash
pip install downsonic
```

For development and other cases: the program's more or less a single file, at `src/downsonic/main.py`.

## usage

```
usage: main.py [-h] [--netrc-file NETRC_FILE] [-u USER] [-p PASSWORD] [-b BITRATE] [-F FORMAT] [-e EXTENSION] [-t THREADS] [-f] [-V] [--non-interactive]
               source destination

examples:
  main.py music.server.local ~/Music
  main.py https://music.server.me ~/Music --netrc-file ~/.another-netrc
  main.py https://music.server.me:1234 ~/Music -F mp3 -b 320

positional arguments:
  source                OpenSubsonic server to download music from; [http[s]://][host][:port], where port defaults to 80 for http, 443 for https, and 8080
                        when unspecified
  destination           destination directory

options:
  -h, --help            show this help message and exit
  --netrc-file NETRC_FILE
                        path to a netrc file with login credentials; defaults to `~/.netrc`
  -u, --user USER       username for server login; see help on `--password`
  -p, --password PASSWORD
                        password for server login ⚠️ avoid supplying your passwords through the terminal in plaintext, and instead consider using a netrc
                        file
  -b, --bitrate BITRATE
                        target bitrate for transcoded files, in kbps; unspecified or `0` set no limit
  -F, --format FORMAT   audio format; navidrome servers, for example, support `mp3`, `flac`, `aac`, and `raw` (no transcoding)
  -e, --extension EXTENSION
                        override the extension of all audio files; when unspecified, each file's extension will be inferred automatically
  -t, --threads THREADS
                        maximum number of threads (and parallel network connections) to use while downloading
  -f, --force           (re)download songs even if they're already in the destination directory
  -V, --verbosity       how much logging to show; `-v` for critical errors (🛑), `-vv` for recoverable errors (⛔️), `-vvv` for warnings (⚠️), `-vvvv` for
                        info (default), and `-vvvvv` for debug (🪲)
  --non-interactive     don't show dynamic UI elements, like progress bars
```

## contributing

Feel free to ask questions here or at [person@dandelion.computer](mailto:person@dandelion.computer). I'll do my best to collaborate with those who'd like to!

## license

[GNU General Public License v3.0 or later](https://spdx.org/licenses/GPL-3.0-or-later.html). See license in [`LICENSE.md`](LICENSE.md).