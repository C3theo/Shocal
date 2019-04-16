"""
    This modules contains classes to build playlists that are up to date
    with the schedule of touring musicians.
    Extraction:
        Web Scrapers
        Spotify API

    Transformation:
        Spotify Artist Table

        Concert Date Table

        Current Artist Table

    Loading
        Pandas Dataframes -> Sqllite Database
        Flask Web application

    Data Sources:
        Spotify API
        Local newspaper and concert websites

    Example:


TODO:
    Flask Web App

"""
import os
import pdb
import random
import re
from datetime import datetime
from pathlib import WindowsPath

import numpy as np
import pandas as pd
import spotipy
import spotipy.oauth2 as oauth
import spotipy.util as util

from bs4 import BeautifulSoup
from requests import Session

from config import logger

# TODO Document Exceptions same as classes
# Move to different file


class AuthorizationError(Exception):
    """ Authorization keys not Cached. """
    # TODO check if token cached - use spotipy function
    pass


class ArtistNotFoundError(Exception):
    """ Artist not on Spotify. """
    pass


# TODO change class name to Session Manager
class DataManager():
    """
    A class used to start sessions, get HTTP Response ,and return Beautiful Soup
    objects.

    Attributes:
        url
        session
        resonse
    """

    def __init__(self, url=None):

        self.url = url

        self.session = None
        self.response = None

    def start_session(self):
        """ Create new Session object with user-agent headers."""

        headers = {
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                'AppleWebKit/537.36 (KHTML, like Gecko)'
                'Chrome/68.0.3440.106 Safari/537.36')}
        # TODO: Find out if this keeps session alive
        with Session() as self.session:
            self.session.headers.update(headers)
            return self

    def get_response(self):
        """
        Set response attr to response
        returned from URL.

        Args: url string
        """
        # TODO: add specific Exceptions
        # add headers to session in get

        try:
            self.response = self.session.get(self.url, stream=True)
            return self
            # TODO: Save json file
        except Exception:
            logger.exception("Exception occured")

    def get_soup(self):
        """ Set soup attr to Beautiful Soup Object using response.

        Args: 
            response.content: string
        """
        # TODO: add specific exceptions
        # No response content Exception
        try:
            return BeautifulSoup(self.response.content, 'lxml')
        except Exception:
            logger.exception("Exception occured")

    def __repr__(self):
        return fr'DataManager({self.url})'

    def __str__(self):
        return fr'DataManager({self.url})'


class ConcertDataManager():
    """
    A class for managing the extraction and transformation of concert data from Beautiful Soup objects.
    Creates Dictionary of data taken from Beautiful Soup object.

        Attributes:
            url: string
            concert_soup: (BeautifulSoup) From DataManager

        Owns:
            DataManager
    """

    url = 'http://www.flagpole.com/events/live-music'

    def __init__(self):

        self.data_mgr = DataManager(url=ConcertDataManager.url)
        self.concert_soup = self.data_mgr.start_session().get_response().get_soup()

    def parse_concert_soup(self):
        """ Return dictionary of upcoming shows in Athens, Ga.

            Args:
                self.concert_soup

            Return:
                concert: dict
                    keys: Date, Event Count, Show Location, Artists, 
                    and Show information.
        """

        logger.info(' Building Concert Dict. ')

        events = self.concert_soup.find(class_='event-list').findAll('h2')

        concert_dict = {}
        for event in events:

            concert_date = event.text
            concert_date = fr'{concert_date} {datetime.today().year}'
            concert_datetime = datetime.strptime(concert_date, '%A, %B %d %Y')

            event_count = event.findNext('p')
            venues = event.findNext('ul').findAll('h4')
            concert_dict[concert_date] = {'datetime': concert_datetime,
                                          'Event Count': event_count.text}
            # Event Count for Data Audit
            concert_dict[concert_date]['Shows'] = []
            for venue in venues:
                info = venue.findNext('p')
                bands = info.fetchNextSiblings()
                names = [each.strong.text.replace('\xa0', '')
                         for each in bands if each.strong]
                concert_dict[concert_date]['Shows'].append({'ShowLocation': venue.text,
                                                            'Artists': names,
                                                            'ShowInfo': info.text})
        # logger.info('Data: %s', concert_dict)

        return concert_dict

    def __repr__(self):
        return fr'ConcertManager({self.url})'

    def __str__(self):
        return fr'ConcertManager({self.url})'

