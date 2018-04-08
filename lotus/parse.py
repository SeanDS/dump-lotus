import os
import logging
import pytz

from .objects import LotusPage
from .exceptions import PageInvalidException

LOGGER = logging.getLogger("lotus-parser")

class LotusParser(object):
    """Parses Lotus Notes documents"""

    def __init__(self, root_path, archive_dir, timezone=None, parser="html.parser"):
        if timezone is None:
            # assume UTC
            timezone = pytz.UTC

        self.root_path = root_path
        self.archive_dir = archive_dir
        self.timezone = timezone
        self.parser = parser

        # page objects
        self.pages = []

        # map from paths to pages
        self.page_paths = {}
    
        if not os.path.isdir(self.archive_dir):
            raise ValueError("specified archive dir, %s, is not a directory" % self.archive_dir)

    def find(self):
        """Parse documents under root path"""

        for (dirpath, _, filenames) in os.walk('.'):
            # remove symlinks
            dirpath = os.path.normpath(dirpath)

            LOGGER.debug("entering %s" % dirpath)

            for filename in filenames:
                # file path relative to root path
                path = os.path.join(dirpath, filename)

                # attempt to parse file
                LOGGER.debug("parsing %s" % path)
                self.parse(path)
    
    def parse(self, path):
        """Attempt to parse the specified file as a Lotus object"""

        try:
            page = LotusPage(path=path, archive_dir=self.archive_dir, timezone=self.timezone, parser=self.parser)
            
            LOGGER.info("found page %s" % page)

            if page in self.pages:
                # this is a duplicate
                # get first occurrance
                original = self.pages[self.pages.index(page)]

                LOGGER.info("path %s is a duplicate of %s" % (page.path, original.path))
            else:
                self.pages.append(page)
            
            # map target path
            self.page_paths[page.path] = page

            return
        except PageInvalidException:
            # not a page
            pass

    def archive(self):
        """Remove duplicate URLs, attachments and images and save"""

        # running list of media file hashes and objects
        media_files = {}

        for page in self.pages:
            # map page paths to objects
            for unique_hash, path in page.urls.items():
                # replace path with object
                page.urls[unique_hash] = self.page_paths[path]

            # map attachment paths to objects
            for unique_hash, attachment in page.attachments.items():
                if unique_hash in media_files:
                    # duplicate; update object
                    LOGGER.info("attachment %s on %s is duplicate of %s" % (attachment, page, media_files[unique_hash]))
                    page.attachments[unique_hash] = media_files[unique_hash]
                else:
                    # add attachment to list
                    media_files[unique_hash] = attachment
            
            # map image paths to objects
            for unique_hash, image in page.images.items():
                if unique_hash in media_files:
                    # duplicate; update object
                    LOGGER.info("image %s on %s is duplicate of %s" % (image, page, media_files[unique_hash]))
                    page.images[unique_hash] = media_files[unique_hash]
                else:
                    # add image to list
                    media_files[unique_hash] = image

            # archive page
            page.archive()

        # archive deduplicated media files
        for media_file in media_files.values():
            media_file.archive()

    @property
    def media(self):
        for page in self.pages:
            yield from page.media