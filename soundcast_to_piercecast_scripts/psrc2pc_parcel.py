#Convert zones in the parcel file
#Nagendra Dhakar, nagendra.dhakar@rsginc.com, 12/22/16

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
import h5py
import numpy as np
import csv

from sqlalchemy import column

# inputs
# wd = r"E:/projects/clients/PierceCounty/GitHub/PierceCastScenarioInputs/inputs/landuse/2050/land_use_2050"
wd = r"E:/projects/clients/PierceCounty/GitHub/PierceCastScenarioInputs/inputs/landuse/2018/land_use_2018"
parcel_file = 'parcels_urbansim.txt'

# correspondence file
parcel_psrc_taz_file = r"data/psrcprcl_pctaz.csv"

# get script's directory
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
except:
    script_dir = os.getcwd()

print(script_dir)

def runPSRCtoPSRCZones():
    #read parcel file
    parcel_file_path = os.path.join(wd, parcel_file)
    parcels_psrc = pd.read_csv(parcel_file_path, sep = " ")
    parcels_fields = list(parcels_psrc.columns)

    #read parcel to psrc taz correspondence
    # parcel_psrc_taz_file_path = os.path.join(script_dir, parcel_psrc_taz_file)
    parcel_psrc_taz = pd.read_csv(parcel_psrc_taz_file).rename(columns={'ParcelID':'parcelid', 'TAZ_PC':'TAZNUM'})

    #merge psrc taz to parcel file
    parcels_psrc = pd.merge(parcels_psrc, parcel_psrc_taz, left_on = 'parcelid', right_on = 'parcelid')
    parcels_psrc['taz_p'] = parcels_psrc['TAZNUM'].astype(np.int32)
    parcels_psrc = parcels_psrc[parcels_fields]
    parcels_psrc = parcels_psrc.sort_values(by = ['parcelid'], ascending=[True])

    if len(parcels_psrc) != len(parcels_psrc[~parcels_psrc.taz_p.isna()]):
        print('ERROR: some parcels do not have a psrc taz assigned')
    else:
        #write out the updated parcel file
        parcel_file_out = parcel_file.split(".")[0]+ "_pc.txt"
        parcel_file_out_path = os.path.join(wd, parcel_file_out)
        parcels_psrc.to_csv(parcel_file_out_path, sep = ' ', index = False,  line_terminator='\n')

if __name__== "__main__":
    print('started ...')
    runPSRCtoPSRCZones()
    print('finished!')

