#!/bin/bash
main () {
#############################################################################

compare Ideas\
    'SELECT user.name,idea.title FROM user LEFT JOIN idea ON idea.user_id=user.id;'\
    'SELECT user.name,idea.title FROM user LEFT JOIN idea ON idea.user_id=user.id;'

compare Improvements\
    'SELECT user.name,improvement.content FROM user LEFT JOIN improvement ON improvement.user_id=user.id;'\
    'SELECT user.name,improvement.content FROM user LEFT JOIN improvement ON improvement.user_id=user.id;'

compare Users\
    'SELECT id,provider,provider_id FROM user;'\
    'SELECT local_id,provider,provider_id FROM user;'


#############################################################################
}
compare () {
    # USAGE: compare NAME OLD_QUERY NEW_QUERY 
    echo "$2"|sqlite3 before.db >before
    echo "$3"|sqlite3 after.db >after
    diff -u before after >/dev/null && echo -e "\033[32m$1 OK\033[0m" || echo -e "\033[31m$1 FAILED\033[0m"
}
BASE=$(basename -s .test.sh $0)
echo "Testing ${BASE}..."
BEFORE=${BASE}.before.sql
AFTER=${BASE}.after.sql
sqlite3 before.db ".read $BEFORE"
sqlite3 after.db ".read $AFTER"
main
rm before.db after.db before after
