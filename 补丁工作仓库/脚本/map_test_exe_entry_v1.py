"""GUI entry with persistent error reporting for a windowed portable EXE."""
import json,sys,traceback
from pathlib import Path
from map_test_tool_v1 import main

if __name__=='__main__':
 try:main()
 except Exception as error:
  detail=traceback.format_exc()
  if '--report' in sys.argv:
   Path(sys.argv[sys.argv.index('--report')+1]).write_text(json.dumps({'status':'failed','error':detail},ensure_ascii=False,indent=2),encoding='utf-8')
  elif '--self-check' not in sys.argv:
   from tkinter import messagebox
   folder=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
   try:(folder/'传送器错误日志.txt').write_text(detail,encoding='utf-8')
   except OSError:pass
   messagebox.showerror('地图传送器启动失败',str(error))
  sys.exit(1)
