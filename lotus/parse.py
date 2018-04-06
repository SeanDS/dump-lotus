import os
import logging

from .objects import LotusPage, LotusMedia
from .exceptions import PageInvalidException, MediaInvalidException

LOGGER = logging.getLogger("parser")

class LotusParser(object):
    """Parses Lotus Notes documents"""

    def __init__(self, root_path):
        self.root_path = root_path

        self.pages = []
        self.media = []

        # unrecognised pages
        self.unrecognised = []

        # identical pages/media with different URLs (some weird Lotus Notes thing)
        self.page_path_aliases = {}
        self.media_path_aliases = {}
    
    def parse_all(self):
        """Parse documents under root path"""

        for (dirpath, _, filenames) in os.walk(self.root_path):
            LOGGER.debug("entering %s" % dirpath)

            for filename in filenames:
                # create full path
                path = os.path.join(dirpath, filename)

                LOGGER.debug("parsing %s" % filename)
                self.parse(path)
    
    def parse(self, path):
        """Attempt to parse the specified file as a Lotus object"""

        try:
            page = LotusPage(path)
            
            LOGGER.info("found page %s: %s" % (page.page, page.title))

            if page in self.pages:
                # this is a duplicate
                # get first occurrance's path
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
            media = LotusMedia(path)

            LOGGER.info("found media %s (%s)" % (media.lotus_id, media.mime_type))

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
    
    def mime_types(self):
        return set([media.mime_type for media in self.media])
