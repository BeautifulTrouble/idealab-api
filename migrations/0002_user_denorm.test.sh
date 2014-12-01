#!/bin/bash
main () {
#############################################################################

compare Ideas\
    'SELECT idea.id,user.name,user.contact FROM idea LEFT JOIN user ON idea.user_id=user.id;' \
    'SELECT id,name,contact FROM idea;'

compare Improvements\
    'SELECT improvement.id,user.contact FROM improvement LEFT JOIN user ON improvement.user_id=user.id;' \
    'SELECT id,contact FROM improvement;'

#############################################################################
}
compare () {
    # USAGE: compare NAME OLD_QUERY NEW_QUERY 
    echo "$2"|sqlite3 before.db >before
    echo "$3"|sqlite3 after.db >after
    diff -u before after >/dev/null && echo -e "\033[32m$1 OK\033[0m" || echo -e "\033[31m$1 FAILED\033[0m"
}
cd $(dirname $(readlink -f $0))
BASE=$(basename -s .test.sh $0)
echo "Testing ${BASE}..."
BEFORE=${BASE}.before
AFTER=${BASE}.after
if file $BEFORE|grep SQL 2>/dev/null; then
    # These are already sqlite dbs
    cp $BEFORE before.db
    cp $AFTER after.db
else
    # These are SQL dumps
    sqlite3 before.db ".read $BEFORE"
    sqlite3 after.db ".read $AFTER"
fi
sqlite3 before.db ".schema" >before
sqlite3 after.db ".schema" >after
echo -e "\033[33mSchema diff\033[0m" 
diff -u before after
main
rm before.db after.db before after
