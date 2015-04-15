<!--
Copyright (c) The SimpleFIN Team
See LICENSE for details.
-->

[![Build Status](https://secure.travis-ci.org/simplefin/simplefin-bridge.png?branch=master)](http://travis-ci.org/simplefin/simplefin-bridge)

# SimpleFIN Bridge Web App #

A web app that provides a SimpleFIN interface for banks that don't.


## Writing a bank-interaction script ##

Your bank interaction script (e.g. a script that download transaction data) will be called with a `DATASTORE_URL` environment variable, like this:

    DATASTORE_URL="http://foo.com" ./your-script

The script produces a response on stdout.  If the script exits with exit code 0, it has succeeded, otherwise it is considered a failure by the caller.

The `DATASTORE_URL` provides a key-value storage interface tied to a single user.  If your script needs user information (such as credentials, MFA answers) it can ask through that URL.  If your script needs to store state between invocations it can store it with that URL.

Here's some examples of using the `DATASTORE_URL` using `curl`.

To get a user's `account_id` you would do something like:

    curl ${DATASTORE_URL}/account_id?prompt=Account+ID

To get a user's PIN you would do something like:

    curl ${DATASTORE_URL}/pin?prompt=PIN

If you want to save the value of some cookies that were set as a result of interacting with a bank's website:

    curl -X PUT -H "Content-Type: text/plain" -d "some-value-for-the-cookie" ${DATASTORE_URL}/cookies

To get previously stored data but **not** ask the user, omit the `prompt=XXX` query parameter:

    curl ${DATASTORE_URL}/cookies


## Where does `DATASTORE_URL` come from? ##



## Example ##

You'll need 4 terminals.

In terminal 1, start the server:

    python sfinb/server.py

In terminal 2, open a user-interaction channel:

    curl http://127.0.0.1:9600/channel/$(curl http://127.0.0.1:9600/channel/open)/events

In terminal 3, request the `testbank/foo` script to be run for the user `jimmy`.  Get the `channel_key` from the output of terminal 2:

    curl http://127.0.0.1:9600/run/jimmy -X POST -d "script=testbank/foo" -d"channel_key=${CHANNEL_KEY_FROM_TERMINAL_2}"

You will see a question event come up on terminal 2.  Use that question id and answer the question in terminal 4:

    curl http://127.0.0.1:9600/question/${QUESTION_ID_FROM_TERMINAL_2} -X POST -d"18293093"

















Copyright &copy; The SimpleFIN Team