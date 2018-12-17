﻿#Copyright [2014] [Puget Sound Regional Council]

#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import os,sys,datetime,re
import subprocess
import inro.emme.desktop.app as app
import json
from shutil import copy2 as shcopy
from distutils import dir_util
import re
import inro.emme.database.emmebank as _eb
import random
import shutil
import h5py
sys.path.append(os.path.join(os.getcwd(),"inputs"))
sys.path.append(os.getcwd())
from input_configuration import *
from logcontroller import *
from input_configuration import *
from emme_configuration import *
import pandas as pd
from emme_configuration import *
import emme_configuration
import input_configuration
import glob

def multipleReplace(text, wordDict):
    for key in wordDict:
        text = text.replace(key, wordDict[key])
    return text

@timed
def copy_daysim_code():
    print 'Copying Daysim executables...'
    if not os.path.exists(os.path.join(os.getcwd(), 'daysim')):
       os.makedirs(os.path.join(os.getcwd(), 'daysim'))
    try:
        dir_util.copy_tree(daysim_code, 'daysim')
    except Exception as ex:
        template = "An exception of type {0} occured. Arguments:\n{1!r}"
        message = template.format(type(ex).__name__, ex.args)
        print message
        sys.exit(1)

@timed
def copy_seed_skims():
    print 'You have decided to start your run by copying seed skims that Daysim will use on the first iteration. Interesting choice! This will probably take around 15 minutes because the files are big. Starting now...'
    if not(os.path.isdir(scenario_inputs+'/seed_skims')):
           print 'It looks like you do not hava directory called' + scenario_inputs+'/seed_skims, where the code is expecting the files to be. Please make sure to put your seed_skims there.'
    for filename in glob.glob(os.path.join(scenario_inputs+'/seed_skims', '*.*')):
        shutil.copy(filename, 'inputs')
    print 'Done copying seed skims.'

def text_to_dictionary(dict_name):
    input_filename = os.path.join('inputs/model/skim_parameters/',dict_name+'.json').replace("\\","/")
    my_file = open(input_filename)
    my_dictionary = {}

    for line in my_file:
        k, v = line.split(':')
        my_dictionary[eval(k)] = v.strip()

    return(my_dictionary)

def json_to_dictionary(dict_name):

    #Determine the Path to the input files and load them
    input_filename = os.path.join('inputs/model/skim_parameters/',dict_name+'.json').replace("\\","/")
    my_dictionary = json.load(open(input_filename))

    return(my_dictionary)
    
@timed    
def setup_emme_bank_folders():
    tod_dict = text_to_dictionary('time_of_day')
    emmebank_dimensions_dict = json_to_dictionary('emme_bank_dimensions')
    
    if not os.path.exists('Banks'):
        os.makedirs('Banks')
    else:
        # remove it
        print 'deleting Banks folder'
        shutil.rmtree('Banks')

    #gets time periods from the projects folder, so setup_emme_project_folder must be run first!
    time_periods = list(set(tod_dict.values()))
    time_periods.append('TruckModel')
    time_periods.append('Supplementals')
    for period in time_periods:
        print period
        print "creating bank for time period %s" % period
        os.makedirs(os.path.join('Banks', period))
        path = os.path.join('Banks', period, 'emmebank')
        emmebank = _eb.create(path, emmebank_dimensions_dict)
        emmebank.title = period
        emmebank.unit_of_length = unit_of_length
        emmebank.coord_unit_length = coord_unit_length  
        scenario = emmebank.create_scenario(1002)
        network = scenario.get_network()
        #need to have at least one mode defined in scenario. Real modes are imported in network_importer.py
        network.create_mode('AUTO', 'a')
        scenario.publish_network(network)
        emmebank.dispose()

@timed
def setup_emme_project_folders():
    emme_toolbox_path = os.path.join(os.environ['EMMEPATH'], 'toolboxes')
    #tod_dict = json.load(open(os.path.join('inputs', 'skim_params', 'time_of_day.json')))

    tod_dict = text_to_dictionary('time_of_day')
    tod_list = list(set(tod_dict.values()))

    if os.path.exists(os.path.join('projects')):
        print 'Delete Project Folder'
        shutil.rmtree('projects')

    # Create master project, associate with all tod emmebanks
    project = app.create_project('projects', master_project)
    desktop = app.start_dedicated(False, "cth", project)
    data_explorer = desktop.data_explorer()   
    for tod in tod_list:
        database = data_explorer.add_database('Banks/' + tod + '/emmebank')
    #open the last database added so that there is an active one
    database.open()
    desktop.project.save()
    desktop.close()
    shcopy(emme_toolbox_path + '/standard.mtbx', os.path.join('projects', master_project))

    # Create time of day projects, associate with emmebank
    tod_list.append('TruckModel') 
    tod_list.append('Supplementals')

    
    for tod in tod_list:
        project = app.create_project('projects', tod)
        desktop = app.start_dedicated(False, "cth", project)
        data_explorer = desktop.data_explorer()
        database = data_explorer.add_database('Banks/' + tod + '/emmebank')
        database.open()
        desktop.project.save()
        desktop.close()
        shcopy(emme_toolbox_path + '/standard.mtbx', os.path.join('projects', tod))
        
   
