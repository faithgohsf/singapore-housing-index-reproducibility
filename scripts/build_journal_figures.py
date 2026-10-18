"""Create title-free 300 dpi journal figures from verified saved outputs."""
from pathlib import Path
import json, os, tempfile
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "shi-pipeline-cache/matplotlib"))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'outputs/tables';F=ROOT/'manuscript/figures';F.mkdir(parents=True,exist_ok=True)
h=pd.read_csv(T/'historical_comparison_buildings__mendeley_v1.csv');h=h[h.paired_for_agreement.eq(True)]
s=json.loads((T/'reconstruction_stage_summary.json').read_text())['historical_comparison']
fig,ax=plt.subplots(figsize=(6.7,4.7));ax.scatter((h.shi+h.historical_shi)/2,h.shi-h.historical_shi,s=5,alpha=.3)
ax.axhline(s['mean_difference_current_minus_historical'],color='black',linestyle='-',label='Mean difference')
for key in ['limits_of_agreement_lower','limits_of_agreement_upper']:ax.axhline(s[key],color='gray',linestyle='--')
ax.plot([],[],color='gray',linestyle='--',label='95% limits of agreement');ax.legend(fontsize=8)
ax.set_xlabel('Mean current and historical-candidate SHI');ax.set_ylabel('Current minus historical-candidate SHI');fig.tight_layout();fig.savefig(F/'Figure_2_Historical_Agreement.png',dpi=300);plt.close(fig)
for number,market,ylabel in [(3,'rent','Building median monthly rent (S$)'),(4,'resale','Building median resale price (S$)')]:
 d=pd.read_csv(T/f'building_level_{market}_by_shi__2024-2025.csv');order=['[1,2)','[2,3)','[3,4)','[4,5)','[5,6]'];samples=[d.loc[d.shi_tier.eq(k),'median_outcome'].to_numpy() for k in order]
 fig,ax=plt.subplots(figsize=(6.7,4.7));ax.boxplot(samples,tick_labels=order,showfliers=False,showmeans=True);ax.set_xlabel('SHI display band');ax.set_ylabel(ylabel);fig.tight_layout();fig.savefig(F/f'Figure_{number}_{market.capitalize()}_Patterns.png',dpi=300);plt.close(fig)
print('Created three title-free 300 dpi figure files in manuscript/figures/.')
