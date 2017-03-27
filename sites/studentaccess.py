import re
import urllib.parse
from ..models.site import Site
from ..utils.webauth import WebAuthBot
from bs4 import BeautifulSoup

URL = 'https://www.reg.uci.edu/access/student'
PAGES = [
    'studylist',
    'transcript',
    'transfers',
    'degreeworks',
    'grades', 
    'profile',
        'academic',
        'enrollment',
        'exams',
        'personal',
    'contact',
    'information'
]

class StudentAccessError(Exception):
    pass

class StudentAccess(Site):
    _params = {
        'seg': 'U'
    }

    def __init__(self, *args, **kwargs):
        Site.__init__(self, *args, **kwargs)

        r = self._session.get(self.url('welcome'))
        soup = BeautifulSoup(r.text, 'html.parser')
        profile = soup.find('li', {'class': 'profile'})

        if not profile or not profile.a or not profile.a.has_attr('href'):
            raise StudentAccessError('Could not find the sidebar link to the student profile')

        qs = urllib.parse.urlparse(profile.a['href']).query
        query = urllib.parse.parse_qs(qs)
        self._params = dict([(k, v.pop()) for k, v in query.items()])

    def getTranscript(self):
        r = self._session.get(self.url('transcript'), params=self._params)
        return Transcript(r.text)

    def url(self, page: str) -> str:
        return '{}/{}/'.format(URL, page)


class Transcript:
    def __init__(self, html: str):
        self._soup = BeautifulSoup(html, 'html.parser')

    def getUniversityRequirements(self) -> dict:
        span = self._soup.find('span', {'class': 'preface'})
        table = span.next_sibling.next_sibling

        if not span or table.name != 'table':
            return False
        
        results = []
        for tr in table.stripped_strings:
            m = re.match(r'([0-9\/]+) ([A-Za-z0-9 ]+) - (Satisfied|Required)', tr)

            if not m:
                return False

            results.append((m.group(1), m.group(2), m.group(3) == 'Satisfied'))

        return results
