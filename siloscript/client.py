# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

import os
import requests
from siloscript.error import NotFound



class Client(object):
    """
    I am a synchronous client for interacting with the key value store
    provided in siloscript.
    """

    def __init__(self, data_url):
        self.url = data_url


    def getValue(self, key, prompt=None, save=True):
        """
        Get a value from the data store.

        @param key: Identifier for the value you want.
        @param prompt: Human-readable version of prompt if wanted.
        @param save: Whether or not to save the value in the database.
            You must provide a C{prompt} if this is C{False}.

        @raise NotFound: If there is no such value and a user is not there to
            supply it.
        """
        params = {}
        if prompt:
            params['prompt'] = prompt
        if save is False:
            params['save'] = 'False'
        r = requests.get('%s/%s' % (self.url, key), params=params)
        if r.status_code == 200:
            return r.text
        raise NotFound(key)
            

    def putValue(self, key, value):
        """
        Save a value in a data store.
        """
        r = requests.put('%s/%s' % (self.url, key), data=value)
        if r.status_code == 200:
            return
        raise NotFound(key)


    def getToken(self, value):
        """
        Exchange a sensitive value for a consistent opaque token.
        """
        r = requests.post(self.url, params={'value': value})
        if r.status_code == 200:
            return r.text
        raise NotFound()



_global_client = Client(os.environ.get('DATASTORE_URL',
        'DATASTORE_URL was not set'))

getValue = _global_client.getValue
putValue = _global_client.putValue
getToken = _global_client.getToken
