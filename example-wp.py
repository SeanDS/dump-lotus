from converters import xml_to_wp_xml

# archive directory
archive_dir = "/path/to/converted/xml/files"

# path to store WordPress XML file
wp_file = "/path/to/store/wordpress/xml/file.xml"

# blog site ID (get this from the WordPress network admin sites screen)
site_id = 22

# URL for main network site (the default site for a WordPress network installation), with trailing slash
base_network_url = "https://test.some-site.com/"

# URL for blog (with trailing slash)
base_url = "https://test.some-site.com/tmp3/"

# URL for directory containing all source media (WordPress will sideload media from this directory)
# This can be any web-accessible directory
base_source_media_url = "https://example.com/path/to/media/"