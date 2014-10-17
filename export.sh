#!/bin/bash

# Previously:
#SELECT id,published,title,short_write_up FROM idea;

[ $# != 1 ] && exit 1

sqlite3 $1 <<EOF
.headers on
.mode csv
.output latest.csv
SELECT idea.id,idea.published,user.name,user.contact,idea.title,idea.short_write_up 
FROM idea 
LEFT JOIN user 
ON idea.user_id = user.id;
EOF

