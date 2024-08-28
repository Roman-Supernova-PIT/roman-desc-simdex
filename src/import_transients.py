import sys
import os
import re
import pathlib
import logging
import json

import numpy
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
        match = re.search( '^snana_([0-9]+)\.parquet$', pqf.name )
        if match is None:
            raise ValueError( f"Failed to parse filename {match}" )
        healpix = int( match.group(1) )
        df = pandas.read_parquet( pqf )

        for n, row in enumerate( df.itertuples() ):
            if n % 1000 == 0:
                _logger.info( f"File {pqf.name}, {n} of {len(df)} done" )

            params = { k: v for k, v in zip( row.model_param_names, row.model_param_values ) }
            for k in params.keys():
                if isinstance( params[k], numpy.float32 ) or isinstance( params[k], numpy.float64 ):
                    # For the sake of json.dumps
                    params[k] = float( params[k] )
            
            subdict = { 'id': int(row.id),
                        'healpix': healpix,
                        'ra': float(row.ra),
                        'dec': float(row.dec),
                        'host_id': int(row.host_id),
                        'gentype': int(row.gentype),
                        'model_name': row.model_name,
                        'start_mjd': float(row.start_mjd),
                        'end_mjd': float(row.end_mjd),
                        'z_cmb': float(row.z_CMB),
                        'mw_ebv': float(row.mw_EBV),
                        'mw_extinction_applied': bool(row.mw_extinction_applied),
                        'av': float(row.AV),
                        'rv': float(row.RV),
                        'v_pec': float(row.v_pec),
                        'host_ra': float(row.host_ra),
                        'host_dec': float(row.host_dec),
                        'host_mag_g': float(row.host_mag_g),
                        'host_mag_i': float(row.host_mag_i),
                        'host_mag_f': float(row.host_mag_F),
                        'host_sn_sep': float(row.host_sn_sep),
                        'peak_mag_g': float(row.peak_mag_g),
                        'peak_mag_i': float(row.peak_mag_i),
                        'peak_mag_f': float(row.peak_mag_F),
                        'lens_dmu': float(row.lens_dmu),
                        'lens_dmu_applied': bool(row.lens_dmu_applied),
                        'model_params': json.dumps(params)
                       }
            
            cursor.execute( f"INSERT INTO transient({','.join(subdict.keys())}) "
                            f"VALUES ({','.join( [ f'%({i})s' for i in subdict.keys() ] )})",
                            subdict )

        con.commit()
    

# ======================================================================
if __name__ == "__main__":
    main()
