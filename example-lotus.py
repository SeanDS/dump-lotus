from converters import lotus_to_xml

# Path to root directory of Lotus Notes scraped site. Set this to the
# directory of the logbook you want to convert.
root_dir = "/path/to/scraped/lotus/directory"

# Directory to archive scraped content. This will be filled with
# individual XML files representing each of the logbook pages.
# This directory will be deleted and recreated if it already exists.
archive_dir = "/path/to/store/individual/xml/files"

# Path to write logs to. Set to None for no logs.
debug_log_file = "lotus.log"

if __name__ == "__main__":
    lotus_to_xml(root_dir, archive_dir, debug_log_file)