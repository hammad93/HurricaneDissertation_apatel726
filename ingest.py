# -*- coding: utf-8 -*-
"""
Created on Tue Sep 15 01:04:55 2020
@author: Hammad, Akash, Jonathan
Scientific units used are as follows,
Coordinates (Lat, Lon) : Decimal Degrees (DD)
Timestamp : Python Datetime
Barometric pressure : mb
Wind Intensity: Knots
"""

import os
import xmltodict
import pickle
import requests
from datetime import datetime
import dateutil.parser
from pytz import timezone
import zipfile
import io
import pandas as pd
import hurricane_ai.plotting_utils
from typing import List, Dict

PROJ_BASE_DIR = os.path.dirname(os.path.realpath(__file__))

def past_track(link):
    """
    From a KMZ file of a storm in the NHC format, we extract the history
    Parameters
    ----------
    link string
        The network link or downloadable KMZ href file
    Returns
    -------
    dict
    """
    kmz = requests.get(link)
    uncompressed = zipfile.ZipFile(io.BytesIO(kmz.content))

    # get the kml name
    for name in uncompressed.namelist():
        # all kml file names begin with al, e.g. 'al202020.kml'
        if name[:2] == 'al':
            file_name = name

    # read the contents of the kml file in the archive
    kml = xmltodict.parse(uncompressed.read(file_name))
    kml['results'] = []
    for attribute in kml['kml']['Document']['Folder']:
        if attribute['name'] == 'Data':
            for entry in attribute['Placemark']:
                # parse time information
                time = datetime.strptime(entry['atcfdtg'],
                                        '%Y%m%d%H').replace(
                    tzinfo=timezone('UTC'))

                # add to results
                kml['results'].append({
                    'time' : time,
                    'wind' : float(entry['intensity']),
                    'lat' : float(entry['lat']),
                    'lon' : float(entry['lon']),
                    'pressure' : float(entry['minSeaLevelPres'])
                })
                print(kml['results'][-1])

    return kml

def nhc() -> List[Dict[str, List]]:
    '''
    Runs the NHC update and populates current Atlantic storms
    Returns
    -------
    array of dict
        Each dictionary is in the following form,
        {
            "storm" : string # the storm ID from the NHC
            "metadata" : dict # the kml files used to create the results
            "entries" : array of dict # The data for the storm in the form,
                {
                    'time' : Datetime,
                    'wind' : Knots,
                    'lat' : Decimal Degrees,
                    'lon' : Decimal Degrees,
                    'pressure' : Barometric pressure (mb)
                }
        }
    '''
    # this link can be reused to download the most recent data
    static_link = 'https://www.nhc.noaa.gov/gis/kml/nhc_active.kml'
    # common timezones for parsing with dateutil. offset by seconds
    timezones = {
        "ADT": 4 * 3600,
        "AST": 3 * 3600,
        "CDT": -5 * 3600,
        "CST": -6 * 3600,
        "CT": -6 * 3600,
        "EDT": -4 * 3600,
        "EST": -5 * 3600,
        "ET": -5 * 3600,
        "GMT": 0 * 3600,
        "PST": -8 * 3600,
        "PT": -8 * 3600,
        "UTC": 0 * 3600,
        "Z": 0 * 3600,
    }

    # create data structure as dictionary
    request = requests.get(static_link)
    data = xmltodict.parse(request.text)
    #TEST_FILE = os.path.join(PROJ_BASE_DIR, 'results/testfile.txt')
    results = []
    
   # f = open(TEST_FILE, 'w')
   # pickle.dump(data, f)
    
    # return if no storms
    if 'Folder' not in data['kml']['Document'].keys() :
        print("No current active storms for ingest")
        return
    
    # parse in storms
    for folder in data['kml']['Document']['Folder']:
        # the id's that start with 'at' are the storms we are interested in
        # others can include 'wsp' for wind speed probabilities
        if folder['@id'][:2] == 'at':
            # some storms don't have any data because they are so weak
            if not 'ExtendedData' in folder.keys():
                continue

            # storm data structure
            storm = {
                'metadata': folder,
                'entries': []
            }
            entry = {}

            for attribute in folder['ExtendedData'][1]:
                if attribute == 'tc:atcfID':  # NHC Storm ID
                    storm['id'] = folder['ExtendedData'][1][attribute]
                elif attribute == 'tc:name':  # Human readable name
                    print(folder['ExtendedData'][1][attribute])
                elif attribute == 'tc:centerLat':  # Latitude
                    entry['lat'] = float(folder['ExtendedData'][1][attribute])
                elif attribute == 'tc:centerLon':  # Longitude
                    entry['lon'] = float(folder['ExtendedData'][1][attribute])
                elif attribute == 'tc:dateTime':  # Timestamp
                    entry['time'] = dateutil.parser.parse(
                        folder['ExtendedData'][1][attribute],
                        tzinfos=timezones)
                elif attribute == 'tc:minimumPressure':  # Barometric pressure
                    entry['pressure'] = float(folder['ExtendedData'][1]
                                              [attribute].split(' ')[0])
                elif attribute == 'tc:maxSustainedWind':  # Wind Intensity
                    # note that we are converting mph to knots
                    entry['wind'] = float(folder['ExtendedData'][1][attribute].
                                          split(' ')[0]) / 1.151

            print(storm['id'])
            print(entry)

            # add entry to storm
            storm['entries'].append(entry)
            # get network link and extract past history
            for links in folder['NetworkLink']:
                if links['@id'] == 'pasttrack':
                    kml = past_track(links['Link']['href'])
                    # add history to entries
                    storm['entries'].extend(kml['results'])

                    # add history to storm metadata
                    storm['metadata']['history'] = kml

            # add to results
            results.append(storm)

    return results

def prep_hurricane_data(observations: List, lag: int) -> pd.DataFrame:
    """
    Converts raw observations to data frame and computes derived features.
    :param observations: Raw hurricane kinematic and barometric measurements.
    :param lag: Number of observation intervals to lag derived features.
    :return: Data frame of raw and derived hurricane measurements.
    """

    # Construct data frame from observations and sort by time
    df = pd.DataFrame(observations).sort_values(by="time")

    # TODO: This assumes everything is UTC - not sure if this is actually the case
    df["time"] = pd.to_datetime(df["time"], utc=True)

    df = df.assign(

        # Maximum wind speed up to time of observation
        max_wind=df["wind"].cummax(),

        # Change in wind speed since beginning of five day interval
        delta_wind=(df["wind"].cummax() - df["wind"].shift(lag).cummax()) / (
                (df["time"] - df["time"].shift(lag)).dt.seconds / 21600),

        # Minimum pressure up to time of observation
        min_pressure=df["pressure"].cummin(),

        # Average change in latitudinal position per hour
        zonal_speed=(df["lat"] - df["lat"].shift(lag)) / ((df["time"] - df["time"].shift(lag)).dt.seconds / 3600),

        # Average change in longitudinal position per hour
        meridonal_speed=(df["lon"] - df["lon"].shift(lag)) / (
                (df["time"] - df["time"].shift(lag)).dt.seconds / 3600),

        # Year/month/day/hour
        year=df["time"].dt.year,
        month=df["time"].dt.month,
        day=df["time"].dt.day,
        hour=df["time"].dt.hour
    )

    # Remove rows where we didn't have enough historical data to compute derived features
    df = df.dropna()
    
    return df