# Lotus Dump
Export Lotus Notes documents into Python objects

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