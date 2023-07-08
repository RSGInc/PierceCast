# from curses import echo
import os, sys, shutil
import numpy as np
import pandas as pd
import sqlalchemy as db

wd = r'E:/projects/clients/PierceCounty/GitHub/PierceCastScenarioInputs/inputs/db'
db_input_file = r'soundcast_inputs.db'
pc_psrc_taz = r'data/psrctaz_pctaz.csv'
pc_psrc_prcl = r'data/psrcprcl_pctaz.csv'
enlisted_personnel = r'data/enlisted_personnel_pc.csv'


db_output_file = r'soundcast_inputs_pc.db'
conn = db.create_engine('sqlite:///'+os.path.join(wd,db_input_file))
if os.path.exists(os.path.join(wd, db_output_file)):
    os.remove(os.path.join(wd, db_output_file))
output_conn = db.create_engine('sqlite:///'+os.path.join(wd,db_output_file), echo=True)


traffic_counts = 'E:/projects/clients/PierceCounty/Tasks/Task_04_Update_Travel_Demand_Models/Task_map_traffic_counts/traffic_counts/traffic_counts_pc_new.csv'
traffic_counts_hourly = 'E:/projects/clients/PierceCounty/Tasks/Task_04_Update_Travel_Demand_Models/Task_map_traffic_counts/traffic_counts/traffic_counts_hourly_pc_new.csv'

def reindex(series1, series2):
    """
    This reindexes the first series by the second series.  This is an extremely
    common operation that does not appear to  be in Pandas at this time.
    If anyone knows of an easier way to do this in Pandas, please inform the
    UrbanSim developers.
    The canonical example would be a parcel series which has an index which is
    parcel_ids and a value which you want to fetch, let's say it's land_area.
    Another dataset, let's say of buildings has a series which indicate the
    parcel_ids that the buildings are located on, but which does not have
    land_area.  If you pass parcels.land_area as the first series and
    buildings.parcel_id as the second series, this function returns a series
    which is indexed by buildings and has land_area as values and can be
    added to the buildings dataset.
    In short, this is a join on to a different table using a foreign key
    stored in the current table, but with only one attribute rather than
    for a full dataset.
    This is very similar to the pandas "loc" function or "reindex" function,
    but neither of those functions return the series indexed on the current
    table.  In both of those cases, the series would be indexed on the foreign
    table and would require a second step to change the index.
    Parameters
    ----------
    series1, series2 : pandas.Series
    Returns
    -------
    reindexed : pandas.Series
    """
    # turns out the merge is much faster than the .loc below
    df = pd.merge(series2.to_frame(name='left'),
                  series1.to_frame(name='right'),
                  left_on="left",
                  right_index=True,
                  how="left")
    return df.right

def expandTazShares(table):    
    print("expand PSRC to PC zone crosswalk to full OD percents table")
    #replicate into expanded OD table
    od_table = pd.DataFrame()
    od_table["o"] = np.repeat(table["taz"].tolist(),len(table))
    od_table["pc_o"] = np.repeat(table["taz_pc"].tolist(),len(table))
    od_table["percent_o"] = np.repeat(table["pctshare"].tolist(),len(table))
    od_table["d"] = np.tile(table["taz"].tolist(),len(table))
    od_table["pc_d"] = np.tile(table["taz_pc"].tolist(),len(table))
    od_table["percent_d"] = np.tile(table["pctshare"].tolist(),len(table))    
    #calculat the share by OD group
    od_table["od"] = od_table["o"] * 10000 + od_table["d"]
    od_table["percent"] = od_table["percent_o"] * od_table["percent_d"]
    #od_table[(od_table.o==1) & (od_table.d==1)] #for debugging
    #od_table[(od_table.o==1) & (od_table.d==4)] #for debugging
    return(od_table)

