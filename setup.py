#!/usr/bin/env python3

import sys

try:
    from setuptools import setup, find_packages
except ImportError:
    print("BuildStream requires setuptools in order to locate plugins. Install "
          "it using your package manager (usually python3-setuptools) or via "
          "pip (pip3 install setuptools).")
    sys.exit(1)

setup(
    name='bst-plugins-bazel',
    version="0.0.1",
    python_requires=">=3.6",
    description="Exploration: A collection of BuildStream plugins that are related to Bazel.",
    author='Sander Striker',
    author_email='s.striker@striker.nl',
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Build Tools'
    ],
    project_urls={
        'Source': 'https://github.com/sstriker/bst-plugins-bazel',
        'Tracker': 'https://github.com/sstriker/bst-plugins-bazel/issues',
    },
    include_package_data=True,
    install_requires=[
    ],
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    entry_points={
        'buildstream.plugins.elements': [
            'bazel = bst_plugins_bazel.elements.bazel',
        ],
    },
    extras_require={
        'test': [
            'buildstream >= 1.93.3.dev0',
            'pytest >= 3.1.0',
            'pytest-datafiles',
            'pytest-env',
            'pytest-xdist',
            'ruamel.yaml',
        ],
    },
    zip_safe=False
)  # eof setup()
