#!/usr/bin/env python3
"""Fixed public counter v1 client. No keys, signing, or broadcasting in this tool."""
import argparse, hashlib, http.client, json, os, shutil, ssl, subprocess, sys, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE='noir-ckb/owned-counter/v1'
OWNER_CODE='0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8'
OWNER_DATA='0x709f3fda12f561cfacf92273c57a98fede188a3f1a59b1f888d113f9cce08649'
TESTNET='0x10639e0895502b5688a6be8cf69460d76541bfa4821629d86d62ba0aae3f9606'
NAMES=['old_count','new_count','context_lo','context_hi']
def require(ok,message):
    if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def raw(s):return bytes.fromhex(s.removeprefix('0x'))
def hx(b):return '0x'+b.hex()
def h(b):return hashlib.blake2b(b,digest_size=32,person=b'ckb-default-hash').digest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def u32(n):return n.to_bytes(4,'little')
def u64(n):return n.to_bytes(8,'little')
def vec(b):return u32(len(b))+b
def table(parts):
    pos=4*(len(parts)+1);offsets=[]
    for p in parts:offsets.append(u32(pos));pos+=len(p)
    return u32(pos)+b''.join(offsets)+b''.join(parts)
def script(s):return table([raw(s['code_hash']),bytes([{'data':0,'type':1,'data1':2,'data2':4}[s['hash_type']]]),vec(raw(s['args']))])
def outpoint(p):return raw(p['tx_hash'])+u32(int(p['index'],16))
def cell_input(i):return u64(int(i['since'],16))+outpoint(i['previous_output'])
def state(n):return b'\x01'+u64(n)
def witness(proof=b'',lock=b''):
    return hx(table([vec(lock) if lock else b'',vec(proof) if proof else b'',b'']))
def witness_parts(encoded):
    b=raw(encoded)
    if not b:return [b'',b'',b'']
    require(len(b)>=16 and int.from_bytes(b[:4],'little')==len(b),'malformed WitnessArgs length')
    offsets=[int.from_bytes(b[i:i+4],'little') for i in (4,8,12)]+[len(b)]
    require(offsets[0]==16 and offsets==sorted(offsets),'malformed WitnessArgs offsets')
    parts=[b[offsets[i]:offsets[i+1]] for i in range(3)]
    for part in parts:require(not part or len(part)>=4 and int.from_bytes(part[:4],'little')==len(part)-4,'malformed witness BytesOpt')
    return parts
def set_proof(encoded,proof):
    parts=witness_parts(encoded);parts[1]=vec(proof);return hx(table(parts))
class RpcError(RuntimeError):
    """An RPC transport failure, safe to display without endpoint credentials."""


def rpc(url,method,params):
    req=urllib.request.Request(
        url,json.dumps(dict(id=1,jsonrpc='2.0',method=method,params=params)).encode(),
        {'Content-Type':'application/json','User-Agent':'noir-ckb/owned-counter-v1'})
    try:
        # Keep urllib's default certificate/hostname verification and 30s timeout.
        with urllib.request.urlopen(req,timeout=30) as response:
            r=json.load(response)
    except urllib.error.HTTPError as error:
        raise RpcError(
            f'RPC {method}: HTTP {error.code}. Check the RPC URL and provider access/rate limits; no retry was attempted.'
        ) from None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
        reason=error.reason if isinstance(error,urllib.error.URLError) else error
        if isinstance(reason, ssl.SSLError):
            advice='TLS verification failed. Check the endpoint certificate and local CA trust; do not disable TLS verification.'
        elif isinstance(reason, TimeoutError):
            advice='Request timed out. Check connectivity and RPC availability.'
        else:
            advice='Network connection failed. Check the RPC URL, DNS and connectivity.'
        raise RpcError(f'RPC {method}: {advice} No retry was attempted.') from None
    require('error' not in r,f'RPC {method}: {r.get("error")}');return r['result']
def network(url,expected):
    require(rpc(url,'get_block_hash',['0x0'])==expected,'RPC genesis differs from pinned network')
    if expected!=TESTNET:require(urllib.request.urlparse(url).hostname in ('127.0.0.1','localhost','::1'),'non-testnet builds only allow loopback development RPC')
def live(url,p):
    r=rpc(url,'get_live_cell',[p,True]);require(r['status']=='live',f'Cell is not live: {p}');return r['cell']
