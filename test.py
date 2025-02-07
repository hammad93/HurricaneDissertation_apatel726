import argparse
import datetime
import json
import os
import pandas as pd
import tensorflow as tf
from datetime import timedelta
from deploy import inference, batch_inference
from hurricane_ai.container.hurricane_data_container import HurricaneDataContainer
from hurricane_ai.container.hurricane_data_container import Hurricane
from hurricane_ai import plotting_utils
import great_circle_calculator.great_circle_calculator as gcc

# Create arugment parser for command line interface
# https://docs.python.org/3/howto/argparse.html
parser = argparse.ArgumentParser()

# cli flags for input file
parser.add_argument('--config', help = 'The file where all the configuration parameters are located', default = None)
# cli flags for test file
parser.add_argument('--test', help = 'The test file in HURDAT format to evaluate the models', default = None)
# cli flags for storm name
parser.add_argument('--name', help = 'The storm name in the test file to run inference on', default = None)
# Read in arguements
args = parser.parse_args()

# read in config file
with open(args.config) as f :
    config = json.load(f)

# TODO: Read in test file from hurricanecontrainer.py
data_container = HurricaneDataContainer()
data = data_container._parse(args.test)

def parse_entries(entries, storm) :
    '''
    "entries" : array of dict # The data for the storm in the form,
                {
                    'time' : Datetime,
                    'wind' : Knots,
                    'lat' : Decimal Degrees,
                    'lon' : Decimal Degrees,
                    'pressure' : Barometric pressure (mb)
                }
    '''
    return [{ 'entries' : [{
            'time' : time,
            'wind' : entries[time]['max_wind'],
            'lat' : entries[time]['lat'],
            'lon' : entries[time]['long'],
            'pressure' : entries[time]['min_pressure']
        } for time in entries],
        'storm' : storm
    }]

def create_table(prediction, storm, deltas) : 
    '''
    Creates an output table meant for CSV export.
    The following are details on the tags in the column name:
    'M' : Multivariate model
    'U' : Universal model
    'predict' : A prediction from the model
    'Truth' : Compared to the prediction, this is the realized value
    'diff' : The difference between in appropriate units
    'Wind' : Wind, in nautical miles
    'Lat' : Latitude, in decimal degrees
    'Lon' : Longitude, in decimeal degrees
    'Dist' : Distance, in meters
    
    Args:
        prediction (list(dict)) : The predictions in dict of form,
        'storm_id' : {
            'name' : String,
            'times' : list(Datetime),
            'wind' : list(float),
            'lat' : list(float),
            'lon' : list(float)
        }
    '''
    results = []
    for index, time in enumerate(prediction['universal'][storm.id]['times']) : 
        time = time.replace(tzinfo=None)
        result = {
            'time' : time,
            'delta' : deltas[index],
            'Mpredict_Wind' : prediction['singular'][storm.id]['wind'][index],
            'Mpredict_Lat' : prediction['singular'][storm.id]['lat'][index],
            'Mpredict_Lon' : prediction['singular'][storm.id]['lon'][index],
            'Upredict_Wind' : prediction['universal'][storm.id]['wind'][index],
            'Upredict_Lat' : prediction['universal'][storm.id]['lat'][index],
            'Upredict_Lon' : prediction['universal'][storm.id]['lon'][index]
        }
        # gcc library uses (lon, lat)
        if time in storm.entries.keys() :
            truth_entry = storm.entries[time]
            result.update({'WindTruth' : truth_entry['max_wind'],
                        'LatTruth' : truth_entry['lat'],
                        'LonTruth' : truth_entry['long'] * -1,
                        'Mdiff_Wind' : truth_entry['max_wind'] - prediction['singular'][storm.id]['wind'][index],
                        'Mdiff_Dist' : gcc.distance_between_points(
                            (truth_entry['long'], truth_entry['lat']),
                            (prediction['singular'][storm.id]['lon'][index],
                             prediction['singular'][storm.id]['lat'][index])),
                        'Mdiff_Lat' : truth_entry['lat'] - prediction['singular'][storm.id]['lat'][index],
                        'Mdiff_Lon' : (truth_entry['long'] * -1) - prediction['singular'][storm.id]['lon'][index],
                        'Udiff_Wind' : truth_entry['max_wind'] - prediction['universal'][storm.id]['wind'][index],
                        'Udiff_Dist' : gcc.distance_between_points(
                            (truth_entry['long'], truth_entry['lat']),
                            (prediction['universal'][storm.id]['lon'][index],
                             prediction['universal'][storm.id]['lat'][index])),
                        'Udiff_Lat' : truth_entry['lat'] - prediction['universal'][storm.id]['lat'][index],
                        'Udiff_Lon' : (truth_entry['long'] * -1) - prediction['universal'][storm.id]['lon'][index]})
        else :
            result.update({'WindTruth' : 'N/A',
                        'LatTruth' : 'N/A',
                        'LonTruth' : 'N/A',
                        'Mdiff_Wind' : 'N/A',
                        'Mdiff_Lat' : 'N/A',
                        'Mdiff_Lon' : 'N/A',
                        'Udiff_Wind' : 'N/A',
                        'Udiff_Lat' : 'N/A',
                        'Udiff_Lon' : 'N/A'})
        results.append(result)
    return results

