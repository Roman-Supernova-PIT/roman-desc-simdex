import sys
import os
import re

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

    kwvalre = re.compile( r'^(?P<k>[^=]+)=(?P<v>.*)$' )
    tuplistre = re.compile( r'^ *([\(\[])(.*)([\]\)]) *$' )
    intre = re.compile( r'^[\+\-]?[0-9]+$' )
    floatre = re.compile( r'^[\+\-]?[0-9]*\.?[0-9]+(e[\+\-]?[0-9]+)?$' )
    minmaxre = re.compile( r'^(.*)_(min|max)' )
    
    def argstr_to_args( self, argstr ):
        """Parse argstr as a bunch of /kw=val to a dictionary, update with request body if it's json."""

        kwargs = {}
        if argstr is not None:
            for arg in argstr.split("/"):
                match = self.kwvalre.search( arg )
                if match is None:
                    app.logger.error( f"error parsing url argument {arg}, must be key=value" )
                    return f'error parsing url argument {arg}, must be key=value', 500
                kw = match.group('k').strip()
                val = match.group('v').strip()
                parsedval = None

                # Look for list or tuple
                match = tuplistre.search( val ):
                if ( match is None ) and ( match.group(1) == match.group(3) ):
                    istuple = ( match.group(1) == '(' )
                    items = [ i.strip for i in match.group(2).split(",") ]
                    parsedval = []
                    for i in items:
                        if intre.search( i ):
                            parsedval.append( int(i) )
                        elif floatre.search( i ):
                            parsedval.append( float(i) )
                        else:
                            parsedval.append( i )
                    if istuple:
                        parsedval = tuple(parsedval )

                else:
                    # Look for int, then float
                    if intre.search( val ):
                        parsedval = int( val )
                    elif floatre.search( val ):
                        parsedval = float( val )
                    else:
                        parsedval = val

                if parsedval is None:
                    app.logger.error( f"error parsing value \"{val}\"; this should never happen!" )
                    return f"error parsing \"{val}\"; this should never happen!", 500
                    
                kwargs[ kw ] = parsedval
                
        if flask.request.is_json:
            kwargs.update( flask.request.json )
        return kwargs


    def parse_kws_to_sql( self, data, pointing_nums=None, pointing_text=None, sca_nums=None, sca_text=None ):
        if pointing_nums is None:
            pointing_nums = { 'num', 'pointing_ra', 'pointing_dec', 'exptime', 'mjd', 'pa' }
        if pointing_text is None:
            pointing_text = { 'filter' }
        if sca_nums is None:
            sca_nums = { 'scanum', 'ra', 'dec', 'ra_00', 'dec_00', 'ra_01', 'dec_01', 'ra_10', 'dec_10',
                         'ra_11', 'dec_11', 'minra', 'maxra', 'mindec', 'maxdec' }
        if sca_text is None:
            sca_text = {}

        andtxt = ''
        q = ''
        subdict = {}
        containing = False
        ra = None
        dec = None
        
        for kw, val in data.items():
            if kw == 'containing':
                if ( ( not isinstance(val, tuple) ) or ( not isinstance(val, list) ) or ( len(val) != 2 )
                     or ( not ( isinstance(val[0], float) or isinstance(val[0], int ) ) )
                     or ( not ( isinstance(val[1], float) or isinstance(val[1], int ) ) ) ):
                    app.logger.error( f"Invalid containing: {val} (type {type(val)}" )
                    raise KeywordParseException( f"containing must be a tuple or list with two decimal degree values" )
                q += f' {andtxt} minra<=%(ra)s AND maxra>=%(ra)s AND mindec<=%(dec)s AND maxdec>=%(dec)s '
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
                minmax = re.group(2)
                field = re.group(1)
            else:
                field = kw

            if ( field in pointing_nums ) or ( field in sca_nums ):
                tab = "p" if ( field in pointing_nums) else "s"
                q += f' {andtxt} {tab}.{field[9:]}' if field[0:8] == 'pointing' else f'{andtxt} {tab}.{field} '
                q += andtxt + ' ' + field
                q += ">=" if minmax == "min" else "<=" if minmax == "max" else "="
                q += "%({tab}_{field})s"
                subdict[ f"{tab}_{field}" ] = val
                andtxt = 'AND'

            elif ( field in pointing_text ) or ( field in sca_text ):
                tab = "p" if ( field in pointing_text ) else "s"
                if minmax is not None:
                    app.logger.error( f"_min and _max invalid with field {field}" )
                    raise KeywordParseException( f"_min and _max invalid with field {field}" )
                q += f' {andtxt} {tab}.{field}=%({tab}_{field})s '
                subdict[ f"{tab}_{field}" ] = val
                andtxt = 'AND'
            
            else:
                app.logger.error( "Invalid search keyword {kw}" )
                raise KeywordParseException( f"Invalid search keyword {kw}" )

        return q, subdict, containing, ra, dec
            
    
