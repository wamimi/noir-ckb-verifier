#!/usr/bin/env python3
"""Full disposable LOCAL-ONLY counter lifecycle. Signs and broadcasts only to loopback dev chain.
Development keys stay in ignored target/private. Never use these keys on public networks.
"""
import argparse,json,os,secrets,subprocess,time
from pathlib import Path
import owned_counter as c
CKB_SHA='800d625b4baaa55cf6408b2f30ad744c4df90d52b94023ce226be875327c9493'
CLI_SHA='994166d983955fb59b6bab172485b3f65ff60487493b62a6569ad93eaa7adffb'
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ['out','ckb','ckb-cli','backend']:ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--rpc-port',type=int,default=18124);ap.add_argument('--p2p-port',type=int,default=18125);ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    out=a.out.resolve();c.require(out.is_relative_to(c.ROOT/'target'),'development accounts must stay below ignored target')
    c.require(c.sha(a.ckb)==CKB_SHA and c.sha(a.ckb_cli)==CLI_SHA,'unsupported node/wallet binary; use pinned Darwin ARM64 releases')
    out.mkdir(parents=True,exist_ok=False);(out/'private').mkdir(mode=0o700);key=out/'private/owner.key';key.write_text(secrets.token_hex(32)+'\n');key.chmod(0o600)
    env=os.environ.copy();env['CKB_CLI_HOME']=str(out/'wallet');env['PYTHONDONTWRITEBYTECODE']='1';url=f'http://127.0.0.1:{a.rpc_port}';logs=[];node=None;manifest=dict(status='running',profile=c.PROFILE,network='isolated-local-development',tool_binaries=dict(ckb_sha256=CKB_SHA,ckb_cli_sha256=CLI_SHA))
    def save():
        (out/'commands.json').write_text(json.dumps(logs,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def run(cmd):
        cmd=list(map(str,cmd));q=subprocess.run(cmd,cwd=c.ROOT,env=env,capture_output=True,text=True,timeout=1800);logs.append(dict(command=cmd,cwd=str(c.ROOT),exit=q.returncode,stdout=q.stdout,stderr=q.stderr));save();print(cmd[:4],'exit',q.returncode,flush=True);c.require(q.returncode==0,q.stdout+q.stderr);return q.stdout
    def client(*args):return run(['python3',c.ROOT/'scripts/owned_counter.py',*args])
    def wallet(*args):return run([a.ckb_cli.resolve(),'--url',url,'--output-format','json','tx',*args])
    def submit(tx,label):
        before=c.read(tx)['transaction'];wallet('sign-inputs','--tx-file',tx,'--privkey-path',key,'--add-signatures','--skip-check');c.require(c.read(tx)['transaction']==before,'wallet modified prepared transaction')
        if label=='update':client('check','--release',release,'--rpc',url,'--tx',tx,'--proof',out/'update-proof')
        txhash=json.loads(wallet('send','--tx-file',tx,'--skip-check'));c.write(out/(label+'-submitted.json'),dict(tx_hash=txhash,status='submitted-not-yet-confirmed'))
        for _ in range(12):
            status=c.rpc(url,'get_transaction',[txhash])['tx_status'];
            if status['status']=='committed':break
            c.require(status['status']!='rejected',str(status));c.rpc(url,'generate_block',[]);time.sleep(.1)
        c.require(c.rpc(url,'get_transaction',[txhash])['tx_status']['status']=='committed','pending transaction: do not resubmit')
        extra=['--deployment'] if label=='deployment' else []
        client('confirm','--release',release,'--rpc',url,'--tx',tx,'--hash',txhash,'--out',out/(label+'-receipt.json'),*extra)
        manifest[label]=dict(tx_hash=txhash,status='committed-and-cells-checked');save();return txhash
    try:
        pub=json.loads(run([a.ckb_cli.resolve(),'--local-only','--output-format','json','util','key-info','--privkey-path',key]));c.write(out/'owner-public.json',pub);arg=pub['lock_arg']
        run([a.ckb.resolve(),'-C',out/'node','init','--chain','dev','--rpc-port',a.rpc_port,'--p2p-port',a.p2p_port,'--genesis-message','noir-ckb-owned-counter-v1-local-only','--ba-arg',arg])
        spec=out/'node/specs/dev.toml';text=spec.read_text();text=text.replace('[params]',f'[[genesis.issued_cells]]\ncapacity = 100_000_000_00000000\nlock.code_hash = "{c.OWNER_CODE}"\nlock.args = "{arg}"\nlock.hash_type = "type"\n\n[params]');spec.write_text(text)
        config=out/'node/ckb.toml';text=config.read_text().replace('/ip4/0.0.0.0/tcp/','/ip4/127.0.0.1/tcp/').replace('max_outbound_peers = 8','max_outbound_peers = 0').replace('discovery_local_address = true','discovery_local_address = false').replace('"Debug", "Terminal"]','"Debug", "Terminal", "IntegrationTest", "Indexer"]');config.write_text(text)
        with (out/'node.log').open('w') as log:node=subprocess.Popen([str(a.ckb.resolve()),'-C',str(out/'node'),'run'],stdout=log,stderr=subprocess.STDOUT)
        for _ in range(40):
            c.require(node.poll() is None,'node failed; inspect node.log')
            try:genesis=c.rpc(url,'get_block_hash',['0x0']);break
            except Exception:time.sleep(.25)
        else:raise RuntimeError('node RPC did not start')
        manifest['genesis']=genesis;save();client('preflight','--rpc',url,'--genesis',genesis,'--out',out/'policy.json')
        run(['python3',c.ROOT/'scripts/setup-owned-counter.py','--out',out/'setup','--backend',a.backend.resolve()])
        client('build','--policy',out/'policy.json','--setup',out/'setup','--out',out/'build');release=out/'build/release.json'
        run(['python3',c.ROOT/'scripts/check-counter-ranges.py','--release',release,'--out',out/'ranges'])
        g=c.rpc(url,'get_block_by_number',['0x0'])['transactions'][0];i=next(i for i,o in enumerate(g['outputs']) if o['lock']['args']==arg)
        client('prepare','deploy','--release',release,'--rpc',url,'--owner',arg,'--funding',g['hash']+':'+hex(i),'--out',out/'deploy.json')
        deployment=submit(out/'deploy.json','deployment')
        client('prepare','create','--release',release,'--rpc',url,'--owner',arg,'--funding',deployment+':2','--deployment',out/'deployment-receipt.json','--out',out/'create.json')
        created=submit(out/'create.json','creation')
        client('prepare','update','--release',release,'--rpc',url,'--owner',arg,'--funding',created+':1','--application',created+':0','--deployment',out/'deployment-receipt.json','--out',out/'update.json')
        client('prove','--release',release,'--rpc',url,'--tx',out/'update.json','--out',out/'update-proof')
        run(['python3',c.ROOT/'scripts/check-owned-counter.py','--release',release,'--rpc',url,'--create',out/'create.json','--update',out/'update-proof/transaction.json','--proof',out/'update-proof','--key',key,'--out',out/'matrix'])
        if a.mutations:run(['python3',c.ROOT/'scripts/mutate-owned-counter.py','--release',release,'--baseline',out/'matrix','--key',key,'--out',out/'mutations'])
        submit(out/'update-proof/transaction.json','update')
        manifest['status']='locally-validated';manifest['release_sha256']=c.sha(release);manifest['matrix_cases']=len(c.read(out/'matrix/results.json'));manifest['mutations_executed']=a.mutations
    except Exception as error:manifest['status']='failed';manifest['error']=str(error);raise
    finally:
        if node is not None:
            node.terminate()
            try:node.wait(timeout=15)
            except subprocess.TimeoutExpired:node.kill();node.wait()
        save()
    print(out/'manifest.json')
if __name__=='__main__':main()
