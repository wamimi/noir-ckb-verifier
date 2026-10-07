#!/usr/bin/env python3
"""Isolated RISC-V mutations: require targeted incorrect acceptance, not arbitrary failure."""
import argparse,copy,importlib.util,json,os,shutil,subprocess
from pathlib import Path
import owned_counter as c
spec=importlib.util.spec_from_file_location('matrix',Path(__file__).with_name('check-owned-counter.py'));matrix=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['release','baseline','key','out']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);r=c.integrity(a.release);build=c.read(Path(r['artifacts']['type']['path']).parent/'build.json');records=[]
    baseline=c.read(a.baseline/'results.json');c.require(all(x['passed'] for x in baseline),'baseline matrix not passing')
    pairs=[('verification','update-valid','invalid-proof-permitted-owner'),('initial_zero','create-valid','create-nonzero'),('capacity','update-valid','capacity-reduced')]
    for mutation,control,target in pairs:
        dest=out/mutation;dest.mkdir();shutil.copytree(c.ROOT/'contracts',dest/'contracts',ignore=shutil.ignore_patterns('target'))
        src=dest/'contracts/crates/owned-counter/src/main.rs';lines=src.read_text().splitlines();start=next(i for i,x in enumerate(lines) if '// MUTATION-BEGIN: '+mutation in x);end=next(i for i,x in enumerate(lines) if '// MUTATION-END: '+mutation in x);selected=lines[start:end+1]
        src.write_text('\n'.join(lines[:start]+lines[end+1:])+'\n')
        env=os.environ.copy();env.update(build['env']);env['CARGO_TARGET_DIR']=str(dest/'target');env['RUSTFLAGS']=env['RUSTFLAGS'].replace(str(c.ROOT)+'=/build',str(dest)+'=/build')
        q=subprocess.run(build['command'],cwd=dest/'contracts',env=env,capture_output=True,text=True,timeout=900);c.write(dest/'build.json',dict(command=build['command'],cwd=str(dest/'contracts'),env={k:v for k,v in env.items() if k.startswith('COUNTER_') or k in ['CARGO_TARGET_DIR','RUSTFLAGS']},exit=q.returncode,stdout=q.stdout,stderr=q.stderr));c.require(q.returncode==0,'mutant compile failed; NOT detected')
        binary=dest/'target/riscv64imac-unknown-none-elf/release/owned-counter';data=binary.read_bytes();oldhash=r['artifacts']['type']['data_hash'];newhash=c.hx(c.h(data))
        tests=dest/'cases';tests.mkdir()
        for name in [control,target]:
            case=c.read(a.baseline/(name+'.json'));t=case['transaction']
            for o in t['outputs']+[x['output'] for x in case['cells']]:
                if o['type'] and o['type']['code_hash']==oldhash:o['type']['code_hash']=newhash
            code=next(x for x in case['cells'] if c.hx(c.h(c.raw(x['data'])))==oldhash);code['data']=c.hx(data)
            if mutation!='initial_zero':
                old=next(x for x in case['cells'] if x['out_point']==t['inputs'][0]['previous_output']);values=c.statement(r['policy'],t,dict(data={'content':old['data']}))
                if name==target and mutation=='verification':
                    payload=(Path(r['setup'])/'adapter/witness.mol.bin').read_bytes();payload=payload[:-128]+b''.join(int(v).to_bytes(32,'little') for v in values)
                else:payload=matrix.fresh_proof(r,values,dest/(name+'-proof'))
                t['witnesses'][0]=c.witness(payload)
            c.write(tests/(name+'.json'),case)
        c.write(tests/'cases.json',[control+'.json',target+'.json'])
        env=os.environ.copy();env.update(COUNTER_CASES=str(tests),COUNTER_TEST_KEY=str(a.key.resolve()))
        cmd=['cargo','+1.95.0','test','--locked','--offline','-p','ckb-integration-tests','--test','owned_counter','--','--ignored','--nocapture']
        q=subprocess.run(cmd,cwd=c.ROOT,env=env,capture_output=True,text=True,timeout=900);c.write(dest/'run.json',dict(command=cmd,env={'COUNTER_CASES':str(tests)},exit=q.returncode,stdout=q.stdout,stderr=q.stderr))
        results=c.read(tests/'results.json');c.require(len(results)==2 and results[0]['passed'] and results[0]['result'].startswith('Ok('),'mutant valid control failed; NOT detected')
        detected=q.returncode!=0 and not results[1]['passed'] and results[1]['result'].startswith('Ok(')
        c.require(detected,'target did not observe incorrect acceptance; NOT detected')
        records.append(dict(mutation=mutation,removed_lines=selected,baseline_binary_sha256=r['artifacts']['type']['sha256'],mutant_binary_sha256=c.sha(binary),mutant_code_hash=newhash,target=target,detected=detected,results=results));(out/'manifest.json').write_text(json.dumps(records,indent=2)+'\n');print(mutation,'detected by incorrect acceptance',flush=True)
if __name__=='__main__':main()
