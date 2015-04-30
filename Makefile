# Copyright (c) The SimpleFIN Team
# See LICENSE for details.
T = siloscript
DOCKER_HOST_IP ?= 127.0.0.1

.PHONY: clean

clean:
	-find siloscript -name "*.pyc" -exec rm {} \;
	-rm *.sqlite
	-rm -r .gpghome

test: start-backends
	RABBITMQ_URL="amqp://guest:guest@$(DOCKER_HOST_IP):5672" trial $(T)

start-backends:
	docker-compose up -d --no-recreate

stop-backends:
	docker-compose stop