# Read crosswalk
xwalk = pd.read_csv(pc_psrc_taz).rename(columns={'taz_psrc':'taz', 'taz_pc':'taz_pc'})
xwalkprcl = pd.read_csv(pc_psrc_prcl).rename(columns={'ParcelID':'parcelid', 'TAZ_PC':'taz_pc'})
xwalkprcl = xwalkprcl.set_index('parcelid')

# Read the traffic counts
# xwalkcountidnetworkid = pd.read_csv(traffic_countid_networkid)
if os.path.isfile(traffic_counts):
    traffic_counts_df = pd.read_csv(traffic_counts)
if os.path.isfile(traffic_counts_hourly):
    traffic_counts_hourly_df = pd.read_csv(traffic_counts_hourly)

# Read enisted personnel file
enlisted_personnel_df = pd.read_csv(enlisted_personnel)

# Read all the table names in db
db_tables = pd.read_sql("select tbl_name from 'main'.sqlite_master", con=conn)['tbl_name'].values

# Store output tables in the dictionary and update as we go along the script
output_pc_tables = {pc_key: pd.read_sql('select * from '+pc_key, con=conn).to_dict('list') for pc_key in db_tables}


# Daily counts
if os.path.isfile(traffic_counts):
    df_daily_counts = pd.DataFrame.from_dict(output_pc_tables.get('daily_counts'))
    count_columns = df_daily_counts.columns
    df_daily_counts = df_daily_counts.drop_duplicates()
    df_daily_counts = df_daily_counts[df_daily_counts.flag < traffic_counts_df.countid.min()].copy()
    orig_sums = df_daily_counts['vehicles'].sum()
    df_daily_counts_pc_df = traffic_counts_df.groupby(['countid', 'countyid'], as_index=False)['AADT'].sum()
    df_daily_counts_pc_df['year'] = 2018
    df_daily_counts_pc_df = df_daily_counts_pc_df[~df_daily_counts_pc_df.countid.isin(range(3733, 3751))]
    df_daily_counts_pc_df = df_daily_counts_pc_df.rename(columns={'countid':'flag', 'AADT':'vehicles'})
    df_daily_counts_pc_df['index'] = df_daily_counts['index'].max() + df_daily_counts_pc_df.index + 1
    df_daily_counts_pc_df = pd.concat([df_daily_counts, df_daily_counts_pc_df], ignore_index=True)
    # Change countyid for countid 2796 to 33 (incorrectly classified as 53)
    df_daily_counts_pc_df.loc[df_daily_counts_pc_df.flag==2796,'countyid'] = 33
    output_pc_tables['daily_counts'] = df_daily_counts_pc_df.to_dict('list')

# Observed external counts
#df_external_counts = pd.DataFrame.from_dict(output_pc_tables.get('observed_external_volumes'))
#count_columns = df_external_counts.columns
#df_external_counts = df_external_counts.drop_duplicates()
#orig_sums = df_external_counts['AWDT'].sum()
#df_external_counts_pc_df = traffic_counts_df.groupby(['countid', 'countyid'], as_index=False)['AADT'].sum()
#df_external_counts_pc_df = df_external_counts_pc_df[df_external_counts_pc_df.countid.isin(range(3733, 3751))]
#df_external_counts_pc_df = df_external_counts_pc_df.set_index('countid')
#df_external_counts['AWDT2'] = reindex(df_external_counts_pc_df.AADT, df_external_counts.external_station).fillna(0).astype('int')
#df_external_counts['AWDT'] = np.where((df_external_counts.AWDT2>0) & (df_external_counts.year==2018),df_external_counts.AWDT2,df_external_counts.AWDT)
#df_external_counts = df_external_counts.drop(columns='AWDT2')
#output_pc_tables['observed_external_volumes'] = df_external_counts.to_dict('list')

