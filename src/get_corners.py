# Reading all of the FITS files to get the corners from all the WCSes is an incredibly slow process.
# (It will take days!)  So, do it once and write a csv file that we can read to use for the import.
# Do this with checkpointing so that if the process dies, it can pick up where it left off.

import sys
import os
import io
import pathlib
import logging
import time
import multiprocessing
import multiprocessing.pool

from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS
import pandas

import warnings
from astropy.wcs import FITSFixedWarning
warnings.simplefilter( 'ignore', category=FITSFixedWarning )

imagedir = pathlib.Path( '/dvs_ro/cfs/cdirs/lsst/shared/external/roman-desc-sims/Roman_data/RomanTDS' )
date = '11_6_23'
nprocs = 5

_logger = logging.getLogger(__name__)
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
    _logger.setLevel( logging.INFO )


_totndone = 0
_ntodo = 0

    
def make_corners( i, pointinginfo, scainfo ):
    global imagedir
    
    corners = []
    for scadex in range( len( scainfo['ra'] ) ):
        sca = scadex + 1
        ra = scainfo['ra'][scadex]
        dec = scainfo['dec'][scadex]

        suffix = f"{pointinginfo["filter"]}_{i}_{sca}.fits.gz"
        _logger.info( f"Doing ...{suffix}" )
        
        fpath = ( imagedir / 'images' / 'simple_model' / pointinginfo['filter']
                  / str(i) / f'Roman_TDS_simple_model_{suffix}' )
        with fits.open( fpath ) as hdus:
            nx = hdus[1].header['NAXIS1']
            ny = hdus[1].header['NAXIS2']
            wcs = WCS( header=hdus[1].header )

        cornerras, cornerdecs = wcs.pixel_to_world_values( [ 0, 0, nx-1, nx-1 ],
                                                           [ 0, ny-1, 0, ny-1 ] )

        minra = min(cornerras)
        maxra = max(cornerras)
        mindec = min(cornerdecs)
        maxdec = max(cornerdecs)

        ##### Attempt to order them so that 00, 01, 10, 11 makes sense on the sky
        raorder = [ 0, 1, 2, 3 ]
        raorder.sort( key=lambda i: cornerras[i] )

        # Try to detect an RA that spans 0
        if cornerras[raorder[3]] - cornerras[raorder[0]] > 180.:
            newras = [ r - 360. if r > 180. else r for r in cornerras ]
            raorder.sort( key=lambda i: newras[i] )
            minra = min(newras)
            maxra = max(newras)
            minra = minra if minra > 0 else minra + 360.
            maxra = maxra if maxra > 0 else maxra + 360.

        # Of the two lowest ras, of those pick the one with the lower dec;
        #   that's 00, the other one is 01

        dex00 = raorder[0] if cornerdecs[raorder[0]] < cornerdecs[raorder[1]] else raorder[1]
        dex01 = raorder[1] if cornerdecs[raorder[0]] < cornerdecs[raorder[1]] else raorder[0]

        # Same thing, now high ra

        dex10 = raorder[2] if cornerdecs[raorder[2]] < cornerdecs[raorder[3]] else raorder[3]
        dex11 = raorder[3] if cornerdecs[raorder[2]] < cornerdecs[raorder[3]] else raorder[2]

        ra_00 = cornerras[ dex00 ]
        dec_00 = cornerdecs[ dex00 ]
        ra_01 = cornerras[ dex01 ]
        dec_01 = cornerdecs[ dex01 ]
        ra_10 = cornerras[ dex10 ]
        dec_10 = cornerdecs[ dex10 ]
        ra_11 = cornerras[ dex11 ]
        dec_11 = cornerdecs[ dex11 ]

        corners.append( [ i, sca, ra_00, dec_00, ra_01, dec_01, ra_10, dec_10, ra_11, dec_11,
                          minra, maxra, mindec, maxdec ] )

    return corners

def write_corners( corners ):
    global _totndone, _ntodo
    
    with open( "corners.csv", "a" ) as csv:
        for row in corners:
            csv.write( ",".join( [ str(r) for r in row ] ) )
            csv.write( "\n" )

    _totndone += 1
    _logger.info( f"...{_totndone} of {_ntodo} done" )
    

def main():
    global _totndone, _ntodo, nprocs, iamgedir, date

    obseq = Table.read( imagedir / f'Roman_TDS_obseq_{date}.fits' )
    radec = Table.read( imagedir / f'Roman_TDS_obseq_{date}_radec.fits' )

    # Figure out how far we got

    _ntodo = len(obseq)
    done = None
    uh_oh = False
    cornerfile = pathlib.Path( "corners.csv" )
    if cornerfile.is_file():
        done = pandas.read_csv( cornerfile ).set_index( [ 'pointing', 'sca' ] )
        donedexes = done.index.get_level_values( 'pointing' ).unique()
        for dex in donedexes:
            l =  len( done.xs( dex, level='pointing' ) )
            if l != 18:
                _logger.error( f"Pointing {dex} only has {l} SCAs" )
                uh_oh = True
        if uh_oh:
            raise RuntimeError( "Current corners file is corrupt" )
        _ntodo -= len( donedexes )
        done = None
    else:
        with open( "corners.csv", "w" ) as csv:
            csv.write( "pointing,sca,ra00,dec00,ra01,dec01,ra10,dec10,ra11,dec11,minra,maxra,mindec,maxdec\n" )

    _logger.info( f"{len(donedexes)} of {len(obseq)} in corners.cvs, {_ntodo} left" )
    _logger.info( 'Starting SCAs' )

    pool = multiprocessing.pool.Pool( nprocs, maxtasksperchild=1 )
    
    for i, (pointinginfo, scainfo) in enumerate( zip( obseq, radec ) ):
        if i in donedexes:
            continue

        pool.apply_async( make_corners, (i, pointinginfo, scainfo), callback=write_corners )

    pool.close()
    _logger.info( "All jobs submitting, waiting." )
    pool.join()

    _logger.info( "...done with SCAs" )
    
            
# ======================================================================

if __name__ == "__main__":
    main()
