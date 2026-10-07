#!/usr/bin/env python3
"""Counter-specific VM matrix using fresh proofs and real standard Lock signatures."""
import argparse,copy,json,os,subprocess
from pathlib import Path
import owned_counter as c

def resolve(url,p):
    q=c.rpc(url,'get_transaction',[p['tx_hash']]);c.require(q and q['tx_status']['status']=='committed','unconfirmed fixture dependency')
    t=q['transaction'];i=int(p['index'],16)
    return dict(out_point=p,output=t['outputs'][i],data=t['outputs_data'][i])
def snapshot(url,tx):
    cells=[]
    def add(p):
        old=next((x for x in cells if x['out_point']==p),None)
        if old:return c.raw(old['data'])
        x=resolve(url,p);cells.append(x);return c.raw(x['data'])
    for i in tx['inputs']:add(i['previous_output'])
    for d in tx['cell_deps']:
        b=add(d['out_point'])
        if d['dep_type']=='dep_group':
            for i in range(int.from_bytes(b[:4],'little')):
                v=b[4+36*i:40+36*i];add(dict(tx_hash=c.hx(v[:32]),index=hex(int.from_bytes(v[32:],'little'))))
    return cells

def fresh_proof(release,values,out):
    out.mkdir();s=Path(release['setup']);c.write(out/'inputs.json',dict(zip(c.NAMES,values)))
    snark=['npx','--offline','snarkjs@0.7.5'];commands=[]
    cmds=[[s/'backend-target/debug/noir-cli','interop',s/'circuit/target/owned_counter_v1.json',out/'inputs.json','--out',out/'interop'],
          snark+['wtns','check',out/'interop/circuit.r1cs',out/'interop/witness.wtns'],
          snark+['groth16','prove',s/'development.zkey',out/'interop/witness.wtns',out/'proof.json',out/'public.json'],
          snark+['groth16','verify',s/'verification_key.json',out/'public.json',out/'proof.json']]
    wrong=values.copy();wrong[2]=str(int(wrong[2])+1);c.write(out/'wrong.json',wrong)
    cmds.append(['cargo','+1.95.0','run','--locked','--offline','-p','artifact-adapter','--bin','noir-ckb-adapter','--','--vk',s/'verification_key.json','--proof',out/'proof.json','--public',out/'public.json','--negative-public',out/'wrong.json','--out',out/'adapter'])
    for cmd in cmds:
        cmd=list(map(str,cmd));r=subprocess.run(cmd,cwd=c.ROOT,capture_output=True,text=True,timeout=900);commands.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');c.require(r.returncode==0 and '[ERROR]' not in r.stdout,r.stdout+r.stderr)
    c.require(c.read(out/'public.json')==values,'public wire order')
    return (out/'adapter/witness.mol.bin').read_bytes()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['release','create','update','proof','key','out']:p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--rpc',required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    r=c.integrity(a.release);c.network(a.rpc,r['policy']['network_domain']);base=c.read(a.update)['transaction'];cells=snapshot(a.rpc,base);payload=(a.proof/'adapter/witness.mol.bin').read_bytes();names=[]
    def save(name,error=None,change=None,sign='valid',initial=False,fresh=False,recompute=False):
        t=copy.deepcopy(c.read(a.create)['transaction'] if initial else base)
        cs=snapshot(a.rpc,t) if initial else copy.deepcopy(cells)
        if change:change(t,cs)
        if fresh or recompute:
            old=next(x for x in cs if x['out_point']==t['inputs'][0]['previous_output']);values=c.statement(r['policy'],t,dict(data={'content':old['data']}))
            b=fresh_proof(r,values,out/(name+'-proof')) if fresh else payload[:-128]+b''.join(int(v).to_bytes(32,'little') for v in values)
            t['witnesses'][0]=c.witness(b)
        c.write(out/(name+'.json'),dict(transaction=t,cells=cs,error=error,sign=sign));names.append(name+'.json');print('prepared',name,flush=True)
    save('create-valid',initial=True)
    save('create-nonzero',53,lambda t,cs:t['outputs_data'].__setitem__(0,c.hx(c.state(1))),initial=True)
    save('create-wrong-id',44,lambda t,cs:t['outputs'][0]['type'].__setitem__('args','0x01'+'11'*32),initial=True)
    save('update-valid')
    save('missing-signature',-2,sign='missing')
    save('wrong-signature',-31,sign='wrong')
    unrelated=(Path(r['setup'])/'adapter/witness.mol.bin').read_bytes()
    save('invalid-proof-permitted-owner',51,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(unrelated[:-128]+payload[-128:])))
    save('wrong-public-order',49,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(payload[:-128]+payload[-96:-64]+payload[-128:-96]+payload[-64:])))
    save('wrong-successor-state',49,lambda t,cs:t['outputs_data'].__setitem__(0,c.hx(c.state(2))))
    save('capacity-reduced',47,lambda t,cs:t['outputs'][0].__setitem__('capacity',hex(int(t['outputs'][0]['capacity'],16)-1)),fresh=True)
    save('capacity-increased',47,lambda t,cs:t['outputs'][0].__setitem__('capacity',hex(int(t['outputs'][0]['capacity'],16)+1)),fresh=True)
    save('owner-changed',46,lambda t,cs:t['outputs'][0]['lock'].__setitem__('args','0x'+'33'*20),fresh=True)
    save('missing-proof',48,lambda t,cs:t['witnesses'].__setitem__(0,c.witness()))
    save('truncated-proof',48,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(payload[:-1])))
    save('trailing-proof',48,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(payload+b'\0')))
    save('proof-in-output-type',48,lambda t,cs:t['witnesses'].__setitem__(0,c.hx(c.table([b'',b'',c.vec(payload)]))))
    def misplaced(t,cs):t['witnesses']=[c.witness(),c.witness(payload)]
    save('proof-wrong-index',48,misplaced)
    def replay(t,cs):
        previous=copy.deepcopy(t['inputs'][0]['previous_output']);new=dict(tx_hash='0x'+'73'*32,index='0x0');t['inputs'][0]['previous_output']=new
        next(x for x in cs if x['out_point']==previous)['out_point']=new
    save('other-outpoint-old-vector',49,replay)
    save('other-outpoint-recomputed-old-proof',51,replay,recompute=True)
    save('other-outpoint-fresh-proof',change=replay,fresh=True)
    def operation(t,cs):
        next(x for x in cs if x['out_point']==t['inputs'][0]['previous_output'])['data']=c.hx(c.state(1));t['outputs_data'][0]=c.hx(c.state(2))
    save('other-operation-old-proof',51,operation,recompute=True)
    save('other-operation-fresh-proof',change=operation,fresh=True)
    def duplicate(t,cs):t['outputs'].insert(1,copy.deepcopy(t['outputs'][0]));t['outputs_data'].insert(1,t['outputs_data'][0])
    save('duplicate-output',42,duplicate)
    def otherid(t,cs):duplicate(t,cs);t['outputs'][1]['type']['args']='0x01'+'44'*32
    save('ambiguous-different-id',42,otherid)
    save('substituted-id',42,lambda t,cs:t['outputs'][0]['type'].__setitem__('args','0x01'+'55'*32))
    def burn(t,cs):t['outputs'].pop(0);t['outputs_data'].pop(0)
    save('destruction',42,burn)
    save('malformed-state',43,lambda t,cs:t['outputs_data'].__setitem__(0,'0x01'))
    save('unrelated-change-capacity',change=lambda t,cs:t['outputs'][1].__setitem__('capacity',hex(int(t['outputs'][1]['capacity'],16)-1)))
    save('unrelated-change-data',change=lambda t,cs:t['outputs_data'].__setitem__(1,'0x1234'))
    save('dependency-order',change=lambda t,cs:t['cell_deps'].reverse())
    def positions(t,cs):
        t['inputs'].reverse();t['witnesses'].reverse();t['outputs'].reverse();t['outputs_data'].reverse()
    save('application-at-index-one',change=positions)
    def missing_vk(t,cs):t['cell_deps']=[d for d in t['cell_deps'] if c.hx(c.h(c.raw(next(x for x in cs if x['out_point']==d['out_point'])['data'])))!=r['policy']['vk_data_hash']]
    save('missing-vk',50,missing_vk)
    def wrong_vk(t,cs):
        v=next(x for x in cs if c.hx(c.h(c.raw(x['data'])))==r['policy']['vk_data_hash']);v['data']=c.hx(c.raw(v['data'])[:-1]+bytes([c.raw(v['data'])[-1]^1]))
    save('wrong-vk',50,wrong_vk)
    def duplicate_vk(t,cs):
        v=copy.deepcopy(next(x for x in cs if c.hx(c.h(c.raw(x['data'])))==r['policy']['vk_data_hash']));v['out_point']=dict(tx_hash='0x'+'66'*32,index='0x0');cs.append(v);t['cell_deps'].append(c.dep(v['out_point']))
    save('duplicate-vk',50,duplicate_vk)
    always=next((Path.home()/'.cargo/registry/src').glob('*/ckb-always-success-script-0.0.1/specs/cells/always_success')).read_bytes()
    def unsupported(t,cs):
        lock=dict(code_hash=c.hx(c.h(always)),hash_type='data1',args='0x');point=dict(tx_hash='0x'+'77'*32,index='0x0');cs.append(dict(out_point=point,output=c.output(100000000000,lock),data=c.hx(always)));t['cell_deps'].append(c.dep(point));t['outputs'][0]['lock']=lock
        next(x for x in cs if x['out_point']==t['inputs'][0]['previous_output'])['output']['lock']=lock
    save('always-success-owner',45,unsupported,recompute=True)
    save('always-success-valid-proof',45,unsupported,fresh=True)
    def owner_code_substitution(t,cs):
        v=next(x for x in cs if c.hx(c.h(c.raw(x['data'])))==c.OWNER_DATA);v['data']=c.hx(always)
    save('resolved-owner-code-substitution',45,owner_code_substitution)
    def duplicate_input(t,cs):
        v=copy.deepcopy(next(x for x in cs if x['out_point']==t['inputs'][0]['previous_output']));v['out_point']=dict(tx_hash='0x'+'81'*32,index='0x0');cs.append(v);t['inputs'].append(dict(since='0x0',previous_output=v['out_point']));t['witnesses'].append(c.witness())
    save('duplicate-input-group',42,duplicate_input)
    def different_input(t,cs):
        duplicate_input(t,cs);cs[-1]['output']['type']['args']='0x01'+'82'*32
    save('ambiguous-input-identities',42,different_input)
    save('initial-duplicate-output',42,duplicate,initial=True)
    save('initial-owner-substitution',46,lambda t,cs:t['outputs'][0]['lock'].__setitem__('args','0x'+'32'*20),initial=True)
    save('initial-unknown-version',41,lambda t,cs:t['outputs'][0]['type'].__setitem__('args','0x02'+t['outputs'][0]['type']['args'][4:]),initial=True)
    save('oversized-witness',48,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(bytes(600))))
    save('wrong-wire-version',48,lambda t,cs:t['witnesses'].__setitem__(0,c.witness(payload[:12]+b'\x02\x00'+payload[14:])))
    save('input-since-excluded',change=lambda t,cs:t['inputs'][0].__setitem__('since','0x1'))
    def too_many_outputs(t,cs):
        while len(t['outputs'])<65:t['outputs'].append(copy.deepcopy(t['outputs'][1]));t['outputs_data'].append('0x')
    save('output-limit',52,too_many_outputs)
    def too_many_inputs(t,cs):
        original=next(x for x in cs if x['out_point']==t['inputs'][1]['previous_output'])
        while len(t['inputs'])<65:
            v=copy.deepcopy(original);v['out_point']=dict(tx_hash='0x'+'83'*32,index=hex(len(t['inputs'])));cs.append(v);t['inputs'].append(dict(since='0x0',previous_output=v['out_point']));t['witnesses'].append(c.witness())
    save('input-limit',52,too_many_inputs)
    def too_many_deps(t,cs):
        for i in range(65):
            point=dict(tx_hash='0x'+'84'*32,index=hex(i));cs.append(dict(out_point=point,output=c.output(100000000000,t['outputs'][0]['lock']),data=c.hx(bytes([i]))));t['cell_deps'].append(c.dep(point))
    save('resolved-dependency-limit',52,too_many_deps)
    c.write(out/'cases.json',names)
    env=os.environ.copy();env.update(COUNTER_CASES=str(out),COUNTER_TEST_KEY=str(a.key.resolve()))
    cmd=['cargo','+1.95.0','test','--locked','--offline','-p','ckb-integration-tests','--test','owned_counter','--','--ignored','--nocapture']
    q=subprocess.run(cmd,cwd=c.ROOT,env=env,capture_output=True,text=True,timeout=900);c.write(out/'run.json',dict(command=cmd,exit=q.returncode,stdout=q.stdout,stderr=q.stderr));print(q.stdout,q.stderr);c.require(q.returncode==0,'VM matrix failed; inspect run.json')
if __name__=='__main__':main()
