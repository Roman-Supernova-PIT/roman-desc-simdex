import sys
import os
import pathlib
import logging
import math

import psycopg2

from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS

import warnings
from astropy.wcs import FITSFixedWarning
warnings.simplefilter( 'ignore', category=FITSFixedWarning )

imagedir = pathlib.Path( '/RomanTDS' )
cornersfile = pathlib.Path( 'corners.csv' )
date = '11_6_23'


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
    
    obseq = Table.read( imagedir / f'Roman_TDS_obseq_{date}.fits' )
    radec = Table.read( imagedir / f'Roman_TDS_obseq_{date}_radec.fits' )
    corners = Table.read( cornersfile )

    _just_testing = True
    
    # Insert all pointings
    # Would be more efficient with a bulk isnert, but we're only doing this
    #  once, so whatevs.
    _logger.info( "Importing pointings" )
    if True:
        for i, row in enumerate( obseq ):
            cursor.execute( "INSERT INTO pointing(num,ra,dec,filter,exptime,mjd,pa) "
                            "VALUES (%(num)s,%(ra)s,%(dec)s,%(filter)s,%(exptime)s,%(mjd)s,%(pa)s)",
                            { 'num': i,
                              'ra': float( row['ra'] ),
                              'dec': float( row['dec'] ),
                              'filter': row['filter'],
                              'exptime': float( row['exptime'] ),
                              'mjd': float( row['date'] ),
                              'pa': float( row['pa'] ) }
                           )
            if i % 1000 == 0:
                _logger.info( f'...did {i+1} of {len(obseq)} pointings' )
        _logger.info( 'Committing...' )
        con.commit()
    _logger.info( '...done' )


    # The SCAs are a lot slower because we have to read each and every file to get the WCS
    #  to get the corners.

    _logger.info( 'Starting SCAs' )
    for i, (pointinginfo, scainfo) in enumerate( zip( obseq, radec ) ):
        for scadex in range( len( scainfo['ra'] ) ):
            sca = scadex + 1
            ra = scainfo['ra'][scadex]
            dec = scainfo['dec'][scadex]

            mycorner = corners[ ( corners['pointing'] == i ) & ( corners['sca'] == sca ) ]
            if len(mycorner) == 0:
                if _just_testing:
                    # corners file isn't complete yet
                    continue
                else:
                    raise RuntimeError( f"Didn't find pointing {i} SCA {sca} in corners file" )
            elif len(mycorner) > 1:
                raise RuntimeError( f"Pointing {i} SCA {sca} shows up more than once in corners file" )
            

            # Do a sanity check
            dists = []
            for a in [ 0, 1 ] :
                for b in [ 0, 1 ]:
                    dra = ( ra - mycorner[f'ra{a}{b}'] ) * math.cos( dec * math.pi / 180 )
                    ddec = dec - mycorner[f'dec{a}{b}']
                    dists.append( math.sqrt( dra*dra + ddec*ddec ) )
            if ( max( dists ) - min( dists ) ) / min( dists ) > 0.2:
                raise ValueError( f"ra={ra}, dec={dec}, 00={ra00},{dec00}, 01={ra01},{dec01}, "
                                  f"10={ra10},{dec10}, 11={ra11},{dec11}" )
            minra = mycorner['minra'][0]
            maxra = mycorner['maxra'][0]
            mindec = mycorner['mindec'][0]
            maxdec = mycorner['maxdec'][0]

            if ( mindec > dec ) or ( maxdec < dec ):
                raise ValueError( f"dec {dec} for {i}:{sca} out of range {mindec} : {maxdec}" )
            if minra < maxra:
                if ( minra > ra ) or ( maxra < ra ):
                    raise ValueError( f"ra {ra} for {i}:{sca} out of range {minra} : {maxra}" )
            else:
                if ( ( ( ra < 180 ) and ( ra > maxra )
                       or
                       ( ra > 180 ) and ( ra < minra ) ) ):
                    raise ValueError( f"ra {ra} for {i}:{sca} out of range {minra} : {maxra}" )


            cursor.execute( "INSERT INTO sca(pointing,scanum,ra,dec,"
                            "  ra_00,dec_00,ra_01,dec_01,ra_10,dec_10,ra_11,dec_11,minra,maxra,mindec,maxdec) "
                            "VALUES(%(pointing)s,%(scanum)s,%(ra)s,%(dec)s,%(ra_00)s,%(dec_00)s,"
                            "       %(ra_01)s,%(dec_01)s,%(ra_10)s,%(dec_10)s,%(ra_11)s,%(dec_11)s,"
                            "       %(minra)s,%(maxra)s,%(mindec)s,%(maxdec)s)",
                            { 'pointing': i,
                              'scanum': sca,
                              'ra': float(ra),
                              'dec': float(dec),
                              'ra_00': float(mycorner['ra00'][0]),
                              'dec_00': float(mycorner['dec00'][0]),
                              'ra_01': float(mycorner['ra01'][0]),
                              'dec_01': float(mycorner['dec01'][0]),
                              'ra_10': float(mycorner['ra10'][0]),
                              'dec_10': float(mycorner['dec10'][0]),
                              'ra_11': float(mycorner['ra11'][0]),
                              'dec_11': float(mycorner['dec11'][0]),
                              'minra': float( minra ),
                              'maxra': float( maxra ),
                              'mindec': float( mindec ),
                              'maxdec': float( maxdec ) } )

        # Commit every pointing because otherwise it just seems kind of out of hand
        con.commit()
        if i % 100 == 0:
            _logger.info( f'...did SCAs for {i+1} of {len(obseq)} pointings' )

    _logger.info( "...done with SCAs" )
            
            
# ======================================================================

if __name__ == "__main__":
    main()