# Observed hourly counts
if os.path.isfile(traffic_counts) and os.path.isfile(traffic_counts_hourly):
    df_hourly_counts = pd.DataFrame.from_dict(output_pc_tables.get('hourly_counts'))
    count_columns = df_hourly_counts.columns
    df_hourly_counts = df_hourly_counts.drop_duplicates()
    df_hourly_counts = df_hourly_counts[df_hourly_counts.flag < traffic_counts_df.countid.min()].copy()
    orig_sums = df_hourly_counts['vehicles'].sum()
    df_hourly_counts_pc_df = traffic_counts_hourly_df.groupby(['countid', 'hour'], as_index=False)['vehicles'].sum()
    df_hourly_counts_pc_df = df_hourly_counts_pc_df[~df_hourly_counts_pc_df.countid.isin(range(3733, 3751))]
    df_hourly_counts_pc_df['countyid'] = 53
    df_hourly_counts_pc_df['year'] = 2018
    df_hourly_counts_pc_df = df_hourly_counts_pc_df.rename(columns={'hour':'start_hour', 'countid':'flag'})
    df_hourly_counts_pc_df['index'] = df_hourly_counts['index'].max() + df_hourly_counts_pc_df.index + 1
    df_hourly_counts_pc_df = pd.concat([df_hourly_counts, df_hourly_counts_pc_df], ignore_index=True)
    output_pc_tables['hourly_counts'] = df_hourly_counts_pc_df.to_dict('list')

# Observed screenline counts
if os.path.isfile(traffic_counts):
    df_screenline_counts = pd.DataFrame.from_dict(output_pc_tables.get('observed_screenline_volumes'))
    count_columns = df_screenline_counts.columns
    df_screenline_counts = df_screenline_counts.drop_duplicates()
    df_screenline_counts = df_screenline_counts[df_screenline_counts.county!='Pierce'].copy()
    orig_sums = df_screenline_counts['observed'].sum()
    df_screenline_counts_pc_df = traffic_counts_df.groupby(['screenlineid', 'Screenline'], as_index=False)['AADT'].sum()
    df_screenline_counts_pc_df['AADT'] = df_screenline_counts_pc_df['AADT'].astype('int')
    df_screenline_counts_pc_df['screenline_id'] = df_screenline_counts_pc_df.screenlineid
    df_screenline_counts_pc_df['index'] = df_screenline_counts_pc_df.index + 1 + df_screenline_counts['index'].max()
    df_screenline_counts_pc_df = df_screenline_counts_pc_df[['index', 'screenline_id', 'Screenline', 'AADT']].rename(columns={'Screenline':'name', 'AADT':'observed'})
    df_screenline_counts_pc_df['year'] = 2018
    df_screenline_counts_pc_df['county'] = 'Pierce'
    df_screenline_counts_pc_df = pd.concat([df_screenline_counts, df_screenline_counts_pc_df], ignore_index=True)
    output_pc_tables['observed_screenline_volumes'] = df_screenline_counts_pc_df.to_dict('list')

# External auto trips
external_taz_start = 3700
# enlisted_personnel_db_df = pd.read_sql("SELECT * FROM enlisted_personnel", con=conn)
enlisted_personnel_db_df = pd.DataFrame.from_dict(output_pc_tables.get('enlisted_personnel'))
enlisted_personnel_pc_df = enlisted_personnel_df.copy()
# enlisted_personnel_pc_df['taz_pc'] = reindex(xwalkprcl.taz_pc, enlisted_personnel_df.ParcelID.astype(int))
# enlisted_personnel_pc_df['Zone'] = enlisted_personnel_pc_df['taz_pc']
for col_name, dtype_ in enlisted_personnel_db_df.dtypes.items():
    enlisted_personnel_pc_df[col_name] = enlisted_personnel_pc_df[col_name].astype(dtype_)
orig_rows = enlisted_personnel_df.shape[0]
new_rows = enlisted_personnel_pc_df.shape[0]
columns_not_same = orig_rows!=new_rows
if columns_not_same:
    print("Didn't work: enlisted_personnel")
else:
    output_pc_tables['enlisted_personnel'] = enlisted_personnel_pc_df[enlisted_personnel_df.columns].to_dict('list')

