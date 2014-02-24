import functools
import json
import logging
import traceback
import sys

from flask import Flask, jsonify, request, Response
import youtube_dl


class NoneFile(object):
    '''
    A file-like object that does nothing
    '''
    def write(self, msg):
        pass

    def flush(self, *args, **kaargs):
        pass

    def isatty(self):
        return False


class ScreenFile(NoneFile):
    def write(self, msg):
        logging.debug(msg)


if not hasattr(sys.stderr, 'isatty'):
    #In GAE it's not defined and we must monkeypatch
    sys.stderr.isatty = lambda: False


class SimpleYDL(youtube_dl.YoutubeDL):
    def __init__(self, *args, **kargs):
        super(SimpleYDL, self).__init__(*args, **kargs)
        self._screen_file = ScreenFile()
        self.add_default_info_extractors()


def get_videos(url):
    '''
    Get a list with a dict for every video founded
    '''
    ydl_params = {
        'cachedir': None,
    }
    ydl = SimpleYDL(ydl_params)
    res = ydl.extract_info(url, download=False)

    #Do not return yet playlists
    def clean_res(result):
        r_type = result.get('_type', 'video')
        if r_type == 'video':
            videos = [result]
        elif r_type == 'playlist':
            videos = []
            for entry in result['entries']:
                videos.extend(clean_res(entry))
        elif r_type == 'compat_list':
            videos = []
            for r in result['entries']:
                videos.extend(clean_res(r))
        return videos
    return clean_res(res)


app = Flask(__name__)

def route_api(subpath, *args, **kargs):
    return app.route('/api/'+subpath, *args, **kargs)

def set_access_control(f):
    @functools.wraps(f)
    def wrapper(*args, **kargs):
        response = f(*args, **kargs)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    return wrapper

@route_api('')
@set_access_control
def api():
    url = request.args['url']
    errors = (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError)
    try:
        videos = get_videos(url)
        result ={
            'youtube-dl.version': youtube_dl.__version__,
            'url': url,
            'videos': videos
        }
    except errors as err:
        result = {'error': str(err)}
        logging.error(traceback.format_exc())
    return jsonify(result)

@route_api('list_extractors')
@set_access_control
def list_extractors():
    ie_list = [{
        'name': ie.IE_NAME,
        'working': ie.working(),
    } for ie in youtube_dl.gen_extractors()]
    # TODO return a dict instead of a list
    # see http://flask.pocoo.org/docs/security/#json-security
    return Response(json.dumps(ie_list), mimetype='application/json')
