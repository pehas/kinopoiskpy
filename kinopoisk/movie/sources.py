# -*- coding: utf-8 -*-
"""
Sources for Movie
"""
from __future__ import unicode_literals
from bs4 import BeautifulSoup, Tag

from dateutil import parser

import simplejson as json
import re

from ..utils import KinopoiskPage, KinopoiskImagesPage


class MoviePremierLink(KinopoiskPage):
    """
    Parser movie info from premiers links
    """
    def parse(self, instance, content):

        if isinstance(content, Tag):
            premier_soup = content
        else:
            content_soup = BeautifulSoup(content, 'lxml')
            premier_soup = content_soup.find('div', {'class': 'premier_item'})

        title_soup = premier_soup.find('span', {'class': 'name_big'}) or premier_soup.find('span', {'class': 'name'})

        instance.id = self.prepare_int(premier_soup['id'])
        instance.title = self.prepare_str(title_soup.find('a').contents[0])
        date = premier_soup.find('meta', {'itemprop': 'startDate'})['content']
        try:
            instance.release = parser.parse(date)
        except:
            pass

        match = re.findall(r'^(.+) \((\d{4})\)$', title_soup.nextSibling.nextSibling.contents[0])
        if len(match):
            instance.title_original = self.prepare_str(match[0][0].strip())
            instance.year = self.prepare_int(match[0][1])

        try:
            instance.plot = self.prepare_str(premier_soup.find('span', {'class': 'sinopsys'}).contents[0])
        except:
            pass

        instance.set_source('premier_link')


class MovieLink(KinopoiskPage):
    """
    Parser movie info from links
    """
    def parse(self, instance, content):
        content_soup = BeautifulSoup(content, 'lxml')

        link = content_soup.find('p', {'class': 'name'})
        if link:
            link = link.find('a')
            if link:
                # /level/1/film/342/sr/1/
                # /film/brigada-2002-77039/sr/1/
                instance.id = self.prepare_int(link['href'].split('/')[2].split('-')[-1])
                instance.url = self.prepare_str(link['href'].split('/')[2])
                # instance.id = self.prepare_int(link['data-id'])
                instance.title = self.prepare_str(link.text)
                instance.series = '(сериал)' in instance.title

        year = content_soup.find('p', {'class': 'name'})
        if year:
            year = year.find('span', {'class': 'year'})
            if year:
                # '1998 &ndash; 2009'
                instance.year = self.prepare_int(year.text[:4])

        otitle = content_soup.find('span', {'class': 'gray'})
        if otitle:
            if 'мин' in otitle.text:
                values = otitle.text.split(', ')
                instance.runtime = self.prepare_int(values[-1].split(' ')[0])
                instance.title_original = self.prepare_str(', '.join(values[:-1]))
            else:
                instance.title_original = self.prepare_str(otitle.text)

        rating = content_soup.find('div', attrs={'class': re.compile('^rating')})
        if rating:
            instance.rating = float(rating['title'].split(' ')[0])

        instance.set_source('link')


class MovieSeries(KinopoiskPage):
    url = '/film/%s/episodes/'

    def parse(self, instance, content):
        import datetime
        soup = BeautifulSoup(content, 'lxml')
        year = datetime.datetime.now().year
        for season in soup.findAll('h1', attrs={'class': 'moviename-big'}):
            if '21px' not in season['style']:
                continue

            parts = season.nextSibling.split(',')
            if len(parts) == 2:
                year = self.prepare_int(parts[0])
            tbody = season.parent.parent.parent
            episodes = []
            for tr in tbody.findAll('tr')[1:]:
                if not tr.find('h1'):
                    continue

                raw_date = tr.find('td', attrs={'width': '20%'}).string
                if raw_date.strip().count('\xa0') == 2:
                    normalized_date = self.prepare_date(raw_date)
                else:
                    normalized_date = raw_date
                title = tr.find('h1').b.string
                if title.startswith('Эпизод #'):
                    title = None
                episodes.append((title, normalized_date))

            if episodes:
                instance.add_series_season(year, episodes)