# External nonwork trips
external_taz_start = 3700
# external_nonwork_df = pd.read_sql("SELECT * FROM external_nonwork", con=conn)
external_nonwork_df = pd.DataFrame.from_dict(output_pc_tables.get('external_nonwork'))
columns_to_adjust = [col_names for col_names in external_nonwork_df.columns if col_names != 'taz']
orig_sums = external_nonwork_df[columns_to_adjust].sum()
external_nonwork_pc_df = xwalk.merge(external_nonwork_df, how='left', on='taz')
external_nonwork_pc_df[columns_to_adjust] = external_nonwork_pc_df[columns_to_adjust].apply(lambda x: x*external_nonwork_pc_df.pctshare)
external_nonwork_pc_df = external_nonwork_pc_df.drop(columns=['taz']).rename(columns={'taz_pc':'taz'}).drop_duplicates()
external_nonwork_pc_df = external_nonwork_pc_df.groupby('taz', as_index=False)[columns_to_adjust].sum()
external_nonwork_pc_df = pd.concat([external_nonwork_pc_df, external_nonwork_df[external_nonwork_df.taz>external_taz_start]], axis=0, ignore_index=True)
for col_name, dtype_ in external_nonwork_df.dtypes.items():
    external_nonwork_pc_df[col_name] = external_nonwork_pc_df[col_name].astype(dtype_)
new_sums = external_nonwork_pc_df[columns_to_adjust].sum()
columns_not_same = [col_names for col_names in columns_to_adjust if np.abs(orig_sums[col_names]-new_sums[col_names]) > 1e-4]
if len(columns_not_same) > 0:
    print("Didn't work: external_nonwork")
else:
    output_pc_tables['external_nonwork'] = external_nonwork_pc_df[external_nonwork_df.columns].to_dict('list')

# External trip distribution
external_taz_start = 3700
# external_trip_dist = pd.read_sql('SELECT * FROM external_trip_distribution', con=conn)
external_trip_dist = pd.DataFrame.from_dict(output_pc_tables.get('external_trip_distribution'))
external_trip_dist = external_trip_dist.drop_duplicates()
groupby_col = ['GEOID', 'Large_Area', 'PSRC_TAZ', 'BKR_TAZ', 'External_Station', 'Station_Name']
ixxi_cols = ['Total_IE', 'Total_EI', 'SOV_Veh_IE', 'SOV_Veh_EI','HOV2_Veh_IE','HOV2_Veh_EI','HOV3_Veh_IE','HOV3_Veh_EI']
orig_sums = external_trip_dist[ixxi_cols].sum()
external_trip_dist = external_trip_dist.groupby(groupby_col, as_index=False, dropna=False)[ixxi_cols].sum()
external_trip_dist_pc_df = xwalk.merge(external_trip_dist.rename(columns={'PSRC_TAZ':'taz'}), how='left', on='taz')
external_trip_dist_pc_df = external_trip_dist_pc_df[~external_trip_dist_pc_df.External_Station.isna()]
external_trip_dist_pc_df[ixxi_cols] = external_trip_dist_pc_df[ixxi_cols].apply(lambda x: x*external_trip_dist_pc_df.pctshare)
external_trip_dist_pc_df = external_trip_dist_pc_df.drop(columns=['taz']).rename(columns={'taz_pc':'taz'}).drop_duplicates()
external_trip_dist_pc_df = external_trip_dist_pc_df.rename(columns={'taz':'PSRC_TAZ'})
# groupby_col = ['GEOID', 'Large_Area', 'taz', 'BKR_TAZ', 'External_Station', 'Station_Name']
external_trip_dist_pc_df = external_trip_dist_pc_df.groupby(groupby_col, as_index=False, dropna=False)[ixxi_cols].sum()
external_trip_dist_pc_df = pd.concat([external_trip_dist_pc_df, external_trip_dist[~external_trip_dist.PSRC_TAZ.isin(xwalk.taz.unique())]], axis=0, ignore_index=True)
# Do JBLM trips
jblm_trip_dist_df = xwalk.merge(external_trip_dist_pc_df.rename(columns={'External_Station':'taz'}), how='left', on='taz')
jblm_trip_dist_df = jblm_trip_dist_df[~jblm_trip_dist_df.PSRC_TAZ.isna()]
jblm_trip_dist_df[ixxi_cols] = jblm_trip_dist_df[ixxi_cols].apply(lambda x: x*jblm_trip_dist_df.pctshare)
jblm_trip_dist_df = jblm_trip_dist_df.drop(columns=['taz']).rename(columns={'taz_pc':'taz'}).drop_duplicates()
jblm_trip_dist_df = jblm_trip_dist_df.rename(columns={'taz':'External_Station'})
# groupby_col = ['GEOID', 'Large_Area', 'taz', 'BKR_TAZ', 'External_Station', 'Station_Name']
jblm_trip_dist_df = jblm_trip_dist_df.groupby(groupby_col, as_index=False, dropna=False)[ixxi_cols].sum()
external_trip_dist_pc_df = pd.concat([external_trip_dist_pc_df[~external_trip_dist_pc_df.External_Station.isin(xwalk.taz_pc.values)], jblm_trip_dist_df], axis=0, ignore_index=True)
# for col_name, dtype_ in external_trip_dist.dtypes.items():
#     external_trip_dist_pc_df[col_name] = external_trip_dist_pc_df[col_name].astype(dtype_)
new_sums = external_trip_dist_pc_df[ixxi_cols].sum()
columns_not_same = [col_names for col_names in ixxi_cols if np.abs(orig_sums[col_names]-new_sums[col_names]) > 1e-4]
if len(columns_not_same) > 0:
    print("Didn't work: external_trip_distribution")