def op(s):
    tx,index=s.split(':');require(len(raw(tx))==32,'OutPoint hash length');return dict(tx_hash=tx,index=hex(int(index,0)))
def owner(arg):
    require(len(raw(arg))==20,'owner identifier must be 20 bytes');return dict(code_hash=OWNER_CODE,hash_type='type',args=arg)
def base(dep):return dict(version='0x0',cell_deps=[dep],header_deps=[],inputs=[],outputs=[],outputs_data=[],witnesses=[])
def output(cap,lock,t=None):return dict(capacity=hex(cap),lock=lock,type=t)
def dep(p):return dict(out_point=p,dep_type='code')
def save_tx(path,tx):write(path,dict(transaction=tx,multisig_configs={},signatures={}))
def minimum(o,d):return (8+33+len(raw(o['lock']['args']))+(33+len(raw(o['type']['args'])) if o['type'] else 0)+len(raw(d)))*100_000_000
def integrity(release):
    r=read(release);require(r['profile']==PROFILE,'profile mismatch')
    for item in r['artifacts'].values():require(sha(item['path'])==item['sha256'],f'artifact changed: {item["path"]}')
    return r
def statement(policy,tx,old,index=0,oi=0):
    new=raw(tx['outputs_data'][oi]);previous=raw(old['data']['content']);s=tx['outputs'][oi]
    require(len(new)==len(previous)==9 and new[0]==previous[0]==1,'state encoding')
    typ=s['type'];require(len(raw(typ['args']))==33,'args length')
    digest=h(b'noir-ckb/owned-counter/context/v1\0'+raw(policy['network_domain'])+h(PROFILE.encode())+h(script(typ))+raw(typ['args'])[1:]+b'\x01'+outpoint(tx['inputs'][index]['previous_output'])+previous+new+h(script(s['lock']))+u64(int(s['capacity'],16)))
    return [str(int.from_bytes(previous[1:],'little')),str(int.from_bytes(new[1:],'little')),str(int.from_bytes(digest[:16],'little')),str(int.from_bytes(digest[16:],'little'))]
def preflight(a):
    network(a.rpc,a.genesis);g=rpc(a.rpc,'get_block_by_number',['0x0']);tx=g['transactions'][0]
    require(hx(h(raw(tx['outputs_data'][1])))==OWNER_DATA,'unexpected genesis ownership binary')
    require(hx(h(script(tx['outputs'][1]['type'])))==OWNER_CODE,'unexpected genesis ownership Type hash')
    p=dict(profile=PROFILE,network_domain=a.genesis,owner_code_hash=OWNER_CODE,owner_data_hash=OWNER_DATA,
           owner_dep=dict(out_point=dict(tx_hash=g['transactions'][1]['hash'],index='0x0'),dep_type='dep_group'))
    write(a.out,p);print(json.dumps(p,indent=2))
def build(a):
    p=read(a.policy);setup=a.setup.resolve();m=read(setup/'manifest.json');require(m['status']=='passed' and m['profile']==PROFILE,'setup did not pass for this profile')
    require(sha(setup/'circuit/src/main.nr')==sha(ROOT/'circuits/owned-counter-v1/src/main.nr'),'setup belongs to a different circuit')
    for f,digest in m['artifacts'].items():require(sha(setup/f)==digest,f'setup artifact changed: {f}')
    require(p['owner_code_hash']==OWNER_CODE and p['owner_data_hash']==OWNER_DATA,'unsupported ownership policy')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.update({'COUNTER_'+k.upper():p[k] for k in ['network_domain','owner_code_hash','owner_data_hash']})
    vk=setup/'adapter/vk.mol.bin';env['COUNTER_VK_DATA_HASH']=hx(h(vk.read_bytes()))
    env['CARGO_TARGET_DIR']=str(out/'target')
    env['RUSTFLAGS']=f'-C target-feature=-a --remap-path-prefix={Path.home()}/.cargo/registry/src=/cargo-registry --remap-path-prefix={Path.home()}/.rustup/toolchains=/rustup-toolchains --remap-path-prefix={ROOT}=/build'
    cmd=['cargo','+1.94.1','build','--locked','--offline','--release','--target','riscv64imac-unknown-none-elf','-p','owned-counter']
    r=subprocess.run(cmd,cwd=ROOT/'contracts',env=env,capture_output=True,text=True)
    write(out/'build.json',dict(command=cmd,env={k:v for k,v in env.items() if k.startswith('COUNTER_') or k in ['RUSTFLAGS','CARGO_TARGET_DIR']},stdout=r.stdout,stderr=r.stderr,exit=r.returncode))
    require(r.returncode==0,r.stdout+r.stderr)
    shutil.copyfile(out/'target/riscv64imac-unknown-none-elf/release/owned-counter',out/'owned-counter')
    shutil.copyfile(vk,out/'vk.mol.bin')
    artifacts={n:dict(path=str(f),sha256=sha(f),data_hash=hx(h(f.read_bytes())),bytes=f.stat().st_size) for n,f in [('type',out/'owned-counter'),('vk',out/'vk.mol.bin')]}
    p.update(vk_data_hash=artifacts['vk']['data_hash'])
    source_files=['contracts/Cargo.toml','contracts/Cargo.lock','contracts/crates/owned-counter/Cargo.toml','contracts/crates/owned-counter/build.rs','contracts/crates/owned-counter/src/main.rs','circuits/owned-counter-v1/Nargo.toml','circuits/owned-counter-v1/src/main.nr']
    write(out/'release.json',dict(profile=PROFILE,policy=p,setup=str(setup),artifacts=artifacts,development_only=True,source_sha256={f:sha(ROOT/f) for f in source_files},build_log_sha256=sha(out/'build.json')))
    print(out/'release.json')
