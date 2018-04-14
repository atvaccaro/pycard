import csv
import json
import logging
import os
import re
import time
import webbrowser
from optparse import OptionParser

from jinja2 import Template
from livereload import Server
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from watchdog.observers import Observer

VERSION = '0.2.0'

RENDERED_CARDS_FILE = 'index.html'


class CardRenderer:
    def __init__(self, input_path, prefix, format):
        self.input_path = input_path
        self.prefix = prefix
        self.format = format

        self.card_data_path = self.get_path(format)
        self.custom_header_path = self.get_path('header.html')
        self.single_card_template_path = self.get_path('html.jinja2')

        self.cards_template_path = os.path.join(os.path.dirname(__file__), 'cards.html.jinja2')

        self.all_cards_rendered_path = os.path.join(input_path, RENDERED_CARDS_FILE)

    def get_path(self, extension):
        return os.path.join(self.input_path, '{}.{}'.format(self.prefix, extension))

    def render_cards(self):
        # I've noticed that when saving the CSV file
        # the server reloads an empty page
        # unless I add a small sleep before attempting to read everything
        time.sleep(0.5)

        # load the card data file
        cards_data = []
        with open(self.card_data_path, 'r', encoding='utf-8-sig') as f:
            if self.format == 'json':
                cards_data = json.load(f)
            else:
                reader = csv.DictReader(f, dialect='custom_delimiter')
                for row in reader:
                    cards_data.append(row)

        rendered_cards = []

        # load the single card template
        with open(self.single_card_template_path, 'r') as template_file:
            template = Template(template_file.read())

            # render the template with card data
            for card_data in cards_data:
                if str(card_data.get('ignore', 'false')).lower() == 'true':
                    continue

                rendered = template.render(
                    card_data,
                    __card_data=card_data,
                    __time=str(time.time())
                )

                num_cards = 1
                try:
                    num_cards = int(card_data.get('num_cards', 1))
                except (ValueError, TypeError):
                    pass

                for i in range(num_cards):
                    rendered_cards.append(rendered)

        # Load custom header html if it exists
        custom_header = None

        if os.path.exists(self.custom_header_path):
            with open(self.custom_header_path, 'r') as f:
                custom_header = f.read()

        # render the cards template with all rendered cards
        with open(self.cards_template_path, 'r') as cards_template_file:
            template = Template(cards_template_file.read())
            with open(self.all_cards_rendered_path, 'w') as all_cards_rendered_file:
                all_cards_rendered_file.write(
                    template.render(
                        rendered_cards=rendered_cards,
                        prefix=self.prefix,
                        custom_header=custom_header
                    )
                )


class RenderingEventHandler(FileSystemEventHandler):
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer

    def on_any_event(self, event):
        if event.src_path == self.card_renderer.all_cards_rendered_path:
            return

        self.card_renderer.render_cards()


def parse_options():
    parser = OptionParser(
        usage='usage: %prog [options]',
        version='%prog {}'.format(VERSION)
    )
    parser.add_option('-p', '--path',
                      help='path to assets',
                      dest='path',
                      default=os.getcwd(),
                      metavar='PATH')

    parser.add_option('-f', '--format',
                      help='csv or json file format',
                      dest='format',
                      default='csv',
                      metavar='FORMAT')

    parser.add_option('-x', '--prefix',
                      help='filename prefix, example _card<.ext>',
                      dest='prefix',
                      default='_card',
                      metavar='PREFIX')

    parser.add_option('-d', '--delimiter',
                      help='delimiter used in the csv file, default: , (comma)',
                      dest='delimiter',
                      default=',',
                      metavar='DELIMITER')

    parser.add_option('--port',
                      help='port to use for live reloaded page',
                      dest='port',
                      type='int',
                      default=8800,
                      metavar='PORT')

    parser.add_option('--address',
                      help='host address to bind to',
                      dest='host_address',
                      default='0.0.0.0',
                      metavar='ADDRESS')

    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    (options, args) = parse_options()

    port = options.port
    assets_path = options.path
    file_prefix = options.prefix
    host_address = options.host_address
    format = options.format

    if format == 'csv':
        csv.register_dialect('custom_delimiter', delimiter=options.delimiter)

    card_renderer = CardRenderer(assets_path, file_prefix, format)

    observer = Observer()
    observer.schedule(LoggingEventHandler(), assets_path, recursive=True)
    observer.schedule(RenderingEventHandler(card_renderer), assets_path, recursive=True)

    card_renderer.render_cards()

    observer.start()

    server = Server()
    server.watch(card_renderer.all_cards_rendered_path)
    webbrowser.open('http://{}:{}'.format(host_address, port))
    server.serve(root=assets_path, port=port, host=host_address)

    observer.stop()
    observer.join()


if __name__ == '__main__':
    main()
