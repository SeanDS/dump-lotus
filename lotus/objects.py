import os.path
import datetime
import urllib
from bs4 import BeautifulSoup
import magic

from .exceptions import PageInvalidException, MediaInvalidException

class LotusObject(object):
    def __init__(self, path):
        self.path = path

    def normalise_rel_path(self, rel_path):
        """Get path relative to working directory where the specified path is relative to this object"""

        # add relative path onto this object's directory
        norm_rel_path = os.path.join(os.path.dirname(self.path), rel_path)

        # get rid of symlinks
        norm_rel_path = os.path.normpath(norm_rel_path)

        return norm_rel_path

class LotusPage(LotusObject):
    def __init__(self, timezone, parser, *args, **kwargs):
        super(LotusPage, self).__init__(*args, **kwargs)

        self.timezone = timezone
        self.parser = parser

        # list of URLs to other pages found in the page content
        self.internal_urls = []

        # list of URLs to embedded attachments
        self.internal_attachments = []

        # list of URLs to embedded images
        self.internal_images = []

        # page content
        self.title = None
        self.page = None
        self.authors = []
        self.categories = []
        self.created = None
        self.content = None

        self.parse()
    
    def parse(self):
        """Parse file at path as a page"""

        with open(self.path, 'r') as obj:
            # parse file as HTML document
            try:
                document = BeautifulSoup(obj, self.parser)
            except UnicodeDecodeError as e:
                # document can't be decoded to unicode (usually indicates that this is binary)
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
            
            # check for cross-referencing links
            if element.name == "a" and element.has_attr("href"):
                if element["href"].endswith("OpenDocument.html"):
                    # this link is an internal cross-reference
                    self.extract_internal_url(element)
                elif "$FILE" in element["href"]:
                    # this is an attached file
                    self.extract_internal_attachment(element)

            # check for embedded images
            if element.name == "img" and element.has_attr("src") and "Body" in element["src"]:
                # this is an embedded image
                self.extract_internal_image(element)
            
            # add element to document content
            content.append(str(element))

        # prettify content
        content = BeautifulSoup("".join(content), self.parser)
        self.content = content.prettify()
    
    def extract_internal_url(self, element):
        page = self.full_url_path(element["href"])

        self.internal_urls.append(page)

    def extract_internal_attachment(self, element):
        attachment = self.full_url_path(element["href"])

        self.internal_attachments.append(attachment)

    def extract_internal_image(self, element):
        image = self.full_url_path(element["src"])

        self.internal_images.append(image)

    def full_url_path(self, path):
        """Return full path for URL, decoding any entities"""

        # decode
        path = urllib.parse.unquote(path)

        # path relative to root
        path = self.normalise_rel_path(path)

        return path

    def __eq__(self, other):
        """Equality comparison operator
        
        Compares Lotus IDs
        """

        return self.title == other.title and self.page == other.page and \
               self.authors == other.authors and self.categories == other.categories and \
               self.created == other.created
    
    def __hash__(self):
        return hash((self.title, self.page, frozenset(self.authors), frozenset(self.categories), self.created))

class LotusMedia(LotusObject):
    def __init__(self, *args, **kwargs):
        super(LotusMedia, self).__init__(*args, **kwargs)
        
        # media data
        self.mime_type = None

        self.parse()
    
    def parse(self):
        """Parse file at path as media"""

        self.mime_type = magic.from_file(self.path, mime=True)
    
    def __eq__(self, other):
        """Equality comparison operator
        
        Compares Lotus IDs
        """

        return self.path == other.path and self.mime_type == other.mime_type
    
    def __hash__(self):
        return hash(self.path)