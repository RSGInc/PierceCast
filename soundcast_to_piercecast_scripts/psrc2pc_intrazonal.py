#Convert PSRC zones to PSRC zones (one to one relation - take the max area)
#Nagendra Dhakar, nagendra.dhakar@rsginc.com, 09/21/16

#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import os, shutil
import pandas as pd
import geopandas as gpd
import h5py
import numpy as np
import csv

# from sympy import N

# inputs
wd = r"E:\projects\clients\PierceCounty\GitHub\PierceCast\inputs\model\intrazonals"

files_list = ["origin_tt.in", "destination_tt.in", "taz_acres.in"]

#Crosswalk file
pc_psrc_taz = r'data\psrctaz_pctaz.csv'
# Requires shapefile to get area in acres
taz_shapefile = r'E:\projects\clients\PierceCounty\Data\FromClient\Zones\TAZ_Export.gdb'

    
def runPSRCtoPCZones():
    #read terminal times
    # read crosswalk between tazs
    xwalk = pd.read_csv(pc_psrc_taz)
    external_taz_start = 3700
    #number of rows in the begining of the file before the actual data - user input
    header_rows = [5, 5, 3]
    for i in range(0, len(files_list)):
        file = files_list[i]
        print ("updating: " + file)
        if i < 2:
            #psrc file
            psrcFileName = file
            psrcFileName = os.path.join(wd, psrcFileName)
            #read header - use "#" as seperator as it is less likely to present in the file
            header = pd.read_table(psrcFileName, delimiter = "#", header = None, nrows = header_rows[i])
            if i == 0:
                ttdata = pd.read_table(psrcFileName, delimiter=" ", header=None, skiprows=header_rows[i], usecols=[1,2,3], names=['Zone_id', 'c', 'termtime'])
                extdata = ttdata[ttdata.Zone_id > external_taz_start]
            else:
                ttdata = pd.read_table(psrcFileName, delimiter=" ", header=None, skiprows=header_rows[i], usecols=[1,2,3], names=['c', 'Zone_id', 'termtime'])
                ttdata['Zone_id'] = ttdata['Zone_id'].str.replace(':','').astype(int)
                extdata = ttdata[ttdata.Zone_id > external_taz_start]
                extdata['Zone_id'] = extdata["Zone_id"].astype(str) + ":"
            tazdata_pc = xwalk.merge(ttdata,how='left', left_on='taz_psrc', right_on='Zone_id')
            tazdata_pc = tazdata_pc.fillna(0)
            tazdata_pc['Zone_id'] = tazdata_pc['taz_pc'].astype(np.int32)
            tazdata_pc = tazdata_pc[["Zone_id", "c", "termtime"]]
            tazdata_pc = tazdata_pc.groupby('Zone_id', as_index=False)['termtime'].aggregate(lambda x: x.max())
            if i==0: #origin file
                tazdata_pc["c"] = "all:"
                tazdata_pc['first'] = np.nan
                tazdata_pc = tazdata_pc[["first", "Zone_id", "c", "termtime"]]
            else: #destination file
                tazdata_pc["c"] = "all" #space before the word 'all' is intentional, the model throws an error if space is not there
                tazdata_pc["Zone_id"] = tazdata_pc["Zone_id"].astype(str) + ":"
                tazdata_pc['first'] = np.nan
                tazdata_pc = tazdata_pc[["first", "c", "Zone_id", "termtime"]]
            tazdata_pc = pd.concat([tazdata_pc, extdata], axis=0, ignore_index=True)
        else:
            #psrc file
            psrcFileName = file
            psrcFileName = os.path.join(wd, psrcFileName)
            #read header - use "#" as seperator as it is less likely to present in the file
            header = pd.read_table(psrcFileName, delimiter = "#", header = None, nrows = header_rows[i])
            taz_gdf = gpd.read_file(taz_shapefile, layer='TAZ_Combo_V2')
            taz_gdf['PCAcres'] = taz_gdf.area/43560
            tazdata_pc = taz_gdf[['NEW_TAZ', 'PCAcres']].rename(columns={'NEW_TAZ':'Zone_id', 'PCAcres':'tazacr'})
            tazdata_pc['c'] = 'all:'
            tazdata_pc['first'] = np.nan
            tazdata_pc = tazdata_pc[["first", "Zone_id", "c", "tazacr"]].sort_values('Zone_id')
        # write - first header and then append the updated data
        outfile = psrcFileName.split(".")[0]
        outfile = outfile + "_pc.in"
        header.to_csv(outfile, sep = '#', header = False, index = False, quoting=csv.QUOTE_NONE, quotechar='"', line_terminator='\n') #had to add space as escapechar otherwise throws an error
        with open(outfile, 'a') as file:
            tazdata_pc.to_csv(file, sep = " ", header = False, index = False, line_terminator='\n')


if __name__== "__main__":
    runPSRCtoPCZones()

