import array as _array
import inro.emme.desktop.app as app
import inro.modeller as _m
import inro.emme.matrix as ematrix
import inro.emme.database.matrix
import inro.emme.database.emmebank as _eb
import json
import numpy as np
import time
import os,sys
import h5py
import shutil
import multiprocessing as mp
import subprocess
from multiprocessing import Pool
import logging
import datetime
import argparse
import traceback
sys.path.append(os.path.join(os.getcwd(),"scripts"))
sys.path.append(os.path.join(os.getcwd(),"scripts", "skimming"))
sys.path.append(os.path.join(os.getcwd(),"inputs"))
sys.path.append(os.getcwd())
from emme_configuration import *
from EmmeProject import *
from data_wrangling import text_to_dictionary, json_to_dictionary
from SkimsAndPaths import emmeMatrix_to_numpyMatrix

#Create a logging file to report model progress
logging.basicConfig(filename=log_file_name, level=logging.DEBUG)

#Report model starting
current_time = str(time.strftime("%H:%M:%S"))
logging.debug('----Began SelectLinkAnalysis script at ' + current_time)

def create_hdf5_demand_container(hdf5_name):
    #create containers for TOD skims
    start_time = time.time()

    hdf5_filename = os.path.join('outputs/sla_results', hdf5_name +'.h5').replace("\\","/")

    # IOError will occur if file already exists with "w-", so in this case
    # just prints it exists. If file does not exist, opens new hdf5 file and
    # create groups based on the subgroup list above.

    # Create a sub groups with the same name as the container, e.g. 5to6, 7to8
    # These facilitate multi-processing and will be imported to a master HDF5 file
    # at the end of the run

    if not os.path.exists(hdf5_filename):
        my_store=h5py.File(hdf5_filename, "w-")
        my_store.create_group(hdf5_name)
        my_store.close()

    end_time = time.time()
    text = 'It took ' + str(round((end_time-start_time),2)) + ' seconds to create the HDF5 file.'
    logging.debug(text)
    return hdf5_filename

def run_select_link(project_name, bank_path):
    #Function to perform select link analysis
     select_link_specification = json_to_dictionary("select_link_analysis", "auto")

     # Change dimensions based on the number of select link analysis that need to be performed.
     bank_dimensions = json_to_dictionary("emme_bank_dimensions")
     my_user_classes = json_to_dictionary("user_classes")
     traffic_classes = len(my_user_classes['Highway'])
     
     bank_dimensions['extra_attribute_values'] = (len(select_link) * (((bank_dimensions['links']+1)*(traffic_classes+1))+((bank_dimensions['turn_entries'] +1)*(traffic_classes)))) + bank_dimensions['extra_attribute_values']
     bank_dimensions['full_matrices'] = (len(select_link) * traffic_classes) + bank_dimensions['full_matrices']

     # Change dimension of the bank to do select link analysis
     _eb.change_dimensions(bank_path, bank_dimensions, keep_backup=True)

     my_project = EmmeProject(project_name)

     analyze = my_project.m.tool("inro.emme.traffic_assignment.path_based_traffic_analysis")
     
     for sub_spec in select_link:
        expr = sub_spec["expression"]
        suffix = sub_spec["suffix"]
        if not expr and not suffix:
            continue        
        slink_id = "@slink_%s" % suffix
        slink_desc = "selected link for %s" % suffix
        if slink_id not in [att.name for att in my_project.current_scenario.extra_attributes()]:
            my_project.create_extra_attribute("LINK", slink_id, slink_desc)
        my_project.network_calculator("link_calculation", result=slink_id, expression="1", selections_by_link=expr)   
    
        select_link_specification["path_analysis"]["link_component"] = slink_id

        full_matrix_names = [mat.name for mat in my_project.bank.matrices() if 'seldem' in mat.name]

        for x in range (0, len(select_link_specification["classes"])):
            att_name = ("@sl_%s_%s" % (my_user_classes["Highway"][x]["Name"].lower(), suffix)).replace('truck','trk').replace('medium','med').replace('heavy','hvy')
            att_des = "%s '%s' sel link flow"% (my_user_classes["Highway"][x]["Name"], suffix)
            link_flow = att_name
            if att_name not in [att.name for att in my_project.current_scenario.extra_attributes()]:
                my_project.create_extra_attribute("LINK", att_name, att_des)

            att_name = ("@psl_%s_%s" % (my_user_classes["Highway"][x]["Name"].lower(), suffix)).replace('truck','trk').replace('medium','med').replace('heavy','hvy')
            att_des = "%s '%s' sel turn flow"% (my_user_classes["Highway"][x]["Name"], suffix)
            turn_flow = att_name
            if att_name not in [att.name for att in my_project.current_scenario.extra_attributes()]:
                my_project.create_extra_attribute("TURN", att_name, att_des)

            name = ("seldem_%s_%s" % (my_user_classes["Highway"][x]["Name"], suffix)).replace('truck','trk').replace('medium','med').replace('heavy','hvy')
            desc = "Selected demand for %s %s" % (my_user_classes["Highway"][x]["Name"], suffix)
            seldem = name
            if seldem not in full_matrix_names:
                text = my_project.tod + ': ' + 'Creating Matrix: ' + seldem
                print(text)
                logging.debug(text)
                my_project.create_matrix(seldem, desc, 'FULL')
            matrix_id = my_project.bank.matrix(seldem).id
            select_link_specification["classes"][x]["analysis"]["results"]["selected_demand"] = matrix_id
            select_link_specification["classes"][x]["analysis"]["results"]["selected_link_volumes"] = link_flow         
            select_link_specification["classes"][x]["analysis"]["results"]["selected_turn_volumes"] = turn_flow         
        
        analyze(select_link_specification)
    
     return True
    

