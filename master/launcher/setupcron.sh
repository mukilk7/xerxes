#!/bin/bash

crontab -r
echo -e "$1 $2 $3 $4 * $5\n$6 $7 $8 $9 * ${10}" > gtlcron
crontab gtlcron
rm -f gtlcron
