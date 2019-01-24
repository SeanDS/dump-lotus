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
    running a script derived from `example-lotus.py`, you must edit the file that contained the error and remove the junk
    characters manually.

## Creating WordPress site
1. Create a new blog for the posts to be imported into on the WordPress Network admin screen.
2. Activate the [Academic Labbook Plugin](https://alp.attackllama.com/) on
   the network admin plugins page.
3. Upload and activate the `Alpine` theme on the network admin themes page.
4. Go to the Academic Labbook Plugin tools page for the target blog and run:
   - "Change Settings"
   - "Convert User Roles"
5. Also change the theme on the target blog's admin area to `Alpine`.
6. Install the "Wordpress Importer" plugin using the WordPress network admin plugin screen. This is
   published by "wordpressdotorg".
7. (Optional) Delete the default post and comment on the target blog.
8. Install `WP-CLI` on the web server. Some commands later in this guide require it.

## Setting up Python project
1. The `setup.py` file in this directory installs the required dependencies, either directly with Python or via `pip`, e.g. with `pip3 install -e .`.

## Building XML files
1. Copy `example-lotus.py.dist` to another location, e.g. `prototype-lotus.py`.
2. Edit `prototype-lotus.py`, setting the relevant paths as specified by the comments in the file,
   including the path to the scraped data above.
3. Run `prototype-write.py` with Python 3: `python3 prototype-lotus.py`.

The script will generate individual XML files for each post and its responses and media, deduplicate
downloaded pages, and replace URLs to pages to local files instead.

## Building WordPress import XML file
1. Copy `example-wp.py.dist` to another location, e.g. `prototype-wp.py`.
2. Edit `prototype-wp.py`, setting the paths to the archive directories set above. You must also
   set site id of the WordPress site you wish to import to (the one you created above) - this number
   can be found in the Network Admin Sites screen by hovering over the link for the relevant site.
   The site ID is the number at the end, after "?id=".
   You must also specify a web URL which points to a web-accessible directory containing all of
   the media created by `prototype-lotus.py`. That means you either have to copy the contents of
   `archive/pages/media` to a web server, or allow web access to this directory on your machine. This directory is accessed by WordPress during the import process, so it needs to be accessible to the
   server on which WordPress is running (it can be on the same server). Note that if this is not
   correctly set up, the importer will not fail, but will not import the media properly - so be
   careful.
2. Run `prototype-wp.py` with Python 3: `python3 prototype-wp.py`.

This script will generate a single WordPress XML file which contains the whole site data. This will
next be imported into WordPress.

## Moving the media to a web directory
1. If you have not done so alread, move the media produced in the media directory defined above to
   the temporary media URL directory as specified in `prototype-wp.py`.

## Importing XML file into WordPress
1. Activate the WordPress Importer plugin on the target site with `wp plugin activate wordpress-importer --path=/path/to/wordpress/base/directory --url=https://url/for/blog/`.
2. Open `wp-config.php` in the WordPress installation directory and add
   `define('ALLOW_UNFILTERED_UPLOADS', true);` to allow unfiltered uploads temporarily.
3. Edit `wordpress-importer.php` in `wp-content/plugins/wordpress-importer` within the WordPress root directory. Comment out the block starting:
`if ( isset( $headers['content-length'] ) && $filesize != $headers['content-length'] ) {`, down to the next `}` (about 4 lines). You can use `/*` and `*/` to do this. The reason for commenting out this code is because it causes failures
  in the import script when the file sizes between source and destination servers are inconsistent - this seems to
  affect text file attachments.
4. Run the import with `sudo -u www-data bash -c 'wp import --path=/path/to/wordpress/base/directory --url=https://url/for/blog/ /path/to/wp.xml --authors=create --user=your-username --debug'`, replacing
   `www-data` with the name of the web server user and `your-username` with the username of the
   network admin account you created the WordPress network site with. This runs the import as the
   web user, which is necessary to avoid potential issues with file and directory permissions.
   The command will take a long time to run on big sites. For some unknown reasons, it also sometimes
   stops the import mid-way through, and appears to be finished when it actually is not. In this case,
   simply rerun the command - it will skip over the posts it has already imported. Close to the end,
   the command goes blank and appears to have frozen, and this can last many minutes or even hours.
   The importer is recounting items in the database and should not be interrupted. Once the command
   finishes you can move on.
5. Remove `define('ALLOW_UNFILTERED_UPLOADS', true);` from `wp-config.php`.
6. Remove edits to `wordpress-importer`.
7. Rebuild cross-references and term counts:
  - Open an interactive PHP shell by running `sudo -u www-data bash -c 'wp shell --path=/path/to/wp/installation --url=https://example.com/blog-name/ --debug'`
  - Type `global $ssl_alp;` then enter
  - Type `$ssl_alp->references->rebuild_references();` then enter
  - Wait until complete (will take many minutes). Upon completion the command will return `NULL`.
  - Exit the shell with `exit`.
  - Type: `sudo -u www-data bash -c 'wp term recount ssl_alp_coauthor --path=/path/to/wp/installation --url=https://example.com/blog-name/'` to recount coauthor posts.
  - Wait until complete. This shouldn't take long.
8. Disable the WordPress Importer plugin.
9. Install the [Update Comments Count](https://wordpress.org/plugins/update-comments-count/) plugin
   and run the tool to update the comments. For some reason, comment counts are usually wrong after
   the import. This tool only needs to be run once, and the plugin can be deleted afterwards.
10. Delete the media hosted on the temporary URL (WordPress has now copied this to its own directory).

## Users
Users are created by the import script, but these users are only added to each blog (e.g. prototype).
For users that are members of many sites, it is desirable to merge the various users created across
the network into one user.

Manual method for users without many posts:

1. Ensure the account you wish to use for the person is present *on the network admin user screen*.
   This means you should either:
    - Pick an existing network account to use,
    - Create a new network user account,
    - Or use e.g. an LDAP plugin to create an authenticated user.
   The account *must* exist, and *must* be a *network* user (i.e. present on the network user page)
   before proceeding. This account is referred to as the "master" account.
2. Add the master account to a blog where the person has posts, by going to the blog's user admin
   page and using "Add existing user" to find and add the master account.
3. From the *network admin user screen*, find the *blog user account* created by the import process
   that is to have its posts merged into the master account, and click "Delete".
4. On the next page, you will be asked "What should be done with the content owned by [xxx]?". Under
   the site, you should select "Attribute all content to" and choose the master account created
   above.
5. Click "Confirm Deletion". This will take a long time (many minutes) for users with lots of posts.

Alternatively, the process can be achieved with WP-CLI, which is better for users with many posts
where there is a risk the HTTP request might timeout. This must be done in two parts as WP-CLI
does not allow users to be deleted from the network with their posts reassigned at the same time.

1. Follow steps 1 and 2 above.
2. Look up the user ID of the master user, e.g. by hovering over the user URL in the network user
   list.
3. In a terminal on the web server, run `wp user delete [username] --reassign=[master-user-id] --url=https://example.com/blog-name/`
   and press enter. This will reassign the posts of `[username]` on the blog to the master user.
4. Delete the now unused blog user from the whole network by running `wp user delete [username] --network`.
   You will be asked for confirmation; type "y" for yes.

## Credits
Sean Leavey
<github@attackllama.com>
