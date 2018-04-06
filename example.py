import logging

from lotus.parse import LotusParser

# set up logger
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.WARNING)

root_path = "/path/to/scraped/tree"

parser = LotusParser(root_path)
parser.parse_all()

# check all images in pages were found
for post in list(parser.pages):
    for url in post.internal_urls:
        if url not in [page.path for page in parser.pages]:
            # not in main list, but is it an alias?
            if url not in parser.page_path_aliases.keys():
                print("%s not found (from %s)" % (url, post.path))