else:
    output_pc_tables['external_trip_distribution'] = external_trip_dist_pc_df[external_trip_dist.columns].to_dict('list')

# Group Quarters
# total_gq_df = pd.read_sql_query("SELECT * FROM group_quarters", con=conn)
total_gq_df = pd.DataFrame.from_dict(output_pc_tables.get('group_quarters'))
total_gq_df = total_gq_df.drop_duplicates()
groupby_col = ['geoid10', 'taz', 'year']
gq_cols = ['dorm_share','military_share','other_share', 'group_quarters']
total_gq_df = total_gq_df.groupby(groupby_col+gq_cols[:-1], as_index=False, dropna=False)[gq_cols[-1]].sum()
orig_sums = total_gq_df[gq_cols[-1]].sum()
total_gq_df_pc_df = xwalk.merge(total_gq_df, how='left', on='taz')
total_gq_df_pc_df[gq_cols[-1]] = total_gq_df_pc_df[gq_cols[-1]]*total_gq_df_pc_df.pctshare
total_gq_df_pc_df = total_gq_df_pc_df.drop(columns=['taz']).rename(columns={'taz_pc':'taz'}).drop_duplicates()
total_gq_df_pc_df = total_gq_df_pc_df.groupby(groupby_col+gq_cols[:-1], as_index=False, dropna=False)[gq_cols[-1]].sum()
total_gq_df_pc_df = pd.concat([total_gq_df_pc_df, total_gq_df[~total_gq_df.taz.isin(xwalk.taz.unique())]], axis=0, ignore_index=True)
for col_name, dtype_ in total_gq_df.dtypes.items():
    total_gq_df_pc_df[col_name] = total_gq_df_pc_df[col_name].astype(dtype_)
new_sums = total_gq_df_pc_df[gq_cols[-1]].sum()
columns_not_same = (np.abs(orig_sums-new_sums) > 1e-4)
if columns_not_same:
    print("Didn't work: group_quarters")
else:
    output_pc_tables['group_quarters'] = total_gq_df_pc_df[total_gq_df.columns].to_dict('list')


