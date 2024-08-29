import sys
import os
import re
import io
import logging
import traceback
from contextlib import contextmanager

import psycopg2

import flask
import flask.views

@contextmanager
def DB():
    try:
        con = psycopg2.connect( dbname=os.getenv('PG_DB'),
                                user=os.getenv('PG_USER'),
                                password=os.getenv('PG_PASSWORD'),
                                host=os.getenv('PG_HOST'),
                                port=os.getenv('PG_PORT' ) )
        yield con
    finally:
        con.rollback()
        con.close()
        

# ======================================================================

class KeywordParseException(Exception):
    pass

# ======================================================================

class BaseView(flask.views.View):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    def dispatch_request( self, *args, **kwargs ):
        try:
            return self.do_the_things( *args, **kwargs )
        except Exception as ex:
            sio = io.StringIO()
            traceback.print_exc( file=sio )
            app.logger.error( sio.getvalue() )
            return f"Exception in {self.__class__.__name__}: {str(ex)}", 500
        

    kwvalre = re.compile( r'^(?P<k>[^=]+)=(?P<v>.*)$' )
    tuplistre = re.compile( r'^ *([\(\[])(.*)([\]\)]) *$' )
    intre = re.compile( r'^[\+\-]?[0-9]+$' )
    floatre = re.compile( r'^[\+\-]?[0-9]*\.?[0-9]+(e[\+\-]?[0-9]+)?$' )
    minmaxre = re.compile( r'^(.*)_(min|max)' )
    
    def argstr_to_args( self, argstr ):
        """Parse argstr as a bunch of /kw=val to a dictionary, update with request body if it's json."""

        app.logger.debug( f"Parsing argstr \"{argstr}\"" )
        
        kwargs = {}
        if argstr is not None:
            for arg in argstr.split("/"):
                match = self.kwvalre.search( arg )
                if match is None:
                    raise KeywordParseException( f"error parsing url argument {arg}, must be key=value" )
                kw = match.group('k').strip()
                val = match.group('v').strip()
                parsedval = None

                # Look for list or tuple
                match = self.tuplistre.search( val )
                if ( ( match is not None ) and
                     ( ( ( match.group(1) == '(' ) and ( match.group(3) == ')' ) )
                       or
                       ( ( match.group(1) == '[' ) and ( match.group(3) == ']' ) )
                      )
                    ):
                    istuple = ( match.group(1) == '(' )
                    app.logger.debug( f"{val} is a {'tuple' if istuple else 'list'}" )
                    items = [ i.strip() for i in match.group(2).split(",") ]
                    app.logger.debug( f"Parsed {match.group(2)} to {items}" )
                    parsedval = []
                    for i in items:
                        if self.intre.search( i ):
                            parsedval.append( int(i) )
                            app.logger.debug( f"Parsed {i} to integer" )
                        elif self.floatre.search( i ):
                            parsedval.append( float(i) )
                            app.logger.debug( f"Parsed {i} to float" )
                        else:
                            parsedval.append( i )
                            app.logger.debug( f"Parsed {i} to string" )
                    if istuple:
                        parsedval = tuple(parsedval )
                    app.logger.debug( f"parsedval={parsedval}" )

                else:
                    app.logger.debug( f"{val} is a scalar" )
                    # Look for int, then float
                    if self.intre.search( val ):
                        parsedval = int( val )
                    elif self.floatre.search( val ):
                        parsedval = float( val )
                    else:
                        parsedval = val

                if parsedval is None:
                    raise KeywordParseException( f"error parsing value \"{val}\"; this should never happen!" )

                app.logger.debug( f"keyword {kw} parsed to {parsedval} (type {type(parsedval)})" )
                
                kwargs[ kw ] = parsedval
                
        if flask.request.is_json:
            kwargs.update( flask.request.json )

        return kwargs


    def parse_kws_to_sql( self, argstr, fieldspec=None, imagesearch=False, transientsearch=False, allfields=None ):
        data = self.argstr_to_args( argstr )
        if not isinstance( data, dict ):
            app.logger.error( f"parse_kws_to_sql: data isn't a dict!  This shouldn't happen" )
            raise Exception( f"parse_kws_to_sql: data isn't a dict!  This shouldn't happen" )

        if ( allfields is not None ) and ( 'fields' in data ):
            if not set( data['fields'] ).issubset( set( allfields ) ):
                diff = set( data['fields' ] ) - set( allfields )
                app.logger.error( f"{self.__class__.__name__}: passed invalid fields {diff}" )
                raise Exception( f"Invalid return fields: {diff}" )
            fields = ",".join( data[ 'fields' ] )
            del data['fields']
        else:
            fields = "*"
            
        try:
            if fieldspec is None:
                if bool(imagesearch) == bool(transientsearch):
                    raise ValueError( "Must either pass fieldspec, "
                                      "or set exactly one of (imagesearch,transientsearch)" )
                if imagesearch:
                    fieldspec = { 'pointing': { 'nums': { 'num', 'pointing_ra', 'pointing_dec',
                                                          'exptime', 'mjd', 'pa' },
                                                'text': { 'filter' },
                                                'abbrev': 'p',
                                                'map': { 'pointing_ra': 'ra', 'pointing_dec': 'dec' },
                                               },
                                  'sca': { 'nums': { 'scanum', 'ra', 'dec',
                                                     'ra_00', 'dec_00', 'ra_01', 'dec_01',
                                                     'ra_10', 'dec_10', 'ra_11', 'dec_11',
                                                     'minra', 'maxra', 'mindec', 'maxdec' },
                                           'text': {},
                                           'map': {},
                                           'abbrev': 's'
                                          }
                                 }
                elif transientsearch:
                    fieldspec = { 'transient': { 'nums': { 'id', 'healpix', 'ra', 'dec', 'host_id', 'gentype',
                                                           'start_mjd', 'end_mjd', 'z_cmb', 'mw_ebv',
                                                           'av', 'rv', 'v_pec', 'host_ra', 'host_dec',
                                                           'host_mag_g', 'host_mag_i', 'host_mag_f',
                                                           'host_sn_sep', 'peak_mjd',
                                                           'peak_mag_g', 'peak_mag_i', 'peak_mag_f',
                                                           'lens_dmu' },
                                                 'text': { 'model_name' },
                                                 'map': {},
                                                 'abbrev': 't'
                                                }
                                 }

            andtxt = ''
            q = ''
            subdict = {}
            containing = False
            ra = None
            dec = None

            for kw, val in data.items():
                # Special case: containing for an image search
                if kw == 'containing':
                    app.logger.debug( f"Gonna check if {val} is a tuple or list of 2 ints/floats" )
                    if ( ( not ( isinstance(val, tuple) or isinstance(val, list) ) ) or ( len(val) != 2 )
                         or ( not ( isinstance(val[0], float) or isinstance(val[0], int) ) )
                         or ( not ( isinstance(val[1], float) or isinstance(val[1], int) ) )
                        ):
                        app.logger.error( f"Invalid containing: {val} (type {type(val)}, "
                                          f"types {[type(i) for i in val]})" )
                        raise KeywordParseException( f"containing must be a tuple or list "
                                                     f"with two decimal degree values" )
                    q += ( f' {andtxt} ( mindec<=%(dec)s AND maxdec>=%(dec)s '
                           f'            AND '
                           f'            ( maxra>minra AND minra<=%(ra)s AND maxra>=%(ra)s ) '
                           f'            OR '
                           f'            ( maxra<minra AND ( %(ra)s<=maxra OR %(ra)s>=minra ) ) ) ' )

                    ra = val[0]
                    dec = val[1]
                    subdict['ra'] = ra
                    subdict['dec'] = dec
                    containing = True
                    andtxt = 'AND'
                    continue

                minmax = None
                field = None
                match = self.minmaxre.search( kw )
                if match is not None:
                    minmax = match.group(2)
                    field = match.group(1)
                else:
                    field = kw

                foundfield = False
                for tab, tabinfo in fieldspec.items():
                    if ( field in tabinfo['nums'] ) or ( field in tabinfo['text'] ):
                        foundfield = True
                        dbfield = field if field not in tabinfo['map'] else tabinfo['map'][field]
                        abbrev = tabinfo['abbrev']
                        if ( field in tabinfo['text'] ) and ( minmax is not None ):
                            raise KeywordParseExcepotion( f"_min and _max invalid with field {field}" )
                        var = f"{abbrev}_{field}{'_min' if minmax=='min' else '_max' if minmax=='max' else ''}"
                        q += f' {andtxt} {abbrev}.{dbfield}'
                        q += ">=" if minmax == "min" else "<=" if minmax == "max" else "="
                        q += f"%({var})s "
                        subdict[ var ] = val
                        andtxt = 'AND'
                        break

                if not foundfield:
                    raise KeywordParseException( f"Unknown search field {field}" )

            return q, subdict, fields, containing, ra, dec

        except KeywordParseException as ex:
            msg = "Failed to parse "
            if argstr is not None:
                msg += f"argument string \"{argstr}\" "
            if ( argstr is not None ) and ( len(flask.request.data) > 0 ):
                msg += "and "
            if len(flask.request.data) > 0:
                msg += f"POST data \"{str(flask.request.data)}\" "
            msg += f": {str(ex)}"
            app.logger.error( msg )
            return msg, 500
            
    
