<!--
Copyright (c) The SimpleFIN Team
See LICENSE for details.
-->

[![Build Status](https://secure.travis-ci.org/simplefin/siloscript.png?branch=master)](http://travis-ci.org/simplefin/siloscript)

# siloscript #

siloscript provides a way to run scripts that might require sensitive user input (such as account credentials).

This was written as a way of giving bank website-scraping scripts a place to store/get data.  But it is general enough to maybe be useful elsewhere.



## Installation ##

Install the latest stable version from GitHub:

    pip install git+git://github.com/simplefin/siloscript.git@master


## Example ##


### Command line ###

You can run silo scripts interactively with `siloscript run`:

    siloscript run siloscript/data/scripts/testscript/foo

See `--help` for more info.


### Web ###

There's a sample web interface you can run.  Install dependencies then run the server:

    siloscript serve

Then open your browser to http://127.0.0.1:7600/static/debug.html

Click the "Run" button and it will run the `scripts/testscript/foo` script in this repo, which asks for an account number.  Enter something.  It will echo it back as a result.

If you click "Run" again, it will not ask you for the information again, because it is cached.





## Writing a user-interaction script ##

The only special thing your script needs to do is expect a `DATASTORE_URL` environment variable, like this:

    DATASTORE_URL="http://foo.com" ./your-script

The script produces the desired response on stdout.  If the script exits with exit code 0, it has succeeded, otherwise it is considered a failure by the caller.

The `DATASTORE_URL` provides a key-value storage interface tied to a single user.  If your script needs user information (such as credentials) it can ask through that URL.  If your script needs to store state between invocations it can store it with that URL.

Here's some examples of using the `DATASTORE_URL` using `curl`.

To get a user's `account_id` you would do something like:

    curl ${DATASTORE_URL}/account_id?prompt=Account+ID

If you want to save the value of some cookies that were set as a result of interacting with a website:

    curl -X PUT -H "Content-Type: text/plain" -d "some-value-for-the-cookie" ${DATASTORE_URL}/cookies

To get previously stored data but **never** ask the user, omit the `prompt=XXX` query parameter:

    curl ${DATASTORE_URL}/cookies


# Running the tests #

The tests can be very slow (especially the ones that do crypto).  On Ubuntu, you can speed things up by doing the following (based on [this article](https://www.digitalocean.com/community/tutorials/how-to-setup-additional-entropy-for-cloud-servers-using-haveged)):

	apt-get install haveged


Copyright &copy; The SimpleFIN Team