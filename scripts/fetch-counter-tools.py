#!/usr/bin/env python3
"""Fetch pinned official Darwin ARM64 CKB tools. No wallet access or network deployment."""
import argparse,hashlib,json,platform,urllib.request,zipfile
from pathlib import Path
TOOLS=[('ckb','v0.210.0','ckb_v0.210.0_aarch64-apple-darwin-portable','80477890543aa4425666dfe4f74022d4c8237cb9767052fef68e7a7e6b811ef2','800d625b4baaa55cf6408b2f30ad744c4df90d52b94023ce226be875327c9493'),('ckb-cli','v2.0.0','ckb-cli_v2.0.0_aarch64-apple-darwin','e19e0fc8228e3cc9eba5e4e3506f2559a8321cf472a9f5392bc6dc4093308d06','994166d983955fb59b6bab172485b3f65ff60487493b62a6569ad93eaa7adffb')]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if (platform.system(),platform.machine())!=('Darwin','arm64'):raise SystemExit('This tested installer pins Darwin ARM64 only; other hosts require separately validated tool pins.')
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);records=[]
 for repo,tag,name,sha,binary_sha in TOOLS:
  url=f'https://github.com/nervosnetwork/{repo}/releases/download/{tag}/{name}.zip';archive=out/(name+'.zip');urllib.request.urlretrieve(url,archive)
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=sha:raise ValueError('archive digest mismatch')
  with zipfile.ZipFile(archive) as z:
   for entry in z.infolist():
    if not (out/entry.filename).resolve().is_relative_to(out):raise ValueError('unsafe archive member')
   z.extractall(out)
  binary=out/name/repo
  if hashlib.sha256(binary.read_bytes()).hexdigest()!=binary_sha:raise ValueError('binary digest mismatch')
  binary.chmod(0o755);records.append(dict(tool=repo,version=tag,url=url,archive_sha256=sha,binary_sha256=binary_sha,binary=str(binary)))
 (out/'manifest.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
if __name__=='__main__':main()
