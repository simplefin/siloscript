# Copyright (c) The SimpleFIN Team
# See LICENSE for details.


class Station(object):
    """
    I coordinate user input for requests.
    """

    def __init__(self, store):
        self.store = store


    def createChannel(self, question_taker):
        """
        Create a channel that will pass on questions to C{question_taker}

        @param question_taker: A function that accepts a string prompt and
            should return a (Deferred) answer.
        """
        channel = uuid