class DataFrameManager():
    """
        A class used to transform a dictionary and return DataFrame Objects.

        Attributes:
            data: dict       
    """

    def __init__(self):
        self.concert_mgr = ConcertDataManager()
        self.data = self.concert_mgr.parse_concert_soup()

    def key_to_front(self, df):
        """
        Rearrange dataframe columns so new surrogate key is first.

        Args: df
        """

        columns = list(df.columns)
        columns.insert(0, columns.pop())

        return df[columns]

    def create_etl_id(self):
        """ Generate ETLID# used for static ETL gate ID's."""
        # use prefix function for col name
        return random.randint(a=1000, b=9999)

    def create_etl_df(self):
        """Create Empty ETLID DataFrame with column names. Used to keep track of existing tables."""
        # Necessary??
        return pd.DataFrame(columns=['TableName', 'ETLID'])

    def update_etl_df(self, df, tbl_name, etl_id):
        """
        Update ETL DataFrame if Table Name and ID not in DataFrame.

        Args:
            df
            tbl_name
            etl_id
        """
        # if etl_df.isin({'ETLID':[etl_id]}):
        pass

    def stage_df(self):
        """
            Return Staging Dataframe

            Arguments: self.data

            Return: stage_df
        """

        # TODO: Refactor using JMESPATH
        schema = {'Artist': [],
                  'ShowDate': [],
                  'ShowLocaton': [],
                  'ShowInfo': []}

        for date, events in self.data.items():
            for show in events['Shows']:
                for artist in show['Artists']:
                    schema['ShowDate'].append(date)
                    schema['ShowLocaton'].append(show['ShowLocation'])
                    schema['ShowInfo'].append(show['ShowInfo'])
                    schema['Artist'].append(artist)

        df = pd.DataFrame(data=schema)
        df.loc[:, 'ETLID'] = 1000
        df['SourceRowID'] = df.index

        stage_df = self.key_to_front(df)

        return stage_df

    def gate1_df(self, df):
        """ 
        Return Spotify DataFrame.

        Args: df

        Returns:

        """

        gate1_df = df.copy()
        gate1_df.drop(
            columns=['ShowDate', 'ShowLocaton', 'ShowInfo'], inplace=True)
        gate1_df.drop_duplicates(subset='Artist', inplace=True)
        gate1_df.loc[:, "SpotifyKey"] = gate1_df['ETLID'] + \
            gate1_df.iloc[::-1].index
        gate1_df.loc[:, "ETLID"] = 4000
        gate1_df = gate1_df[['SpotifyKey', 'SourceRowID', 'Artist', 'ETLID']]

        return gate1_df

    def gate2_df(self, df):
        """
        Return Concert Table DataFrame.

        Args: df

        Returns:
        """

        gate2_df = df
        gate2_df.ShowDate = pd.to_datetime(gate2_df.ShowDate)
        days = gate2_df.ShowDate.apply(lambda x: x.day).astype(str)
        key = gate2_df.index.astype(str)
        key_col = key + days
        key_col = key_col.astype(int)
        gate2_df['ShowKey'] = key_col
        gate2_df.loc[:, "ETLID"] = 2000
        gate2_df = gate2_df[['ShowKey', 'SourceRowID',
                             'ShowDate', 'ShowLocaton', 'ETLID']]

        return gate2_df

    def gate2a_df(self, df):
        """
        Return Upcoming Shows DataFrame.

        Args: df gate2 DataFrame

        Returns:
        """

        today = datetime.datetime.today()
        current = df[df['ShowDate'] > today]
        end = ', '.join(list(current.columns)[:-1])
        gate2a_df = df[fr'{list(current.columns)[-1]}, {end}']

        return gate2a_df

    def record_data(self, data):
        """
        Return multi-indexed dataframe of all collected concert data.

        Args: data

        Returns:
        """

        # Where, When, Who, How Much?
        # Columns: Venue, Showtime, Artist, Price
        # Stores All Data
        # Not really necessary if just trying to keep track of artists in playlist

        labels = ['Venue', 'Artists', 'Price']
        conc_df = pd.DataFrame()

        for date in data:
            concerts = data[date]['Shows']
            df = pd.DataFrame(data=concerts)

            tuples = list(zip([date] * 3, list(labels)))
            index = pd.MultiIndex.from_tuples(
                tuples, names=['Date', 'Details'])
            df.columns = index

            conc_df = pd.concat([conc_df, df], axis=1)

        return conc_df

    def dates_artists(self, data):
        """
        Return dataframe of artists indexed by show date.

        Args: data

        Returns:

        """

        date_artists = []
        for date, event in data.items():
            artists = [art for show in event['Shows'] for art in show['Artists']
                       if art.lower() != 'open mic']
        if artists:
            date_artists.append({date: artists})

        # TODO: make helper function for growing dfs from list
        da_df = pd.DataFrame()
        for show_date in date_artists:
            df = pd.DataFrame(data=show_date)
            da_df = pd.concat([df, da_df], axis=1)

        return da_df

    def artists_df(self, data):
        """
        Return dataframe of list of showdates indexed by artists.

        Args: data
        """

        # Unique set of Artists
        artists = {each for k, v in data.items()
                   for show in v['Shows']
                   for each in show['Artists']}
        artists = sorted(list(artists))

        # Lists of all Show Dates for each Artist
        a_dict = {each: [] for each in artists}
        for date, event in data.items():
            for show in event['Shows']:
                for artist in show['Artists']:
                    a_dict[artist].append(date)

        df_data = {'Artists': list(a_dict.keys()),
                   'Dates': list(a_dict.values()),
                   'Spotify': False,
                   'Future Shows': False}
        df = pd.DataFrame(data=df_data)
        df = df.astype({'Artists': str,
                        'Dates': list,
                        'Spotify': bool,
                        'Future Shows': bool})

        return df

    def __repr__(self):
        return fr'DataFrameManager()'

    def __str__(self):
        return fr'DataFrameManager()'

