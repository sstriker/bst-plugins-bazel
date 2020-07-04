BuildStream Bazel Plugins
*************************

A collection of plugins for `BuildStream <https://buildstream.build>`_ that are
related to `Bazel <https://bazel.build>`_.

The purpose of this collection of plugins is to make BuildStream and Bazel
work together in seamless fashion.  These plugins should make it easy to work
with a mix of projects where some build with traditional build tools, and
others using Bazel.  Dependencies are made possible in both directions.
Bazel is configured using BuildStream to increase hermiticity and
repeatability over time.


Usage
=====

There are two ways to use external BuildStream plugins, either as a submodule,
or as a Python package. See BuildStream's
`External plugin documentation <https://docs.buildstream.build/master/format_project.html#loading-plugins>`_
for more details.

Using the plugins as a Python package
-------------------------------------
To use the bazel plugins as a Python package within a BuildStream project,
you will first need to install bst-plugins-container via pip::

   pip install bst-plugins-bazel

The plugins must be declared in *project.conf*. To do this, please refer
to BuildStream's
`Local plugins documentation <https://docs.buildstream.build/master/format_project.html#local-plugins>`_.

Using the plugins locally within a project
------------------------------------------
To use the bazel plugins locally within a
BuildStream project, you will first need to clone the repo to a location
**within your project**::

    git clone https://github.com/sstriker/bst-plugins-bazel.git

The plugins must be declared in *project.conf*. To do this, please refer
to BuildStream's
`Pip plugins documentation <https://docs.buildstream.build/master/format_project.html#local-plugins>`_.
