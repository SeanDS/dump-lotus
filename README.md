# Dump Lotus
Get rid of Lotus Notes! Export Lotus Notes documents into Python objects,
where they can be further exported into generic XML documents.

## Requirements
System packages:
  - `python3`
  - `wget`

Python packages:
  - `pytz`
  - `python-magic`

## Instructions
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
4. Run the Python parser.
  - You can use the example script, or create your own.

Extra notes:
  - The Lotus Notes web client does not correctly display content given its character encoding. Some
    documents may contain broken characters that will confuse the parser. In addition to this, some
    attached files with special characters may not be downloaded correctly, as the Lotus Notes web interface
    does not correctly translate these URLs. You may, for some URLs, get a `Http Status Code: 400` message
    explaining `Http request contains a malformed escape sequence`, despite the attachment working in the
    full Lotus Notes client. In this case, it is suggested to:
      - Manually fix these characters
      - Manually download these files via the client
    Then, because of the behaviour of `wget`, you must also find any URLs that reference this
    URL and change from from absolute form back to relative (the `convert-links` flag is used, which is
    helpful for this application, except when files are not downloaded; then they are converted to absolute
    URLs).

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

## Inserting data into WordPress
There is also a set of classes to interface with WordPress via `WP-CLI`.

### Instructions
1. Create WordPress users manually.
  - This step is not automated as users may already exist, have different names or the users associated with
    Lotus Notes pages may not be part of the new site.
  - The users are mapped to WordPress users using the `user_map` dict supplied later.

## Credits
Sean Leavey  
<github@attackllama.com>