def prepare(a):
    r=integrity(a.release);p=r['policy'];network(a.rpc,p['network_domain']);lock=owner(a.owner)
    funding=op(a.funding);f=live(a.rpc,funding);require(f['output']['lock']==lock and f['output']['type'] is None and f['data']['content']=='0x','funding must be empty standard-owner Cell')
    tx=base(p['owner_dep']);tx['inputs']=[dict(since='0x0',previous_output=funding)];total=int(f['output']['capacity'],16)
    if a.operation=='deploy':
        for name in ['type','vk']:
            d=hx(Path(r['artifacts'][name]['path']).read_bytes());o=output(0,lock);o['capacity']=hex(minimum(o,d));tx['outputs'].append(o);tx['outputs_data'].append(d)
    else:
        deployment=read(a.deployment);require(deployment['release_sha256']==sha(a.release),'deployment release mismatch')
        for name in ['type','vk']:
            cell=live(a.rpc,deployment[name]);require(hx(h(raw(cell['data']['content'])))==r['artifacts'][name]['data_hash'],'deployed bytes mismatch');tx['cell_deps'].append(dep(deployment[name]))
        if a.operation=='create':
            typ=dict(code_hash=r['artifacts']['type']['data_hash'],hash_type='data1',args=hx(b'\x01'+h(cell_input(tx['inputs'][0])+u64(0))))
            tx['outputs']=[output(a.capacity,lock,typ)];tx['outputs_data']=[hx(state(0))]
            print('WARNING: no withdrawal/destruction path; application capacity remains locked.')
        else:
            app=op(a.application);old=live(a.rpc,app);o=old['output'];require(o['lock']==lock and o['type']['code_hash']==r['artifacts']['type']['data_hash'] and o['type']['hash_type']=='data1','unsupported application Cell')
            count=int.from_bytes(raw(old['data']['content'])[1:],'little');require(count<2**64-1,'terminal counter cannot update; capacity remains locked')
            tx['inputs'].insert(0,dict(since='0x0',previous_output=app));total+=int(o['capacity'],16)
            tx['outputs']=[o];tx['outputs_data']=[hx(state(count+1))]
    change=total-sum(int(o['capacity'],16) for o in tx['outputs'])-a.fee
    tx['outputs'].append(output(change,lock));tx['outputs_data'].append('0x')
    for o,d in zip(tx['outputs'],tx['outputs_data']):require(int(o['capacity'],16)>=minimum(o,d),'insufficient funding / occupied capacity')
    tx['witnesses']=[witness() for _ in tx['inputs']]
    save_tx(a.out,tx)
    print(json.dumps(dict(transaction_file=str(a.out),fee_shannons=a.fee,signs=False,broadcasts=False)))
