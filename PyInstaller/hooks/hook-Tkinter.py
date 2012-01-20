import sys
import os
import re

from PyInstaller import is_win, is_darwin, is_unix, mf
from PyInstaller import bindepend
from PyInstaller.build import Tree
from PyInstaller.depend import dylib
from PyInstaller.hooks.hookutils import logger

def find_tk_win():
    pattern = re.compile(r'(?i)tcl(\d)(\d)\.dll')
    for nm, fnm, typ in binaries:
        mo = pattern.match(nm)
        if not mo:
            continue
        tclbindir = os.path.dirname(fnm)
        # Either Python21/DLLs with the .tcl files in
        #        Python21/tcl/tcl8.3 and Python21/tcl/tk8.3
        # or D:/Programs/Tcl/bin with the .tcl files in
        #    D:/Programs/Tcl/lib/tcl8.0 and D:/Programs/Tcl/lib/tk8.0
        ver = '.'.join(mo.groups())
        tclnm = 'tcl%s' % ver
        tknm = 'tk%s' % ver
        for attempt in ['../tcl', '../lib']:
            if os.path.exists(os.path.join(tclbindir, attempt, tclnm)):
                TCL_root = os.path.join(tclbindir, attempt, tclnm)
                TK_root = os.path.join(tclbindir, attempt, tknm)
                return TCL_root, TK_root


def find_tk_darwin(binaries):
    pattern = re.compile(r'_tkinter')
    for nm, fnm, typ in binaries:
        mo = pattern.match(nm)
        if not mo:
            continue
        TCL_root = "/System/Library/Frameworks/Tcl.framework/Versions/Current"
        TK_root = "/System/Library/Frameworks/Tk.framework/Versions/Current"
        return TCL_root, TK_root


def find_tk_unix(binaries):
    pattern = re.compile(r'libtcl(\d\.\d)?\.so')
    for nm, fnm, typ in binaries:
        mo = pattern.match(nm)
        if not mo:
            continue
        tclbindir = os.path.dirname(fnm)
        ver = mo.group(1)
        if ver is None:
            # We found "libtcl.so.0" so we need to get the version
            # from the lib directory.
            for name in os.listdir(tclbindir):
                mo = re.match(r'tcl(\d.\d)', name)
                if mo:
                    ver = mo.group(1)
                    break
        # Linux: /usr/lib with the .tcl files in /usr/lib/tcl8.3
        #        and /usr/lib/tk8.3
        TCL_root = os.path.join(tclbindir, 'tcl%s' % ver)
        TK_root = os.path.join(tclbindir, 'tk%s' % ver)
        return TCL_root, TK_root


def collect_tkfiles(tclroot, tkroot):
    if is_darwin:
        tcldir = "Tcl.framework"
        tkdir = "Tk.framework"
    else:
        tcldir = "tcl"
        tkdir = "tk"

    tcltree = Tree(tclroot, os.path.join('_MEI', tcldir),
                   excludes=['demos', 'encoding', '*.lib', 'tclConfig.sh'])
    tktree = Tree(tkroot, os.path.join('_MEI', tkdir),
                  excludes=['demos', 'encoding', '*.lib', 'tkConfig.sh'])
    return (tcltree + tktree)


def _prep_hook():
    # :fixme: find another way for accessing all dependencies
    # :fixme:     w/o a new ImportTracker instance.
    tracker = mf.ImportTracker()
    tracker.analyze_r('Tkinter')
    binaries = []
    for modnm, mod in tracker.modules.items():
        if isinstance(mod, mf.ExtensionModule):
            binaries.append((mod.__name__, mod.__file__, 'EXTENSION'))

    # Always add python's dependencies first. This ensures that
    # assembly depencies under Windows get pulled in first and we do
    # not need to add assembly DLLs to the exclude list explicitly.
    binaries.extend(bindepend.Dependencies([('', sys.executable, '')]))
    binaries.extend(bindepend.Dependencies(binaries))

    if is_win:
        tcl_tk = find_tk_win(binaries)
    elif is_darwin:
        tcl_tk = find_tk_darwin(binaries)
    elif is_unix:
        tcl_tk = find_tk_unix(binaries)
    else:
        # If no pattern is in place for this platform, skip TCL/TK detection.
        tcl_tk = -1

    if tcl_tk == -1:
        logger.info("... skipping TCL/TK detection on this target platform (%s)"
                    % sys.platform)
    elif tcl_tk is None:
        logger.error("could not find TCL/TK")
    else:
        global tktree
        tktree = collect_tkfiles(*tcl_tk)

# _prep_hook must be run only once to avoid recursion as _prep_hook
# calls ImportTracker().analyze_r('Tkinter') which imports this hook
# again.
_prep_hook()

def hook(mod):
    mod.datas.extend(tktree)
    return mod
