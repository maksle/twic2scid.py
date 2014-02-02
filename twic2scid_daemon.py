#!/usr/bin/env python

import requests
import sys

from time import strftime


so = sys.stdout
se = sys.stderr

log = open('daemon_log', 'w+r')

sys.stdout = log
sys.stderr = log

import twic2scid

sys.stdout = so
sys.stderr = se

log.seek(0)

body = """
<!DOCTYPE html>
<html>
    <head></head>
    <body>
        <h1>TWIC games to Scid log</h1>
        Run on {0} <br><br> {1}
    </body>
</html>

""".format(strftime("%h-%m-%Y %I:%M%p"),
           log.read().replace('\n', '<br>'))

requests.post(
    "https://api.mailgun.net/v2/sandbox60725.mailgun.org/messages",
    auth=("api", "key-6z5qp1d53m4gpix4njyz-70trd-5uoj2"),
    data={"from": "maks@mailgun <postmaster@sandbox60725.mailgun.org>",
          "to": "Maksim <maxchgr@gmail.com>",
          "subject": "TWIC to Scid output",
          "html": body})

log.close()