def prove(a):
    r=integrity(a.release);network(a.rpc,r['policy']['network_domain']);tx=read(a.tx)['transaction'];old=live(a.rpc,tx['inputs'][0]['previous_output'])
    values=statement(r['policy'],tx,old);out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);setup=Path(r['setup']);m=read(setup/'manifest.json')
    for f in ['development.zkey','interop/circuit.r1cs','circuit/target/owned_counter_v1.json','verification_key.json']:
        require(sha(setup/f)==m['artifacts'][f],f'proving artifact changed: {f}')
    cli=setup/'backend-target/debug/noir-cli';require(sha(cli)==m['backend_binary_sha256'],'backend binary changed')
    write(out/'inputs.json',dict(zip(NAMES,values)));commands=[]
    def run(cmd):
        cmd=list(map(str,cmd));q=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=900)
        commands.append(dict(command=cmd,exit=q.returncode,stdout=q.stdout,stderr=q.stderr));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        require(q.returncode==0 and '[ERROR]' not in q.stdout,q.stdout+q.stderr)
    run([cli,'interop',setup/'circuit/target/owned_counter_v1.json',out/'inputs.json','--out',out/'interop'])
    require(sha(out/'interop/circuit.r1cs')==sha(setup/'interop/circuit.r1cs'),'R1CS differs from setup')
    snark=['npx','--offline','snarkjs@0.7.5']
    run(snark+['wtns','check',out/'interop/circuit.r1cs',out/'interop/witness.wtns'])
    run(snark+['groth16','prove',setup/'development.zkey',out/'interop/witness.wtns',out/'proof.json',out/'public.json'])
    require(read(out/'public.json')==values,'public ordering mismatch')
    run(snark+['groth16','verify',setup/'verification_key.json',out/'public.json',out/'proof.json'])
    wrong=values.copy();wrong[2]=str(int(wrong[2])+1);write(out/'wrong.json',wrong)
    run(['cargo','+1.95.0','run','--locked','--offline','-p','artifact-adapter','--bin','noir-ckb-adapter','--','--vk',setup/'verification_key.json','--proof',out/'proof.json','--public',out/'public.json','--negative-public',out/'wrong.json','--out',out/'adapter'])
    require((out/'adapter/vk.mol.bin').read_bytes()==Path(r['artifacts']['vk']['path']).read_bytes(),'wrong pinned VK')
    tx['witnesses'][0]=set_proof(tx['witnesses'][0],(out/'adapter/witness.mol.bin').read_bytes())
    save_tx(out/'transaction.json',tx);write(out/'binding.json',dict(statement=values,input=tx['inputs'][0]['previous_output'],release_sha256=sha(a.release)))
    print(out/'transaction.json')
def check(a):
    r=integrity(a.release);network(a.rpc,r['policy']['network_domain']);tx=read(a.tx)['transaction'];binding=read(a.proof/'binding.json')
    require(binding['release_sha256']==sha(a.release),'proof release differs')
    require(len(tx['inputs'])==2 and len(tx['outputs'])==2,'this client supports one app plus one funding/change Cell')
    old=live(a.rpc,tx['inputs'][0]['previous_output']);o=old['output'];new=tx['outputs'][0]
    require(o['type']==new['type'] and new['type']['code_hash']==r['artifacts']['type']['data_hash'] and new['type']['hash_type']=='data1','Type identity changed')
    require(o['lock']==new['lock'] and new['lock']==owner(new['lock']['args']),'owner changed or unsupported')
    require(o['capacity']==new['capacity'],'application capacity changed')
    values=statement(r['policy'],tx,old);require(values==binding['statement'] and values==read(a.proof/'public.json'),'operation differs; regenerate proof')
    require(0<=int(values[0])<2**64-1 and int(values[1])==int(values[0])+1,'invalid increment')
    require(witness_parts(tx['witnesses'][0])[1]==vec((a.proof/'adapter/witness.mol.bin').read_bytes()),'proof witness changed or misplaced')
    total=0
    for i in tx['inputs']:
        cell=live(a.rpc,i['previous_output']);require(cell['output']['lock']==new['lock'],'unexpected input owner');total+=int(cell['output']['capacity'],16)
    fee=total-sum(int(o['capacity'],16) for o in tx['outputs']);require(0<=fee<=100000000,'fee outside client limit')
    require(tx['outputs'][1]['lock']==new['lock'] and tx['outputs'][1]['type'] is None,'unexpected change destination')
    for o,d in zip(tx['outputs'],tx['outputs_data']):require(int(o['capacity'],16)>=minimum(o,d),'occupied capacity')
    require(r['policy']['owner_dep'] in tx['cell_deps'],'missing pinned ownership dep group')
    hashes=[hx(h(raw(live(a.rpc,d['out_point'])['data']['content']))) for d in tx['cell_deps'] if d['dep_type']=='code']
    require(hashes.count(r['artifacts']['type']['data_hash'])==1 and hashes.count(r['artifacts']['vk']['data_hash'])==1,'missing/ambiguous pinned code or VK')
    s=Path(r['setup']);cmd=['npx','--offline','snarkjs@0.7.5','groth16','verify',str(s/'verification_key.json'),str(a.proof/'public.json'),str(a.proof/'proof.json')]
    require(sha(s/'verification_key.json')==read(s/'manifest.json')['artifacts']['verification_key.json'],'VK JSON changed')
    q=subprocess.run(cmd,capture_output=True,text=True,timeout=60);require(q.returncode==0 and 'OK!' in q.stdout,'proof verification failed')
    print(json.dumps(dict(status='checked-before-signing',input=tx['inputs'][0]['previous_output'],statement=values,fee_shannons=fee,signs=False,broadcasts=False)))

