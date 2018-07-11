import os
import glob
import logging
import datetime
from random import randint
import pytz
from lxml import etree

from lotus.tools import (working_directory, WP_PUB_DATE_FORMAT, WP_POST_DATE_FORMAT,
                         WP_POST_DATE_GMT_FORMAT, sanitize_title)

# post IDs added so far
ADDED_POST_IDS = []

# media filenames added so far
ATTACHMENT_FILENAMES = []
IMAGE_FILENAMES = []

def unique_post_id():
    """Get unique post id"""
    post_id = str(1e5 + randint(1, 1e5))

    while post_id in ADDED_POST_IDS:
        post_id = str(1e5 + randint(1, 1e5))
    
    ADDED_POST_IDS.append(post_id)

    return post_id

# set up logger
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("lotus-parser")

# directory containing archived XML files
page_dir = "/home/sean/Workspace/pt/archive/pages"
media_dir = "/home/sean/Workspace/pt/archive/pages/media"
meta_dir = "/home/sean/Workspace/pt/archive/meta"

# file to write WordPress XML to
wp_file = "/home/sean/Workspace/pt/wp.xml"

# site ID
SITE_ID = 20

# URL for site (with trailing slash)
BASE_URL = "https://test.attackllama.com/tmp2/"
BASE_NETWORK_URL = "https://test.attackllama.com/"
BASE_MEDIA_URL = BASE_URL + "wp-content/uploads/sites/" + str(SITE_ID) + "/"

# URL for directory containing all media
BASE_SOURCE_MEDIA_URL = "https://cottage.attackllama.com/tmp/media/"

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
link.text = BASE_URL
description = etree.SubElement(channel, "description")
description.text = "Just another WordPress site"
pubdate = etree.SubElement(channel, "pubDate")
pubdate.text = now.strftime(WP_PUB_DATE_FORMAT)
language = etree.SubElement(channel, "language")
language.text = "en-GB"
wxr_version = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}wxr_version")
wxr_version.text = "1.2"
base_site_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_site_url")
base_site_url.text = BASE_NETWORK_URL
base_blog_url = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}base_blog_url")
base_blog_url.text = BASE_URL
generator = etree.SubElement(channel, "generator")
generator.text = "dump-lotus"

# term ID
next_term_id = 1

# get page filenames
filenames = list(glob.glob(page_dir + "/*.xml"))
unique_hash_to_post_id = {}

# get post IDs out of files
with working_directory(page_dir):
    for path in filenames:
        # remove symlinks
        path = os.path.normpath(path)

        # parse
        page = etree.parse(path).getroot()

        # store unique hash -> post id
        unique_hash_to_post_id[os.path.basename(path).rstrip(".xml")] = page.find("page").text

# authors and categories
with working_directory(meta_dir):
    # parse authors
    authors = etree.parse("authors.xml").getroot()
    for author_id, author in enumerate(authors, 1):
        # author display name
        author_name = author.text
        
        # URL-friendly author name
        author_slug = sanitize_title(author_name)

        # author
        wp_author = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}author")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_id").text = etree.CDATA(str(author_id))
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_login").text = etree.CDATA(author_name)
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_email").text = etree.CDATA("")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_display_name").text = etree.CDATA(author_name)
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_first_name").text = etree.CDATA("")
        etree.SubElement(wp_author, "{http://wordpress.org/export/1.2/}author_last_name").text = etree.CDATA("")

        # coauthor term
        wp_coauthor = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}term")
        etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_id").text = etree.CDATA(str(next_term_id))
        etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_taxonomy").text = etree.CDATA("ssl_alp_coauthor")
        etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_slug").text = etree.CDATA(author_slug)
        etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_parent").text = etree.CDATA("")
        etree.SubElement(wp_coauthor, "{http://wordpress.org/export/1.2/}term_name").text = etree.CDATA(author_name)

        next_term_id += 1

    # parse categories
    categories = etree.parse("categories.xml").getroot()
    for category in categories:
        category_name = category.text

        wp_category = etree.SubElement(channel, "{http://wordpress.org/export/1.2/}category")
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}term_id").text = str(next_term_id)
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_nicename").text = etree.CDATA(sanitize_title(category_name))
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}category_parent").text = etree.CDATA("")
        etree.SubElement(wp_category, "{http://wordpress.org/export/1.2/}cat_name").text = etree.CDATA(category_name)

        next_term_id += 1

