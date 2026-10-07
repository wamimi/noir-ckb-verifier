#!/usr/bin/env python3
"""Exact new circuit boundary tests, including fresh maximum-range proof."""
import argparse,importlib.util,json,subprocess
from pathlib import Path
import owned_counter as c
spec=importlib.util.spec_from_file_location('matrix',Path(__file__).with_name('check-owned-counter.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=c.integrity(a.release);out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);s=Path(r['setup']);records=[]
 values=[str(2**64-2),str(2**64-1),str(2**128-1),str(2**128-1)]
 m.fresh_proof(r,values,out/'maximum-valid');records.append(dict(case='maximum-valid',fresh_proof=True,passed=True))
 cases={'old-out-of-range':[2**64,2**64+1,1,2],'new-overflow':[2**64-1,2**64,1,2],'not-increment':[0,2,1,2],'context-lo-overflow':[0,1,2**128,2],'context-hi-overflow':[0,1,1,2**128]}
 for name,values in cases.items():
  d=out/name;d.mkdir();c.write(d/'inputs.json',dict(zip(c.NAMES,map(str,values))));cmd=list(map(str,[s/'backend-target/debug/noir-cli','interop',s/'circuit/target/owned_counter_v1.json',d/'inputs.json','--out',d/'interop']))
  q=subprocess.run(cmd,capture_output=True,text=True,timeout=60);record=dict(case=name,command=cmd,exit=q.returncode,stdout=q.stdout,stderr=q.stderr);c.write(d/'command.json',record)
  c.require(q.returncode!=0 and 'Cannot satisfy constraint' in (q.stdout+q.stderr),'not an observed constraint failure: '+q.stdout+q.stderr)
  records.append(dict(case=name,passed=True,fresh_proof=False,boundary='witness constraint solving'))
 c.write(out/'results.json',records);print(json.dumps(records,indent=2))
if __name__=='__main__':main()