def inspect(a):
    r=integrity(a.release)
    print(json.dumps(dict(status='artifacts-verified',release_sha256=sha(a.release),profile=r['profile'],policy=r['policy'],artifacts=r['artifacts'],development_only=r['development_only']),indent=2))
def confirm(a):
    r=integrity(a.release);network(a.rpc,r['policy']['network_domain']);expected=read(a.tx)['transaction'];q=rpc(a.rpc,'get_transaction',[a.hash]);require(q and q['tx_status']['status']=='committed','transaction not confirmed')
    actual=q['transaction'];require(all(actual[k]==expected[k] for k in expected if k!='witnesses'),'committed raw transaction differs')
    for i,(o,d) in enumerate(zip(expected['outputs'],expected['outputs_data'])):
        cell=live(a.rpc,dict(tx_hash=a.hash,index=hex(i)));require(cell['output']==o and cell['data']['content']==d,'live output mismatch')
    for i in expected['inputs']:require(rpc(a.rpc,'get_live_cell',[i['previous_output'],False])['status']!='live','input still live')
    receipt=dict(status='committed-and-cells-checked',tx_hash=a.hash,network=r['policy']['network_domain'],release_sha256=sha(a.release),outputs=[dict(tx_hash=a.hash,index=hex(i)) for i in range(len(expected['outputs']))])
    if a.deployment:
        require(len(expected['outputs'])==3,'deployment requires code, VK, change')
        for i,name in enumerate(['type','vk']):require(hx(h(raw(actual['outputs_data'][i])))==r['artifacts'][name]['data_hash'],'confirmed dependency artifact mismatch')
        receipt.update(type=receipt['outputs'][0],vk=receipt['outputs'][1])
    write(a.out,receipt);print(json.dumps(receipt,indent=2))
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('preflight');a.add_argument('--rpc',required=True);a.add_argument('--genesis',required=True);a.add_argument('--out',type=Path,required=True);a.set_defaults(func=preflight)
    a=sub.add_parser('build');a.add_argument('--policy',type=Path,required=True);a.add_argument('--setup',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.set_defaults(func=build)
    a=sub.add_parser('prepare');a.add_argument('operation',choices=['deploy','create','update']);a.add_argument('--owner',required=True);a.add_argument('--funding',required=True);a.add_argument('--deployment',type=Path);a.add_argument('--application');a.add_argument('--capacity',type=int,default=200*100_000_000);a.add_argument('--fee',type=int,default=1_000_000);a.add_argument('--out',type=Path,required=True);a.set_defaults(func=prepare)
    a=sub.add_parser('prove');a.add_argument('--tx',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.set_defaults(func=prove)
    a=sub.add_parser('confirm');a.add_argument('--tx',type=Path,required=True);a.add_argument('--hash',required=True);a.add_argument('--deployment',action='store_true');a.add_argument('--out',type=Path,required=True);a.set_defaults(func=confirm)
    a=sub.add_parser('inspect');a.add_argument('--release',type=Path,required=True);a.set_defaults(func=inspect)
    a=sub.add_parser('check');a.add_argument('--tx',type=Path,required=True);a.add_argument('--proof',type=Path,required=True);a.set_defaults(func=check)
    for name in ['prepare','prove','confirm','check']:
        sub.choices[name].add_argument('--release',type=Path,required=True);sub.choices[name].add_argument('--rpc',required=True)
    args=p.parse_args();args.func(args)
def cli():
    try:
        main()
    except RpcError as error:
        print(f'error: {error}',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':sys.exit(cli())
