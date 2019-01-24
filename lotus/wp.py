import os
import logging
from random import randint
import datetime
import urllib.parse
import glob
import pytz
from lxml import etree

from .tools import working_directory, sanitize_title

class WordPressXMLWriter:
    # namespaces
    NSMAP = {"wp": "http://wordpress.org/export/1.2/",
             "dc": "http://purl.org/dc/elements/1.1/",
             "wfw": "http://wellformedweb.org/CommentAPI/",
             "content": "http://purl.org/rss/1.0/modules/content/",
             "excerpt": "http://wordpress.org/export/1.2/excerpt/"}

    WP_PUB_DATE_FORMAT = r"%a, %d %b %Y %H:%M:%S %z"
    WP_POST_DATE_FORMAT = r"%Y-%m-%d %H:%M:%S"
    WP_POST_DATE_GMT_FORMAT = r"%Y-%m-%d %H:%M:%S"

    def __init__(self, title, archive_dir, wp_file, site_id, base_network_url, base_url,
                 base_source_media_url, debug_log_file=None):
        if not base_url.endswith("/"):
            # required for joining URLs
            base_url += "/"

        if not base_network_url.endswith("/"):
            # required for joining URLs
            base_network_url += "/"

        if not base_source_media_url.endswith("/"):
            # required for joining URLs
            base_source_media_url += "/"

        self.title = title
        self.archive_dir = archive_dir
        self.wp_file = wp_file
        self.site_id = int(site_id)
        self.base_network_url = base_network_url
        self.base_url = base_url
        self.base_source_media_url = base_source_media_url

        self.added_post_ids = []
        # author display names -> ids
        self.added_author_map = {}
        self.last_author_id = 0
        self.last_comment_id = 0
        self.last_term_id = 0
        self.attachment_filenames = []
        self.image_filenames = []

        self.nposts = 0
        self.ncomments = 0
        self.nimages = 0
        self.nattachments = 0
        self.nurls = 0
        self.nauthors = 0
        self.ncategories = 0

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

    def _xml_streamer(self):
        # current time
        now = datetime.datetime.now(pytz.utc)

        document = etree.Element("rss", version="2.0", nsmap=self.NSMAP)
        channel = etree.SubElement(document, "channel")
        title = etree.SubElement(channel, "title")
        title.text = self.title
        link = etree.SubElement(channel, "link")
        link.text = self.base_url
        description = etree.SubElement(channel, "description")
        description.text = "Logbook"
        pubdate = etree.SubElement(channel, "pubDate")
        pubdate.text = now.strftime(self.WP_PUB_DATE_FORMAT)
        language = etree.SubElement(channel, "language")
        language.text = "en-GB"
        wxr_version = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}wxr_version")
        wxr_version.text = "1.2"
        base_site_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_site_url")
        base_site_url.text = self.base_network_url
        base_blog_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_blog_url")
        base_blog_url.text = self.base_url
        generator = etree.SubElement(channel, "generator")
        generator.text = "dump-lotus"

        return document, channel

    def unique_post_id(self):
        """Get unique post id"""
        candidate_post_id = max(self.added_post_ids) + 1

        while candidate_post_id in self.added_post_ids:
            candidate_post_id += 1
        
        self.added_post_ids.append(candidate_post_id)

        return candidate_post_id

    def unique_author_id(self):
        """Get unique author id"""
        self.last_author_id += 1
        return self.last_author_id

    def unique_comment_id(self):
        """Get unique comment id"""
        self.last_comment_id += 1
        return self.last_comment_id

    def unique_term_id(self):
        """Get unique term id"""
        self.last_term_id += 1
        return self.last_term_id

    @property
    def page_dir(self):
        return os.path.join(self.archive_dir, "pages")
    
    @property
    def meta_dir(self):
        return os.path.join(self.archive_dir, "meta")
    
    @property
    def base_media_url(self):
        return self.base_url + "wp-content/uploads/sites/" + str(self.site_id) + "/"

    @property
    def page_filenames(self):
        return glob.glob(self.page_dir + "/*.xml")

    @property
    def author_xml_path(self):
        return os.path.join(self.meta_dir, "authors.xml")

    @property
    def category_xml_path(self):
        return os.path.join(self.meta_dir, "categories.xml")

    def _post_xml_by_hash(self, unique_hash):
        path = os.path.join(self.page_dir, unique_hash + ".xml")

        return etree.parse(path).getroot()

    def _generate_post_id_hash_map(self):
        unique_hash_to_post_id = {}
        
        for path in self.page_filenames:
            # remove symlinks
            path = os.path.normpath(path)

            # parse XML
            page = etree.parse(path).getroot()

            # extract unique hash from filename
            unique_hash = os.path.basename(path).rstrip(".xml")

            # extract page number
            page_number_str = page.find("page").text
            try:
                page_number = int(page_number_str)
            except ValueError:
                # invalid page number, e.g. a float
                force_new = True
            else:
                force_new = False

            # assign a unique post id to this page
            post_id_clashes = []
            if page_number in self.added_post_ids or force_new:
                # post id clash
                post_id_clashes.append(unique_hash)
            else:
                self.added_post_ids.append(page_number)

                # store unique hash -> post id
                unique_hash_to_post_id[unique_hash] = page_number
            
            # deal with duplicates
            candidate_post_id = max(self.added_post_ids) + 1

            while post_id_clashes:
                while candidate_post_id in self.added_post_ids:
                    candidate_post_id += 1
                
                # get next clashing post
                unique_hash = post_id_clashes.pop(0)
                unique_hash_to_post_id[unique_hash] = candidate_post_id
                self.added_post_ids.append(candidate_post_id)

                self.logger.warning("assigned clashing page number %s (%s) to %i",
                                    page_number_str, page.find("title").text, candidate_post_id)

                candidate_post_id += 1

        return unique_hash_to_post_id

    def _generate_authors(self, channel):
        # create XML representing the site's authors and categories
        author_data = etree.parse(self.author_xml_path).getroot()

        for author in author_data:
            author_id = self.unique_author_id()

            # author display name
            author_display_name = author.text
            author_nicename = self.sanitize_author(author.text)
            
            # URL-friendly author name
            term_slug = self.author_term_name(author_nicename)

            term_id = self.unique_term_id()

            # terms have slug: ssl-alp-coauthor-[nicename]
            # and name: [display name]

            # author
            wp_author = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}author")
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_id").text = etree.CDATA(str(author_id))
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_login").text = etree.CDATA(author_nicename)
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_email").text = etree.CDATA("")
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_display_name").text = etree.CDATA(author_display_name)
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_first_name").text = etree.CDATA("")
            etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_last_name").text = etree.CDATA("")

            # coauthor term
            wp_coauthor = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}term")
            etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_id").text = etree.CDATA(str(term_id))
            etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_taxonomy").text = etree.CDATA("ssl_alp_coauthor")
            etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_slug").text = etree.CDATA(term_slug)
            etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_parent").text = etree.CDATA("")
            etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_name").text = etree.CDATA(author_display_name)

            self.added_author_map[author_display_name] = author_id

            self.nauthors += 1

    def _generate_categories(self, channel):
        # parse categories
        categories = etree.parse(self.category_xml_path).getroot()
        for category in categories:
            category_name = category.text
            category_nicename = sanitize_title(category_name)

            term_id = self.unique_term_id()

            wp_category = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}category")
            etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}term_id").text = str(term_id)
            etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_nicename").text = etree.CDATA(category_nicename)
            etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_parent").text = etree.CDATA("")
            etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}cat_name").text = etree.CDATA(category_name)

            self.ncategories += 1

    def _generate_attachment(self, attachment, channel, content, parent_post_id, first_author):
        # file path
        attachment_path = attachment.attrib["path"]
        
        # base filename
        attachment_filename = os.path.basename(attachment_path)

        # hash
        attachment_hash = attachment.text

        # file data
        filestats = os.stat(attachment_path)

        # make the creation time the modification time, which is set to the file's original creation time
        attachment_created = datetime.datetime.fromtimestamp(filestats.st_mtime)

        # create fake WordPress file path, to trick import to use the original modified date
        # YYYY/MM/filename.jpg
        root, ext = os.path.splitext(attachment_filename)
        fake_wp_file_path = attachment_created.strftime("%Y/%m/") + root + ext.lower()

        # guess new URL
        new_url = self.base_media_url + fake_wp_file_path

        # replace all href and src tags with new path
        content = content.replace("href=\"%s\"" % attachment_hash, "href=\"%s\"" % new_url)
        content = content.replace("src=\"%s\"" % attachment_hash, "src=\"%s\"" % new_url)

        if attachment_path in self.attachment_filenames:
            # skip adding, as this already exists
            return content
        else:
            self.attachment_filenames.append(attachment_path)

        # slug
        attachment_slug = sanitize_title(attachment_filename)

        # media URL
        media_url = self.base_source_media_url + attachment_filename

        # new post id
        attachment_post_id = self.unique_post_id()

        # create item
        attachment_item = etree.SubElement(channel, "item")

        # title
        etree.SubElement(attachment_item, "title").text = etree.CDATA(attachment_filename)
        # link
        etree.SubElement(attachment_item, "link").text = etree.CDATA(self.base_url + attachment_slug)
        # publication date
        etree.SubElement(attachment_item, "pubDate").text = attachment_created.strftime(self.WP_PUB_DATE_FORMAT)
        # creator (first author)
        etree.SubElement(attachment_item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
        # guid
        etree.SubElement(attachment_item, "guid", isPermaLink="false").text = etree.CDATA(media_url)
        # description
        etree.SubElement(attachment_item, "description").text = etree.CDATA("")
        # content
        etree.SubElement(attachment_item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA("")
        # excerpt
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
        # post id
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_id").text = str(attachment_post_id)
        # post date
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(attachment_created.strftime(self.WP_POST_DATE_FORMAT))
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(attachment_created.strftime(self.WP_POST_DATE_GMT_FORMAT))
        # statuses
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("closed")
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(attachment_slug)
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("inherit")
        # WP meta
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_parent").text = str(parent_post_id)
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("attachment")
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_password").text = ""
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"
        etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}attachment_url").text = etree.CDATA(media_url)
        media_post_meta = etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}postmeta")
        etree.SubElement(media_post_meta, "{http://wordpress.org/export/1.2/}meta_key").text = etree.CDATA("_wp_attached_file")
        etree.SubElement(media_post_meta, "{http://wordpress.org/export/1.2/}meta_value").text = etree.CDATA(fake_wp_file_path)

        self.nattachments += 1

        return content

    def _generate_image(self, image, channel, content, parent_post_id, first_author):
        # file path
        image_path = image.attrib["path"]
        
        # base filename
        image_filename = os.path.basename(image_path)

        # hash
        image_hash = image.text

        # file data
        filestats = os.stat(image_path)
        image_created = datetime.datetime.fromtimestamp(filestats.st_ctime)

        # create fake WordPress file path, to trick import to use the original modified date
        # YYYY/MM/filename.jpg
        root, ext = os.path.splitext(image_filename)
        fake_wp_file_path = image_created.strftime("%Y/%m/") + root + ext.lower()

        # guess new URL
        new_url = self.base_media_url + fake_wp_file_path

        # replace all href and src tags with new path
        content = content.replace("href=\"%s\"" % image_hash, "href=\"%s\"" % new_url)
        content = content.replace("src=\"%s\"" % image_hash, "src=\"%s\"" % new_url)

        if image_path in self.image_filenames:
            # skip adding, as this already exists
            return content
        else:
            self.image_filenames.append(image_path)

        # slug
        image_slug = sanitize_title(image_filename)

        # media URL
        media_url = self.base_source_media_url + image_filename

        # new post id
        image_post_id = self.unique_post_id()

        # create item
        image_item = etree.SubElement(channel, "item")

        # title
        etree.SubElement(image_item, "title").text = etree.CDATA(image_filename)
        # link
        etree.SubElement(image_item, "link").text = etree.CDATA(self.base_url + image_slug)
        # publication date
        etree.SubElement(image_item, "pubDate").text = image_created.strftime(self.WP_PUB_DATE_FORMAT)
        # creator (first author)
        etree.SubElement(image_item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
        # guid
        etree.SubElement(image_item, "guid", isPermaLink="false").text = etree.CDATA(media_url)
        # description
        etree.SubElement(image_item, "description").text = etree.CDATA("")
        # content
        etree.SubElement(image_item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA("")
        # excerpt
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
        # post id
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_id").text = str(image_post_id)
        # post date
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(image_created.strftime(self.WP_POST_DATE_FORMAT))
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(image_created.strftime(self.WP_POST_DATE_GMT_FORMAT))
        # statuses
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("closed")
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(image_slug)
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("inherit")
        # WP meta
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_parent").text = str(parent_post_id)
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("attachment")
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_password").text = ""
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"
        etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}attachment_url").text = etree.CDATA(media_url)
        image_post_meta = etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}postmeta")
        etree.SubElement(image_post_meta, "{http://wordpress.org/export/1.2/}meta_key").text = etree.CDATA("_wp_attached_file")
        etree.SubElement(image_post_meta, "{http://wordpress.org/export/1.2/}meta_value").text = etree.CDATA(fake_wp_file_path)

        self.nimages += 1

        return content

    def _generate_posts(self, channel):
        # page hashes and their corresponding unique post ids
        post_id_map = self._generate_post_id_hash_map()

        # generate posts
        for unique_hash, post_id in post_id_map.items():
            # load page
            post_xml = self._post_xml_by_hash(unique_hash)

            # main post
            self.logger.info("opening %s", unique_hash)
            self._generate_post(post_xml, channel, post_id, post_id_map)

    def _generate_post(self, post, channel, post_id, post_id_map):
        # create post XML element
        item = etree.SubElement(channel, "item")

        page_title = post.find("title").text
        # make slug from title
        slug = sanitize_title(page_title)
        # page number from Lotus Notes (not necessarily same on WordPress)
        original_page_number = post.find("page").text
        # creation date object
        created = datetime.datetime.fromtimestamp(int(post.find("created").text))

        # extract first author
        first_author_element = post.find("authors").find("author")
        
        if not hasattr(first_author_element, "text"):
            # skip
            self.logger.warning("skipped empty author post %s (lotus p%s, created %s)",
                                page_title, original_page_number, created)
            return

        first_author = self.sanitize_author(first_author_element.text)

        self.logger.info("adding %s (lotus p%s, created %s)", page_title, original_page_number,
                         created)

        # generate categories
        for category in post.find("categories"):
            category_name = category.text
            category_nicename = sanitize_title(category_name)
            etree.SubElement(item, "category", domain="category", nicename=category_nicename).text = etree.CDATA(category_name)
        
        # generate coauthors
        for author in post.find("authors"):
            author_name = author.text
            author_login = self.sanitize_author(author_name)
            author_term_name = self.author_term_name(author_login)
            etree.SubElement(item, "category", domain="ssl_alp_coauthor", nicename=author_term_name).text = etree.CDATA(author_name)

        # content
        try:
            content = post.find("content").text
        except:
            # for empty posts
            content = ""

        # replace cross references with proper URL
        for other_page_url in post.find("urls"):
            content = self.replace_url(content, other_page_url, post_id_map)

        # media
        for attachment in post.find("attachments"):
            content = self._generate_attachment(attachment, channel, content, post_id, first_author)

        # images
        for image in post.find("images"):
            content = self._generate_image(image, channel, content, post_id, first_author)

        # title
        etree.SubElement(item, "title").text = etree.CDATA(page_title)
        # URL
        etree.SubElement(item, "link").text = ""
        # publication date
        etree.SubElement(item, "pubDate").text = created.strftime(self.WP_PUB_DATE_FORMAT)
        # creator (first author)
        etree.SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
        # guid
        etree.SubElement(item, "guid", isPermaLink="false").text = self.base_url + "?p=" + str(post_id)
        # description
        etree.SubElement(item, "description").text = etree.CDATA("")
        # content
        etree.SubElement(item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA(content)
        # excerpt
        etree.SubElement(item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
        # post id
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_id").text = str(post_id)
        # post date
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(created.strftime(self.WP_POST_DATE_FORMAT))
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(created.strftime(self.WP_POST_DATE_GMT_FORMAT))
        # statuses
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("open")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(slug)
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("publish")
        # WP meta
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_parent").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("post")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_password").text = ""
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"

        self.nposts += 1

        # responses
        for response in post.find("responses"):
            self._generate_comment(response, post, item, channel, post_id, page_title, post_id_map)

    def _generate_comment(self, response, parent, item, channel, post_id, page_title, post_id_map):
        response_created = datetime.datetime.fromtimestamp(float(response.find("created").text))
        response_authors = response.find("authors")
        response_first_author_element = response_authors.find("author")

        if not hasattr(response_first_author_element, "text"):
            # skip
            self.logger.info("skipped empty author response created %s on page %s",
                             response_created, page_title)
            return

        response_first_author_display_name = response_first_author_element.text
        response_first_author_nicename = self.sanitize_author(response_first_author_display_name)
        response_first_author_id = self.added_author_map[response_first_author_display_name]

        self.logger.info("adding response by %s to %s", response_first_author_display_name, page_title)

        try:
            content = response.find("content").text
        except AttributeError:
            # for empty comments
            content = ""

        # replace cross references with proper URL
        for other_page_url in parent.find("urls"):
            content = self.replace_url(content, other_page_url, post_id_map)

        # media
        for attachment in parent.find("attachments"):
            content = self._generate_attachment(attachment, channel, content, post_id, response_first_author_nicename)

        # images
        for image in parent.find("images"):
            content = self._generate_image(image, channel, content, post_id, response_first_author_nicename)

        # comment id
        comment_id = self.unique_comment_id()

        response_author_display_names = [author.text for author in response_authors]

        if len(response_author_display_names) > 1:
            # edit content to include all authors
            full_author_list = ", ".join(response_author_display_names)
            content = "[Authors: %s]\n\n%s" % (full_author_list, content)

        # create item
        comment_item = etree.SubElement(item, "{http://wordpress.org/export/1.2/}comment")

        # comment id
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_id").text = str(comment_id)
        # author
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_author").text = etree.CDATA(response_first_author_display_name)
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_author_email").text = ""
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_author_url").text = ""
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_author_IP").text = ""
        # date
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_date").text = etree.CDATA(response_created.strftime(self.WP_POST_DATE_FORMAT))
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_date_gmt").text = etree.CDATA(response_created.strftime(self.WP_POST_DATE_GMT_FORMAT))
        # content
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_content").text = etree.CDATA(content)
        # other
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_approved").text = "1"
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_type").text = ""
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_parent").text = "0"
        # user id
        etree.SubElement(comment_item, "{http://wordpress.org/export/1.2/}comment_user_id").text = str(response_first_author_id)

        self.ncomments += 1

    def generate(self):
        # create XML streamer
        document, channel = self._xml_streamer()

        self._generate_authors(channel)
        self._generate_categories(channel)
        self._generate_posts(channel)

        with open(self.wp_file, "wb") as f:
            tree = etree.ElementTree(document)
            tree.write(f, pretty_print=True)

        self.logger.info("generated:")
        self.logger.info("\t%i posts", self.nposts)
        self.logger.info("\t%i media items (%i images, %i attachments)", self.nimages + self.nattachments, self.nimages, self.nattachments)
        self.logger.info("\t%i internal URLs", self.nurls)
        self.logger.info("\t%i authors", self.nauthors)
        self.logger.info("\t%i categories", self.ncategories)

    def replace_url(self, content, other_page_url, post_id_map):
        # hash to search for in content is not necessarily the same as the other hash because they are
        # deduplicated
        search_hash = other_page_url.text

        # unique hash of target
        other_page_hash = os.path.basename(other_page_url.attrib["path"]).rstrip(".xml")

        # new URL (must be fully qualified)
        crossref_url = self.base_url + "?p=" + str(post_id_map[other_page_hash])

        self.nurls += 1

        return content.replace("<a href=\"%s\"" % search_hash, "<a href=\"%s\"" % crossref_url)

    def sanitize_author(self, author_name):
        return sanitize_title(author_name)

    def author_term_name(self, author_nicename):
        return "ssl-alp-coauthor-" + author_nicename