# ======================================================================

class MainPage(BaseView):
    def dispatch_request( self ):
        return flask.render_template( 'roman_desc_simdex.html' )

# ======================================================================

class FindImages(BaseView):
    def dispatch_request( self, argstr=None ):
        data = self.argstr_to_args( argstr )
        if not isinstance( data, dict ):
            app.logger.error( "FindImages: data isn't a dict!  This shouldn't happen" )
            return f"FindImages: data isn't a dict!  This shouldn't happen", 500

        wheretxt, subdict, containing, ra, dec = self.parse_kws_to_sql( data )

        q = ( "SELECT p.num AS pointingnum,p.ra AS borera,p.dec AS boredec,p.filter,p.exptime,p.mjd,p.pa,"
              "  s.scanum,s.ra,s.dec,s.ra_00,sa.dec_00,sa.ra_01,s.dec_01,s.ra_10,s.dec_10,s.ra_11,s.dec_11" )
        if containing:
            q += " INTO TEMP TABLE temp_find_images "
        q += " FROM scal s INNER JOIN pointing p ON s.pointing=p.num "
        q += f" WHERE {wheretxt} "
        q += " ORDER BY p.mjd "

        with DB() as con:
            cursor = con.cusor()
            cursor.execute( q, subdict )

            if containing:
                cursor.execute( "SELECT * FROM temp_find_images WHERE "
                                "q3c_poly_query(%(ra)s, %(dec)s, "
                                "((ra_00,dec_00), (ra_01,dec_01), (ra_11,dec_11), (ra10,dec_10))::polygon",
                                { 'ra': ra, 'dec': dec } )

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
    "/campaigns": Campaigns,
    "/collections/<string:campaign>": Collections,
    "/surveyinfo/<string:campaign>/<string:collection>": SurveyInfo,
    "/instrinfo/<string:campaign>/<string:collection>": InstrInfo,
    "/analysisinfo/<string:campaign>/<string:collection>": AnalysisInfo,
    "/tiers/<string:campaign>/<string:collection>": Tiers,
    "/surveys/<string:campaign>/<string:collection>": Surveys,
    "/summarydata/<string:campaign>/<string:collection>": SummaryData,
    "/snzhist/<string:campaign>/<string:collection>/<string:sim>": SNZHist,
    "/snzhist/<string:campaign>/<string:collection>/<string:sim>/<path:argstr>": SNZHist,
    "/spechist/<string:which>/<string:campaign>/<string:collection>/<string:sim>/<int:strategy>": SpecHist,
    ( "/spechist/<string:which>/<string:campaign>/<string:collection>/<string:sim>"
      "/<int:strategy>/<path:argstr>" ): SpecHist,
    "/randomltcv/<string:campaign>/<string:collection>/<string:sim>/<int:gentype>/<string:z>/<string:dz>": RandomLTCV,
    ( "/randomltcv/<string:campaign>/<string:collection>/<string:sim>"
      "/<int:gentype>/<string:z>/<string:dz>/<string:tier>" ): RandomLTCV,
    ( "/randomspectrum/<string:campaign>/<string:collection>/<string:sim>/<int:gentype>/<string:z>/<string:dz>"
      "/<string:t>/<string:dt>/<path:argstr>" ): RandomSpectrum,
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
