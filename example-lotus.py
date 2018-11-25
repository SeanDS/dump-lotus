from pytz import timezone
from lotus.search import LotusXMLBuilder

# Path to root directory of Lotus Notes scraped site. Set this to the
# directory of the logbook you want to convert.
root_dir = "/path/to/scraped/lotus/directory"

# Filename of the contents page contained within root_dir.
root_contents_page = "By Diary Date?OpenView.html"

# Directory to archive scraped content. This will be filled with
# individual XML files representing each of the logbook pages.
# This directory will be deleted and recreated if it already exists.
archive_dir = "/path/to/store/individual/xml/files"

# Path to write logs to. Set to None for no logs.
debug_log_file = "lotus.log"

if __name__ == "__main__":
    builder = LotusXMLBuilder(root_dir, root_contents_page, archive_dir,
                              debug_log_file=debug_log_file, timezone=timezone("Europe/Berlin"))
    builder.dump()