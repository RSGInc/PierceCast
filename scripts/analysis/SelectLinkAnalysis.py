import time
import os,sys
import h5py
import inro.emme.database.emmebank as _eb
from multiprocessing import Pool
import logging
import traceback
sys.path.append(os.path.join(os.getcwd(),"scripts"))
sys.path.append(os.path.join(os.getcwd(),"scripts", "skimming"))
sys.path.append(os.path.join(os.getcwd(),"inputs"))
sys.path.append(os.getcwd())
from emme_configuration import *
from EmmeProject import *
from data_wrangling import json_to_dictionary
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

def expand_daily_bank(daily_bank_path):
     #Function to perform select link analysis
     select_link_specification = json_to_dictionary("select_link_analysis", "auto")

     # Change dimensions based on the number of select link analysis that need to be performed.
     bank_dimensions = json_to_dictionary("emme_bank_dimensions")
     my_user_classes = json_to_dictionary("user_classes")
     traffic_classes = len(my_user_classes['Highway'])

     bank_dimensions['extra_attribute_values'] = (len(select_link_tods) * len(select_link) * (((bank_dimensions['links']+1)*(traffic_classes+3))+((bank_dimensions['turn_entries'] +1)*(traffic_classes+3)))) + bank_dimensions['extra_attribute_values']
     bank_dimensions['full_matrices'] = (len(select_link_tods) * len(select_link) * traffic_classes) + bank_dimensions['full_matrices']

     # Change dimension of the daily bank to hold the results
     _eb.change_dimensions(daily_bank_path, bank_dimensions, keep_backup=False)

def export_daily_network(network):
    _attribute_list = network.attributes('LINK')
    _attribute_list = [att_name for att_name in _attribute_list if '@sl' in att_name or '@psl' in att_name]  

    network_data = {k: [] for k in _attribute_list}
    i_node_list = []
    j_node_list = []
    for link in network.links():
        for colname, array in network_data.items():
            if colname != 'modes':
                try:
                    network_data[colname].append(link[colname])  
                except:
                    network_data[colname].append(0)
        i_node_list.append(link.i_node.id)
        j_node_list.append(link.j_node.id)

    network_data['i_node'] = i_node_list
    network_data['j_node'] = j_node_list
    df = pd.DataFrame.from_dict(network_data)
    df['ij'] = df['i_node'].astype('str') + '-' + df['j_node'].astype('str')
    return df


