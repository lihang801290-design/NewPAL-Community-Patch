"""Wait for normal game exit, back up baseline, install/read back, launch via Steam."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import winreg
import flash_v4 as glow
import walk_start_v1 as walk
from newpal_processes_v1 import game_pids


def running():
    # Inventory failures propagate; never mistake a failed command for no game.
    return bool(game_pids())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wait',type=int,default=180)
    ap.add_argument('--launch-steam',action='store_true');args=ap.parse_args()
    source=glow.ROOT/'NewPAL_Release.exe'
    candidate=glow.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.flash-v4-walk-v1.exe'
    baseline=source.read_bytes();glow.verify_baseline(baseline)
    flashed,_=glow.build_candidate(baseline)
    expected=walk.apply(flashed)
    if candidate.read_bytes()!=expected:raise ValueError('candidate differs from regenerated verified build')
    appid=(glow.ROOT/'Steam_appid.txt').read_text(encoding='ascii').strip()
    if not appid.isdigit():raise ValueError('invalid Steam app id')
    steam=None
    if args.launch_steam:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
            steam=Path(winreg.QueryValueEx(key,'SteamExe')[0])
        if not steam.is_file():raise ValueError('Steam executable not found')
    print('Waiting for normal game exit; the running game will not be forced closed',flush=True)
    deadline=time.monotonic()+args.wait
    while running():
        if time.monotonic()>=deadline:raise TimeoutError('Game still running; no file changed')
        time.sleep(1)
    if source.read_bytes()!=baseline:raise ValueError('installed EXE changed while waiting')
    backup=glow.ROOT/'修改exe备份/NewPAL_Release.exe.orig-flash10s-walk-v1-20261029'
    if backup.exists():
        if backup.read_bytes()!=baseline:raise ValueError('backup name already has different content')
    else:
        shutil.copy2(source,backup)
    if backup.read_bytes()!=baseline:raise IOError('backup readback differs')
    temp=source.with_name('NewPAL_Release.exe.installing')
    with temp.open('xb') as f:
        f.write(expected);f.flush();os.fsync(f.fileno())
    if running():
        temp.unlink();raise RuntimeError('Game restarted before install; no game file changed')
    try:
        os.replace(temp,source)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    if source.read_bytes()!=expected:raise IOError('installed EXE readback differs')
    report={'status':'installed and readback verified; joystick gameplay validation pending',
            'baseline_sha1':glow.GOLDEN,'installed_sha1':hashlib.sha1(expected).hexdigest(),
            'backup':str(backup),'steam_app_id':appid,'steam_launch_requested':args.launch_steam}
    output=glow.ROOT/'补丁工作仓库/候选版本/installation-v1.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if args.launch_steam:
        subprocess.Popen([str(steam),'-applaunch',appid],cwd=str(steam.parent),
                         creationflags=subprocess.CREATE_NO_WINDOW)
        print('Launch requested through Steam',flush=True)


if __name__=='__main__':main()
