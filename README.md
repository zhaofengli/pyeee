# PyEEE
A Python library for accessing UCI EEE automatically. Also contains useful utilities for other UCI services, such as WebAuth.

## Requirements
* Python 3
* `requests`
* `beautifulsoup4`

## WebAuth
PyEEE provides a wrapper around Session in [Requests](http://www.python-requests.org/), to help you authenticate to WebAuth automatically.

```
import pyeee
import requests
eee = pyeee.EEE('your_ucinetid', 'your_password')
s = requests.Session()
eee.attachSession(s)
```

Now the session has superpowers! Use `get()`, `post()` and other methods as you normally would, and PyEEE will automatically authenticate you with WebAuth in case you get redirected to a login page.
```
r = s.get('https://eee.uci.edu/myeee')
```

You will get a response of MyEEE, logged into your account. This works with any URL that redirects you to WebAuth (https://login.uci.edu), as well as any URL under eee.uci.edu.

This means you can do:
```
s.get('https://checkmate.ics.uci.edu/')
```

And even:
```
s.get('https://login.uci.edu/ucinetid/webauth?return_url=https%3A%2F%2Feee.uci.edu%2F')
```

Build your bots, and forget about the pesky WebAuth.

### Authenticating manually
If you want more control, you can do things manually:
```
urlWithToken = eee.authenticate('https://eee.uci.edu/myeee')
```
This will give you a modified MyEEE URL with the authentication token included in the query string, while giving your session some tasty cookies. Follow this URL to get to the actual MyEEE.
