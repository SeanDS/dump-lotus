import sys
import os.path
import logging
import abc
import datetime
import hashlib
import urllib
import re
import shutil
from binaryornot.check import is_binary
from lxml import etree
from bs4 import BeautifulSoup, UnicodeDammit
import magic

from .exceptions import PageInvalidException, MediaInvalidException

LOGGER = logging.getLogger("lotus-object")

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
    def __init__(self, timezone, parser, *args, **kwargs):
        self.timezone = timezone
        self.parser = parser

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
    
        super(LotusPage, self).__init__(*args, **kwargs)

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
            raise PageInvalidException("countn't find logbook description field")
        elif description != "Logbook Entry":
            raise PageInvalidException("document description doesn't read \"Logbook Entry\"")

        # if we got this far, extract some metadata
        # extract title, page number, etc. from first table
        meta_table = document.find("table", width="100%", border="1")
        self.parse_table_meta(meta_table)

        # extract content
        # this is anything after the table
        self.parse_content(meta_table.next_siblings)

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
        self.created = date_obj + datetime.timedelta(hours=12)
    
    def parse_content(self, elements):
        """Parse specified elements as the page content"""

        # elements to ignore
        ignore_elements = ["script"]
        
        # empty page content
        content = []

        for element in elements:
            if element.name in ignore_elements:
                # skip
                continue
            elif element.name == "a" and element.text == "top" and element.has_attr("href") and element["href"].endswith("#top"):
                # ignore link to top
                # e.g. <a href="bd348c3ef391266bc125748f00501d0f%3FOpenDocument.html#top"><font size="1">top</font></a>
                continue
            elif element.name == "a" and element.has_attr("name") and element["name"] == "top":
                # ignore weird top links
                # <a name="top"></a>
                continue
                            
            # look for links, attachments, images
            element = self.extract_references(element)
            
            # add element to document content
            content.append(str(element))

        self.content = content
    
    def extract_references(self, element):
        """Find page or media links in element"""

        if not hasattr(element, 'contents'):
            # this is not a tag
            return element

        # check for cross-referencing links
        if element.name == "a" and element.has_attr("href"):
            if element["href"].endswith("OpenDocument.html"):
                # replace this internal link
                element = self.extract_cross_reference(element)
            elif "$FILE" in element["href"]:
                # replace this attached file
                element = self.extract_attachment(element)
        # check for embedded images
        elif element.name == "img" and element.has_attr("src") and "Body" in element["src"]:
            # replace this embedded image
            element = self.extract_image(element)
        
        return element

    def extract_cross_reference(self, element):
        # get path relative to root
        path = self.full_url_path(element["href"])

        # generate unique id
        key = path_hash(path)

        # replace URL with unique ID
        element["href"] = key

        self.urls[key] = path

        return element

    def extract_attachment(self, element):
        # get path relative to root
        path = self.full_url_path(element["href"])

        try:
            media = LotusMedia(path=path, archive_dir=self.archive_dir)
        except MediaInvalidException:
            # not attachment
            return element

        # replace URL with unique ID
        element["href"] = media.file_hash

        LOGGER.info("found attachment %s" % media)
        self.attachments[media.file_hash] = media

        return element

    def extract_image(self, element):
        # get path relative to root
        path = self.full_url_path(element["src"])

        try:
            media = LotusMedia(path=path, archive_dir=self.archive_dir)
        except MediaInvalidException:
            # not image
            return element

        # replace URL with unique ID
        element["src"] = media.file_hash

        LOGGER.info("found image %s" % media)
        self.images[media.file_hash] = media

        return element

    def full_url_path(self, path):
        """Return full path for URL, decoding any entities"""

        # decode
        path = urllib.parse.unquote(path)

        # path relative to root
        path = self.normalise_rel_path(path)

        return path

    def archive(self):
        """Archive page"""

        # create XML tree
        page = etree.Element("page")

        # add metadata
        etree.SubElement(page, "title").text = etree.CDATA(self.title)
        etree.SubElement(page, "page").text = etree.CDATA(self.page)
        etree.SubElement(page, "created").text = self.created.isoformat()

        # add authors
        authors = etree.SubElement(page, "authors")

        for author in self.authors:
            etree.SubElement(authors, "author").text = etree.CDATA(author)

        # add categories
        categories = etree.SubElement(page, "categories")

        for category in self.categories:
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

        # save pretty version
        tree = etree.ElementTree(page)
        tree.write(self.archive_path, encoding="utf-8", xml_declaration=True)

    @property
    def archive_path(self):
        # unique hash of this object
        # can't just use hash(self) as filename as this is sometimes negative and not stable between
        # kernel instances
        unique_hash = path_hash(self.path)

        # XML filename
        filename = "%s.xml" % unique_hash

        return os.path.join(self.archive_dir, filename)

    @property
    def archive_dir(self):
        return os.path.join(self.base_archive_dir, "pages")

    @property
    def media(self):
        yield from self.attachments.values()
        yield from self.images.values()

    def __str__(self):
        return self.title

    def __eq__(self, other):
        """Equality comparison operator
        
        Compares Lotus IDs
        """

        return self.title == other.title and self.page == other.page and \
               self.authors == other.authors and self.categories == other.categories and \
               self.created == other.created
    
    def __hash__(self):
        return (self.title, self.page, frozenset(self.authors), frozenset(self.categories), self.created)

class LotusMedia(LotusObject):
    def __init__(self, *args, **kwargs):        
        # media data
        self.mime_type = None

        # archive path
        self._archive_path = None

        # unique hash of file contents
        self.file_hash = None

        super(LotusMedia, self).__init__(*args, **kwargs)
    
    def parse(self):
        """Parse file at path as media"""

        LOGGER.debug("getting mime type")
        self.mime_type = magic.from_file(self.path, mime=True)
        
        self.compute_file_hash()

    def compute_file_hash(self):
        LOGGER.debug("computing MD5 hash")

        md5 = hashlib.md5()

        with open(self.path, 'rb') as obj:
            while True:
                data = obj.read(1048576)

                if not data:
                    # end of file
                    break
                
                md5.update(data)
            
        self.file_hash = md5.hexdigest()

    def archive(self):
        """Archive media file"""

        # copy file to archive
        shutil.copyfile(self.path, self.archive_path)

    @property
    def archive_path(self):
        # first path attempt
        path = os.path.join(self.archive_dir, self.sanitised_filename)

        count = 1

        while os.path.isfile(path):
            path = os.path.join(self.archive_dir, self.sanitised_filename) + str(count)

            count += 1
        
        return path

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
        match = re.search("FieldElemFormat=(\w+)", filename)

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
