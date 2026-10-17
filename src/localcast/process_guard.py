"""Windows job lifetime: only FFmpeg children launched by this application.

The child starts suspended, is assigned to our kill-on-close job, then resumes.
This closes the crash window between spawning a running child and claiming it.
"""

import ctypes
import os
import subprocess
from ctypes import wintypes

import psutil


class ProcessGuard:
    def __init__(self):
        self.handle = None
        if os.name != 'nt':
            return

        class Basic(ctypes.Structure):
            _fields_ = [('ProcessTime', ctypes.c_longlong), ('JobTime', ctypes.c_longlong),
                        ('Flags', wintypes.DWORD), ('Minimum', ctypes.c_size_t),
                        ('Maximum', ctypes.c_size_t), ('Active', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t), ('Priority', wintypes.DWORD),
                        ('Scheduling', wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [('Basic', Basic), ('IO', ctypes.c_ulonglong * 6),
                        ('ProcessMemory', ctypes.c_size_t), ('JobMemory', ctypes.c_size_t),
                        ('PeakProcess', ctypes.c_size_t), ('PeakJob', ctypes.c_size_t)]

        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                      ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                 ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def spawn(self, command, **options):
        if self.handle:
            options['creationflags'] = options.get('creationflags', 0) | 0x4  # CREATE_SUSPENDED
        process = subprocess.Popen(command, **options)
        try:
            if self.handle:
                if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
                    raise ctypes.WinError(ctypes.get_last_error())
                psutil.Process(process.pid).resume()
            return process
        except Exception:
            process.kill()
            process.wait(timeout=5)
            for pipe in (process.stdout, process.stderr):
                if pipe:
                    pipe.close()
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
