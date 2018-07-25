import os
import logging
import pickle

from lotus.tools import working_directory
from lotus.parse import LotusParser

# set up logger
logging.basicConfig(level=logging.INFO)

## START EDITING

# path to root directory of Lotus Notes scraped directory (the directory containing
# `intranet.aei.uni-hannover.de`)
root_dir = "/path/to/scraped/lotus/directory"

# directory to archive scraped content
archive_dir = "/path/to/store/individual/xml/files"

## STOP EDITING

with working_directory(root_dir):
    parser = LotusParser(root_dir, archive_dir)
    parser.find()

    # add notice to each page to link to the archive
    message = """
<pre>
    This post was imported from Lotus Notes.
    To view the original, click <a href="%s">here</a>.
</pre>
%s
    """

    for page in parser.pages:
        # path is whatever wget saved, but without ".html" extension, and with the root path
        # removed and protocol added
        # warning: don't use rstrip as this matches characters in any order
        original_url = "https://" + page.path[:-5]
        page.content =  message % (original_url, page.content)

    # save everything into files
    parser.archive()