# Heavy Trucks
external_taz_start = 3700
# heavy_trucks = pd.read_sql('SELECT * FROM heavy_trucks', con=conn)
heavy_trucks = pd.DataFrame.from_dict(output_pc_tables.get('heavy_trucks'))
heavy_trucks = heavy_trucks.drop_duplicates()
groupby_col = ['record', 'atri_zone', 'taz', 'year']
data_col = ['htkpro', 'htkatt']
heavy_trucks = heavy_trucks.groupby(groupby_col, as_index=False, dropna=False)[data_col].sum()
orig_sums = heavy_trucks[data_col].sum()
heavy_trucks_pc_df = xwalk.merge(heavy_trucks, how='left', on='taz').dropna()
heavy_trucks_pc_df[data_col] = heavy_trucks_pc_df[data_col].apply(lambda x: x*heavy_trucks_pc_df.pctshare)
heavy_trucks_pc_df = heavy_trucks_pc_df.drop(columns=['taz']).rename(columns={'taz_pc':'taz'}).drop_duplicates().dropna()
heavy_trucks_pc_df = heavy_trucks_pc_df.groupby(groupby_col, as_index=False, dropna=False)[data_col].sum()
heavy_trucks_pc_df = pd.concat([heavy_trucks_pc_df, heavy_trucks[~heavy_trucks.taz.isin(xwalk.taz.unique())]], axis=0, ignore_index=True)
for col_name, dtype_ in heavy_trucks.dtypes.items():
    heavy_trucks_pc_df[col_name] = heavy_trucks_pc_df[col_name].astype(dtype_)
new_sums = heavy_trucks_pc_df[data_col].sum()
columns_not_same = [col_names for col_names in data_col if np.abs(orig_sums[col_names]-new_sums[col_names]) > 1e-4]
if len(columns_not_same) > 0:
    print("Didn't work: heavy_trucks")
else:
    output_pc_tables['heavy_trucks'] = heavy_trucks_pc_df[heavy_trucks.columns].to_dict('list')

# JBLM Trips
external_taz_start = 3700
# jblm_trips = pd.read_sql('SELECT * FROM jblm_trips', con=conn)
jblm_trips = pd.DataFrame.from_dict(output_pc_tables.get('jblm_trips'))
jblm_trips = jblm_trips.drop_duplicates()
groupby_col = ['record', 'atri_zone', 'taz', 'year']
data_col = ['trips']
orig_sums = jblm_trips[data_col].sum()
odShares = expandTazShares(xwalk)
jblm_trips_pc_df = jblm_trips.merge(odShares, how='left', left_on=['origin_zone', 'destination_zone'],right_on=['o','d']).dropna()
jblm_trips_pc_df['trips'] = jblm_trips_pc_df['trips'] * jblm_trips_pc_df['percent']
ext_o = jblm_trips.loc[jblm_trips.origin_zone==3733]
ext_d = jblm_trips.loc[jblm_trips.destination_zone==3733]
ext_o_trips_pc_df = ext_o.merge(xwalk, how='left', left_on=['destination_zone'],right_on=['taz']).dropna()
ext_o_trips_pc_df['trips'] = ext_o_trips_pc_df['trips'] * ext_o_trips_pc_df['pctshare']
ext_o_trips_pc_df = ext_o_trips_pc_df.rename(columns={'taz':'d', 'taz_pc':'pc_d', 'pctshare':'percent_d'})
ext_o_trips_pc_df['o'] = ext_o_trips_pc_df['origin_zone']
ext_o_trips_pc_df['pc_o'] = ext_o_trips_pc_df['origin_zone']
ext_o_trips_pc_df['percent_o'] = 1
ext_o_trips_pc_df['percent'] = ext_o_trips_pc_df['percent_d']
ext_o_trips_pc_df['od'] = ext_o_trips_pc_df['o'] * 10000 + ext_o_trips_pc_df['d']
ext_o_trips_pc_df = ext_o_trips_pc_df[jblm_trips_pc_df.columns]

