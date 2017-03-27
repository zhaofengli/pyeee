from ..utils.webauth import WebAuthBot

class Site:
    _session = None
    _webauth = None

    def __init__(self, ucinetid: str, password: str):
        """Initializes the object

           Args:
               ucinetid (str): UCINetID
               password (str): Password
        """
        self._webauth = WebAuthBot(ucinetid, password)
        self._session = self._webauth.buildSession()
