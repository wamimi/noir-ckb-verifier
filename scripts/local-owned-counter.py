#!/usr/bin/env python3
"""Full disposable LOCAL-ONLY counter lifecycle. Signs and broadcasts only to loopback dev chain.
Development keys stay in ignored target/private. Never use these keys on public networks.
"""
import argparse,json,os,secrets,subprocess,time
from pathlib import Path
import owned_counter as c
import counter_platform as cp
QUICK_SKIPPED=['check-counter-ranges (5 out-of-range rejections + maximum-range proof)','check-owned-counter (48 adversarial CKB-VM cases)','mutate-owned-counter (3 contract mutations)']
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ['out','ckb','ckb-cli','backend']:ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--rpc-port',type=int,default=18124);ap.add_argument('--p2p-port',type=int,default=18125);ap.add_argument('--mutations',action='store_true');ap.add_argument('--quick',action='store_true',help='skip ranges, VM matrix and mutations; proof, pre-signing check and signed lifecycle still run');ap.add_argument('--join-test',action='store_true',help='deploy with one key, publish a bundle, then create and update as a second key through join-counter-testnet.py');a=ap.parse_args()
    c.require(not(a.quick and a.mutations),'--quick and --mutations are mutually exclusive')
    c.require(not(a.join_test and (a.quick or a.mutations)),'--join-test is its own mode')
    platform_key,entry=cp.detect();CKB_SHA=entry['tools']['ckb']['binary_sha256'];CLI_SHA=entry['tools']['ckb-cli']['binary_sha256']
    out=a.out.resolve();c.require(out.is_relative_to(c.ROOT/'target'),'development accounts must stay below ignored target')
    c.require(c.sha(a.ckb)==CKB_SHA and c.sha(a.ckb_cli)==CLI_SHA,f'unsupported node/wallet binary; use the pinned {platform_key} releases (scripts/fetch-counter-tools.py)')
    out.mkdir(parents=True,exist_ok=False);(out/'private').mkdir(mode=0o700);key=out/'private/owner.key';key.write_text(secrets.token_hex(32)+'\n');key.chmod(0o600)
    env=cp.tool_environment(os.environ,a.ckb.resolve().parent.parent,platform_key,entry);env['CKB_CLI_HOME']=str(out/'wallet');env['PYTHONDONTWRITEBYTECODE']='1';url=f'http://127.0.0.1:{a.rpc_port}';logs=[];node=None;manifest=dict(status='running',profile=c.PROFILE,network='isolated-local-development',platform=platform_key,platform_status=entry['status'],validation='join-test' if a.join_test else ('quick' if a.quick else ('full' if a.mutations else 'full-without-mutations')),skipped=QUICK_SKIPPED if (a.quick or a.join_test) else ([] if a.mutations else [QUICK_SKIPPED[2]]),tool_binaries=dict(ckb_sha256=CKB_SHA,ckb_cli_sha256=CLI_SHA))
    def save():
        (out/'commands.json').write_text(json.dumps(logs,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def run(cmd):
        cmd=list(map(str,cmd));q=subprocess.run(cmd,cwd=c.ROOT,env=env,capture_output=True,text=True,timeout=1800);logs.append(dict(command=cmd,cwd=str(c.ROOT),exit=q.returncode,stdout=q.stdout,stderr=q.stderr));save();print(cmd[:4],'exit',q.returncode,flush=True);c.require(q.returncode==0,q.stdout+q.stderr);return q.stdout
    steps=(['local chain','setup + fresh proof','contract build','deployment','publish bundle','participant: verify bundle and toolchain','participant: create','participant: update'] if a.join_test else
           ['local chain','setup + fresh proof','contract build']+([] if a.quick else ['range checks'])+['deployment','creation','update proof']+([] if a.quick else ['48-case VM matrix'])+(['mutations'] if a.mutations else [])+['pre-signing check, sign, submit, confirm update'])
    def stage(name):
        print(f'== Stage {steps.index(name)+1}/{len(steps)}: {name}',flush=True)
    def client(*args):return run(['python3',c.ROOT/'scripts/owned_counter.py',*args])
    def wallet(*args):return run([a.ckb_cli.resolve(),'--url',url,'--output-format','json','tx',*args])
    def join(*args):return run(['python3','-B',c.ROOT/'scripts/join-counter-testnet.py',*args])
    def mine(txhash):
        for _ in range(12):
            status=c.rpc(url,'get_transaction',[txhash])['tx_status']
            if status['status']=='committed':break
            c.require(status['status']!='rejected',str(status));c.rpc(url,'generate_block',[]);time.sleep(.1)
        c.require(c.rpc(url,'get_transaction',[txhash])['tx_status']['status']=='committed','pending transaction: do not resubmit')
    def participant_submit(tx,label,work,pkey):
        before=c.read(tx)['transaction'];wallet('sign-inputs','--tx-file',tx,'--privkey-path',pkey,'--add-signatures','--skip-check');c.require(c.read(tx)['transaction']==before,'wallet modified prepared transaction')
        if label.startswith('participant-update'):join('check','--work',work)
        txhash=json.loads(wallet('send','--tx-file',tx,'--skip-check'));mine(txhash);join('confirm','--work',work,'--hash',txhash)
        manifest[label]=dict(tx_hash=txhash,status='committed-and-cells-checked');save();return txhash
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
        stage('local chain');pub=json.loads(run([a.ckb_cli.resolve(),'--local-only','--output-format','json','util','key-info','--privkey-path',key]));c.write(out/'owner-public.json',pub);arg=pub['lock_arg']
        run([a.ckb.resolve(),'-C',out/'node','init','--chain','dev','--rpc-port',a.rpc_port,'--p2p-port',a.p2p_port,'--genesis-message','noir-ckb-owned-counter-v1-local-only','--ba-arg',arg])
        issued=[arg]
        if a.join_test:
            pkey=out/'private/participant.key';pkey.write_text(secrets.token_hex(32)+'\n');pkey.chmod(0o600)
            parg=json.loads(run([a.ckb_cli.resolve(),'--local-only','--output-format','json','util','key-info','--privkey-path',pkey]))['lock_arg'];c.require(parg!=arg,'participant key must differ');issued.append(parg)
        spec=out/'node/specs/dev.toml';text=spec.read_text();text=text.replace('[params]',''.join(f'[[genesis.issued_cells]]\ncapacity = 100_000_000_00000000\nlock.code_hash = "{c.OWNER_CODE}"\nlock.args = "{x}"\nlock.hash_type = "type"\n\n' for x in issued)+'[params]');spec.write_text(text)
        config=out/'node/ckb.toml';text=config.read_text().replace('/ip4/0.0.0.0/tcp/','/ip4/127.0.0.1/tcp/').replace('max_outbound_peers = 8','max_outbound_peers = 0').replace('discovery_local_address = true','discovery_local_address = false').replace('"Debug", "Terminal"]','"Debug", "Terminal", "IntegrationTest", "Indexer"]');config.write_text(text)
        with (out/'node.log').open('w') as log:node=subprocess.Popen([str(a.ckb.resolve()),'-C',str(out/'node'),'run'],stdout=log,stderr=subprocess.STDOUT)
        for _ in range(40):
            c.require(node.poll() is None,'node failed; inspect node.log')
            try:genesis=c.rpc(url,'get_block_hash',['0x0']);break
            except Exception:time.sleep(.25)
        else:raise RuntimeError('node RPC did not start')
        manifest['genesis']=genesis;save();client('preflight','--rpc',url,'--genesis',genesis,'--out',out/'policy.json')
        stage('setup + fresh proof');run(['python3',c.ROOT/'scripts/setup-owned-counter.py','--out',out/'setup','--backend',a.backend.resolve()])
        stage('contract build');client('build','--policy',out/'policy.json','--setup',out/'setup','--out',out/'build');release=out/'build/release.json'
        if not a.quick:stage('range checks');run(['python3',c.ROOT/'scripts/check-counter-ranges.py','--release',release,'--out',out/'ranges'])
        g=c.rpc(url,'get_block_by_number',['0x0'])['transactions'][0];i=next(i for i,o in enumerate(g['outputs']) if o['lock']['args']==arg)
        client('prepare','deploy','--release',release,'--rpc',url,'--owner',arg,'--funding',g['hash']+':'+hex(i),'--out',out/'deploy.json')
        stage('deployment');deployment=submit(out/'deploy.json','deployment')
        if a.join_test:
            stage('publish bundle');join('make-bundle','--release',release,'--deployment',out/'deployment-receipt.json','--out',out/'join-bundle')
            stage('participant: verify bundle and toolchain');jw=out/'join';join('init','--out',jw,'--rpc',url,'--bundle',out/'join-bundle','--no-record','--backend',a.backend.resolve(),'--tools',a.ckb.resolve().parent.parent)
            pi=next(i for i,o in enumerate(g['outputs']) if o['lock']['args']==parg)
            stage('participant: create');join('create','--work',jw,'--owner',parg,'--funding',g['hash']+':'+hex(pi));participant_submit(jw/'create.json','participant-creation',jw,pkey)
            stage('participant: update');join('update','--work',jw);participant_submit(Path(c.read(jw/'state.json')['tx']),'participant-update-1',jw,pkey)
            st=c.read(jw/'state.json');c.require(st['count']==1 and st['owner']==parg,'participant counter did not reach 1')
            manifest.update(status='join-test-validated',release_sha256=c.sha(release),participant_owner=parg,deployer_owner=arg,matrix_cases=0,mutations_executed=False);save();print(out/'manifest.json');return
        client('prepare','create','--release',release,'--rpc',url,'--owner',arg,'--funding',deployment+':2','--deployment',out/'deployment-receipt.json','--out',out/'create.json')
        stage('creation');created=submit(out/'create.json','creation')
        client('prepare','update','--release',release,'--rpc',url,'--owner',arg,'--funding',created+':1','--application',created+':0','--deployment',out/'deployment-receipt.json','--out',out/'update.json')
        stage('update proof');client('prove','--release',release,'--rpc',url,'--tx',out/'update.json','--out',out/'update-proof')
        if not a.quick:stage('48-case VM matrix');run(['python3',c.ROOT/'scripts/check-owned-counter.py','--release',release,'--rpc',url,'--create',out/'create.json','--update',out/'update-proof/transaction.json','--proof',out/'update-proof','--key',key,'--out',out/'matrix'])
        if a.mutations:stage('mutations');run(['python3',c.ROOT/'scripts/mutate-owned-counter.py','--release',release,'--baseline',out/'matrix','--key',key,'--out',out/'mutations'])
        stage('pre-signing check, sign, submit, confirm update');submit(out/'update-proof/transaction.json','update')
        manifest['status']='quick-lifecycle-validated' if a.quick else 'locally-validated';manifest['release_sha256']=c.sha(release);manifest['matrix_cases']=0 if a.quick else len(c.read(out/'matrix/results.json'));manifest['mutations_executed']=a.mutations
    except Exception as error:manifest['status']='failed';manifest['error']=str(error);raise
    finally:
        if node is not None:
            node.terminate()
            try:node.wait(timeout=15)
            except subprocess.TimeoutExpired:node.kill();node.wait()
        save()
    print(out/'manifest.json')
if __name__=='__main__':main()