def add_sla_results_to_daily_bank(project_name):
     my_project = EmmeProject(project_name)
     daily_network = my_project.current_scenario.get_network()
     full_matrix_names = [mat.name for mat in my_project.bank.matrices() if 'seldem' in mat.name]
     full_attribute_names = [att.name for att in  my_project.current_scenario.extra_attributes() if 'sl' in att.name]
     daily_matrices = {}
     first_iter = True
     for tod in select_link_tods:
         print('Adding {} to the Daily Bank'.format(tod))
         path = os.path.join('Banks', tod, 'emmebank')
         bank = _eb.Emmebank(path)
         scenario = bank.scenario(1002)
         # Get all the selected demand matrices
         daily_matrix_names = [mat.name for mat in bank.matrices() if 'seldem' in mat.name]
         # Create select demand matrices in the daily bank
         for daily_matrix_name in daily_matrix_names:
             if daily_matrix_name not in full_matrix_names:
                my_project.create_matrix(daily_matrix_name, '', 'FULL')
                full_matrix_names.append(daily_matrix_name)
         
         # Add the selected demand to selected daily matrix total
         daily_matrices.update({mat.name: mat.get_numpy_data() + daily_matrices.get(mat.name, 0.0) for mat in bank.matrices() if 'seldem' in mat.name})

         #  Get all the link attributes
         link_attr_names = [att.name for att in scenario.extra_attributes() if '@sl' in att.name]
         daily_link_attr_names = [attr_name for attr_name in link_attr_names]
         for daily_link_attr_name in daily_link_attr_names:
             if daily_link_attr_name not in full_attribute_names:
                my_project.create_extra_attribute('LINK', daily_link_attr_name, '')
                daily_network.create_attribute('LINK', daily_link_attr_name)
                full_attribute_names.append(daily_link_attr_name)
             if first_iter:
                my_project.delete_extra_attribute(daily_link_attr_name)
                my_project.create_extra_attribute('LINK', daily_link_attr_name, '')
                daily_network.delete_attribute('LINK', daily_link_attr_name)
                daily_network.create_attribute('LINK', daily_link_attr_name)
         


         #  Get all the turn attributes
         turn_attr_names = [att.name for att in scenario.extra_attributes() if '@psl' in att.name]
         daily_turn_attr_names = [attr_name for attr_name in turn_attr_names]
         for daily_turn_attr_name in daily_turn_attr_names:
             if daily_turn_attr_name not in full_attribute_names:
                my_project.create_extra_attribute('TURN', daily_turn_attr_name, '')
                daily_network.create_attribute('TURN', daily_turn_attr_name)
                full_attribute_names.append(daily_turn_attr_name)
             if first_iter:
                my_project.delete_extra_attribute(daily_turn_attr_name)
                my_project.create_extra_attribute('TURN', daily_turn_attr_name, '')
                daily_network.delete_attribute('TURN', daily_turn_attr_name)
                daily_network.create_attribute('TURN', daily_turn_attr_name)         

         if first_iter:
             first_iter=False
                  
         for att in link_attr_names:
             if '@sl' in att:
                 #  Create a temporary variable to hold value and then add to the original one.
                 tod_value = scenario.get_attribute_values('LINK', [att])
                 temp_att = att + 't'
                 daily_network.create_attribute('LINK', temp_att)
                 daily_network.set_attribute_values('LINK', [temp_att], tod_value)
                 if 'tveh' in att:
                    att_name = '@sl_tveh_' + tod
                    if att_name in daily_network.attributes('LINK'):
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('LINK', att_name, '')
                        daily_network.create_attribute('LINK', att_name)
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)
                 if 'med' in att:
                    att_name = '@sl_mtrk_' + tod
                    if att_name in daily_network.attributes('LINK'):
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('LINK', att_name, '')
                        daily_network.create_attribute('LINK', att_name)
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)
                 if 'hvy' in att:
                    att_name = '@sl_htrk_' + tod
                    if att_name in daily_network.attributes('LINK'):
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('LINK', att_name, '')
                        daily_network.create_attribute('LINK', att_name)
                        daily_network.set_attribute_values('LINK', [att_name], tod_value)

                 for link in daily_network.links():
                     link[att] = link[att] + link[temp_att]
                 
                 daily_network.delete_attribute('LINK',temp_att)

         for att in turn_attr_names:
             if '@psl' in att:
                 #  Create a temporary variable to hold value and then add to the original one.
                 tod_value = scenario.get_attribute_values('TURN', [att])
                 temp_att = att + 't'       
                 daily_network.create_attribute('TURN', temp_att)
                 daily_network.set_attribute_values('TURN', [temp_att], tod_value)
                 if 'tveh' in att:
                    att_name = '@psl_tveh_' + tod
                    if att_name in daily_network.attributes('TURN'):
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('TURN', att_name, '')
                        daily_network.create_attribute('TURN', att_name)
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)
                 if 'med' in att:
                    att_name = '@psl_mtrk_' + tod
                    if att_name in daily_network.attributes('TURN'):
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('TURN', att_name, '')
                        daily_network.create_attribute('TURN', att_name)
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)
                 if 'hvy' in att:
                    att_name = '@psl_htrk_' + tod
                    if att_name in daily_network.attributes('TURN'):
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)
                    else:
                        my_project.create_extra_attribute('TURN', att_name, '')
                        daily_network.create_attribute('TURN', att_name)
                        daily_network.set_attribute_values('TURN', [att_name], tod_value)

                 for turn in daily_network.turns():
                     turn[att] = turn[att] + turn[temp_att]
                 
                 daily_network.delete_attribute('TURN',temp_att)
                  
     my_project.current_scenario.publish_network(daily_network)
     #  Add matrices to the daily bank
     for matrix in my_project.bank.matrices():
         if 'seldem' in matrix.name:
             matrix.set_numpy_data(daily_matrices[matrix.name])

     daily_network = my_project.current_scenario.get_network()
     network_df = export_daily_network(daily_network)
     network_df.to_csv('outputs/sla_results/daily_network.csv', index=False)

    #  # Add up all the vehicles and store it in the database
    #  att = '@sl_tveh'
    #  if att in daily_network.attributes('LINK'):
    #     my_project.delete_extra_attribute(att)
    #     my_project.create_extra_attribute('LINK', att, '')
    #     daily_network.delete_attribute('LINK', att)
    #     daily_network.create_attribute('LINK', att)
    #  else:
    #     my_project.create_extra_attribute('LINK', att, '')
    #     daily_network.create_attribute('LINK', att)
     
    #  link_expr = ' + '.join([t_att for t_att in daily_network.attributes('LINK') if '@sl' in t_att and 'tveh' not in t_att and 'link' not in t_att])
    #  my_project.network_calculator("link_calculation", result=att, expression=link_expr, selections_by_link='all')

    #  # Add up all the vehicles and store it in the database
    #  att = '@psl_tveh'
    #  if att in daily_network.attributes('TURN'):
    #     my_project.delete_extra_attribute(att)
    #     my_project.create_extra_attribute('TURN', att, '')
    #     daily_network.delete_attribute('TURN', att)
    #     daily_network.create_attribute('TURN', att)
    #  else:
    #     my_project.create_extra_attribute('TURN', att, '')
    #     daily_network.create_attribute('TURN', att)
     
    #  turn_expr = ' + '.join([t_att for t_att in daily_network.attributes('TURN') if '@psl' in t_att and 'tveh' not in t_att and 'link' not in t_att and 'trk' not in t_att])
    #  NAMESPACE = "inro.emme.network_calculation.network_calculator"
    #  network_calc = my_project.m.tool(NAMESPACE)
    #  spec = json_to_dictionary(os.path.join('lookup','link_calculation'))
    #  spec['result'] = att
    #  spec['expression'] = turn_expr
    #  spec['selections'] = {'incoming_link': 'all', 'outgoing_link': 'all'}
    #  my_project.network_calc_result = network_calc(spec)

     return True

