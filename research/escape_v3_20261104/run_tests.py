from pathlib import Path
import json,unittest,io
root=Path(__file__).resolve().parents[2]
suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_escape_v3*.py')
log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
out=Path(__file__).parent/'results';out.mkdir(exist_ok=True)
(out/'unit_tests.txt').write_text(log.getvalue())
summary={'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'passed':r.wasSuccessful()}
(out/'test_result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));raise SystemExit(not r.wasSuccessful())