ext_d_trips_pc_df = ext_d.merge(xwalk, how='left', left_on=['origin_zone'],right_on=['taz']).dropna()
ext_d_trips_pc_df['trips'] = ext_d_trips_pc_df['trips'] * ext_d_trips_pc_df['pctshare']
ext_d_trips_pc_df = ext_d_trips_pc_df.rename(columns={'taz':'o', 'taz_pc':'pc_o', 'pctshare':'percent_o'})
ext_d_trips_pc_df['d'] = ext_d_trips_pc_df['destination_zone']
ext_d_trips_pc_df['pc_d'] = ext_d_trips_pc_df['destination_zone']
ext_d_trips_pc_df['percent_d'] = 1
ext_d_trips_pc_df['percent'] = ext_d_trips_pc_df['percent_o']
ext_d_trips_pc_df['od'] = ext_d_trips_pc_df['o'] * 10000 + ext_d_trips_pc_df['d']
ext_d_trips_pc_df = ext_d_trips_pc_df[jblm_trips_pc_df.columns]

jblm_trips_pc_df = pd.concat([jblm_trips_pc_df, ext_o_trips_pc_df, ext_d_trips_pc_df], axis=0)
groupby_col = ['year', 'matrix_id', 'geoid10', 'pc_o', 'pc_d', 'trip_direction', 'jblm_gate']
jblm_trips_pc_df = jblm_trips_pc_df.groupby(groupby_col, as_index=False, dropna=False)[data_col].sum()
jblm_trips_pc_df = jblm_trips_pc_df.rename(columns={'pc_o':'origin_zone', 'pc_d':'destination_zone'})
jblm_trips_pc_df['record'] = jblm_trips_pc_df.index+1
jblm_trips_pc_df = jblm_trips_pc_df[jblm_trips.columns]
# for col_name, dtype_ in jblm_trips.dtypes.items():
#     jblm_trips_pc_df[col_name] = jblm_trips_pc_df[col_name].astype(dtype_)
new_sums = jblm_trips_pc_df[data_col].sum()
columns_not_same = (np.abs(orig_sums-new_sums) > 1e-4).values
if columns_not_same:
    print("Didn't work: jblm_trips")
else:
    output_pc_tables['jblm_trips'] = jblm_trips_pc_df[jblm_trips.columns].to_dict('list')


# Parking zones
# df_parking_zones = pd.read_sql('SELECT * FROM parking_zones', con=conn)
df_parking_zones = pd.DataFrame.from_dict(output_pc_tables.get('parking_zones'))
df_parking_zones = df_parking_zones.drop_duplicates()
df_parking_zones_pc_df = df_parking_zones.rename(columns={'TAZ':'taz'}).merge(xwalk, how='left', on='taz').dropna()
df_parking_zones_pc_df = df_parking_zones_pc_df.drop(columns=['taz']).rename(columns={'taz_pc':'TAZ'}).drop_duplicates().dropna()
df_parking_zones_pc_df = df_parking_zones_pc_df.sort_values('pctshare').drop(columns=['pctshare'])
df_parking_zones_pc_df = df_parking_zones_pc_df.groupby('TAZ').first().reset_index()
for col_name, dtype_ in df_parking_zones.dtypes.items():
    df_parking_zones_pc_df[col_name] = df_parking_zones_pc_df[col_name].astype(dtype_)
output_pc_tables['parking_zones'] = df_parking_zones_pc_df[df_parking_zones.columns].to_dict('list')

# PSRC zones
# df_psrc = pd.read_sql("SELECT * FROM psrc_zones", con=conn)
df_psrc = pd.DataFrame.from_dict(output_pc_tables.get('psrc_zones'))
df_psrc = df_psrc.drop_duplicates()
df_psrc_pc_df = df_psrc.merge(xwalk, how='left', on='taz').dropna()
df_psrc_pc_df = df_psrc_pc_df.drop(columns=['taz', 'pctshare']).rename(columns={'taz_pc':'taz'}).drop_duplicates().dropna()
df_psrc_pc_df = df_psrc_pc_df[df_psrc.columns]
df_psrc_pc_df = pd.concat([df_psrc_pc_df, df_psrc.loc[df_psrc.external==1,]], axis=0, ignore_index=True)
df_psrc_pc_df = df_psrc_pc_df.drop(columns='record').drop_duplicates().reset_index(drop=True)
df_psrc_pc_df['record'] = df_psrc_pc_df.index+1
for col_name, dtype_ in df_psrc.dtypes.items():
    df_psrc_pc_df[col_name] = df_psrc_pc_df[col_name].astype(dtype_)
