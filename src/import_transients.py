import sys
import os
import pathlib
import logging

import pandas
import psycopg2

pqdir = pathlib.Path( "/Roman+DESC/PQ+HDF5_ROMAN+LSST_LARGE" )

_logger = logging.getLogger(__name__)
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
    _logger.setLevel( logging.INFO )


def main():
    con = psycopg2.connect( dbname=os.getenv('PG_DB'),
                            user=os.getenv('PG_USER'),
                            password=os.getenv('PG_PASSWORD'),
                            host=os.getenv('PG_HOST'),
                            port=os.getenv('PG_PORT' ) )
    cursor = con.cursor()

    pqfiles = pqdir.glob( "*.parquet" )
    for pqf in pqfiles:
        df = pandas.read_parquet( pqf )
        import pdb; pdb.set_trace()
        pass
    

# ======================================================================
if __name__ == "__main__":
    main()
