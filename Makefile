IMAGE_REPO ?= brineylab
MODEL ?= boltz2
TAG ?= dev

.PHONY: build-image push-image install start up stop down restart status logs backup

build-image:
	./scripts/build_image.sh $(MODEL) $(TAG)

push-image:
	./scripts/build_image.sh $(MODEL) $(TAG) --push

install:
	./deploy.sh install

start up:
	./deploy.sh start

stop down:
	./deploy.sh stop

restart:
	./deploy.sh restart

status:
	./deploy.sh status

logs:
	./deploy.sh logs

backup:
	./deploy.sh backup