@timed    
def copy_scenario_inputs():
    print 'Copying scenario inputs...' 
    dir_util.copy_tree(scenario_inputs,'inputs/scenario')

@timed
def copy_large_inputs():
    print 'Copying large inputs...' 
    dir_util.copy_tree(scenario_inputs+'/networks','Inputs/networks')
    dir_util.copy_tree(scenario_inputs+'/trucks','Inputs/trucks')
    dir_util.copy_tree(scenario_inputs+'/supplemental','inputs/supplemental')
    dir_util.copy_tree(scenario_inputs+'/supplemental','inputs/supplemental')
    if run_supplemental_generation:
        shcopy(scenario_inputs+'/tazdata/tazdata.in','inputs/trucks')
    dir_util.copy_tree(scenario_inputs+'/tolls','Inputs/tolls')
    dir_util.copy_tree(scenario_inputs+'/Fares','Inputs/Fares')
    dir_util.copy_tree(scenario_inputs+'/bikes','Inputs/bikes')
    dir_util.copy_tree(base_inputs+'/observed','Inputs/observed')
    dir_util.copy_tree(base_inputs+'/corridors','inputs/corridors')
    dir_util.copy_tree(scenario_inputs+'/parking','inputs/parking')
    shcopy(scenario_inputs+'/landuse/hh_and_persons.h5','Inputs')
    shcopy(base_inputs+'/etc/survey.h5','scripts/summarize/inputs/calibration')
    
    # node to node short distance files:
    shcopy(base_inputs+'/short_distance_files/node_index_2014.txt', 'Inputs')
    shcopy(base_inputs+'/short_distance_files/node_to_node_distance_2014.h5', 'Inputs')
    shcopy(base_inputs+'/short_distance_files/parcel_nodes_2014.txt', 'Inputs')


@timed
def copy_shadow_price_file():
    print 'Copying shadow price file.' 
    if not os.path.exists('working'):
       os.makedirs('working')
    shcopy(base_inputs+'/shadow_prices/shadow_prices.txt','working')

@timed
def rename_network_outs(iter):
    for summary_name in network_summary_files:
        csv_output = os.path.join(os.getcwd(), 'outputs',summary_name+'.csv')
        if os.path.isfile(csv_output):
            shcopy(csv_output, os.path.join(os.getcwd(), 'outputs',summary_name+str(iter)+'.csv'))
            os.remove(csv_output)

@timed          
def clean_up():
    delete_files = ['working\\household.bin', 'working\\household.pk', 'working\\parcel.bin',
                   'working\\parcel.pk', 'working\\parcel_node.bin', 'working\\parcel_node.pk', 'working\\park_and_ride.bin',
                   'working\\park_and_ride_node.pk', 'working\\person.bin', 'working\\person.pk', 'working\\zone.bin',
                   'working\\zone.pk']

    for file in delete_files: 
        if(os.path.isfile(os.path.join(os.getcwd(), file))):
            os.remove(os.path.join(os.getcwd(), file))
        else:
            print file

@timed
def copy_accessibility_files():
    if run_integrated:
        import_integrated_inputs()
    else:
        if not os.path.exists('inputs/scenario/landuse'):
            os.makedirs('inputs/scenario/landuse')
        
        print 'Copying UrbanSim parcel file'
        try:
            shcopy(scenario_inputs+'/landuse/parcels_urbansim.txt','inputs/scenario/landuse')
        except:
            print 'error copying urbansim parcel file at ' + scenario_inputs + '/landuse/parcels_urbansim.txt'
            sys.exit(1)
          
        
        print 'Copying Transit stop file'
        try:      
            shcopy(scenario_inputs+'/networks/transit/transit_stops.csv','inputs/scenario/networks/transit')
        except:
            print 'error copying transit stops file at ' + scenario_inputs + '/networks/transit_transit_stops.csv'
            sys.exit(1)

        
        print 'Copying Military parcel file'
        try:
            shcopy(scenario_inputs+'/landuse/parcels_military.csv','inputs/scenario/landuse')
        except:
            print 'error copying military parcel file at ' + scenario_inputs+'/landuse/parcels_military.csv'
            sys.exit(1)

        
        print 'Copying JBLM file'
        try:
            shcopy(scenario_inputs+'/landuse/distribute_jblm_jobs.csv','inputs/scenario/landuse')
        except:
            print 'error copying military parcel file at ' + scenario_inputs+'/landuse/distribute_jblm_jobs.csv'
            sys.exit(1)

        
        print 'Copying Hourly and Daily Parking Files'
        if base_year != model_year: 
            try:
                shcopy(scenario_inputs+'/landuse/parking_costs.csv','inputs/scenario/landuse')
            except:
                print 'error copying parking file at' + scenario_inputs+'/landuse/parking_costs.csv'
                sys.exit(1)

