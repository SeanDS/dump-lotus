#!/usr/bin/env python

from setuptools import setup, find_packages

REQUIREMENTS = [
    "lxml",
    "beautifulsoup4",
    "pytz",
    "python-magic"
]

setup(
    name="dump-lotus",
    use_scm_version=True,
    description="Convert Lotus Notes documents and attachments into Python objects",
    author="Sean Leavey",
    author_email="sean.leavey@ligo.org",
    url="https://github.com/SeanDS/dump-lotus",
    packages=find_packages(),
    install_requires=REQUIREMENTS,
    license="GPLv3",
    zip_safe=False,
    classifiers=[
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6"
    ]
)