# ======================================================================

class MainPage(BaseView):
    def dispatch_request( self ):
        return flask.render_template( 'roman_desc_simdex.html' )

# ======================================================================

class FindRomanImages(BaseView):
    def do_the_things( self, argstr=None ):
        allfields = [ 'pointingnum', 'borera', 'boredec', 'filter', 'exptime', 'mjd', 'pa',
                      'scanum', 'ra', 'dec', 'ra_00', 'dec_00', 'ra_01', 'dec_01',
                      'ra_10', 'dec_10', 'ra_11', 'dec_11', ]

        ( wheretxt, subdict, fields,
          containing, ra, dec ) = self.parse_kws_to_sql( argstr, imagesearch=True, allfields=allfields )

        if re.search( wheretxt, "^/s*$" ):
            return "findimages failed: must include some search criteria", 500
        
        q = ( "SELECT p.num AS pointingnum,p.ra AS borera,p.dec AS boredec,p.filter,p.exptime,p.mjd,p.pa,"
              "  s.scanum,s.ra,s.dec,s.ra_00,s.dec_00,s.ra_01,s.dec_01,s.ra_10,s.dec_10,s.ra_11,s.dec_11" )
        if containing:
            q += " INTO TEMP TABLE temp_find_images "
        q += " FROM sca s INNER JOIN pointing p ON s.pointing=p.num "
        q += f" WHERE {wheretxt} "
        q += " ORDER BY p.mjd "

        with DB() as con:
            cursor = con.cursor()
            app.logger.debug( f"q={q}" )
            app.logger.debug( f"subdict={subdict}" )
            app.logger.debug( f"Sending query: {cursor.mogrify(q,subdict)}" )
            cursor.execute( q, subdict )

            if containing:
                q = ( f"SELECT {fields} FROM temp_find_images WHERE "
                      f"q3c_poly_query(%(ra)s, %(dec)s, "
                      f"ARRAY[ra_00,dec_00, ra_01,dec_01, ra_11,dec_11, ra_10,dec_10])" )
                subdict = { 'ra': ra, 'dec': dec }
                app.logger.debug( f"Sending query: {cursor.mogrify(q,subdict)}" )
                cursor.execute( q, subdict )

            cols = [ d[0] for d in cursor.description ]
            rows = cursor.fetchall()

        rval = { c: [ r[i] for r in rows ] for i, c in enumerate( cols ) }

        return rval
                    
                         
