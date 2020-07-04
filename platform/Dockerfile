FROM ubuntu AS base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update

# Add Bazel repository
RUN apt-get -y install curl gnupg
RUN curl https://bazel.build/bazel-release.pub.gpg | apt-key add -
RUN echo "deb [arch=amd64] https://storage.googleapis.com/bazel-apt stable jdk1.8" | tee /etc/apt/sources.list.d/bazel.list

# Install Bazel
RUN apt-get update
RUN apt-get -y install bazel

# Prepare for using Bazel offline
RUN apt-get -y install git python3 python
RUN mkdir /bazel-src
RUN mkdir /bazel-dist
RUN git clone --depth 1 --branch $(bazel version | head -1 | sed -e 's/Build label: //') https://github.com/bazelbuild/bazel /bazel-src
RUN cd /bazel-src && bazel build @additional_distfiles//:archives.tar && tar xvf bazel-bin/external/additional_distfiles/archives.tar \
  -C "/bazel-dist" --strip-components=3
RUN echo build --distdir=/bazel-dist >>/etc/bazel.bazelrc
RUN rm -rf /bazel-src

#
RUN mkdir /bazel
WORKDIR /bazel

# Clean up
RUN apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Switch back to dialog for any ad-hoc use of apt-get
ENV DEBIAN_FRONTEND=dialog

FROM scratch as platform
COPY --from=base / /
