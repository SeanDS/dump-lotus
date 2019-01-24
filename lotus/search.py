import os
import shutil
import urllib
import glob
import logging
import urllib.parse
from lxml import etree
from bs4 import BeautifulSoup, UnicodeDammit

from .tools import working_directory
from .objects import LotusPage


class LotusXMLBuilder:
    def __init__(self, root_dir, root_contents_page, archive_dir, timezone=None, parser=None,
                 debug_log_file=None):        
        self.root_dir = root_dir
        self.root_contents_page = os.path.join(self.root_dir, root_contents_page)
        self.archive_dir = archive_dir
        self.timezone = timezone
        self.parser = parser

        # parsed pages
        self.pages = []
        # map of duplicate page paths to originals
        # (this also includes non-duplicate pages mapped to themselves)
        self.page_paths = {}
        # orphaned pages not found on contents but linked from other documents
        self.orphaned_pages = []

        self._setup_logging(debug_log_file)

    def _setup_logging(self, debug_log_file):
        # base logger
        self.logger = logging.getLogger("lotus")
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(name)-25s - %(levelname)-8s - %(message)s")

        # log INFO or higher to stdout
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)

        if debug_log_file is not None:
            # delete existing log file
            if os.path.exists(debug_log_file):
                os.remove(debug_log_file)
                
            # log DEBUG or higher to file
            file_handler = logging.FileHandler(debug_log_file)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)

    def _make_archive_dir(self):
        # delete everything in archive directories
        if os.path.exists(self.archive_dir):
            shutil.rmtree(self.archive_dir)

        # create archive directory structure
        os.mkdir(os.path.join(self.archive_dir))
        os.mkdir(os.path.join(self.archive_dir, 'meta'))
        os.mkdir(os.path.join(self.archive_dir, 'pages'))
        os.mkdir(os.path.join(self.archive_dir, 'pages', 'media'))

    @staticmethod
    def _absolute_path(path):
        return os.path.normpath(os.path.join(os.getcwd(), urllib.parse.unquote(path)))

    @property
    def authors(self):
        authors = set()
        for page in self.pages:
            authors.update(page.authors)
            for response in page.response_pages:
                authors.update(response.authors)
        
        return authors

    @property
    def author_archive_filepath(self):
        return os.path.join(self.archive_dir, "meta", "authors.xml")

    @property
    def categories(self):
        categories = set()
        for page in self.pages:
            categories.update(page.categories)
            for response in page.response_pages:
                categories.update(response.categories)
        
        return categories
    
    @property
    def category_archive_filepath(self):
        return os.path.join(self.archive_dir, "meta", "categories.xml")

    @property
    def _documents_relative_to_contents(self):
        with working_directory(self.root_dir):
            return glob.iglob("**/*?OpenDocument.html", recursive=True)

    def read(self):
        self._make_archive_dir()

        with working_directory(self.root_dir):
            with open(self.root_contents_page, "r") as obj:
                # read contents
                file_contents = obj.read()

                # parse file as HTML document, converting to unicode
                dammit = UnicodeDammit(file_contents, ['windows-1252'])
                document = BeautifulSoup(dammit.unicode_markup, self.parser)

            # search document for pages
            page_links = document.findAll("a", target="NotesView")

            # list of page dicts
            pages_info = []

            current_page = {}

            # running list of parsed urls
            parsed_urls = []

            for page_link in page_links:
                page_title = page_link.text
                
                if page_title.startswith("---------- Respond:"):
                    # link is a response
                    current_page["response_urls"].append(page_link["href"])
                else:
                    # jump over elements until we get to page number
                    page_number = page_link.next.next.next.next.next.next.next.next.next
                    # add previous page to list if this isn't the first page
                    if current_page:
                        pages_info.append(current_page)
                    # create new page dict
                    current_page = {"title": page_title,
                                    "number": page_number,
                                    "url": page_link["href"],
                                    "response_urls": []}
            
                # store decoded URL
                parsed_urls.append(urllib.parse.unquote(page_link["href"]))

            extra_pages = []

            # parse remaining pages not on the contents - this is necessary because there are
            # duplicate pages with different URLs... which is stupid :-/
            for page_link in self._documents_relative_to_contents:
                if page_link in parsed_urls:
                    # skip
                    continue
                
                extra_pages.append(page_link)                
                parsed_urls.append(page_link)

            # total number of pages found
            total = len(pages_info)
            total_extra = len(extra_pages)

            # loop over pages in reverse (to get chronological order)
            for count, page_info in enumerate(reversed(pages_info), 1):
                self.logger.info("%i / %i reading %s (p%s) with %i response(s)",
                                 count, total, page_info["title"], page_info["number"],
                                 len(page_info["response_urls"]))

                # convert paths to absolute, local links
                main_path = self._absolute_path(page_info["url"])
                response_paths = [self._absolute_path(response_path) for response_path in page_info["response_urls"]]

                # parse main document
                page = LotusPage(main_path, self.archive_dir, response_paths=response_paths,
                                 timezone=self.timezone, parser=self.parser)

                self.logger.info("parsed %s" % page)

                if page in self.pages:
                    # this is a duplicate
                    # get first occurrance
                    original = self.pages[self.pages.index(page)]

                    self.logger.warning("path %s is a duplicate of %s" % (page.path, original.path))
                else:
                    self.pages.append(page)

                    original = page
                
                # map target path
                self.logger.debug("mapping %s to %s" % (page.path, original))
                self.page_paths[page.path] = original

                # add response paths
                for response_page in page.response_pages:
                    if response_page.path in self.page_paths:
                        raise ValueError("a response has been found (%s) with the same path as a page" % response_page.path)

                    # map links in responses to original posts
                    self.page_paths[response_page.path] = original

            # loop over extra pages and find their duplicates
            for count, path in enumerate(extra_pages, 1):
                # convert path to full path
                path = os.path.join(self.root_dir, path)

                self.logger.info("%i / %i reading extra page %s", count, total_extra, path)

                # parse extra page
                page = LotusPage(path, self.archive_dir, timezone=self.timezone, parser=self.parser)

                self.logger.info("parsed %s" % page)

                if page in self.pages:
                    # this is a duplicate
                    # get first occurrance
                    original = self.pages[self.pages.index(page)]

                    self.logger.warning("path %s is a duplicate of %s" % (page.path, original.path))
                else:
                    # this is not a duplicate but is not on the contents page...
                    self.logger.info("adding page '%s' not found on contents page "
                                     "(no responses will be added)", page)
                    
                    self.orphaned_pages.append(page)

                    original = page
                
                # map target path
                self.logger.debug("mapping %s to %s" % (page.path, original))
                self.page_paths[page.path] = original

    def dump(self):
        self.read()

        self.logger.debug("Page paths:")
        self.logger.debug(self.page_paths)

        # running list of media file hashes and objects
        media_files = {}

        # running counts of pages, etc.
        npages = 0
        nimages = 0
        nattachments = 0
        nurls = 0
        nauthors = 0
        ncategories = 0

        # loop over pages first then orphans second so the orphans don't disrupt page number order
        for page in self.pages + self.orphaned_pages:
            npages += 1
            self.logger.debug("archiving %s" % page)

            # map page paths to objects
            for unique_hash, path in page.urls.items():
                nurls += 1
                # replace path with target, deduplicated object
                page.urls[unique_hash] = self.page_paths[path]

            # map attachment paths to objects
            for unique_hash, attachment in page.attachments.items():
                nattachments += 1
                if unique_hash in media_files:
                    # duplicate; update object
                    self.logger.info("attachment %s on %s is duplicate of %s" % (attachment, page, media_files[unique_hash]))
                    page.attachments[unique_hash] = media_files[unique_hash]
                else:
                    # add attachment to list
                    media_files[unique_hash] = attachment
            
            # map image paths to objects
            for unique_hash, image in page.images.items():
                nimages += 1
                if unique_hash in media_files:
                    # duplicate; update object
                    self.logger.info("image %s on %s is duplicate of %s" % (image, page, media_files[unique_hash]))
                    page.images[unique_hash] = media_files[unique_hash]
                else:
                    # add image to list
                    media_files[unique_hash] = image

            # archive page
            page.archive()

        # archive deduplicated media files
        for media_file in media_files.values():
            media_file.archive()
        
        # archive authors
        authors = etree.Element("authors")
        for author in self.authors:
            nauthors += 1
            etree.SubElement(authors, "author").text = etree.CDATA(author)
        tree = etree.ElementTree(authors)
        tree.write(self.author_archive_filepath, encoding="utf-8", xml_declaration=True)

        # archive categories
        categories = etree.Element("categories")
        for category in self.categories:
            ncategories += 1
            etree.SubElement(categories, "category").text = etree.CDATA(category)
        tree = etree.ElementTree(categories)
        tree.write(self.category_archive_filepath, encoding="utf-8", xml_declaration=True)

        self.logger.info("archived:")
        self.logger.info("\t%i pages (%i orphans)", npages, len(self.orphaned_pages))
        self.logger.info("\t%i media items (%i images, %i attachments)", nimages + nattachments, nimages, nattachments)
        self.logger.info("\t%i internal URLs", nurls)
        self.logger.info("\t%i authors", nauthors)
        self.logger.info("\t%i categories", ncategories)
