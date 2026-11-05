"""Read-only Toolhelp process inventory; no tasklist/WMI/CIM dependency."""
import ctypes
from ctypes import wintypes as wt

class ProcessEntry(ctypes.Structure):
    _fields_=[('dwSize',wt.DWORD),('cntUsage',wt.DWORD),('th32ProcessID',wt.DWORD),
        ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wt.DWORD),
        ('cntThreads',wt.DWORD),('th32ParentProcessID',wt.DWORD),
        ('pcPriClassBase',wt.LONG),('dwFlags',wt.DWORD),('szExeFile',wt.WCHAR*260)]

def processes():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[wt.DWORD,wt.DWORD];k.CreateToolhelp32Snapshot.restype=wt.HANDLE
    k.Process32FirstW.argtypes=[wt.HANDLE,ctypes.POINTER(ProcessEntry)];k.Process32FirstW.restype=wt.BOOL
    k.Process32NextW.argtypes=[wt.HANDLE,ctypes.POINTER(ProcessEntry)];k.Process32NextW.restype=wt.BOOL
    k.CloseHandle.argtypes=[wt.HANDLE];k.CloseHandle.restype=wt.BOOL
    snapshot=k.CreateToolhelp32Snapshot(0x2,0)
    if snapshot in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
    result=[]
    try:
        entry=ProcessEntry();entry.dwSize=ctypes.sizeof(entry)
        ok=k.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            result.append((int(entry.th32ProcessID),entry.szExeFile))
            ok=k.Process32NextW(snapshot,ctypes.byref(entry))
        error=ctypes.get_last_error()
        if error!=18:raise ctypes.WinError(error)
    finally:k.CloseHandle(snapshot)
    return result

def game_pids():return [pid for pid,name in processes() if name.casefold()=='newpal_release.exe']
