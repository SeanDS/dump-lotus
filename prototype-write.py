import os
import shutil
import logging
import pickle

from lotus.tools import working_directory
from lotus.parse import LotusParser

## START EDITING

# debug log file
debug_log_file = "prototype-write.log"

# path to root directory of Lotus Notes scraped directory (the directory containing
# `intranet.aei.uni-hannover.de`)
root_dir = "/path/to/scraped/lotus/directory"

# directory to archive scraped content
archive_dir = "/path/to/store/individual/xml/files"

## STOP EDITING

# delete the log file
if os.path.exists(debug_log_file):
    os.remove(debug_log_file)

# delete everything in archive directories
if os.path.exists(archive_dir):
    shutil.rmtree(archive_dir)

# create archive directory structure
os.mkdir(archive_dir)
os.mkdir(os.path.join(archive_dir, 'meta'))
os.mkdir(os.path.join(archive_dir, 'pages'))
os.mkdir(os.path.join(archive_dir, 'pages', 'media'))

# set up loggers
formatter = logging.Formatter("%(name)-25s - %(levelname)-8s - %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler(debug_log_file)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger = logging.getLogger("lotus")
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

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