def run_select_link(project_name):
     #Function to perform select link analysis
     select_link_specification = json_to_dictionary("select_link_analysis", "auto")

     # Change dimensions based on the number of select link analysis that need to be performed.
    #  bank_dimensions = json_to_dictionary("emme_bank_dimensions")
     my_user_classes = json_to_dictionary("user_classes")
    #  traffic_classes = len(my_user_classes['Highway'])
     
    #  bank_dimensions['extra_attribute_values'] = (len(select_link) * (((bank_dimensions['links']+1)*(traffic_classes+1))+((bank_dimensions['turn_entries'] +1)*(traffic_classes)))) + bank_dimensions['extra_attribute_values']
    #  bank_dimensions['full_matrices'] = (len(select_link) * traffic_classes) + bank_dimensions['full_matrices']

    #  # Change dimension of the bank to do select link analysis
    #  _eb.change_dimensions(bank_path, bank_dimensions, keep_backup=True)

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

        tveh_att_name = '@sl_tveh_' + suffix
        if tveh_att_name not in [att.name for att in my_project.current_scenario.extra_attributes()]:
            my_project.create_extra_attribute("LINK", tveh_att_name, 'Total vehicles in select link analysis')
        link_expr = ' + '.join([att.name for att in my_project.current_scenario.extra_attributes() if '@sl' in att.name and 'link' not in att.name and 'tveh' not in att.name])
        my_project.network_calculator("link_calculation", result=tveh_att_name, expression=link_expr, selections_by_link='all')

        tveh_att_name = '@psl_tveh_' + suffix
        if tveh_att_name not in [att.name for att in my_project.current_scenario.extra_attributes()]:
            my_project.create_extra_attribute("TURN", tveh_att_name, 'Total vehicles in select link analysis')
        turn_expr = ' + '.join([att.name for att in my_project.current_scenario.extra_attributes() if '@psl' in att.name and 'link' not in att.name and 'tveh' not in att.name])
        NAMESPACE = "inro.emme.network_calculation.network_calculator"
        network_calc = my_project.m.tool(NAMESPACE)
        turn_spec = json_to_dictionary(os.path.join('lookup','link_calculation'))
        turn_spec['result'] = tveh_att_name
        turn_spec['expression'] = turn_expr
        turn_spec['selections'] = {'incoming_link': 'all', 'outgoing_link': 'all'}
        my_project.network_calc_result = network_calc(turn_spec)
        
        tveh_matrix_name = 'seldem_tveh_' + suffix
        if tveh_matrix_name not in full_matrix_names:
            my_project.create_matrix(tveh_matrix_name, 'Selected demand for all vehicles', 'FULL')
        matrix_id = my_project.bank.matrix(seldem).id
        matrix_expr = ' + '.join([classes['analysis']['results']['selected_demand'] for classes in select_link_specification["classes"]])
        my_project.matrix_calculator(result=matrix_id, expression=matrix_expr)
    
     return True

