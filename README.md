# Dump Lotus
Export AEI Lotus Notes documents into Python objects, where they can be further exported into generic XML
documents and WordPress import XML files.

Note: this is a converter library for a specific Lotus Notes application implementation. It may be useful
for importing other Lotus Notes based applications into WordPress but it will require tweaking.

## Requirements
System packages:
  - `python3`
  - `wget`

Python packages:
  - `binaryornot`,
  - `lxml`,
  - `beautifulsoup4`,
  - `pytz`,
  - `python-magic`

You also need write access to the web server being used to host the WordPress site. Part of the import process
requires some files on the web server to be edited.

## Preparing Lotus Notes logbook for scraping
1. Change the dates of all Lotus Notes posts that have post dates in the future. While the presence of such
   posts does not break the importer, it does lead to images attached to the post being given upload dates
   in the future and posts not appearing on the website by default.
2. Change any page numbers with non-integer numbers, e.g. "955.5", to whole itegers. These disrupt the internal
   numbering system in WordPress and can lead to incorrectly linked imported posts.

## Scraping Lotus Notes pages
1. Generate a web backup of your Lotus Notes application.
  - This requires your Lotus Notes administrator.
2. (Optional) If your backup is protected by Lotus cookie-based web authentication, obtain the
    `DomAuthSessId` cookie contents from your browser after logging in to the web backup.
      - You can read cookie values for example in Firefox with the [Cookiebro](https://nodetics.com/cookiebro/)
        web extension.
      - Place the cookie domain (first column) and value (last column) into the provided `cookies.txt` file.
2. Run `scrape.sh`, having set the appropraite target and domain.
  - This will generate a tree of files and directories containing your posts and attached media.
  - The tree can be large (many gigabytes) if you have many notes.
  - You can manually browse this tree using a web browser by opening an HTML file beginning `Contents`,
    or by opening a particular page HTML file. The embedded media files should all work, as `wget`,
    used by `scrape.sh`, updates these to point to local copies. Non-ASCII text may not be displayed
    correctly by the browser due to the documents' lack of character encoding settings, but the
    underlying HTML files should be properly formatted if viewed in UTF-8 mode.
3. (Optional) Delete files with names beginning `Contents` and `Outline Page`.
  - These are matched by the scraper because they link to relevant posts.
  - They are not required for the Python parser, and since each file can be many megabytes of HTML,
    they slow down the parsing operation.

Extra notes:
  - The Lotus Notes web client does not correctly display content given its character encoding. Some
    documents may contain broken characters that will confuse the parser. In addition to this, some
    attached files with special characters may not be downloaded correctly, as the Lotus Notes web interface
    does not correctly translate these URLs. You may, for some URLs, get a `Http Status Code: 400` message
    explaining `Http request contains a malformed escape sequence`, despite the attachment working in the
    full Lotus Notes client. In this case, it is suggested to:
      1. Manually download the file from Lotus Notes. For this you must first find the corresponding page in
         Lotus Notes by opening up the HTML file that is mentioned in the error message either when running
         `scrape.sh` or after running `prototype-write.py` (see below). Find the title or page number and
         search for it on Lotus Notes. Find the file that is causing the problem, then download it and
         manually place it in the directory where it is supposed to be in your scraped archive.
      2. IMPORTANT: you must also edit the `href` path of the image in the scraped HTML document to point
         to the file you downloaded. This is because, when `wget` cannot download a file, it replaces the
         relative URL with the fully qualified version (i.e. including the `http://.../...` part). This is
         not what we want, so you must remove the first part. Use the paths of other (working) images in
         the HTML file as a guide for what the start of the URL should look like.
  - Lotus Notes also does not strip out invisible, invalid or control characters entered into it. If
    someone has copy-and-pasted text from e.g. Microsoft Word into Lotus Notes, it may contain junk
    characters which are invalid. These cause the XML parser to throw an error. If you get an error when
    running `prototype-write.py`, you must edit the file that contained the error and remove the junk
    characters manually.

## Creating WordPress site
1. Create a new blog for the posts to be imported into on the WordPress Network admin screen.
2. Activate the [Academic Labbook Plugin](https://alp.attackllama.com/) on
   the network admin plugins page.
3. Activate the `Alpine` theme on the network admin themes page.
4. Change the theme on the target blog appearance page to `Alpine`.
5. Install the "Wordpress Importer" plugin using the WordPress network admin plugin screen. This is
   published by "wordpressdotorg".
6. (Optional) Delete the default post and comment on the target blog.

## Setting up Python project
1. Run `setup.py` in this directory to install the dependencies, either directly with Python or via pip,
   e.g.: `pip3 install --user -e .`

## Building XML files
1. Create empty directories with the following structure:
  - /meta
  - /pages
  - /pages/media
2. Edit `prototype-write.py`, setting the paths to the above directories, and setting the URL where the
   media will be hosted temporarily.
3. Run `prototype-write.py`.

## Building WordPress import XML file
1. Edit `wp-write.py`, setting the paths to the archive directories set above. Also set the SITE_ID of the
   WordPress site you wish to import to - this can be found in the Network Admin Sites screen by hovering over
   the link for the relevant site. The site ID is the number at the end, after "?id=".
   You must also specify a web URL which points to a directory containing all of the media created by
   `prototype-write.py`. This is accessed by WordPress during the import process, so it needs to be a URL
   accessible to the server on which WordPress is running (it can be on the same server).
2. Run `wp-write.py`.

## Moving the media to a web directory
1. Move the media produced in the media directory defined above to the temporary media URL directory.

## Importing XML file into WordPress
1. Activate the WordPress Importer plugin with `wp plugin activate wordpress-importer --path=/path/to/wordpress/base/directory --url=https://url/for/blog/`.
2. Open `wp-config.php` in the WordPress network base directory and add
   `define('ALLOW_UNFILTERED_UPLOADS', true);` to allow unfiltered uploads temporarily
3. Edit `wordpress-importer.php` in `wp-content/plugins/wordpress-importer` within the WordPress root directory.
   Comment out the block starting:
`if ( isset( $headers['content-length'] ) && $filesize != $headers['content-length'] ) {`, down to the next `}` (about 4 lines). You can use `/*` and `*/` to do this. The reason for commenting out this code is because it causes failures
  in the import script when the file sizes between source and destination servers are inconsistent - this seems to
  affect text file attachments.
4. Run the import with `wp import --path=/path/to/wordpress/base/directory --url=https://url/for/blog/ /path/to/wp.xml --authors=create --user=your-username --debug`, replacing `your-username` with the username of the network admin account
  you created the WordPress network site with.
5. Remove `define('ALLOW_UNFILTERED_UPLOADS', true);` from `wp-config.php`.
6. Remove edits to `wordpress-importer`
7. Rebuild cross-references:
  - Open an interactive PHP shell by running `wp shell --path=/path/to/wp/installation --url=https://example.com/blog-name/ --debug`
  - Type `global $ssl_alp;`
  - Type `$ssl_alp->references->rebuild_references();`
  - Wait until complete (will take many minutes). Upon completion the command will return `NULL`.
8. Rebuild term counts: `wp term recount ssl_alp_coauthor --path=/path/to/wp/installation --url=https://example.com/blog-name/`
9. Disable the WordPress Importer plugin.
10. Delete the media hosted on the temporary URL (WordPress has now copied this to its own directory).

## Users
Lotus Notes users are created by the import script but not automatically added to the blog. You **must**
add every user to the blog using the WordPress network admin screen, otherwise the author list on the blog
will not be complete and it will not be possible to merge the imported Lotus Notes users with WordPress
accounts.

### Adding users to the blog
Once the site is imported, you probably want to merge the users created by the import script with real network
users. This must be done from the WordPress network admin screen.

1. Add all users that exist in the Lotus Notes logbook to the new blog (using the network admin). Skip sending
   the confirmation email otherwise the user will not be added until they click a link in their email.
2. Add all WordPress users that will have the Lotus Notes users merged to the blog too.
3. Use the network admin page to individually merge the Lotus Notes account into its corresponding WordPress
   acount. This is done by clicking "Delete" under the Lotus Notes user account on the network admin user list,
   then choosing to attribute their posts to the target WordPress user.

## Lotus Notes quirks
Some Lotus Notes quirks that must be kept in mind by the user:
  - Page numbers are not unique. Different documents can happily have the same page numbers.
  - Page numbers aren't necessarily integer. Numbers like `123.5` are allowed, so don't assume they are
    integer.
  - Links between one page and another, and between pages and attached/embedded media, are not necessarily
    uniquely defined for each file. The same file (page, attachment, etc.) can have different URLs. The
    parser de-duplicates these and maintains lists of aliases.

And some consequences for the parser:
  - Page numbers are stored as strings
  - Pages are considered unique by a function of their title, page number, authors, categories and creation
    date. If two pages have these exact values, but different content, they will be considered the same
    and only one copy will be saved.

## Credits
Sean Leavey  
<github@attackllama.com>