# ======================================================================

class FindTransients(BaseView):
    def do_the_things( self, argstr=None ):
        allfields = [ 'id', 'healpix', 'ra', 'dec', 'host_id', 'gentype', 'model_name',
                      'start_mjd', 'end_mjd', 'z_cmb', 'mw_ebv', 'mw_extinction_applied',
                      'av', 'rv', 'v_pec', 'host_ra', 'host_dec',
                      'host_mag_g', 'host_mag_i', 'host_mag_f', 'host_sn_sep',
                      'peak_mjd', 'peak_mag_g', 'peak_mag_i', 'peak_mag_f',
                      'lens_dmu', 'lens_dmu_applied', 'model_params' ]

        wheretxt, subdict, fields, _, _, _ = self.parse_kws_to_sql( argstr, transientsearch=True, allfields=allfields )

        q = f"SELECT {fields} FROM transient t WHERE {wheretxt}"

        with DB() as con:
            cursor = con.cursor()
            app.logger.debug( f"q={q}" )
            app.logger.debug( f"subdict={subdict}" )
            app.logger.debug( f"Sending query: {cursor.mogrify(q,subdict)}" )
            cursor.execute( q, subdict )
            cols = [ d[0] for d in cursor.description ]
            rows = cursor.fetchall()

        rval = { c: [ r[i] for r in rows ] for i, c in enumerate( cols ) }

        return rval

# ======================================================================

app = flask.Flask( __name__, instance_relative_config=True )
# app.logger.setLevel( logging.INFO )
app.logger.setLevel( logging.DEBUG )

app.add_url_rule( "/",
                  view_func=MainPage.as_view("mainpage"),
                  strict_slashes=False )

rules = {
    "/findromanimages": FindRomanImages,
    "/findromanimages/<path:argstr>": FindRomanImages,
    "/findtransients": FindTransients,
    "/findtransients/<path:argstr>": FindTransients,
}

# Dysfunctionality alert: flask routing doesn't interpret "0" or "5" as
# a float.  (It thinks it's an int and an int only.)

lastname = None
for url, cls in rules.items():
    match = re.search( "^/([^/]+)", url )
    if match is None:
        raise ValueError( f"Bad url {url}" )
    name = match.group(1)
    if name == lastname:
        # Kind of a hack so that flask doesn't get pissy about repeated names
        name += "x"
    lastname = name
    app.add_url_rule( url, view_func=cls.as_view(name), methods=["GET","POST"], strict_slashes=False )

# ****
# for rule in app.url_map.iter_rules():
#     app.logger.debug( f"Found rule {rule}" )
# ****
