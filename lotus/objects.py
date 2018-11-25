import sys
import os.path
import logging
import abc
import datetime
import hashlib
import urllib.parse
import re
import shutil
import pytz

from binaryornot.check import is_binary
from lxml import etree
from bs4 import BeautifulSoup, UnicodeDammit
import magic

from .exceptions import PageInvalidException, MediaInvalidException

LOGGER = logging.getLogger("lotus")

def path_hash(path):
    return hashlib.md5(path.encode('utf-8')).hexdigest()


class LotusObject(object, metaclass=abc.ABCMeta):
    def __init__(self, path, archive_dir):
        self.path = path
        self.base_archive_dir = archive_dir

        # check object archive dir exists
        if not os.path.isdir(self.archive_dir):
            raise ValueError("archive directory %s doesn't exist" % self.archive_dir)

        # parse object
        self.parse()

    def normalise_rel_path(self, rel_path):
        """Get path relative to working directory where the specified path is relative to this object"""

        # add relative path onto this object's directory
        norm_rel_path = os.path.join(os.path.dirname(self.path), rel_path)

        # get rid of symlinks
        norm_rel_path = os.path.normpath(norm_rel_path)

        return norm_rel_path

    @abc.abstractmethod
    def parse(self):
        return NotImplemented

    @abc.abstractmethod
    def archive(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def archive_path(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def archive_dir(self):
        return NotImplemented

    def __repr__(self):
        return str(self)


class LotusPage(LotusObject):
    def __init__(self, *args, timezone=None, parser=None, response_paths=None, **kwargs):
        if timezone is None:
            # assume UTC
            timezone = pytz.UTC
        
        if parser is None:
            parser = "html.parser"

        self.timezone = timezone
        self.parser = parser
        
        if response_paths is None:
            response_paths = []
        
        self.response_paths = list(response_paths)
        self.response_pages = []

        # page content
        self.title = None
        self.page = None
        self.authors = []
        self.categories = []
        self.created = None
        self.content = None
        self.urls = {}
        self.attachments = {}
        self.images = {}

        # fields
        self._hash_filename = None

        super().__init__(*args, **kwargs)

    def parse(self):
        """Parse file at path as a page"""

        # check if file can be parsed
        if is_binary(self.path):
            raise PageInvalidException()

        with open(self.path, 'r') as obj:
            try:
                # read contents
                file_contents = obj.read()

                # parse file as HTML document, converting to unicode
                dammit = UnicodeDammit(file_contents, ['windows-1252'])
                document = BeautifulSoup(dammit.unicode_markup, self.parser)
            except UnicodeDecodeError as e:
                raise PageInvalidException(e)

        # document should say "Logbook Entry" in a centered div
        logbook_entry_txt = document.find("div", align="center")

        if logbook_entry_txt is None:
            raise PageInvalidException("couldn't find logbook description")

        description = logbook_entry_txt.b.font.text

        # check description reads "Logbook Entry"
        if description is None:
            raise PageInvalidException("couldn't find logbook description field")
        elif description != "Logbook Entry":
            raise PageInvalidException("document description doesn't read \"Logbook Entry\"")

        # if we got this far, extract some metadata
        # extract title, page number, etc. from first table
        meta_table = document.find("table", width="100%", border="1")
        self.parse_table_meta(meta_table)

        # extract content
        # this is anything after the table
        self.parse_content(meta_table.next_siblings)

        # parse responses
        for response_path in self.response_paths:
            response = self.__class__(response_path, self.base_archive_dir, timezone=self.timezone,
                                      parser=self.parser)
            self.response_pages.append(response)

            # add data to parent
            self.images = {**response.images, **self.images}
            self.attachments = {**response.attachments, **self.attachments}
            self.urls = {**response.urls, **self.urls}

    def parse_table_meta(self, table):
        if table is None:
            raise PageInvalidException("invalid table tag")

        # everything in this table is contained in a single tr
        container = table.find("tr")

        # first column contains page number, created and modified dates
        first_column = container.find("td", bgcolor="#EFEFEF", width="1%")
        
        # page number field
        page_number_field = first_column.find("font", size="2")
        # page number is next sibling
        # NOTE: not necessarily integer!
        self.page = page_number_field.next_sibling.text

        # ignore created/modified dates as these are not fully qualified (get date elsewhere)

        # second column contains title, author, categories and date
        second_column = first_column.next_sibling

        # data is all contained in font tags
        font_tags = second_column.find_all("font", size="2")

        # page title
        self.title = font_tags[1].text

        # page author(s)
        authors = font_tags[3].text

        # split authors by commas
        self.authors = [author.strip() for author in authors.split(",") if author != ""]

        # page categories
        categories = font_tags[5].text

        # split categories by commas
        self.categories = [category.strip() for category in categories.split(",") if category != ""]

        # diary date
        date_str = font_tags[7].text

        # parse date
        date_obj = datetime.datetime.strptime(date_str, "%m/%d/%Y")

        # set its timezone
        date_obj.replace(tzinfo=self.timezone)

        # set time to midday
        #self.created = date_obj + datetime.timedelta(hours=12)
        self.created = date_obj
    
    def parse_content(self, elements):
        """Parse specified elements as the page content"""
        
        # empty page content
        lines = []

        for element in elements:
            if element.name == "a" and element.text == "top" and element.has_attr("href") and element["href"].endswith("#top"):
                # skip link to top
                continue

            self.parse_element(element)
            # add elements to document content
            lines.append(str(element))

        self.content = "".join(lines)
    
    def parse_element(self, element):
        """Parse element"""

        self.extract_references(element)

        if hasattr(element, 'children'):
            for child in element.children:
                self.parse_element(child)

    def extract_references(self, element):
        """Find page or media links in element"""

        if not hasattr(element, 'contents'):
            # this is not a tag
            return

        # check for cross-referencing links
        if element.name == "a" and element.has_attr("href"):
            if element["href"].endswith("OpenDocument"):
                # URL on the scraped domain but not scraped
                LOGGER.warning("cross-referenced URL not matched: %s", element["href"])
            elif element["href"].endswith("OpenDocument.html"):
                # replace this internal link
                self.extract_cross_reference(element)
            elif "$FILE" in element["href"]:
                # replace this attached file
                self.extract_attachment(element)
        # check for embedded images
        elif element.name == "img" and element.has_attr("src"):
            # replace this embedded image
            self.extract_image(element)

    def extract_cross_reference(self, element):
        # get path relative to root
        path = self.full_url_path(element["href"])

        # generate unique id
        key = path_hash(path)

        # replace URL with unique ID
        element["href"] = key

        self.urls[key] = path

    def extract_attachment(self, element):
        # get path relative to root
        path = self.full_url_path(element["href"])

        try:
            media = LotusMedia(created=self.created, path=path, archive_dir=self.archive_dir)
        except MediaInvalidException:
            # not attachment
            return

        # replace URL with unique ID
        element["href"] = media.file_hash

        LOGGER.debug("found attachment %s" % media)
        self.attachments[media.file_hash] = media

    def extract_image(self, element):
        # get path relative to root
        path = self.full_url_path(element["src"])

        try:
            media = LotusMedia(created=self.created, path=path, archive_dir=self.archive_dir)
        except MediaInvalidException:
            # not image
            return

        # replace URL with unique ID
        element["src"] = media.file_hash

        LOGGER.debug("found image %s" % media)
        self.images[media.file_hash] = media

    def full_url_path(self, path):
        """Return full path for URL, decoding any entities"""

        # decode
        path = urllib.parse.unquote(path)

        # path relative to root
        path = self.normalise_rel_path(path)

        return path

    def archive(self):
        """Archive page"""

        LOGGER.info("archiving page '%s' (%s)" % (self.title, self.path))

        # create XML tree
        page = etree.Element("page")

        # add metadata
        etree.SubElement(page, "title").text = etree.CDATA(self.title)
        etree.SubElement(page, "page").text = etree.CDATA(self.page)
        etree.SubElement(page, "created").text = str(round(self.created.timestamp()))

        # add authors
        authors = etree.SubElement(page, "authors")

        for author in self.authors:
            # decode entities
            author = urllib.parse.unquote(author)
            etree.SubElement(authors, "author").text = etree.CDATA(author)

        # add categories
        categories = etree.SubElement(page, "categories")

        for category in self.categories:
            # decode entities
            category = urllib.parse.unquote(category)
            etree.SubElement(categories, "category").text = etree.CDATA(category)

        # add encoded content
        etree.SubElement(page, "content").text = etree.CDATA(self.content)

        # add attachments
        attachments = etree.SubElement(page, "attachments")

        for unique_hash, attachment in self.attachments.items():
            etree.SubElement(attachments, "attachment", path=attachment.archive_path).text = unique_hash

        # add images
        images = etree.SubElement(page, "images")

        for unique_hash, image in self.images.items():
            etree.SubElement(images, "image", path=image.archive_path).text = unique_hash

        # add urls
        urls = etree.SubElement(page, "urls")

        for unique_hash, other_page in self.urls.items():
            if other_page is None:
                # skip not found page
                continue

            etree.SubElement(urls, "url", path=other_page.archive_path).text = unique_hash

        # add responses
        responses = etree.SubElement(page, "responses")

        for response_page in self.response_pages:
            response = etree.SubElement(responses, "response")

            # add metadata
            etree.SubElement(response, "created").text = str(round(response_page.created.timestamp()))

            # add authors
            response_authors = etree.SubElement(response, "authors")

            for author in response_page.authors:
                etree.SubElement(response_authors, "author").text = etree.CDATA(author)

            # add encoded content
            etree.SubElement(response, "content").text = etree.CDATA(response_page.content)

        # save pretty version
        tree = etree.ElementTree(page)
        tree.write(self.archive_path, encoding="utf-8", xml_declaration=True)

        LOGGER.debug("wrote page '%s' to %s", self.title, self.archive_path)

    @property
    def archive_path(self):
        return os.path.join(self.archive_dir, self.hash_filename)

    @property
    def hash_filename(self):
        if self._hash_filename is None:
            # unique hash of this object
            # can't just use hash(self) as filename as this is sometimes negative and not stable between
            # kernel instances
            #unique_hash = path_hash(self.path)
            unique_hash = hashlib.md5(str(hash(self)).encode('utf-8')).hexdigest()

            # XML filename
            self._hash_filename = "%s.xml" % unique_hash
        
        return self._hash_filename

    @property
    def archive_dir(self):
        return os.path.join(self.base_archive_dir, "pages")

    @property
    def media(self):
        yield from self.attachments
        yield from self.images

    def __str__(self):
        return self.title

    def __eq__(self, other):
        """Equality comparison operator"""
        #return self.title == other.title and self.page == other.page and \
        #       self.authors == other.authors and self.categories == other.categories and \
        #       self.created == other.created
        return hash(self) == hash(other)
    
    def __hash__(self):
        return hash((self.title, frozenset(self.authors), frozenset(self.categories), str(self.created)))


class LotusMedia(LotusObject):
    def __init__(self, created, *args, **kwargs):        
        # media data
        self.mime_type = None

        # archive path
        self._archive_path = None

        # date
        self.created = created

        # unique hash of file contents
        self._file_hash = None

        super(LotusMedia, self).__init__(*args, **kwargs)
    
    def parse(self):
        """Parse file at path as media"""

        LOGGER.debug("getting mime type")
        self.mime_type = magic.from_file(self.path, mime=True)
        
        # force file hash to be computed
        _ = self.file_hash

    @property
    def file_hash(self):
        if self._file_hash is None:
            LOGGER.debug("computing MD5 hash")

            md5 = hashlib.md5()

            with open(self.path, 'rb') as obj:
                while True:
                    data = obj.read(1048576)

                    if not data:
                        # end of file
                        break
                    
                    md5.update(data)
                
            self._file_hash = md5.hexdigest()
        
        return self._file_hash

    @property
    def hash_filename(self):
        _, ext = os.path.splitext(self.sanitised_filename)
        return self.file_hash + ext.lower()

    def archive(self):
        """Archive media file"""

        LOGGER.info("archiving media '%s' (%s)" % (self.file_hash, self.path))

        # copy file to archive
        shutil.copyfile(self.path, self.archive_path)

        # modification timestamp, in seconds
        mod_timestamp = round(self.created.timestamp())

        # set modification and access times
        os.utime(self.archive_path, times=(mod_timestamp, mod_timestamp))

    @property
    def archive_path(self):
        #if self._archive_path is None:
        #    # append hash to start to try to make unique
        #    filename = self.file_hash[:10] + "_" + self.sanitised_filename
        #
        #    # first path attempt
        #    first_filename = os.path.join(self.archive_dir, filename)
        #    root, ext = os.path.splitext(first_filename)
        #    path = root + ext
        #
        #    count = 1
        #
        #    while os.path.isfile(path):
        #        path = root + str(count) + ext
        #        count += 1
        #    
        #    self._archive_path = path
        #
        #return self._archive_path
        return os.path.join(self.archive_dir, self.hash_filename)

    @property
    def sanitised_filename(self):
        """Sanitised filename
        
        This works the same way as WordPress's filename sanitiser; see
        https://codex.wordpress.org/Function_Reference/sanitize_file_name.

        This is NOT guaranteed to be unique. Use self.archive_path for a unique file path.
        """

        # get filename from path
        filename = os.path.basename(self.path)

        # find Lotus Notes extension
        match = re.search(r"FieldElemFormat=(\w+)", filename)

        if match is not None:
            file_extension = match.group(1)
        else:
            file_extension = ""
        
        # get rid of extra Lotus Notes junk if present
        filename = filename.replace('OpenElement', '')
        filename = filename.replace('FieldElemFormat=' + file_extension, '')

        # add extension
        if file_extension:
            filename += "." + file_extension
        
        # characters to remove
        remove_chars = ["?", "[", "]", "/", "\\", "=", "<", ">", ":", ";", ",", "'", "\"", "&", "$", "#", "*", "(", ")", "|", "~", "`", "!", "{", "}", "%", "+", chr(0)]

        # not sure what this is doing, but it causes an error :-/
        #filename = re.sub(r'#\x{00a0}#siu', ' ', filename)

        for c in remove_chars:
            filename = filename.replace(c, '')
        
        filename = filename.replace('%20', '-')
        filename = filename.replace('+', '-')
        filename = re.sub(r'[\r\n\t -]+', '-', filename)
        # remove leading or trailing special characters
        filename = filename.strip('.-_')

        # skip unnamed file check (where e.g. "exe" becomes "unnamed-file.exe")
        # and other file extension stuff

        return filename

    @property
    def archive_dir(self):
        return os.path.join(self.base_archive_dir, "media")

    def __str__(self):
        return "%s (%s)" % (self.sanitised_filename, self.mime_type)

    def __eq__(self, other):
        """Equality comparison operator"""

        return self.path == other.path and self.mime_type == other.mime_type
    
    def __hash__(self):
        # use original path
        return hash(self.path)