output_pc_tables['psrc_zones'] = df_psrc_pc_df[df_psrc.columns].to_dict('list')

# SeaTac Airport
# df_seatac = pd.read_sql("SELECT * FROM seatac", con=conn)
df_seatac = pd.DataFrame.from_dict(output_pc_tables.get('seatac'))
df_seatac = df_seatac.drop_duplicates()
orig_sums = df_seatac['enplanements'].sum()
df_seatac_pc_df = df_seatac.merge(xwalk, how='left', on='taz').dropna()
df_seatac_pc_df['enplanements'] = df_seatac_pc_df['enplanements'] * df_seatac_pc_df['pctshare']
df_seatac_pc_df = df_seatac_pc_df.drop(columns=['taz', 'pctshare']).rename(columns={'taz_pc':'taz'}).drop_duplicates().dropna()
df_seatac_pc_df = df_seatac_pc_df[df_seatac.columns]
for col_name, dtype_ in df_seatac.dtypes.items():
    df_seatac_pc_df[col_name] = df_seatac_pc_df[col_name].astype(dtype_)
new_sums = df_seatac_pc_df['enplanements'].sum()
columns_not_same = np.abs(orig_sums-new_sums) > 1e-4
if columns_not_same:
    print("Didn't work: seatac")
else:
    output_pc_tables['seatac'] = df_seatac_pc_df[df_seatac.columns].to_dict('list')

# SeaTac Airport
# df_special = pd.read_sql("SELECT * FROM special_generators", con=conn)
df_special = pd.DataFrame.from_dict(output_pc_tables.get('special_generators'))
df_special = df_special.drop_duplicates()
orig_sums = df_special.trips.sum()
df_special_pc_df = df_special.merge(xwalk, how='left', on='taz').dropna()
df_special_pc_df['trips'] = df_special_pc_df['trips'] * df_special_pc_df['pctshare']
df_special_pc_df = df_special_pc_df.drop(columns=['taz', 'pctshare']).rename(columns={'taz_pc':'taz'}).drop_duplicates().dropna()
df_special_pc_df = df_special_pc_df[df_special.columns]
for col_name, dtype_ in df_special.dtypes.items():
    df_special_pc_df[col_name] = df_special_pc_df[col_name].astype(dtype_)
new_sums = df_special_pc_df.trips.sum()
columns_not_same = np.abs(orig_sums-new_sums) > 1e-4
if columns_not_same:
    print("Didn't work: special_generators")
else:
    output_pc_tables['special_generators'] = df_special_pc_df[df_special.columns].to_dict('list')

# TAZ Geography
# county_df = pd.read_sql('SELECT * FROM taz_geography', con=conn)
county_df = pd.DataFrame.from_dict(output_pc_tables.get('taz_geography'))
county_df = county_df.drop_duplicates()
county_df_pc_df = county_df.merge(xwalk, how='left', on='taz').dropna()
county_df_pc_df = county_df_pc_df.drop(columns=['taz', 'pctshare']).rename(columns={'taz_pc':'taz'}).drop_duplicates().dropna()
county_df_pc_df = county_df_pc_df[county_df.columns]
for col_name, dtype_ in county_df.dtypes.items():
    county_df_pc_df[col_name] = county_df_pc_df[col_name].astype(dtype_)
output_pc_tables['taz_geography'] = county_df_pc_df[county_df.columns].to_dict('list')

for key,value in output_pc_tables.items():
    print('Writing table '+ key +' to the database')
    pd.DataFrame.from_dict(value).to_sql(name=key, con=output_conn, index=False)