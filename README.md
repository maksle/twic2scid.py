twic2scid.py
============

See http://sourceforge.net/p/scidvspc/code/HEAD/tree/scripts/twic2scid.py

My version of scid vs pc's twic2scid.py. It scrapes theweekinchess.com for the
weekly games and and merges to my scid db. The twic files are the actual db.

Download the current week's TWIC games and append them to an existing
Scid database and perform spellchecking.

Usage: twic2scid.py [Options] [database [spellingfile]]

Options:
  -h, --help  show this help message and exit


  -a, --all   gets all pgn archives on the page. Overrides -n if specified.


  -n LATESTN  gets LATESTN archives. LATESTN must be an integer. If LATESTN is
              greater than the number of pgn archives found on the twic page,
              this is equivalent to --all. If LATESTN is zero, this option is
              ignored.


 -d DATABASE, --database=DATABASE
              specify the scid database to merge into. Default value
              is 'twic'. Note that this omits the extension .si4 of
              the database.


 -s SPELLING, --spelling=SPELLING
               specifies the spelling file for meta corrections.
               Default value is 'spelling.ssp'.


Example usage:

    twic2scid.py -n 3 -d ~/scidbases/twic -s ~/scidbases/spelling.ssp
merges latest 3 pgns into specified scid database and spelling file.

    twic2scid.py -a
merges all pgns available into the default database with the default spelling file.

    twic2scid.py --latestn=5 --spelling=another_spelling.ssp
merges latest 5 pgns into the default database 'twic.si4' in current directory, and uses spelling file 'another_spelling.ssp' in current directory.


If no database/spellingfile args are given, these defaults are used (note -
database does not include ".si4")

scid_database = "twic"

scid_spelling = "spelling.ssp"

