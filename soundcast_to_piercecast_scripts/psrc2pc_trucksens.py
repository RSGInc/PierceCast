#Convert PSRC zones to BKR zones (one to one relation - take the max area)
#Nagendra Dhakar, nagendra.dhakar@rsginc.com, 09/14/16

#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.


# NOTE:
# Added special generator data manually
# copy pasted thecorresponding zone data in soundacast

import os, shutil
import pandas as pd
import h5py
import numpy as np
import csv

#inputs
wd = r'E:\projects\clients\PierceCounty\GitHub\PierceCast\inputs\model\trucks'
truck_file = r'truck_districts.ens'

#Cross walk file
pc_psrc_taz = r'data/psrctaz_pctaz.csv'
xwalk = pd.read_csv(pc_psrc_taz).rename(columns={'taz_psrc':'taz', 'taz_pc':'taz_pc'}).drop(columns='pctshare')

def runTruckDistrictsEns():
    print('processing: ' + truck_file )
    # read psrc zone group file
    external_zone_start = 3700
    outfile = os.path.join(wd,truck_file.split('.')[0] + '_pc.ens')
    psrcFileName = os.path.join(wd, truck_file)
    #read header - use "#" as seperator as it is less likely to present in the file
    truck_districts_header = pd.read_table(psrcFileName, delimiter = "#", header = None, nrows = 2)
    ttdata = pd.read_table(psrcFileName, delimiter=" ", header=None, skiprows=2, names=['c', 'districts', 'Zone_id'])
    tazdata_pc = xwalk.merge(ttdata,how='left', left_on='taz', right_on='Zone_id')
    tazdata_pc = tazdata_pc.fillna(0)
    tazdata_pc['Zone_id'] = tazdata_pc['taz_pc']
    tazdata_pc = tazdata_pc[["c", "districts", "Zone_id"]].drop_duplicates()
    tazdata_pc = tazdata_pc.groupby('Zone_id', as_index=False).first()[["c", "districts", "Zone_id"]]
    tazdata_pc = pd.concat([tazdata_pc, ttdata[ttdata.Zone_id > external_zone_start]], axis=0, ignore_index=True)
    truck_districts_header.to_csv(outfile, sep = '#', header = False, index = False, \
        quoting=csv.QUOTE_NONE, quotechar='"', line_terminator='\n') #had to add space as escapechar otherwise throws an error
    with open(outfile, 'a') as file:
        tazdata_pc.to_csv(file, sep = " " , header = False, index = False, line_terminator='\n')

if __name__== "__main__":
    runTruckDistrictsEns()