def start_pool(select_link_project_list):
    #An Emme databank can only be used by one process at a time. Emme Modeler API only allows one instance of Modeler and
    #it cannot be destroyed/recreated in same script. In order to run things con-currently in the same script, must have
    #seperate projects/banks for each time period and have a pool for each project/bank.
    #Fewer pools than projects/banks will cause script to crash.
    pool = Pool(processes=len(select_link_project_list))
    pool_list = pool.map(run_select_link_parallel_wrapped,select_link_project_list[0:len(select_link_project_list)])
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

def run_select_link_parallel_wrapped(project_name):
    try:
        pool_list = run_select_link(project_name)
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
    # Start Select Link Analysis
    # This code is organized around the time periods for which we run select_link_analysis, 
    # often represented by the variable "tod". This variable will always
    # represent a Time of Day string, such as 6to7, 7to8, 9to10, etc.
    start_of_run = time.time()
    pool_list = []
    select_link_project_list = [os.path.join('Projects', select_link_tod, select_link_tod + '.emp') for select_link_tod in select_link_tods]
    # select_link_bank_list = [os.path.join('Banks', select_link_tod, 'emmebank') for select_link_tod in select_link_tods]
    select_link_parallel_num = len(select_link_project_list)
    for i in range(0, len(select_link_project_list), select_link_parallel_num):
        lp = select_link_project_list[i:i+select_link_parallel_num]
        pool_list.append(start_pool(lp))

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
    
    text = "Emme Select Link Analysis completed normally"
    print(text)
    logging.debug(text)
    # This is where the daily bank will be updated
    # daily_bank_path = os.path.join(os.getcwd(), 'Banks', 'Daily', 'emmebank')
    # expand_daily_bank(daily_bank_path)
    project_name = os.path.join(os.getcwd(), 'projects', 'Daily', 'Daily.emp')
    add_sla_results_to_daily_bank(project_name)
    text = "Added select link analysis results to the daily bank"
    print(text)
    logging.debug(text)
    end_of_run = time.time()
    text = 'The Total Time for all processes took', round((end_of_run-start_of_run)/60,2), 'minutes to execute.'
    print(text)
    logging.debug(text)

if __name__ == "__main__":
    main()
