import argparse
import json
from functools import partial
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from livereload import Server
from more_itertools import chunked


PROJECT_DIR = Path(__file__).resolve().parent


def encode_path(path):
    """Encode spaces/Cyrillic and normalize metadata from Windows exports."""
    return quote(path.replace('\\', '/'), safe='/')


def load_books(metadata_path):
    with metadata_path.open(encoding='utf-8') as metadata_file:
        books = json.load(metadata_file)
    for book in books:
        genres = book['genres']
        if isinstance(genres, str):
            book['genres'] = [genre.strip().rstrip('.') for genre in genres.split(',') if genre.strip()]
    return books


def on_reload(metadata_path, books_per_page):
    environment = Environment(
        loader=FileSystemLoader(PROJECT_DIR),
        autoescape=select_autoescape(['html']),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters['url_path'] = encode_path
    template = environment.get_template('template.html')
    books_pages = list(chunked(load_books(metadata_path), books_per_page)) or [[]]
    pages_dir = PROJECT_DIR / 'pages'
    pages_dir.mkdir(exist_ok=True)
    for page_number, books in enumerate(books_pages, start=1):
        context = dict(
            books_rows=list(chunked(books, 2)), current_page=page_number,
            total_pages=len(books_pages), asset_prefix='../', page_prefix='',
        )
        html = template.render(**context)
        (pages_dir / f'index{page_number}.html').write_text(html, encoding='utf-8')
        if page_number == 1:
            context.update(asset_prefix='', page_prefix='pages/')
            (PROJECT_DIR / 'index.html').write_text(template.render(**context), encoding='utf-8')
    # Remove generated pages left behind when the metadata list shrinks.
    for old_page in pages_dir.glob('index*.html'):
        number = old_page.stem.removeprefix('index')
        if number.isdigit() and int(number) > len(books_pages):
            old_page.unlink()
    print(f'Готово: {sum(map(len, books_pages))} книг, {len(books_pages)} страниц.', flush=True)


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('Укажите число больше нуля.')
    return number


def main():
    parser = argparse.ArgumentParser(description='Собрать библиотеку и запустить локальный сервер.')
    parser.add_argument('--metadata', type=Path, default=PROJECT_DIR / 'meta_data.json')
    parser.add_argument('--books-per-page', type=positive_integer, default=20)
    parser.add_argument('--build', action='store_true', help='Только собрать HTML, без сервера.')
    parser.add_argument('--port', type=int, default=5500)
    args = parser.parse_args()
    metadata_path = args.metadata.resolve()

    rebuild = partial(on_reload, metadata_path, args.books_per_page)
    rebuild()
    if args.build:
        return
    server = Server()
    server.watch(str(PROJECT_DIR / 'template.html'), rebuild)
    server.watch(str(metadata_path), rebuild)
    server.watch(str(PROJECT_DIR / 'static' / 'bootstrap.min.css'))
    server.watch(str(PROJECT_DIR / 'static' / 'favicon.svg'))
    print(f'Откройте http://127.0.0.1:{args.port}/', flush=True)
    server.serve(root=str(PROJECT_DIR), host='127.0.0.1', port=args.port, open_url_delay=None)


if __name__ == '__main__':
    main()