output_times = [6, 12, 24, 36, 48]
input_length = 6
# create hurricane objects for different unique hurricanes
for storm in data.storm_id.unique() :
    # get the storm entries
    entries = data[data['storm_id'] == storm]
    # not enough entries
    if len(entries) < input_length :
        print(f"{storm} only has {len(entries)} entries and the minimum is {input_length}. Skipping")
        continue
    
    # convert to hurricane object
    hurricane = Hurricane(storm, storm)
    for index, entry in entries.iterrows() :
        hurricane.add_entry(entry[2:]) # start at index 2 because of HURDAT2 format
    
    # check to see if we're running on all time steps
    if "all_timesteps" in config :
        buffer = 1 if config['all_timesteps']['placeholders'] else 5 # buffer determines start and end index
        tables = dict()
        
        if not os.path.exists(f"results/{storm}_gis_files") :
            os.mkdir(f"results/{storm}_gis_files") # make a directory for the images and kml
        
        predictions = {
            'universal' : batch_inference(config['base_directory'],
                                   config['model_file'],
                                   config['scaler_file'],
                                   output_times,
                                   parse_entries(hurricane.entries, storm)),
            'singular' : batch_inference(config['univariate']['base_directory'],
                                   None,
                                   None,
                                   output_times,
                                   parse_entries(hurricane.entries, storm)) if 'univariate' in config else None
        }
        # clean up inference session
        tf.keras.backend.clear_session()
        
        tables = {timestamp : create_table(
            {'universal' : { storm : {
                            'times' : [timestamp + timedelta(hours = hour) for hour in output_times],
                            'wind' : predictions['universal'][storm][timestamp]['wind'],
                            'lat' : predictions['universal'][storm][timestamp]['lat'],
                            'lon' : predictions['universal'][storm][timestamp]['lon']
                           }},
             'singular' : { storm : {
                            'times' : [timestamp + timedelta(hours = hour) for hour in output_times],
                            'wind' : predictions['singular'][storm][timestamp]['wind'],
                            'lat' : predictions['singular'][storm][timestamp]['lat'],
                            'lon' : predictions['singular'][storm][timestamp]['lon']
                           }}
            }, hurricane, output_times) for timestamp in [ * hurricane.entries][len(output_times) : ] }
        
        # Save to excel sheet
        print("Writing files to Excel . . . ", end = '')
        with pd.ExcelWriter(f"results/{storm}.xlsx") as writer :
            full_join = []
            for timestep in tables :
                pd.DataFrame.from_dict(tables[timestep]).to_excel(
                    writer, sheet_name = timestep.strftime("%Y_%m_%d_%H_%M"), index = False)
                full_join.extend(tables[timestep]) # Create overview and aggregate page
            
            full_join_df = pd.DataFrame.from_dict(full_join)
            full_join_df.to_excel(writer, sheet_name = 'full_join', index = False)
            # generate overview page
            overview = [full_join_df[full_join_df.time == time].sort_values(by ='delta').iloc[0]
                       for time in full_join_df.time.unique()]
            pd.DataFrame(overview).to_excel(writer, sheet_name = 'overview', index = False)
        
        # for index in range(buffer, len(hurricane.entries))  :
        while False :
            timestamp = [* hurricane.entries][index]
            prediction = {
                'universal' : inference(config['base_directory'],
                                   config['model_file'],
                                   config['scaler_file'],
                                   output_times,
                                   parse_entries({
                                       time : hurricane.entries[time] for time in [* hurricane.entries][ : index + 1]
                                   }, storm)),
                'singular' : inference(config['univariate']['base_directory'],
                                   None,
                                   None,
                                   output_times,
                                   parse_entries({
                                       time : hurricane.entries[time] for time in [* hurricane.entries][ : index + 1]
                                   }, storm)) if 'univariate' in config else None
            }
            # note that this clears the memory, without this line, there's a fatal memory leak
            tf.keras.backend.clear_session()
            
            # add results to appropriate data structures
            tables[timestamp] = create_table(prediction, hurricane, output_times)
            inferences.append(prediction)
            
            # create plotting file, including KML and a PNG ouput with a track
            plotting_utils.process_results({
                    'inference' : prediction['universal'],
                    'track' : args.test
                },
                postfix = f"{storm}_gis_files/universal_{timestamp.strftime('%Y_%m_%d_%H_%M')}")
            if prediction['singular'] :
                plotting_utils.process_results({
                    'inference' : prediction['singular'],
                    'track' : args.test
                },
                postfix = f"{storm}_gis_files/singular_{timestamp.strftime('%Y_%m_%d_%H_%M')}")        
            
        print("Done!")
        
    else :
        # generate inference dictionary
        inferences = {
            'universal' : inference(config['base_directory'],
                               config['model_file'],
                               config['scaler_file'],
                               parse_entries(hurricane.entries, storm)),
            'singular' : inference(config['univariate']['base_directory'],
                               None,
                               config['univariate']['scaler_file'],
                               parse_entries(hurricane.entries, storm)) if 'univariate' in config.keys() else None
        }
        # create plotting file, including KML and a PNG ouput with a track
        plotting_utils.process_results({'inference' : inferences['universal'], 'track' : args.test}, postfix = 'universal')
        if inferences['singular'] :
            plotting_utils.process_results({'inference' : inferences['singular'], 'track' : args.test}, postfix = 'singular')
        # create a CSV for the output
        pd.DataFrame.from_dict(create_table(inferences,hurricane)
                              ).to_csv(f'results/inferences_{[* hurricane.entries][-1].strftime("%Y_%m_%d_%H_%M")}.csv')