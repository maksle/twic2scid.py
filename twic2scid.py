#!/usr/bin/env python3

# Download the current week's TWIC games and append them to an existing
# Scid database and perform spellchecking.

# Usage: twic2scid.py [Options] [database [spellingfile]]

# Options:
#   -h, --help  show this help message and exit
#   -a, --all   gets all pgn archives on the page. Overrides -n if specified.
#   -n LATESTN  gets LATESTN archives. LATESTN must be an integer. If LATESTN is
#               greater than the number of pgn archives found on the twic page,
#               this is equivalent to --all. If LATESTN is zero, this option is
#               ignored.
#   -d DATABASE, --database=DATABASE
#               specify the scid database to merge into. Default value
#               is 'twic'. Note that this omits the extension .si4 of
#               the database.
#   -s SPELLING, --spelling=SPELLING
#               specifies the spelling file for meta corrections.
#               Default value is 'spelling.ssp'.

# Example usage:
#   twic2scid.py -n 3 -d ~/scidbases/twic -s ~/scidbases/spelling.ssp
#     --merges latest 3 pgns into specified scid database and spelling file.
#   twic2scid.py -a
#     --merges all pgns available into the default database with the default spelling file.
#   twic2scid.py --latestn=5 --spelling=another_spelling.ssp
#     --merges latest 5 pgns into the default database 'twic.si4' in current directory, and uses spelling file 'another_spelling.ssp' in current directory.


# If no database/spellingfile args are given, these defaults are used
# (note - database does not include ".si4")

# scid_database = "twic"
# scid_spelling = "spelling.ssp"

# This version fixes a few bugs, and will use lftp if you have it
# installed, wget if not.  If neither of those work, it will attempt to
# download the URL directly, using Python's urllib.py module (which
# doesn't do regetting, retrying, etc).

# By John Wiegley

# Modifications by Maksim Grinman:
# 3/20/2013: Updated to work with the new TWIC site at http://www.theweekinchess.com/twic
# 3/23/2013: Updated to support optional flags -a and -n.
# 11/25/2015: Updated to add optional flag -l

# NOTE: This program comes with absolutely NO WARRANTY.  If anything
# goes wrong, it may delete your database entirely instead of adding
# to it!  I recommend backing up your database, trying it out, and
# then adding a "last week rollback" type of copy command to your
# cronjob, just to make sure.


import glob
import os
import re
import subprocess
import sys
import tempfile
import requests
import zipfile

from bs4 import BeautifulSoup
from optparse import OptionParser

os.environ["PATH"] = os.environ["PATH"] + ":/usr/local/bin"

usage = (
    "Usage: %prog [Options]\n\n"
    "twic2scid.py --help to see options.\n\n"
    "Example usage:\n"
    "  twic2scid.py -n 3 -d ~/scidbases/twic -s ~/scidbases/spelling.ssp\n"
    "    --merges latest 3 pgns into specified scid database and spelling file.\n"
    "  twic2scid.py -a\n"
    "    --merges all pgns available into the default database with the default spelling file.\n"
    "  twic2scid.py --latestn=5 --spelling=another_spelling.ssp\n"
    "    --merges latest 5 pgns into the default database 'twic.si4' in current directory, and uses "
    "spelling file 'another_spelling.ssp' in current directory.\n"
    "  twic2scid.py -l 1098,1040\n"
    "    --gets twic1098 and twic1040 pgns only"
)

parser = OptionParser(usage)

parser.add_option(
    "-a",
    "--all",
    "--sync",
    action="store_true",
    dest="all",
    help="gets all pgn archives on the page. Overrides -n if specified.",
)

parser.add_option(
    "-n",
    "--latestn",
    type="int",
    dest="latestn",
    help="gets LATESTN archives. LATESTN must be an integer. If LATESTN is greater than the number of pgn archives found on the twic page, this is equivalent to --all. If LATESTN is zero, this option is ignored.",
)

parser.add_option(
    "-l",
    "--list",
    type="string",
    dest="list",
    help="comma delimited list of twic ids to fetch. Takes precedence over -a and -n",
)

parser.add_option(
    "-d",
    "--database",
    dest="database",
    help="specify the scid database to merge into. Default value is 'twic'. Note that this omits the extension .si4 of the database.",
)

parser.add_option(
    "-s",
    "--spelling",
    dest="spelling",
    help="specifies the spelling file for meta corrections. Default value is 'spelling.ssp'.",
)