# Decorated Methods for controlling several Web Scrapers
# Doesn't work well with complicated scrapes
# This method vs. Scrapy WebScrapers ??

#     @midtown
#     def search(self, search_func):
#         self.artists = {
#             ' '.join(each.text.split())
#             for each in self.soup.findAll(class_=search_func)}

# def midtown(f):

#     def wrapper(*args, **kwargs):
#         search = re.compile('c-lineup__caption-text js-view-details'
#                             ' js-lineup__caption-text ')

#         return f(search)

#     return wrapper

# def athens(func):

#     def wrapper(self):
#         search = re.compile("")

#         def str_func(soup_tag):
#             return ' '.join(soup_tag.text.split())

#         return func(self, str_func, search)

#     return wrapper

# TODO:
# separate class for playlist
# class ArtistDataManager():


class PlaylistManager():
    """
    A class used to handle Spotify authentication and updating playlist.

    Args:
        ply_name
        new_artists

    Instance Attributes
        artists
        ply_name
        sp
        token
        usr_playlists
        artist_ids
        ply_id

    Class Attributes:
        username
        client_id
        client_secret
        scope
        redirect_uri
    """
# Shocal app config
# TODO move to env file for deployment
    # username = os.environ['SPOTIPY_USERNAME']
    # client_id = os.environ['SPOTIPY_CLIENT_ID']
    # client_secret = os.environ['SPOTIPY_CLIENT_SECRET']
    # scope = 'playlist-modify-private playlist-read-private'
    # redirect_uri = 'https://www.google.com/'

    #TODO: Test env file
    username = os.environ['SPOTIFY_USERNAME']
    client_id = os.environ['SPOTIFY_CLIENT_ID']
    client_secret = os.environ['SPOTIFY_CLIENT_SECRET']
    scope = os.environ['SPOTIFY_SCOPE']
    redirect_uri = os.environ['SPOTIFY_REDIRECT_URI']

    def __init__(self, ply_name=None, artists=None):

        self.ply_name = ply_name
        self.artists = artists

        self.token = None
        self.response_code = None
        self.sp = None
        self.user_playlists = None
        self.ply_id = None
        self.artist_ids = None
        self.client_mgr = None

        self.session = DataManager().start_session().session

    def create_client_mgr(self):
        """ 
        Create SpotifyOauth object.

        Args:
            client_id
            client_secret
            redirect_uri
            scope
            cache_path

        """
        cache_path = WindowsPath("__pycache__") / fr'.cache-{self.username}'
        self.client_mgr = spotipy.oauth2.SpotifyOAuth(self.client_id, self.client_secret,
                                                      self.redirect_uri, scope=self.scope,
                                                      cache_path=cache_path)

    def get_auth_token(self):
        """ 
        Get oauth token from cache or prompt for new token.
        """

        try:
            self.token_info = self.client_mgr.get_cached_token()
            # TODO: Fix EOL error

        # TODO: add other exceptions
        except Exception:
            # Or scope not subset
            # expired
            logger.error("No token in cache, or invalid scope.", exc_info=True)

    def create_spotify(self):
        """
        Create Spotify object.

        Args: token, session, client_mgr
        """

        auth_info = {'auth': self.token, 'requests_session': self.session,
                     'client_credentials_manager': self.client_mgr}
        # Create Spotify object
        # TODO: Test token and client_mgr
        self.sp = self.catch(spotipy.Spotify, auth_info)

    # TODO: Determine how the Playlist will be 'maintained'
    def create_playlist(self):
        """
        Create playlist with ply_name attribute if it does not already exist.
        """

        try:
            self.sp.user_playlist_create(
                self.username, self.ply_name, public=False)
        except spotipy.client.SpotifyException:
            logger.error(fr"Invalid Scope: {self.sp.client_credentials_manager.scope}", exc_info=True)
        except Exception:
            logger.error("Exception occured.", exc_info=True)

    def get_playlists(self):
        """
        Set usr_playlist attribute to list of current user playlist names.
        """

        self.usr_playlists = self.catch(self.sp.current_user_playlists)

    def get_playlist_id(self, name=None):
        """
        Return uri of specified user playlists. 
        """

        # TODO: Refactor w/o for loop
        for each in self.usr_playlists['items']:
            # How to use catch()??
            #  Check format of usr_playlists
            try:
                each['name'] == name

            except Exception:
                logger.exception(" Exception occured. ")

            else:
                self.ply_id = self.get_uri(each["uri"])

    def get_artist_ids(self):
        """ 
        Set artist_ids attribute to list of artist ids returned from
        find_artist_info().
        """

        self.artist_ids = [
            self.find_artist_info('artist', each)['artists']['items'][0]['uri']
            for each in self.artists]

    def find_artist_info(self, category, item):
        """ Query artist api """

        kwargs = {'q': fr'{category}: {item}', 'type': category}
        return self.catch(self.sp.search, kwargs)

    def get_top_tracks(self, num_songs=10):
        """ Return uris of all the artists top ten tracks."""

        for each in self.artist_ids:
            results = self.sp.artist_top_tracks(each)
            uris = {
                self.get_uri(each['uri'])
                for each in results['tracks'][:num_songs]}
        return uris

    def add_tracks(self, uris):
        """
        Add tracks to playlist matchig ply_id attribute.

        Args: uris
        """

        self.sp.user_playlist_add_tracks(self.username, self.ply_id, uris)

    def clear_playlist(self, sp, user, playlist_id=None):
        """ Remove all tracks from playlist. """

        playlist_tracks = sp.user_playlist_tracks(user, playlist_id)
        sp.user_playlist_remove_all_occurrences_of_tracks(
            user, playlist_id, playlist_tracks, snapshot_id=None)

    def update_playlist(self):
        """
        Update spotify playlist
        """
        pass

    def get_uri(self, string):
        """
        Return URI at the end of Spotify String.

        Args: string
        """
        str_list = string.split(':')
        return str_list[-1]


def catch(func, kwargs):
    """
    Helper function for logging unknown exceptions.
    """

    try:
        return func(**kwargs)
    except Exception:
        logger.exception('Exception occured')