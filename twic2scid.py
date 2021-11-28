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
import shutil
import subprocess
import sys
import tempfile
import requests
import zipfile

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

print("Downloading the Week in Chess main page...")

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0"
}
url = requests.get(
    "https://theweekinchess.com/twic",
    headers=headers,
)

# list of pgn links found
pgn_links = []

found = 0

from bs4 import BeautifulSoup

bs = BeautifulSoup(url.content, features="lxml")
links = bs.find_all("a")
hrefs = [_.get("href") for _ in links if _.get("href")]
hrefs = [(href, re.search(r"twic(\d+)g.zip", href)) for href in hrefs]
hrefs = [(href, match.group(1)) for (href, match) in hrefs if match]

if options.list:
    hrefs = [(href, _id) for (href, _id) in hrefs if int(_id) in options.list]
elif options.latestn:
    hrefs = hrefs[-options.latestn]

pgn_links = [href for (href, _id) in hrefs]

if not pgn_links:
    print("Could not find PGN zipfile name in twic.html!")
    sys.exit(1)

# I prefer to use lftp here, since it does all the retrying and status
# display for me

print('Getting PGN archives "%s"...' % pgn_links)

# will hold scid databases to be merged
databases = []

# will hold zips downloaded, each zip should contain a pgn file
pgn_zips = []

# containers = will hold pointer to each 'container' for cleanup after use
containers = []

for link in pgn_links:
    container = tempfile.mktemp(".zip")
    containers.append(container)

    if os.path.isfile("/usr/bin/lftp"):
        status = systemapi("lftp -c 'get %s -o %s; quit'" % (link, container))
    else:
        status = systemapi("wget -O %s %s" % (container, link))
        if status != 0:
            print("lftp or wget not working, retrying directly...")
            with open(container, "wb") as fd:
                fd.write(requests.get(link, headers=headers).content)

    pgn_zips.append(zipfile.ZipFile(container))

print("Unzipping and converting to scid databases...")

PGNSCID = "/usr/share/scid/bin/pgnscid"
SCMERGE = "/usr/share/scid/bin/scmerge"
SCSPELL = "/usr/share/scid/bin/scripts/sc_spell.tcl"

for pgn_zip in pgn_zips:
    for file in pgn_zip.namelist():
        if re.search(r"\.pgn$", file):
            output = tempfile.mktemp(".pgn")
            with open(output, "wb") as outfd:
                outfd.write(pgn_zip.read(file))
            with open(file, "a") as outfd2:
                pass
            shutil.copy(output, file)
            database = tempfile.mktemp()
            systemapi(f"{PGNSCID} -f %s %s" % (output, database))
            databases.append(database)

            os.unlink(output)
    pgn_zip.close()

map(os.unlink, containers)

print("Merging databases into %s.new..." % scid_database)

if databases:
    status = systemapi(
        f"{SCMERGE} %s %s %s"
        % (scid_database + ".new", scid_database, " ".join(databases))
    )

    for file in databases:
        map(os.unlink, glob.glob("%s.s*" % file))

    if status == 0:
        print("Moving new database to %s..." % scid_database)
        list(map(os.unlink, glob.glob("%s.s*" % scid_database)))
        systemapi(f"{SCMERGE} %s %s" % (scid_database, scid_database + ".new"))
        list(map(os.unlink, glob.glob("%s.s*" % (scid_database + ".new"))))
        print("Spell checking the new database...")
        systemapi(f"{SCSPELL} %s %s" % (scid_database, scid_spelling))
        print("Writing to log file twic.log of links successfully merged...")
        for link in pgn_links[::-1]:
            systemapi("echo '%s' >> twic.log" % link)