def systemapi(cmd):
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    out, err = proc.communicate()
    if out:
        print(out.decode())
    if err:
        print(err.decode())
    return proc.returncode


script_directory = os.path.dirname(os.path.realpath(__file__))

PGNSCID = "/usr/share/scid/bin/pgnscid"
SCMERGE = "/usr/share/scid/bin/scmerge"
SCSPELL = "/usr/share/scid/bin/scripts/sc_spell.tcl"

# DEFAULTS are set here
parser.set_defaults(database="twic", spelling="spelling.ssp")

(options, args) = parser.parse_args()

if options.all or options.latestn == 0 or options.latestn is None:
    options.latestn = None
else:
    options.latestn = abs(options.latestn)

if options.list:
    if "-" in options.list:
        options.list = [int(_) for _ in options.list.split("-")]
        assert len(options.list) == 2
        options.list = list(range(options.list[0], options.list[1] + 1))
    else:
        options.list = options.list.split(",")

scid_database = options.database
scid_spelling = options.spelling


headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0"
}


def fetch_links():
    print("Downloading the Week in Chess main page...")
    url = requests.get("https://theweekinchess.com/twic", headers=headers, timeout=30)
    bs = BeautifulSoup(url.content, features="lxml")
    links = bs.find_all("a")
    hrefs = [_.get("href") for _ in links if _.get("href")]
    hrefs = [(href, re.search(r"twic(\d+)g.zip", href)) for href in hrefs]
    hrefs = [(href, match.group(1)) for (href, match) in hrefs if match]
    return hrefs


def filter_hrefs(hrefs, options):
    if options.list:
        hrefs = [(href, id_) for (href, id_) in hrefs if int(id_) in options.list]
    elif options.latestn:
        hrefs = sorted(hrefs, key=lambda v: int(v[1]))
        hrefs = hrefs[-options.latestn :]
    return hrefs


def get_merged_ids_from_log() -> set:
    merged = set()
    with open("twic.log", "r") as merge_log:
        for href in merge_log:
            match = re.search(r"twic(\d+)g.zip", href)
            if match:
                merged.add(match.group(1))
    return merged


def main():
    databases = []
    hrefs = filter_hrefs(fetch_links(), options)
    merged_ids = get_merged_ids_from_log()
    if not hrefs:
        print("Could not find PGN zipfile name in twic.html!")
        sys.exit(1)
    for href, id_ in hrefs:
        # if os.path.isfile(os.path.join(script_directory, f"twic{id_}.pgn")):
        #     continue
        if id_ in merged_ids:
            print(f"skipping {id_}")
            continue
        container = download(href)
        database = make_databases_from_zip(container)
        databases.append(database)
        os.unlink(container)
    if databases:
        status = merge(databases)
        if status == 0:
            for href, _ in hrefs[::-1]:
                systemapi(f"echo '{href}' >> twic.log")


def download(href):
    container = tempfile.mktemp(".zip")
    if os.path.isfile("/usr/bin/lftp"):
        status = systemapi(f"lftp -c 'get {href} -o {container}; quit'")
    else:
        status = systemapi(f"wget --no-verbose -O {container} {href}")
    if status != 0:
        print("lftp or wget not working, retrying directly...")
        with open(container, "wb") as fd:
            fd.write(requests.get(href, headers=headers, timeout=30).content)
    return container


def make_databases_from_zip(container) -> str:
    with zipfile.ZipFile(container) as pgn_zip:
        for name in pgn_zip.namelist():
            if not re.search(r"\.pgn$", name):
                continue
            with open(name, "wb") as outfd:
                outfd.write(pgn_zip.read(name))
            database = tempfile.mktemp()
            systemapi(f"{PGNSCID} -f %s %s" % (name, database))
            return database


def merge(databases):
    new = scid_database + ".new"
    print(f"Merging databases into {new}")
    status = systemapi(f"{SCMERGE} {new} {scid_database} {' '.join(databases)}")

    for db in databases:
        map(os.unlink, glob.glob(f"{db}.s*"))

    if status == 0:
        print(f"Moving new database to {scid_database}...")
        list(map(os.unlink, glob.glob(f"{scid_database}.s*")))
        systemapi(f"{SCMERGE} {scid_database} {new}")
        list(map(os.unlink, glob.glob(f"{new}.s*" % (scid_database + ".new"))))
        print("Spell checking the new database...")
        systemapi(f"{SCSPELL} {scid_database} {scid_spelling}")
        print("Writing to log file twic.log of links successfully merged...")

    return status


main()
