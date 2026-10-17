"""Describe building/dwelling coverage including rental-only and newer stock."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'outputs/tables'
b=pd.read_csv(T/'building_level_shi__release__current_2026-10-08.csv')
sold=['1room_sold','2room_sold','3room_sold','4room_sold','5room_sold','exec_sold','multigen_sold','studio_apartment_sold'];rent=['1room_rental','2room_rental','3room_rental','other_room_rental']
s=b[sold].sum(axis=1);r=b[rent].sum(axis=1)
b['composition_group']=np.select([(s.eq(0)&r.gt(0)),(s.gt(0)&r.gt(0)),(s.gt(0)&r.eq(0))],['rental-category only','sold and rental categories','sold-category only'],default='unclassified')
b['shi_band']=pd.cut(b.shi,[1,2,3,4,5,6.00000001],right=False,labels=['[1,2)','[2,3)','[3,4)','[4,5)','[5,6]']).astype('string').fillna('missing/invalid')
b['completion_period']=pd.cut(b.year_completed,[-np.inf,1979,1999,2019,np.inf],labels=['before 1980','1980–1999','2000–2019','2020 onward']).astype('string').fillna('missing')
b['town_source_code']=b.bldg_contract_town.fillna('missing')
for market in ['rental','resale']:
 linked=pd.read_csv(T/f'{market}_eligible_linked__2024-2025.csv',usecols=['building_id']);b[market+'_records_observed']=b.building_id.isin(linked.building_id)
 prediction='rental_oof_predictions.csv' if market=='rental' else 'resale_baseline_oof_predictions.csv'
 ids=pd.read_csv(T/prediction,usecols=['building_id']);b[market+'_model_eligible']=b.building_id.isin(ids.building_id)
b['coordinate_exact']=b.one_map_status.eq('exact_onemap_address');rows=[]
for dimension in ['shi_band','composition_group','completion_period','town_source_code']:
 for group,d in b.groupby(dimension,dropna=False):
  row={'dimension':dimension,'group':str(group),'buildings':len(d),'recorded_dwelling_units':int(d.total_dwelling_units.sum()),'valid_shi_buildings':int(d.shi_status.eq('valid').sum()),'exact_coordinate_buildings':int(d.coordinate_exact.sum())}
  for market in ['rental','resale']:
   for flag in ['records_observed','model_eligible']:
    keep=d[market+'_'+flag];row[market+'_'+flag+'_buildings']=int(keep.sum());row[market+'_'+flag+'_building_dwelling_units']=int(d.loc[keep,'total_dwelling_units'].sum())
  rows.append(row)
output=pd.DataFrame(rows);output.to_csv(T/'coverage_by_housing_group__2026-10-17.csv',index=False)
(T/'coverage_by_housing_group__2026-10-17.json').write_text(output.to_json(orient='records',indent=2)+'\n')
for dimension,d in output.groupby('dimension'):
 assert d.buildings.sum()==len(b)
 assert d.recorded_dwelling_units.sum()==b.total_dwelling_units.sum()
print(output[output.dimension.eq('composition_group')].to_string(index=False));print('All four dimensions reconcile to',len(b),'buildings and',int(b.total_dwelling_units.sum()),'recorded dwelling units; not resident coverage.')
