IMAGE_REPO ?= brineylab
MODEL ?= boltz2
TAG ?= dev

.PHONY: build-image push-image

build-image:
	./scripts/build_image.sh $(MODEL) $(TAG)

push-image:
	./scripts/build_image.sh $(MODEL) $(TAG) --push
