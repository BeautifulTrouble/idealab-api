#!/bin/bash

# Previously:
#SELECT id,published,title,short_write_up FROM idea;

[ $# != 1 ] && exit 1

sqlite3 $1 <<EOF
.headers on
.mode csv
.output latest.csv
SELECT id,published,name,contact,title,short_write_up FROM idea;
EOF