def start_pool(select_link_project_list, select_link_bank_list):
    #An Emme databank can only be used by one process at a time. Emme Modeler API only allows one instance of Modeler and
    #it cannot be destroyed/recreated in same script. In order to run things con-currently in the same script, must have
    #seperate projects/banks for each time period and have a pool for each project/bank.
    #Fewer pools than projects/banks will cause script to crash.
    pool = Pool(processes=len(select_link_project_list))
    pool_list = pool.starmap(run_select_link_parallel_wrapped,zip(select_link_project_list[0:len(select_link_project_list)],select_link_bank_list[0:len(select_link_project_list)]))
    pool.close()

    return pool_list

def export_pool(select_link_project_list):
    #An Emme databank can only be used by one process at a time. Emme Modeler API only allows one instance of Modeler and
    #it cannot be destroyed/recreated in same script. In order to run things con-currently in the same script, must have
    #seperate projects/banks for each time period and have a pool for each project/bank.
    #Fewer pools than projects/banks will cause script to crash.
    pool = Pool(processes=len(select_link_project_list))
    pool_list = pool.map(run_select_link_export_parallel_wrapped,select_link_project_list[0:len(select_link_project_list)])
    pool.close()

    return pool_list

def start_export_to_hdf5(select_link_project_list):
    #An Emme databank can only be used by one process at a time. Emme Modeler API only allows one instance of Modeler and
    #it cannot be destroyed/recreated in same script. In order to run things con-currently in the same script, must have
    #seperate projects/banks for each time period and have a pool for each project/bank.
    #Fewer pools than projects/banks will cause script to crash.
    pool = Pool(processes=len(select_link_project_list))
    pool_list = pool.map(start_export_to_hdf5_parallel_wrapped,select_link_project_list[0:len(select_link_project_list)])
    pool.close()

    return pool_list

def run_select_link_parallel_wrapped(project_name, bank_path):
    try:
        pool_list = run_select_link(project_name, bank_path)
    except:
        print('%s: %s' % (project_name, traceback.format_exc()))

    return pool_list

def run_select_link_export_parallel_wrapped(project_name):
    pool_list = []
    try:
        pool_list = export_select_link_results(project_name)
    except:
        print('%s: %s' % (project_name, traceback.format_exc()))

    return pool_list

def start_export_to_hdf5_parallel_wrapped(project_name):
    pool_list = []
    try:
        pool_list = export_demand_to_hdf5(project_name)
    except:
        print('%s: %s' % (project_name, traceback.format_exc()))

    return pool_list

