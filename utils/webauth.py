import re
import types
import requests
import urllib.parse
from bs4 import BeautifulSoup

WEBAUTH_ENDPOINT = 'https://login.uci.edu/ucinetid/webauth'
EEE_NETLOC = 'eee.uci.edu'

AUTH_MARKERS = {
    'eee.uci.edu': {
        'auth': ('a', {'class': 'logoutlink'}),
        'anon': ('a', {'class': 'loglink'})
    },
    'www.reg.uci.edu': {
        'auth': ('span', {'class': 'logout'}),
        'anon': ('a', {'id', 'webauth'})
    }
}

class WebAuthFailureError(Exception):
    pass

class WebAuthUnknownError(Exception):
    pass

class WebAuthLoopError(Exception):
    pass

class WebAuthBot:
    __ucinetid = ''
    __password = ''

    def __init__(self, ucinetid, password):
        '''Initializes WebAuthBot'''
        self.__ucinetid = ucinetid
        self.__password = password

    def attachSession(self, session: requests.Session) -> None:
        """Gives a Session superpowers
        
        This will decorate the get(), post() and request() methods of the session, in order to transparently authenticate with WebAuth when presented with one.

        For example, you can use s.get("https://checkmate.ics.uci.edu") and you will get the Checkmate page. WebAuthBot will deal with the login redirect transparently, without you noticing.

        If you try something like s.get("https://login.uci.edu/ucinetid/webauth?return_url=http%3A%2F%2Fcheckmate.ics.uci.edu"), you will also get the Checkmate page as the response, magically.

        To disable the WebAuthBot augmentations, set the `eee` attribute to False.

        Args:
            session: A Session object
        """
        session.eee = True
        eeeobj = self

        def session_request(self, method, url, **kwargs):
            if not self.eee:
                # WebAuthBot augs disabled, pass through
                return requests.Session.request(self, method, url, **kwargs)
            else:
                response = requests.Session.request(self, method, url, **kwargs)
                parsed = urllib.parse.urlparse(response.url)
                if response.url.startswith(WEBAUTH_ENDPOINT):
                    # Needs authentication
                    needsAuth = True
                elif parsed.netloc in AUTH_MARKERS and response.headers['content-type'].startswith('text/html'):
                    soup = BeautifulSoup(response.text, 'html.parser')
                    if soup.find(*AUTH_MARKERS[parsed.netloc]['auth']):
                        needsAuth = False
                    else:
                        needsAuth = True
                else:
                    needsAuth = False

                if needsAuth:
                    target = eeeobj.authenticate(url, self)
                    targetres = requests.Session.request(self, method, target, **kwargs)
                    if targetres.url.startswith(WEBAUTH_ENDPOINT):
                        raise WebAuthLoopError
                    return targetres
                else:
                    return response

        session.request = types.MethodType(session_request, session)

    def buildSession(self) -> requests.Session:
        """Builds a WebAuthBot-enhanced Session object

        This is as same as initializing a Session object then passing it to EEE.attachSession().

        Returns:
            A WebAuthBot-enhanced Session object.
        """
        s = requests.Session()
        self.attachSession(s)
        return s

    def authenticate(self, returnUrl: str, session: requests.Session=None) -> str:
        """Attempts to authenticate to WebAuth

        Note:
            Although optional, it is strongly recommended to pass a Session object so that the auth cookies can be preserved. This is required for EEE, for example.

        Args:
            returnUrl: The URL of a protected resource
            session (optional): A Session object. If not specified, one will be created just for this call.

        Returns:
            The return URL, possibly with a auth token included in the query string. A cookie will be added to the session.
        """
        if session is None:
            session = requests.Session()

        if returnUrl.startswith(WEBAUTH_ENDPOINT):
            # Looks like a WebAuth URL
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(returnUrl).query)
            if 'return_url' in qs:
                # Get the real return URL
                endpoint = returnUrl
                returnUrl = qs['return_url'].pop()
            else:
                # Not a parsable WebAuth URL
                endpoint = WEBAUTH_ENDPOINT
        else:
            endpoint = WEBAUTH_ENDPOINT

        data = {
            'referer': '',
            'return_url': returnUrl,
            'info_text': '',
            'info_url': '',
            'submit_type': '',
            'ucinetid': self.__ucinetid,
            'password': self.__password,
            'login_button': 'Login' # Surprisingly, this is required
        }
        params = {
            'return_url': returnUrl
        }

        session.eee = False
        r = session.post(endpoint, params=params, data=data)
        session.eee = True
        if r.url.startswith(WEBAUTH_ENDPOINT):
            soup = BeautifulSoup(r.text, 'html.parser')
            redirect = soup.find('meta', {
                'http-equiv': 'refresh'
            } );
            if not redirect:
                # The attempt was unsuccessful
                raise WebAuthFailureError

            if not redirect.has_attr('content'):
                raise WebAuthUnknownError('Malformed <meta> tag')

            matches = re.match(r'^[0-9]\;url\=(.+)', redirect['content'])
            if not matches:
                raise WebAuthUnknownError('Malformed content attribute: {}'.format(redirect['content']))

            return matches.group(1)
        else:
            # WebAuth is not supposed to do that
            # Don't know what to do - Let's bail
            raise WebAuthUnknownError
    
