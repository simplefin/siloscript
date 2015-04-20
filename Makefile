# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

.PHONY: clean

clean:
	-find siloscript -name "*.pyc" -exec rm {} \;
	-rm *.sqlite
	-rm -r .gpghome
