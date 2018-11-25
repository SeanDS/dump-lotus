import os
import contextlib
import re

@contextlib.contextmanager
def working_directory(path):
    # previous directory
    previous_path = os.getcwd()

    # change directory to new path
    os.chdir(path)
    
    # hand control to context
    yield
    
    # change directory back to previous path
    os.chdir(previous_path)

def sanitize_title(text):
    """Approximate clone of WordPress's sanitize_title_with_dashes
    https://github.com/WordPress/WordPress/blob/be6aa715fedb64fba8a848706e050f489c56df82/wp-includes/formatting.php#L2204
    """
    text = re.sub(r"<[^>]*?>", "", text)
    text = re.sub(r"%([a-fA-F0-9][a-fA-F0-9])", r"---\1---", text)
    text = text.strip("%")
    text = re.sub(r"---([a-fA-F0-9][a-fA-F0-9])---", r"%\1", text)
    text = text.lower()
    text = re.sub(r"&.+?;", "", text)
    text = text.replace(".", "-")
    text = re.sub(r"[^%a-z0-9 _-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip()

    return text