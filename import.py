#!/usr/bin/env python2

import contextlib
import csv
import os, os.path
import platform
import shutil
import time
import urllib2
try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
if platform.node() == 'change':
    DB_FILE = 'idealab.db'
    DB_PATH = THIS_DIR + '/' + DB_FILE
    DOC_ID = '1EJRqTOjDbwV6iNf9tfL2Rz7g8OrDaiYvxLFc1ar1598'
    CSV_URL = 'https://docs.google.com/spreadsheets/d/{}/export?format=csv'.format(DOC_ID)
else:
    DB_FILE = 'dummy.db'
    DB_PATH = THIS_DIR + '/' + DB_FILE
    CSV_URL = 'http://localhost:8000/dummy.csv'

def backup_db(path=THIS_DIR + '/backups'):
    try:
        os.mkdir(path)
    except OSError: pass
    shutil.copy(DB_PATH, '%s/%s.%s' % (path, DB_FILE, time.strftime('%F@%R')))

def utf8izer(reader):
    for line in reader:
        yield [col.decode('utf8') for col in line]

def main():
    backup_db()

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    with contextlib.closing(urllib2.urlopen(CSV_URL)) as file:
        for id,published,title,short_write_up in utf8izer(csv.reader(file)):
            published = '1' if published == '1' else '0'
            c.execute('''
                UPDATE idea 
                SET published=?,title=?,short_write_up=? 
                WHERE id=?
            ''', (published, title, short_write_up, id))
    db.commit()
    db.close()

if __name__ == '__main__':
    main()

