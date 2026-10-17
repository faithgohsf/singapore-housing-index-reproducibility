from pathlib import Path
import sys,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from export_manuscript_economic_table import table_rows

def data():
 def c(a,b,d):return dict(model_a=a,model_b=b,mae_a=10.0,mae_b=10.0-d,improvement_mae_a_minus_b=d,improvement_ci95=[-1.5,2.5])
 return {'rental':{'comparisons':[c('A','B',2),c('C','D',-.5)]},'resale_baseline':{'comparisons':[c('A','B',3)]},'resale_adjusted':{'comparisons':[c('C','D',-.5)]}}

def test_economic_export_preserves_unfavourable_differences_and_interval_signs():
 r=table_rows(data());assert len(r)==5 and r[0][0]=='Analysis and comparison' and r[-1][3]=='-0.50' and r[-1][4]=='-1.50 to 2.50'

def test_missing_comparison_cannot_silently_export_wrong_table():
 d=data();d['resale_adjusted']['comparisons']=[]
 with pytest.raises(ValueError,match='Expected one comparison'):table_rows(d)
