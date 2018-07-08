import os
import glob
import logging
import datetime
import pytz
from lxml import etree

from lotus.tools import (working_directory, WP_PUB_DATE_FORMAT, WP_POST_DATE_FORMAT,
                         WP_POST_DATE_GMT_FORMAT, sanitize_title)

# set up logger
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("lotus-parser")

# directory containing archived XML files
page_dir = "/home/sean/Workspace/pt/archive/pages"
media_dir = "/home/sean/Workspace/pt/archive/pages/media"
meta_dir = "/home/sean/Workspace/pt/archive/meta"

# file to write WordPress XML to
wp_file = "/home/sean/Workspace/pt/wp.xml"

# URL for site (with trailing slash)
BASE_URL = "http://example.com/"

# current time
now = datetime.datetime.now(pytz.utc)

# namespaces
NSMAP = {"wp": "http://wordpress.org/export/1.2/",
         "dc": "http://purl.org/dc/elements/1.1/",
         "wfw": "http://wellformedweb.org/CommentAPI/",
         "content": "http://purl.org/rss/1.0/modules/content/",
         "excerpt": "http://wordpress.org/export/1.2/excerpt/"}

# create XML streamer
rss = etree.Element("rss", version="2.0", nsmap=NSMAP)
channel = etree.SubElement(rss, "channel")
title = etree.SubElement(channel, "title")
title.text = "Prototype"
link = etree.SubElement(channel, "link")
link.text = "http://example.com"
description = etree.SubElement(channel, "description")
description.text = "Just another WordPress site"
pubdate = etree.SubElement(channel, "pubDate")
pubdate.text = now.strftime(WP_PUB_DATE_FORMAT)
language = etree.SubElement(channel, "language")
language.text = "en-GB"
wxr_version = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}wxr_version")
wxr_version.text = "1.2"
base_site_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_site_url")
base_site_url.text = "http://example.com"
base_blog_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_blog_url")
base_blog_url.text = "http://example.com"
generator = etree.SubElement(channel, "generator")
generator.text = "dump-lotus"

# authors and categories
with working_directory(meta_dir):
    # parse authors
    authors = etree.parse("authors.xml").getroot()
    for author_id, author in enumerate(authors, 1):
        wp_author = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}author")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_id").text = str(author_id)
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_login").text = etree.CDATA(author.text)
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_email").text = etree.CDATA("")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_display_name").text = etree.CDATA("")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_first_name").text = etree.CDATA("")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_last_name").text = etree.CDATA("")

    # parse categories
    categories = etree.parse("categories.xml").getroot()
    for category_id, category in enumerate(categories, 1):
        category_name = category.text

        wp_category = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}category")
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}term_id").text = str(category_id)
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_nicename").text = etree.CDATA(sanitize_title(category_name))
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_parent").text = etree.CDATA("")
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}cat_name").text = etree.CDATA(category_name)

# pages
with working_directory(page_dir):
    for filename in glob.glob(page_dir + "/*.xml"):
        # remove symlinks
        filename = os.path.normpath(filename)

        print(filename)

        # parse
        page = etree.parse(filename).getroot()

        post_id = page.find("page").text
        created = datetime.datetime.fromtimestamp(float(page.find("created").text))

        # create item
        item = etree.SubElement(channel, "item")

        # title
        etree.SubElement(item, "title").text = page.find("title").text
        # URL
        etree.SubElement(item, "link").text = ""
        # publication date
        etree.SubElement(item, "pubDate").text = created.strftime(WP_PUB_DATE_FORMAT)
        # creator (first author)
        etree.SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(page.find("authors").find("author").text)
        # guid
        etree.SubElement(item, "guid", isPermaLink="False").text = BASE_URL + "?p=" + post_id
        # description
        etree.SubElement(item, "description").text = ""
        # content
        etree.SubElement(item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA(page.find("content").text)
        # excerpt
        etree.SubElement(item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
        # post id
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_id").text = post_id
        # post date
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(created.strftime(WP_POST_DATE_FORMAT))
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(created.strftime(WP_POST_DATE_GMT_FORMAT))
        # statuses
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("open")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("publish")
        # WP meta
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_parent").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("post")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_password").text = ""
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"
        # categories
        for category in page.find("categories"):
            category_name = category.text
            category_nicename = sanitize_title(category_name)
            etree.SubElement(item, "category", domain="category", nicename=category_nicename).text = etree.CDATA(category_name)
        # coauthors
        ## TODO

# attachments
## TODO

with open(wp_file, "wb") as f:
    tree = etree.ElementTree(rss)
    tree.write(f, pretty_print=True)