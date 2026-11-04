"""Usage: run_all.py REPAIRED.zip PATCH.zip VALIDATION.zip ORIGINAL_MOTHER.csv ORIGINAL_MARGIN.csv
All inputs read-only. Outputs restricted to this research directory.
"""
from pathlib import Path
import sys,hashlib,zipfile,subprocess,json
HERE=Path(__file__).resolve().parent
expected=['67d833114dda72aa89f0890bac65d84d37686bfd06f66c18da728af7e721e052','12121d2684874cb96ec456edce980aa696af6c2a1bf2ae834157ea33588b8b4d','fdf59bf21a68c3027410ebae00c1595d170552cf285c13e8a7fffa5425a6bc33']
if len(sys.argv)!=6:raise SystemExit(__doc__)
inputs=[Path(s).resolve() for s in sys.argv[1:]]
work=HERE/'work';work.mkdir(exist_ok=True)
for p,name,want in zip(inputs,['repaired','patch','prior'],expected):
 assert hashlib.sha256(p.read_bytes()).hexdigest()==want,p
 with zipfile.ZipFile(p) as z:
  assert all(not Path(s).is_absolute() and '..' not in Path(s).parts for s in z.namelist())
  z.extractall(work/name)
def run(script,*args):subprocess.run([sys.executable,str(HERE/script),*[str(a) for a in args]],check=True)
r=work/'repaired';out=HERE/'results'
run('replay_source_snapshot.py','--mother',r/'data/research_combined_mother_2023_2026_oct27.csv','--archive',r/'data/electronics_observed_membership_2023_2026_oct27.csv','--out',work/'strict')
run('reproduce_inputs.py',r,work/'strict',out)
run('verify_original_margin.py',inputs[3],inputs[4],r/'data/margin_backfill_patch_2023_2025.csv',out/'original_margin_audit.json')
run('run_tests.py')
run('validate_v3.py',work/'prior')
print('Completed research-only reproduction. Read results/decision.json. Trading authority NONE.')