def export_demand_to_hdf5(project_name):

    start_export_hdf5 = time.time()
    my_project = EmmeProject(project_name)
    hdf5_filename = create_hdf5_demand_container(my_project.tod)
    my_store = h5py.File(hdf5_filename, "r+")
    e = "SELDEM" in my_store
    #Now delete "Skims" store if exists   
    if e:
        del my_store["SELDEM"]
        skims_group = my_store.create_group("SELDEM")
        #If not there, create the group
    else:
        skims_group = my_store.create_group("SELDEM")
    
    # First Store a Dataset containing the Indicices for the Array to Matrix using mf01
    try:
        mat_id = my_project.bank.matrix("mf01")
        emme_matrix = my_project.bank.matrix(mat_id)
        em_val = emme_matrix.get_data()
        my_store["SELDEM"].create_dataset("indices", data=em_val.indices, compression='gzip')

    except RuntimeError:
        del my_store["SELDEM"]["indices"]
        my_store["SELDEM"].create_dataset("indices", data=em_val.indices, compression='gzip')
    
    # Selected demand matrix names
    full_matrix_names = [mat.name for mat in my_project.bank.matrices() if 'seldem' in mat.name]

    for matrix_name in full_matrix_names:
        matrix_id = my_project.bank.matrix(matrix_name).id
        matrix_value = emmeMatrix_to_numpyMatrix(matrix_name, my_project.bank, 'float32', 1, 99999)
        
        #delete old skim so new one can be written out to h5 container
        my_store["SELDEM"].create_dataset(matrix_name, data=matrix_value.astype('float32'),compression='gzip')
        print(matrix_name+' was transferred to the HDF5 container.')
    
    my_store.close()
    end_export_hdf5 = time.time()
    print('It took', round((end_export_hdf5-start_export_hdf5)/60,2), ' minutes to export all selected demand to the HDF5 File.')
    text = 'It took ' + str(round((end_export_hdf5-start_export_hdf5)/60,2)) + ' minutes to import matrices to Emme.'
    logging.debug(text)

def export_network_sla_results(network):
    """ Calculate link-level results by time-of-day, append to csv """

    _attribute_list = network.attributes('LINK')  
    _attribute_list = [_attribute for _attribute in _attribute_list if '@sl' in _attribute]

    network_data = {k: [] for k in _attribute_list}
    i_node_list = []
    j_node_list = []
    network_data['modes'] = []
    for link in network.links():
        for colname, _ in network_data.items():
            if colname != 'modes':
                try:
                    network_data[colname].append(link[colname])  
                except:
                    network_data[colname].append(0)
        i_node_list.append(link.i_node.id)
        j_node_list.append(link.j_node.id)
        network_data['modes'].append(link.modes)   
    network_data['i_node'] = i_node_list
    network_data['j_node'] = j_node_list
    return pd.DataFrame.from_dict(network_data)

def export_select_link_results(project_name):
    my_project = EmmeProject(project_name)
    # Export link-level results for multiple attributes
    network = my_project.current_scenario.get_network()
    network_df = export_network_sla_results(network)
    network_df['ij'] = network_df['i_node'].astype('str') + '-' + network_df['j_node'].astype('str')
    network_df['modes'] = network_df['modes'].apply(lambda x: ''.join(list([j.id for j in x])))  
    network_df['tod'] = my_project.tod
    network_df = network_df[~network_df.modes.isin(['xk','kx'])]
    network_df.to_csv('outputs/sla_results/link_results_'+my_project.tod+'.csv', index=False)
    return network_df


def main():
    # Remove strategy output directory if it exists; for first assignment, do not add results to existing volumes

    # Start Select Link Analysis
    # This code is organized around the time periods for which we run select_link_analysis, 
    # often represented by the variable "tod". This variable will always
    # represent a Time of Day string, such as 6to7, 7to8, 9to10, etc.
    start_of_run = time.time()
    pool_list = []
    select_link_project_list = [os.path.join('Projects', select_link_tod, select_link_tod + '.emp') for select_link_tod in select_link_tods]
    select_link_bank_list = [os.path.join('Banks', select_link_tod, 'emmebank') for select_link_tod in select_link_tods]
    select_link_parallel_num = len(select_link_project_list)
    for i in range(0, len(select_link_project_list), select_link_parallel_num):
        lp = select_link_project_list[i:i+select_link_parallel_num]
        lb = select_link_bank_list[i:i+select_link_parallel_num]
        pool_list.append(start_pool(lp, lb))

    if not os.path.exists(os.path.join(os.getcwd(), 'outputs', 'sla_results')):
        os.makedirs(os.path.join(os.getcwd(), 'outputs', 'sla_results'))
    pool_list = []
    for i in range(0, len(select_link_project_list), select_link_parallel_num):
        lp = select_link_project_list[i:i+select_link_parallel_num]
        pool_list.append(export_pool(lp))

    pool_list = []
    for i in range(0, len(select_link_project_list), select_link_parallel_num):
        lp = select_link_project_list[i:i+select_link_parallel_num]
        pool_list.append(start_export_to_hdf5(lp))
    
    end_of_run = time.time()
    text = "Emme Select Link Analysis completed normally"
    print(text)
    logging.debug(text)
    text = 'The Total Time for all processes took', round((end_of_run-start_of_run)/60,2), 'minutes to execute.'
    print(text)
    logging.debug(text)

if __name__ == "__main__":
    main()