class MovieMainPage(KinopoiskPage):
    """
    Parser of main movie page
    """
    url = '/film/%s/'

    def parse(self, instance, content):

        instance_id = re.compile(r'<script type="text/javascript"> id_film = (\d+); </script>').findall(content)
        if instance_id:
            instance.id = self.prepare_int(instance_id[0])

        content_info = BeautifulSoup(content, 'lxml')
        title = content_info.find('h1', {'class': 'moviename-big'})
        if title:
            instance.title = self.prepare_str(title.text)

        title_original = content_info.find('span', {'itemprop': 'alternativeHeadline'})

        if title_original:
            instance.title_original = self.prepare_str(title_original.text)

        # <div class="brand_words" itemprop="description">
        plot = content_info.find('div', {'class': 'brand_words', 'itemprop': 'description'})
        if plot:
            instance.plot = self.prepare_str(plot.text)

        table_info = content_info.find('table', {'class': re.compile(r'^info')})
        if table_info:
            for tr in table_info.findAll('tr'):
                tds = tr.findAll('td')
                name = tds[0].text
                value = tds[1].text
                if value == '-':
                    continue

                if name == 'слоган':
                    instance.tagline = self.prepare_str(value)
                elif name == 'время':
                    instance.runtime = self.prepare_int(value.split(' ')[0])
                elif name == 'год':
                    try:
                        instance.year = self.prepare_int(value.split('(')[0])
                    except ValueError:
                        pass
                    instance.series = 'сезон' in value
                elif name == 'режиссер':
                    for ac in tds[1].findAll('a'):
                        if ac.text != '...':
                            instance.directors.append(self.prepare_str(ac.text))
                elif name == 'сценарий':
                    for ac in tds[1].findAll('a'):
                        if ac.text != '...':
                            instance.scenarios.append(self.prepare_str(ac.text))
                elif name == 'продюсер':
                    for ac in tds[1].findAll('a'):
                        if ac.text != '...':
                            instance.producers.append(self.prepare_str(ac.text))
                elif name == 'страна':
                    countries = value.split(', ')
                    for country in countries:
                        instance.countries.append(self.prepare_str(country))
                elif name == 'жанр':
                    genres = value.split(', ')
                    for genre in genres:
                        if genre != '...\nслова\n':
                            instance.genres.append(self.prepare_str(genre))
                elif name == 'бюджет':
                    instance.budget = self.find_profit(tds[1])
                elif name == 'сборы в США':
                    instance.profit_usa = self.find_profit(tds[1])
                elif name == 'сборы в России':
                    instance.profit_russia = self.find_profit(tds[1])
                elif name == 'сборы в мире':
                    instance.profit_world = self.find_profit(tds[1])
                elif name == 'возраст':
                    try:
                        instance.age = self.prepare_str(tr.findAll('span')[0].text)
                    except Exception:
                        pass
                elif name == 'премьера (мир)' or name == 'премьера (РФ)':
                    try:
                        instance.release = self.prepare_date(tr.findAll('a')[0].text)
                    except Exception:
                        pass

        rating = content_info.find('span', attrs={'class': 'rating_ball'})
        if rating:
            instance.rating = float(rating.string)
        
        block_rating = content_info.find('div', attrs={'id': 'block_rating'})
        if block_rating:
            div1 = block_rating.find('div', attrs={'class': 'div1'})
            if div1:
                div_rating = div1.find_next('div')
                if div_rating:
                    rating_imdbs = re.findall(r'IMDb: ([0-9\.]+)', div_rating.text)
                    if len(rating_imdbs):
                        instance.rating_imdb = float(rating_imdbs[0])
 
        trailers = re.findall(r'GetTrailerPreview\(([^\)]+)\)', content)
        if len(trailers):
            instance.add_trailer(json.loads(trailers[0].replace("'", '"')))

        actors = content_info.find('div', {'id': 'actorList'})
        if actors and actors.ul:
            for ac in actors.ul.findAll('li'):
                actor = ac.a.text
                if actor != "...":
                    instance.actors.append(self.prepare_str(actor))

        instance.set_source('main_page')


class MoviePostersPage(KinopoiskImagesPage):
    """
    Parser of movie posters page
    """
    url = '/film/%s/posters/'
    field_name = 'posters'


class MovieStillsPage(KinopoiskImagesPage):
    """
    Parser of movie stills page
    """
    url = '/film/%s/stills/'
    field_name = 'stills'


class MovieTrailersPage(KinopoiskPage):
    """
    Parser of kinopoisk trailers page
    """
    url = '/film/%s/video/'

    def parse(self, instance, content):
        trailers = re.findall(r'GetTrailerPreview\(([^\)]+)\)', content)
        for trailer in trailers:
            instance.add_trailer(json.loads(trailer.replace("'", '"')))

        instance.youtube_ids = list(set(re.findall(r'//www.youtube.com/v/(.+)\?', content)))
        instance.set_source(self.content_name)