def find_inputs(base_directory, save_list):
    for root, dirs, files in os.walk(base_directory):
        for file in files:
            if '.' in file:
                save_list.append(file)

def build_output_dirs():
    for path in ['outputs',r'outputs/daysim','outputs/bike','outputs/network','outputs/transit','outputs/landuse','outputs/emissions']:
        if not os.path.exists(path):
            os.makedirs(path)

def import_integrated_inputs():
    """
    Convert Urbansim input file into separate files:
    - parcels_urbansim.txt
    - hh_and_persons.h5
    """

    print "Importing land use files from urbansim"

    # Copy soundcast inputs and separate input files
    h5_inputs_dir = os.path.join(urbansim_outputs_dir,model_year,'soundcast_inputs.h5')
    shcopy(h5_inputs_dir,r'inputs/scenario/landuse/hh_and_persons.h5')

    h5_inputs = h5_inputs = h5py.File('inputs/scenario/landuse/hh_and_persons.h5')

    # Export parcels file as a txt file input
    parcels = pd.DataFrame()
    for col in h5_inputs['parcels'].keys():
        parcels[col] = h5_inputs['parcels'][col][:]
        
    parcels.to_csv(r'inputs/scenario/landuse/parcels_urbansim.txt', sep=' ', index=False)

    # Delete parcels group
    del h5_inputs['parcels']

def update_skim_parameters():
    """
    Update user classes to include only defined modes (AVs, TNCs)
    Skim parameters are generated from full-size templates.
    """

    # Based on toggles from input_configuration, remove modes if not used
    # from user_class and demand matrix list in skim_parameters input folder.

    keywords = []
    if not include_av:
        keywords.append('av_')
    if not include_tnc:
        keywords.append('tnc_')

    root_path = os.path.join(os.getcwd(),r'inputs/model/skim_parameters')

    for filename in ['user_classes', 'demand_matrix_dictionary']:
        new_file_path = os.path.join(root_path, filename+'.json')
        with open(os.path.join(root_path, filename+'_template.json')) as template_file, open(new_file_path, 'w') as newfile:
            for line in template_file:
                if not any(keyword in line for keyword in keywords):
                    newfile.write(line)

def update_daysim_modes():
    """
    Apply settings in input_configuration to daysim_configuration:

    include_tnc: PaidRideShareModeIsAvailable,
    include_av: AV_IncludeAutoTypeChoice,
    tnc_av: AV_PaidRideShareModeUsesAVs 
    """

    # Store values from input_configuration in a dictionary:
    av_settings = ['include_av', 'include_tnc', 'tnc_av']

    daysim_dict = {
        'AV_IncludeAutoTypeChoice': 'include_av',
        'PaidRideShareModeIsAvailable':'include_tnc',
        'AV_PaidRideShareModeUsesAVs': 'tnc_av',
    }

    mode_config_dict = {}    
    for setting in av_settings:
        mode_config_dict[setting] = globals()[setting]
  
    # Copy temp file to use 
    daysim_config_path = os.path.join(os.getcwd(),'daysim_configuration_template.properties')
    new_file_path = os.path.join(os.getcwd(),'daysim_configuration_template_tmp.properties')

    with open(daysim_config_path) as template_file, open(new_file_path, 'w') as newfile:
        for line in template_file:
            if any(value in line for value in daysim_dict.keys()):
                var = line.split(" = ")[0]
                line = var + " = " + str(mode_config_dict[daysim_dict[var]]).lower() + "\n"
                newfile.write(line)
            else:
                newfile.write(line)

    # Replace the original file with the updated version
    try:
        os.remove(daysim_config_path)
        os.rename(new_file_path, daysim_config_path)
    except OSError as e:  ## if failed, report it back to the user ##
        print ("Error: %s - %s." % (e.filename, e.strerror))

