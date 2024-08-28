import sys
import os
import re
import logging
import argparse
import pathlib
from contextlib import contextmanager

import psycopg2
import psycopg2.errors

_dbname = None
_dbuser = None
_dbpass = None
_dbhost = None
_dbport = None
_dbport = None


_logger = logging.getLogger("main")
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
_logger.setLevel( logging.INFO )


@contextmanager
def DB( dbcon=None ):
    global _dbname, _dbuser, _dbpass, _dbhost, _dbport
    
    if dbcon is not None:
        yield dbcon
        return
    
    if any( [ _dbname is None, _dbuser is None, _dbpass is None, _dbhost is None, _dbport is None ] ):
        raise RuntimeError( "Need all of _dbname, _dbuser, _dbpass, _dbhost, _dbport" )

    try:
        con = None
        con = psycopg2.connect( dbname=_dbname, user=_dbuser, password=_dbpass, host=_dbhost, port=_dbport )
        yield con
    finally:
        con.rollback()
        con.close()


def get_all_migrations():
    p = pathlib.Path( "." )
    migrations = [ m.name for m in p.glob( "*.sql" ) ]
    migrations.sort()
    return migrations

        
def get_applied_migrations():
    with DB() as con:
        cursor = con.cursor()
        try:
            cursor.execute( "SELECT name FROM _migrations ORDER BY name" )
            migrations = [ row[0] for row in cursor.fetchall() ]
        except psycopg2.errors.UndefinedTable:
            con.rollback()
            cursor.execute( "CREATE TABLE _migrations( "
                            "   name text, "
                            "   applied_on timestamptz default now() ) " )
            con.commit()
            migrations = []

    return migrations


def apply_migration( mig ):
    statements = []
    curstatement = ""
    semiend = re.compile( "^(.*);\s*$" )
    with open(mig) as ifp:
        for line in ifp:
            match = semiend.search( line )
            if semiend.search( line ):
                curstatement += match.group(1)
                statements.append( curstatement )
                curstatement = ""
            else:
                curstatement += " " + line

    if not re.search( "^\s*$", curstatement ):
        raise RuntimeError( f"Error in {mig}: left over text at end: {curstatement}" )


    with DB() as con:
        cursor = con.cursor()
        try:
            for statement in statements:
                cursor.execute( statement )
            cursor.execute( "INSERT INTO _migrations(name) VALUES (%(name)s)", {'name': mig} )
            con.commit()
        except Exception as ex:
            con.rollback()
            _logger.error( f"Exception applying {mig}: {ex}" )
            _logger.error( f"Verify that the database is not all screwed up!" )
            raise

def main():
    global _dbname, _dbuser, _dbpass, _dbhost, _dbport
    
    parser = argparse.ArgumentParser( "run_migrations",
                                      description=( "Run all PostgreSQL *.sql files in current directory, "
                                                    "remembering what's done" ),
                                      formatter_class=argparse.ArgumentDefaultsHelpFormatter )
    parser.add_argument( '-d', '--dbname', default=os.getenv('PG_DB', None), help='database name' )
    parser.add_argument( '-u', '--dbuser', default=os.getenv('PG_USER', None), help='database user' )
    parser.add_argument( '-p', '--dbpass', default=os.getenv('PG_PASSWORD', None), help='database password' )
    parser.add_argument( '-H', '--dbhost', default=os.getenv('PG_HOST', None), help='database host' )
    parser.add_argument( '-P', '--dbport', type=int, default=os.getenv('PG_PORT', 5432), help='database port' )
    args = parser.parse_args()

    _dbname = args.dbname
    _dbuser = args.dbuser
    _dbpass = args.dbpass
    _dbhost = args.dbhost
    _dbport = args.dbport

    allmig = get_all_migrations()
    appliedmig = get_applied_migrations()

    unknownmig = [ i for i in appliedmig if i not in allmig ]
    if len( unknownmig ) > 0:
        raise RuntimeError( f"Migrations inconsistency: the following applied migrations are unknown: {unknownmig}" )

    if len(appliedmig) > 0:
        lastdex = allmig.index( appliedmig[-1] )
        missing = [ i for i in allmig[:lastdex+1] if i not in appliedmig ]
        if len( missing ) > 0:
            raise RuntimeError( f"Migrations inconsistency: the following migrations should have already been "
                                f"applied: {missing}" )

    # This next condition sould be guaranteed by the last two, but be safe
    if not all( [ allmig[i] == appliedmig[i] for i in range(len(appliedmig)) ] ):
        raise RuntimeError( f"The first {len(appliedmig)} migrations are inconsistent between what exists "
                            f"and what has been applied." )


    toapply = [ i for i in allmig if i not in appliedmig ]
    if len( toapply ) == 0:
        _logger.info( "No migrations to apply." )
    else:
        nl = '\n'
        _logger.info( f"Migrations to apply:\n   {f'{nl}   '.join(toapply)}" )
        for mig in toapply:
            _logger.info( f"Applying {mig}..." )
            apply_migration( mig )


# ======================================================================

if __name__ == "__main__":
    main()
