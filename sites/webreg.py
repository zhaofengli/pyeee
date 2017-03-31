import re
import requests
from bs4 import BeautifulSoup
from ..models.site import Site
from ..utils.webauth import WebAuthBot


class WebRegUnavailableError(Exception):
    """WebReg is currently unavailable
    """
    pass


class WebRegAuthError(Exception):
    """Generic authentication error
    """
    pass


class WebRegUnknownError(Exception):
    """An unknown WebReg error
    """
    pass


class WebRegEnrollmentError(Exception):
    """An unknown enrollment error
    """
    pass


class WebRegTimeConflictError(WebRegEnrollmentError):
    """The meeting time of the requested class conflicts with the time of another enrolled course
    """
    pass


class WebRegPrerequisiteError(WebRegEnrollmentError):
    """The user has not taken the prerequsite courses
    """
    pass


class WebRegNotEnrolledError(WebRegEnrollmentError):
    """The user is not currently enrolled in the course
    """
    pass


class WebRegClassLevelError(WebRegEnrollmentError):
    """The user does not have the required class level
    """
    pass


WEBREG_REDIRECT = 'https://www.reg.uci.edu/cgi-bin/webreg-redirect.sh'
WEBREG_ERRORS = [
    (WebRegTimeConflictError, r'Sorry, your class was not added\. Meeting time of this course conflicts with the time of another course in which you are enrolled or waitlisted\. +([0-9]+)', [1]),
    (WebRegPrerequisiteError, r'Sorry, your class was not added\. You are ineligible to enroll due to prerequisites, corequisites, or repeat restrictions\. View the Schedule of Classes comments prior to contacting your academic advisor\.', False),
    (WebRegClassLevelError, r'Sorry, your class was not added\. Only students within the ([A-Za-z]+) class level \(([0-9]+) or more units\) are eligible for enrollment in this course\.', [1, 2]),
    (WebRegNotEnrolledError, r'Your class was NOT DROPPED\. You are not currently enrolled in this course\. We are unable to process your drop request\.', False),
]


class WebReg:
    _url = ''
    _curPage = 'enrollQtrMenu'
    _call = '0000'

    def __init__(self, *args, call: str=None, url: str=None, **kwargs):
        """Initializes WebReg object

        Args:
            call (str, optional): WebReg's session ID. If specified, we will attempt to reuse the session. Note that this will only work when connecting from the same IP.
            url (str, optional): WebReg's URL. Required when `call` is specified, since there are multiple WebReg instances and session IDs are instance-specific.
        """
        Site.__init__(self, *args, **kwargs)

        if call is None:
            self.authenticate()
        else:
            if url is None:
                raise WebRegAuthError()
            self._call = call
            self._url = url

    def authenticate(self):
        """Authenticates to WebReg
        """
        # Authenticate to get the link to the main menu
        rdpage = self._session.get(WEBREG_REDIRECT)
        soup = BeautifulSoup(rdpage.text, 'html.parser')
        redirect = soup.find('meta', {'http-equiv': 'refresh'})

        if not redirect or not redirect.has_attr('content'):
            raise WebRegUnavailableError

        matches = re.match(r'^[0-9]\; *url\=(.+)', redirect['content'])
        if not matches:
            raise WebRegUnknownError('Malformed redirect')

        loginurl = matches.group(1)

        # Parse the main menu to get the required call number (session ID)
        home = self._session.get(loginurl)
        self._url = home.url
        soup = BeautifulSoup(home.text, 'html.parser')
        callinput = soup.find('input', {'type': 'hidden', 'name': 'call'})

        if not callinput:
            raise WebRegAuthError

        self._call = callinput['value']

    def submit(self, data: dict, nologin: bool=False):
        """Makes a raw POST submission

        Args:
            data (dict): The POST data to be submitted
            nologin (bool, optional): If True, we won't attempt to automatically log back in in case our session gets invalidated. Defaults to False.
        """
        post = {
            'page': self._curPage,
            'call': self._call,
            'submit': ''
        }
        post.update(data)
        response = self._session.post(self._url, data=post)
        soup = BeautifulSoup(response.text, 'html.parser')

        if soup.find('table', {'id': 'webreg-login-box'}):
            # We are logged out
            if not nologin:
                self.authenticate()
                r = self.submit(data, nologin=True)
                if not r:
                    raise WebRegAuthError
            else:
                return False

        return response

    def navigate(self, page: str) -> requests.Response:
        """Navigates to a page

        Args:
            page (str): Name of the page

        Returns:
            requests.Response
        """
        response = self.submit({'mode': page})
        self._curPage = page
        return response

    def logout(self):
        """Logs out of WebReg
        """
        self.submit({'mode': 'exit'}, nologin=True)

    def enroll(self, courseCode: str, mode: str='add', pnp: bool=None, varUnits: int=None, authCode: str='') -> requests.Response:
        """Attempts to add, drop or change a course.

        Args:
            courseCode (str): The course code
            mode (str, optional): One of 'add', 'drop' and 'change'. Defaults to 'add'.
            pnp (bool, optional): Whether to take the course P/NP. Defaults to None.
            varUnits (int, optional): The requested number of variable units. Defaults to None.
            authCode (str, optional): The authorization code. Defaults to ''.

        Returns:
            requests.Response

        Raises:
            One of the WebReg errors.
        """
        self.navigate('enrollmentMenu')
        post = {
            'mode': mode,
            'courseCode': courseCode,
            'gradeOption': {False: '1', True: '2', None: ''}[pnp],
            'varUnits': '' if varUnits is None else str(varUnits),
            'authCode': authCode
        }
        response = self.submit(post)
        soup = BeautifulSoup(response.text, 'html.parser')
        error = soup.find('div', {'class': 'WebRegErrorMsg'})
        if error:
            msg = next(iter(error.stripped_strings))

            for exception, pattern, groups in WEBREG_ERRORS:
                matches = re.match(pattern, msg)
                if matches:
                    if groups != False:
                        raise exception([matches.group(x) for x in groups])
                    else:
                        raise exception()

            raise WebRegEnrollmentError(msg)
        self.navigate('enrollQtrMenu')
        return response

    def addCourse(self, *args, **kwargs):
        return self.enroll(*args, **kwargs, mode='add')

    def dropCourse(self, *args, **kwargs):
        return self.enroll(*args, **kwargs, mode='drop')

    def listSchedule(self):
        """List the currently enrolled courses

        Note:
            This is unfinished, and the API will be changed
        """

        response = self.navigate('listSchedule')
        soup = BeautifulSoup(response.text, 'html.parser')
        studyList = soup.find('table', {'class', 'studyList'})

        if not studyList:
            raise WebRegUnknownError('Could not find study list')

        raw = list(studyList.contents[3].stripped_strings)[12].split('\n')

        self.navigate('enrollQtrMenu')

        return raw