# pages
with working_directory(page_dir):
    for path in filenames:
        # remove symlinks
        path = os.path.normpath(path)

        print(path)

        # parse
        page = etree.parse(path).getroot()

        post_id = page.find("page").text
        created = datetime.datetime.fromtimestamp(float(page.find("created").text))

        page_title = page.find("title").text
        slug = sanitize_title(page_title)

        author_elements = page.find("authors").find("author")
        if not hasattr(author_elements, 'text'):
            # skip
            print("Skipped empty author post %s", path)
            continue

        first_author = author_elements.text

        # page content
        content = page.find("content").text

        # add post ID to list
        ADDED_POST_IDS.append(post_id)

        # create post item
        item = etree.SubElement(channel, "item")

        # categories
        for category in page.find("categories"):
            category_name = category.text
            category_nicename = sanitize_title(category_name)
            etree.SubElement(item, "category", domain="category", nicename=category_nicename).text = etree.CDATA(category_name)
        # coauthors
        for author in page.find("authors"):
            author_name = author.text
            author_nicename = sanitize_title(author_name)
            etree.SubElement(item, "category", domain="ssl_alp_coauthor", nicename=author_nicename).text = etree.CDATA(author_name)

        # replace cross references with proper URL
        for other_page_url in page.find("urls"):
            # hash to search for in content is not necessarily the same as the other hash because they are
            # deduplicated
            search_hash = other_page_url.text

            # actual filename of target (without extension)
            other_page_filename = os.path.basename(other_page_url.attrib["path"]).rstrip(".xml")

            # new URL (must be fully qualified)
            crossref_url = BASE_URL + "?p=" + unique_hash_to_post_id[other_page_filename]

            content = content.replace("<a href=\"%s\"" % search_hash, "<a href=\"%s\"" % crossref_url)

        # media
        for attachment in page.find("attachments"):
            # file path
            attachment_path = attachment.attrib["path"]
            
            # base filename
            attachment_filename = os.path.basename(attachment_path)

            # hash
            attachment_hash = attachment.text

            # file data
            filestats = os.stat(attachment_path)
            attachment_created = datetime.datetime.fromtimestamp(filestats.st_ctime)

            # create fake WordPress file path, to trick import to use the original modified date
            # YYYY/MM/filename.jpg
            root, ext = os.path.splitext(attachment_filename)
            fake_wp_file_path = attachment_created.strftime("%Y/%m/") + root + ext.lower()

            # guess new URL
            new_url = BASE_MEDIA_URL + fake_wp_file_path

            # replace all href and src tags with new path
            content = content.replace("href=\"%s\"" % attachment_hash, "href=\"%s\"" % new_url)
            content = content.replace("src=\"%s\"" % attachment_hash, "src=\"%s\"" % new_url)

            if attachment_path in ATTACHMENT_FILENAMES:
                # skip adding, as this already exists
                continue
            else:
                ATTACHMENT_FILENAMES.append(attachment_path)

            # slug
            attachment_slug = sanitize_title(attachment_filename)

            # media URL
            media_url = BASE_SOURCE_MEDIA_URL + attachment_filename

            # new post id
            attachment_post_id = unique_post_id()

            # create item
            attachment_item = etree.SubElement(channel, "item")

            # title
            etree.SubElement(attachment_item, "title").text = etree.CDATA(attachment_filename)
            # link
            etree.SubElement(attachment_item, "link").text = etree.CDATA(BASE_URL + attachment_slug)
            # publication date
            etree.SubElement(attachment_item, "pubDate").text = attachment_created.strftime(WP_PUB_DATE_FORMAT)
            # creator (first author)
            etree.SubElement(attachment_item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
            # guid
            etree.SubElement(attachment_item, "guid", isPermaLink="false").text = etree.CDATA(media_url)
            # description
            etree.SubElement(attachment_item, "description").text = etree.CDATA("")
            # content
            etree.SubElement(attachment_item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA(media_url)
            # excerpt
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
            # post id
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_id").text = attachment_post_id
            # post date
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(attachment_created.strftime(WP_POST_DATE_FORMAT))
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(attachment_created.strftime(WP_POST_DATE_GMT_FORMAT))
            # statuses
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("closed")
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(attachment_slug)
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("inherit")
            # WP meta
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_parent").text = post_id
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("attachment")
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}post_password").text = ""
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"
            etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}attachment_url").text = etree.CDATA(media_url)
            media_post_meta = etree.SubElement(attachment_item, "{http://wordpress.org/export/1.2/}postmeta")
            etree.SubElement(media_post_meta, "{http://wordpress.org/export/1.2/}meta_key").text = etree.CDATA("_wp_attached_file")
            etree.SubElement(media_post_meta, "{http://wordpress.org/export/1.2/}meta_value").text = etree.CDATA(fake_wp_file_path)

        for image in page.find("images"):
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
            new_url = BASE_MEDIA_URL + fake_wp_file_path

            # replace all href and src tags with new path
            content = content.replace("href=\"%s\"" % image_hash, "href=\"%s\"" % new_url)
            content = content.replace("src=\"%s\"" % image_hash, "src=\"%s\"" % new_url)

            if image_path in IMAGE_FILENAMES:
                # skip adding, as this already exists
                continue
            else:
                IMAGE_FILENAMES.append(image_path)

            # slug
            image_slug = sanitize_title(image_filename)

            # media URL
            media_url = BASE_SOURCE_MEDIA_URL + image_filename

            # new post id
            image_post_id = unique_post_id()

            # create item
            image_item = etree.SubElement(channel, "item")

            # title
            etree.SubElement(image_item, "title").text = etree.CDATA(image_filename)
            # link
            etree.SubElement(image_item, "link").text = etree.CDATA(BASE_URL + image_slug)
            # publication date
            etree.SubElement(image_item, "pubDate").text = image_created.strftime(WP_PUB_DATE_FORMAT)
            # creator (first author)
            etree.SubElement(image_item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
            # guid
            etree.SubElement(image_item, "guid", isPermaLink="false").text = etree.CDATA(media_url)
            # description
            etree.SubElement(image_item, "description").text = etree.CDATA("")
            # content
            etree.SubElement(image_item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA(media_url)
            # excerpt
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/excerpt/}encoded").text = etree.CDATA("")
            # post id
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_id").text = image_post_id
            # post date
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_date").text = etree.CDATA(image_created.strftime(WP_POST_DATE_FORMAT))
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_date_gmt").text = etree.CDATA(image_created.strftime(WP_POST_DATE_GMT_FORMAT))
            # statuses
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}comment_status").text = etree.CDATA("closed")
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}ping_status").text = etree.CDATA("closed")
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(image_slug)
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("inherit")
            # WP meta
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_parent").text = post_id
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("attachment")
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}post_password").text = ""
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"
            etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}attachment_url").text = etree.CDATA(media_url)
            image_post_meta = etree.SubElement(image_item, "{http://wordpress.org/export/1.2/}postmeta")
            etree.SubElement(image_post_meta, "{http://wordpress.org/export/1.2/}meta_key").text = etree.CDATA("_wp_attached_file")
            etree.SubElement(image_post_meta, "{http://wordpress.org/export/1.2/}meta_value").text = etree.CDATA(fake_wp_file_path)

        # post

        # title
        etree.SubElement(item, "title").text = etree.CDATA(page_title)
        # URL
        etree.SubElement(item, "link").text = ""
        # publication date
        etree.SubElement(item, "pubDate").text = created.strftime(WP_PUB_DATE_FORMAT)
        # creator (first author)
        etree.SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = etree.CDATA(first_author)
        # guid
        etree.SubElement(item, "guid", isPermaLink="false").text = BASE_URL + "?p=" + post_id
        # description
        etree.SubElement(item, "description").text = etree.CDATA("")
        # content
        etree.SubElement(item, "{http://purl.org/rss/1.0/modules/content/}encoded").text = etree.CDATA(content)
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
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_name").text = etree.CDATA(slug)
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}status").text = etree.CDATA("publish")
        # WP meta
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_parent").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}menu_order").text = "0"
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_type").text = etree.CDATA("post")
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}post_password").text = ""
        etree.SubElement(item, "{http://wordpress.org/export/1.2/}is_sticky").text = "0"

with open(wp_file, "wb") as f:
    tree = etree.ElementTree(rss)
    tree.write(f, pretty_print=True)