import re
import sys
import unicodedata

import requests
import bs4
import sqlite3
from tqdm import tqdm


def search_physical(sess: requests.Session, tq, book: str):
    tqdm.write(f"Search: {book!r}")
    # tq.set_description(f"Search: {book!r}")
    r = sess.get(
        "https://catalog.lacountylibrary.org/client/en_US/default/search/results",
        params=[
            ("qu", book),
            ("qf", "ITYPE\tMaterial+Type\t1:BOOK\tBook"),
            ("qf", "LANGUAGE\tLanguage\tENG\tEnglish"),
            ("qf", "LIBRARY\tLibrary\t1:330\tCulver City Julian Dixon Library"),
        ],
    )
    r.raise_for_status()
    return r.text


def search_ebook(sess: requests.Session, tq, book: str):
    tqdm.write(f"Search: {book!r}")
    # tq.set_description(f"Search: {book!r}")
    r = sess.get(
        "https://catalog.lacountylibrary.org/client/en_US/default/search/results",
        params=[
            ("qu", book),
            ("te", "ERC_ST_DEFAULT"),
        ],
    )
    r.raise_for_status()
    return r.text


def print_search_results(html: str):
    soup = bs4.BeautifulSoup(html, "lxml")
    wrapper = soup.find(id="results_wrapper")
    if wrapper is None:
        return
    cells = wrapper.find_all(class_="cell_wrapper")
    results: list[bs4.PageElement] = [i.find(class_="results_bio") for i in cells]
    for r in results:
        unwanted_classes = {"availableDiv"}
        elts = r.find_all(
            lambda elt: len(set(elt["class"]) & unwanted_classes) == 0, recursive=False
        )
        out = [i.get_text().replace("\xa0", "") for i in elts]
        if len(out) == 4:
            _title, _author, fmt, _fmtdesc = out
            # NO AUDIOBOOKS!!
            if fmt == 'Format: eAudiobook':
                continue
        tqdm.write(repr(out))


def gen_normalized_query(title, author):
    # Split on colon (subtitles) and parens (series info/editions)
    clean_title = title.split(":")[0].split("(")[0]

    # Normalize unicode (e.g., 'Kondō' -> 'Kondo')
    # NFKD decomposes characters (ō -> o + ¯), then we filter non-ASCII
    clean_title = unicodedata.normalize('NFKD', clean_title) \
        .encode('ascii', 'ignore').decode('utf-8')
    
    # Replace non-alphanumeric with SPACE
    clean_title = re.sub(r"[^a-zA-Z0-9]", " ", clean_title)
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    
    # Normalize unicode for author too
    clean_author = unicodedata.normalize('NFKD', author) \
        .encode('ascii', 'ignore').decode('utf-8')
    clean_author = re.sub(r"[^a-zA-Z0-9]", " ", clean_author)
    clean_author = re.sub(r"\s+", " ", clean_author).strip()
    
    author_names = clean_author.split()
    if len(author_names) > 1:
        # Last name is usually the most significant index key in library systems
        # Using just the last name often reduces noise from middle initials
        # e.g. "Douglas Stone" -> "Stone"
        final_author = author_names[-1]
    else:
        final_author = author_names[0]

    return f"{clean_title} {final_author}"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"phys", "ebook"}:
        print(f"Usage: {sys.argv[0]} <phys|ebook>", file=sys.stderr)
        sys.exit(1)
    
    search_func = None
    if sys.argv[1] == "phys":
        search_func = search_physical
    elif sys.argv[1] == "ebook":
        search_func = search_ebook
    else:
        raise AssertionError()

    db = sqlite3.connect("db.sqlite3")
    r = db.execute("SELECT Title, Author FROM goodreads WHERE Bookshelves = 'to-read'")
    results = list(r.fetchall())

    sess = requests.Session()
    with tqdm(results) as tq:
        for title, author in tq:
            query = gen_normalized_query(title, author)
            html = search_func(sess, tq, query)
            print_search_results(html)


if __name__ == "__main__":
    main()
