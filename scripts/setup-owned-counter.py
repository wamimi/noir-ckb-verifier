#!/usr/bin/env python3
"""Fresh PUBLIC DEVELOPMENT ONLY setup for the fixed owned-counter/v1 circuit."""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_REV = '828025f3a0090e2934940956c0f5dc8093eb5532'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--backend',type=Path,default=ROOT.parent/'Noir-Groth16')
    args=ap.parse_args(); out=args.out.resolve(); backend=args.backend.resolve()
    out.mkdir(parents=True,exist_ok=False)
    log=[]; manifest={'status':'running','setup':'PUBLIC DEVELOPMENT ONLY; single-party, public entropy; NOT production','profile':'noir-ckb/owned-counter/v1'}
    def save():
        (out/'commands.json').write_text(json.dumps(log,indent=2)+'\n')
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def run(cmd,cwd=ROOT,env=None,expected=0):
        cmd=list(map(str,cmd)); e=os.environ.copy();e.update(env or {})
        r=subprocess.run(cmd,cwd=cwd,env=e,capture_output=True,text=True,timeout=900)
        log.append(dict(command=cmd,cwd=str(cwd),env=env or {},exit=r.returncode,stdout=r.stdout,stderr=r.stderr));save()
        print(cmd[0:3],r.returncode,flush=True)
        if r.returncode!=expected or (expected==0 and '[ERROR]' in r.stdout): raise RuntimeError(r.stdout+r.stderr)
        return r.stdout+r.stderr
    try:
        assert run(['git','rev-parse','HEAD'],backend).strip()==BACKEND_REV
        assert not run(['git','status','--porcelain'],backend).strip()
        manifest['backend_revision']=BACKEND_REV
        version=run(['nargo','--version']);assert '1.0.0-beta.18' in version and '99bb8b5cf33d7669adbdef096b12d80f30b4c0c9' in version
        manifest['nargo']=version
        snark=['npx','--offline','snarkjs@0.7.5'];assert 'snarkjs@0.7.5' in run(snark+['--version'],expected=99)
        run(['cargo','+1.95.0','build','--locked','--offline','-p','noir-cli'],backend,{'CARGO_TARGET_DIR':str(out/'backend-target')})
        cli=out/'backend-target/debug/noir-cli';manifest['backend_binary_sha256']=sha(cli)
        shutil.copytree(ROOT/'circuits/owned-counter-v1',out/'circuit')
        run(['nargo','compile','--print-acir'],out/'circuit')
        artifact=out/'circuit/target/owned_counter_v1.json'
        abi=json.loads(artifact.read_text())['abi'];assert [p['name'] for p in abi['parameters']]==['old_count','new_count','context_lo','context_hi']
        assert all(p['visibility']=='public' and p['type']=={'kind':'field'} for p in abi['parameters'])
        assert abi['return_type'] is None
        values={'old_count':'0','new_count':'1','context_lo':'13','context_hi':'17'}
        inputs=out/'inputs.json';inputs.write_text(json.dumps(values)+'\n')
        run([cli,'interop',artifact,inputs,'--out',out/'interop'],backend)
        run(snark+['wtns','check',out/'interop/circuit.r1cs',out/'interop/witness.wtns'])
        run(snark+['r1cs','export','json',out/'interop/circuit.r1cs',out/'r1cs.json'])
        run(snark+['wtns','export','json',out/'interop/witness.wtns',out/'witness.json'])
        r1cs=json.loads((out/'r1cs.json').read_text());assert r1cs['nPubInputs']==4 and r1cs['nOutputs']==0
        assert json.loads((out/'witness.json').read_text())[:5]==['1','0','1','13','17']
        manifest['constraints']=r1cs['nConstraints'];manifest['wires']=r1cs['nVars']
        power=(2*r1cs['nConstraints']).bit_length();manifest['ptau_power']=power
        run(snark+['powersoftau','new','bn128',str(power),out/'initial.ptau'])
        run(snark+['powersoftau','contribute',out/'initial.ptau',out/'contributed.ptau','--name=PUBLIC DEVELOPMENT ONLY','-e=PUBLIC-DEVELOPMENT-ONLY-owned-counter-v1'])
        run(snark+['powersoftau','prepare','phase2',out/'contributed.ptau',out/'phase2.ptau'])
        run(snark+['powersoftau','verify',out/'phase2.ptau'])
        run(snark+['groth16','setup',out/'interop/circuit.r1cs',out/'phase2.ptau',out/'initial.zkey'])
        run(snark+['zkey','contribute',out/'initial.zkey',out/'development.zkey','--name=PUBLIC DEVELOPMENT ONLY','-e=PUBLIC-DEVELOPMENT-ONLY-owned-counter-v1-phase2'])
        run(snark+['zkey','verify',out/'interop/circuit.r1cs',out/'phase2.ptau',out/'development.zkey'])
        run(snark+['zkey','export','verificationkey',out/'development.zkey',out/'verification_key.json'])
        run(snark+['groth16','prove',out/'development.zkey',out/'interop/witness.wtns',out/'proof.json',out/'public.json'])
        assert json.loads((out/'public.json').read_text())==list(values.values())
        run(snark+['groth16','verify',out/'verification_key.json',out/'public.json',out/'proof.json'])
        for slot in range(4):
            changed=list(values.values());changed[slot]=str(int(changed[slot])+1)
            p=out/f'changed-{slot}.json';p.write_text(json.dumps(changed)+'\n')
            assert 'Invalid proof' in run(snark+['groth16','verify',out/'verification_key.json',p,out/'proof.json'],expected=1)
        run(['cargo','+1.95.0','run','--locked','--offline','-p','artifact-adapter','--bin','noir-ckb-adapter','--','--vk',out/'verification_key.json','--proof',out/'proof.json','--public',out/'public.json','--negative-public',out/'changed-0.json','--out',out/'adapter'])
        manifest['status']='passed'
        manifest['artifacts']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and 'backend-target' not in p.parts and p.name not in ['commands.json','manifest.json']}
    except Exception as error:
        manifest['status']='failed';manifest['error']=str(error);raise
    finally:save()
if __name__=='__main__':main()
