import logging

from lotus.parse import LotusParser

# set up logger
logging.basicConfig()

# path to scraped Lotus Notes pages
root_dir = "/path/to/scraped/tree"

# path to archive XML versions of Lotus Notes pages
archive_dir = "archive"

# set up parser
parser = LotusParser(root_dir, archive_dir)

# find Lotus objects
parser.find()

# save to archive
parser.archive()