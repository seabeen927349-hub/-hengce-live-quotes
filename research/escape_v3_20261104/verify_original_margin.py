"""Independent original-file join audit; never modifies either source."""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd,numpy as np

def run(mother_path,margin_path,patch_path,output):
 def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
 expected={'mother':'d746f1f302ea8eb77569f35cf3d2e02895f25d390d35c273ee1535c9ed0a5d62','margin':'142300b99ad66564f79db38e7270332e3300946a0ea63d9c86e6141a0d81cb12'}
 assert sha(mother_path)==expected['mother'];assert sha(margin_path)==expected['margin']
 m=pd.read_csv(mother_path,usecols=['Date','Ticker','Margin_MarginBalance'],dtype={'Ticker':str})
 r=pd.read_csv(margin_path,usecols=['Date','Ticker','MarginBalance'],dtype={'Ticker':str})
 patch=pd.read_csv(patch_path,dtype={'Ticker':str})
 for x in (m,r,patch):assert not x.duplicated(['Date','Ticker']).any()
 j=m.merge(r,on=['Date','Ticker'],how='outer',validate='one_to_one',indicator=True)
 both=j._merge.eq('both');old=both & j.Margin_MarginBalance.notna();fill=both & j.Margin_MarginBalance.isna()
 assert np.array_equal(j.loc[old,'Margin_MarginBalance'],j.loc[old,'MarginBalance'])
 a=j.loc[fill,['Date','Ticker','MarginBalance']].rename(columns={'MarginBalance':'Margin_MarginBalance'}).sort_values(['Date','Ticker']).reset_index(drop=True)
 b=patch[a.columns].sort_values(['Date','Ticker']).reset_index(drop=True)
 pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=True)
 report={'original_sha256':expected,'original_price_rows':len(m),'original_margin_rows':len(r),'joined_rows':int(both.sum()),'existing_verified_equal':int(old.sum()),'restored_null_rows':int(fill.sum()),'margin_only':int(j._merge.eq('right_only').sum()),'price_only':int(j._merge.eq('left_only').sum()),'conflicts':0,'patch_exact_match':True,'new_network_TWSE_query_performed':False,'authority':'RESEARCH_ONLY','trading_authority':'NONE'}
 assert report['restored_null_rows']==702055 and report['existing_verified_equal']==14287
 Path(output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mother');p.add_argument('margin');p.add_argument('patch');p.add_argument('output');a=p.parse_args();run(a.mother,a.margin,a.patch,a.output)
