#!/bin/sh
docker build . -t bst-plugins-bazel-platform
docker save bst-plugins-bazel-platform -o image.tar
tar xf image.tar
mv */layer.tar ../tests/project/files/platform.tar
