import os
import logging
import contextlib
import pytz

from .objects import LotusPage, LotusMedia
from .exceptions import PageInvalidException, MediaInvalidException

LOGGER = logging.getLogger("parser")

class LotusParser(object):
    """Parses Lotus Notes documents"""

    def __init__(self, root_path, timezone=None, parser="html.parser"):
        if timezone is None:
            # assume UTC
            timezone = pytz.UTC

        self.root_path = root_path
        self.timezone = timezone
        self.parser = parser

        self.pages = []
        self.media = []

        # unrecognised pages
        self.unrecognised = []

        # identical pages/media with different URLs (some weird Lotus Notes thing)
        self.page_path_aliases = {}
        self.media_path_aliases = {}
    
    def parse_all(self):
        """Parse documents under root path"""

        with self.working_directory(self.root_path):
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
            page = LotusPage(path=path, timezone=self.timezone, parser=self.parser)
            
            LOGGER.info("found page %s: %s" % (page.page, page.title))

            if page in self.pages:
                # this is a duplicate
                # get first occurrance
                first_page = self.pages[self.pages.index(page)]

                LOGGER.info("page is a duplicate of %s" % first_page.path)

                # add alias
                self.page_path_aliases[page.path] = first_page.path
            else:
                self.pages.append(page)
            
            return
        except PageInvalidException:
            # not a page
            pass
        
        try:
            media = LotusMedia(path=path)

            LOGGER.info("found media %s (%s)" % (media.path, media.mime_type))

            if media in self.media:
                # this is a duplicate
                # get first occurrance's path
                first_media = self.media[self.media.index(media)]

                LOGGER.info("media is a duplicate of %s" % first_media.path)
                
                # add alias
                self.media_path_aliases[media.path] = first_media.path
            else:
                self.media.append(media)

            return
        except MediaInvalidException:
            # not media
            pass

        LOGGER.debug("item %s not recognised" % path)
        self.unrecognised.append(path)
    
    @property
    def mime_types(self):
        return set([media.mime_type for media in self.media])

    @property
    def authors(self):
        return set([author for page in self.pages for author in page.authors])

    @property    
    def categories(self):
        return set([category for page in self.pages for category in page.categories])
    
    @property
    def internal_urls(self):
        return set([url for page in self.pages for url in page.internal_urls])

    @property
    def internal_attachments(self):
        return set([attachment for page in self.pages for attachment in page.internal_attachments])

    @property
    def internal_images(self):
        return set([image for page in self.pages for image in page.internal_images])
    
    @contextlib.contextmanager
    def working_directory(self, path):
        # previous directory
        previous_path = os.getcwd()

        # change directory to new path
        os.chdir(path)
        
        # hand control to context
        yield
        
        # change directory back to previous path
        os.chdir(previous_path)