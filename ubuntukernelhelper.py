#!/usr/bin/env python

# Copyright (C) 2011-14, Carsten Juttner <carjay@gmx.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# Simple script automating the cool method described in
# http://blog.avirtualhome.com
#
# Also added a possibility to generate one's own local version so the "real"
# kernel package does not overwrite our own (one can "hold" the packages but
# we might want to still get notified when a new - higher - version goes "live")
#


import sys
import os
import pwd
from getopt import gnu_getopt, GetoptError
import re
import shutil
import subprocess

def pexec(args, showoutput = False):
    buf = None
    res = ""
    p = subprocess.Popen(args, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    while buf != "":
        buf = p.stdout.read()
        if showoutput:
            sys.stdout.write(buf)
            sys.stdout.flush()
        res += buf
    p.wait()
    buf = p.stdout.read()
    if showoutput:
        sys.stdout.write(buf)
        sys.stdout.flush()
    res += buf
    return res.strip(), p.returncode


def check_local(localname, debiandir):
    # if a localname is set we assume that we do want a local version
    if localname == None:
        sys.stdout.write("Do you want to make this a local .DEB so the version is higher than the distribution one ")
        sys.stdout.write("(else it will just have a different flavourname)?.\n")
        sys.stdout.write("(y/N)?")
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        if answer == 'y':
            sys.stdout.write("Enter a name you want to use for the local version (will get appended to the official version)\n")
            sys.stdout.flush()
            localname = sys.stdin.readline().strip()
        else:
            return True # no local version requested
    
    msg = "Local version of the Ubuntu Kernel Package"
    changelogpath = os.path.join(debiandir, "changelog")
    if not os.path.exists(changelogpath):
        # although not generating a local version would not mean we cannot build a kernel at all,
        # this occurring indicates something unusual happened so we better investigate and
        # return false here
        print("Error: changelog not found at %s, something is wrong" % changelogpath)
        return False
    output, err = pexec(['dch', '-l', localname, '-c', changelogpath, msg])
    if err != 0:
        print("An error occurred trying to update the changelog using dch:")
        sys.stdout.write(output)
        return False
    return True


def get_arch(debiandir):
    mcfgdir = os.path.join(os.getcwd(), debiandir, "config")
    configs = []
    for x in os.listdir(mcfgdir):
        if os.path.isdir(os.path.join(mcfgdir,x)):
            configs.append(x)
    configs = sorted(configs)
    
    print("Choose config:")
    for idx, cfg in enumerate(configs):
        print("  %d: %s" % (idx+1, cfg))
    sys.stdout.write("Enter desired number: ")
    sys.stdout.flush()
    cfgidx = sys.stdin.readline()
    try:
        arch = configs[int(cfgidx)-1]
    except ValueError:
        print("invalid selection")
        return None
    sys.stdout.write("\n")
    return arch


def generate_flavour(flavourname, arch, debiandir):
    currentkernel, err = pexec(['uname', '-r'])
    if err:
        print("Error reading current kernel with 'uname -r' : '%s'" % currentkernel)
        return None

    mcfgdir = os.path.join(os.getcwd(), debiandir, "config")

    # sanity check
    srcconfig = os.path.join(mcfgdir, arch, "config.flavour.generic")
    if not os.path.exists(srcconfig):
        print("Error, expected generic kernel config at '%s' but it does not exist" % srcconfig)
        return None

    # offer choice of using the currently running config (may fail if kernel versions are too distant)
    currentconfig = "/boot/config-%s" % (currentkernel)
    if os.path.exists(currentconfig):
        sys.stdout.write('Do you want to use the kernel config of the currently running kernel "%s" (y/N)? ' % currentkernel)
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        if answer == 'y':
            srcconfig = currentconfig
                
    
    destconfig = os.path.join(mcfgdir, arch, "config.flavour.%s" % flavourname)
    print("using '%s' kernel config to create new flavour %s" % (srcconfig, flavourname))
    
    shutil.copy2(srcconfig, destconfig)
    
    print("cleaning kernel dir")
    output, err = pexec(['fakeroot', 'debian/rules', 'clean'], True)
    if err:
        print("Error cleaning config")
        return None

    print("updating configs")
    output, err = pexec(['fakeroot', 'debian/rules', 'updateconfigs'], True)
    if err:
        print("Error updating configs")
        return None

    # here we'd usually want to edit the config which is a bit tricky
    # to do from a script, probably better to split this here somehow
    # so hand back the updated config file for further processing
    try:
        with open(destconfig, "rt") as configh:
            cfg = configh.read()
    except Exception, e:
        print("Error reading the generated config file '%s': '%s'" % (destconfig, str(e)))
        return None

    return cfg


def patch_flavour(flavourname, savedconfig, arch, debiandir, localname):
    # we need to reset the dir so build works
    # this means we have to save the generated config

    sys.stdout.write("Need to clear out the build dir, this will delete everything not committed!!!\n")
    sys.stdout.write("Are you sure (y/N)?")
    sys.stdout.flush()
    answer = sys.stdin.readline().strip().lower()
    if answer != 'y':
        print("build cancelled.")
        return
    
    output, err = pexec(['git', 'reset', '--hard'], True)
    if err:
        print("Error git-resetting")
        return
    
    output, err = pexec(['git', 'clean', '-df'], True)
    if err:
        print("Error git-cleaning")
        return
    
    if not check_local(localname, debiandir):
        return

    print("copying back kernel config")
    mcfgdir = os.path.join(os.getcwd(), debiandir, "config")
    kernelconfig = os.path.join(mcfgdir, arch, "config.flavour.%s" % flavourname)
    try:
        with open(kernelconfig,'wt+') as configh:
            configh.write(savedconfig)
    except Exception, e:
        print("Error writing back kernel config to '%s' : '%s'" % (kernelconfig, str(e)))
        return
    
    print("getting last abi")
    abidir = os.path.join(os.getcwd(), debiandir, "abi")
    abientries = os.listdir(abidir)
    abis = []
    for e in abientries:
        if os.path.isdir(os.path.join(abidir, e)):
            abis.append(e)
    if len(abis) == 0:
        print("Error: empty abi directory '%s'" % abidir)
        return
    currentabi = sorted(abis)[-1]

    currentabidir = os.path.join(abidir, currentabi, arch)
    
    print("copying generic abi configs to our flavour")
    
    genericabi    = os.path.join(currentabidir, "generic")
    genericmodabi = os.path.join(currentabidir, "generic.modules")
    
    if not os.path.exists(genericabi):
        print("Error: generic abi file '%s' does not exist" % genericabi)
        return

    if not os.path.exists(genericmodabi):
        print("Error: generic abi modules file '%s' does not exist" % genericmodabi)
        return
    
    shutil.copy2(genericabi,    os.path.join(currentabidir, flavourname))
    shutil.copy2(genericmodabi, os.path.join(currentabidir, "%s.modules" % flavourname))
    
    # we need to make the build system aware or our flavours
    getabifile = os.path.join(os.getcwd(), debiandir, "etc", "getabis")
    rulesfile = os.path.join(os.getcwd(), debiandir, "rules.d", "%s.mk" % arch)
    varssrcfile = os.path.join(os.getcwd(), debiandir, "control.d", "vars.generic")

    for filename, searchpattern in ( (getabifile, r'''getall\s+%s''' % arch), (rulesfile, r'''flavours.*''') ):
        try:
            print("appending flavour to %s" % filename)
            with open(filename, 'rt') as fh:
                linebuf = fh.readlines()
                
                with open(filename + '.repl', 'wb') as wh:
                    for l in linebuf:
                        if(re.match(searchpattern, l.strip())):
                            wh.write(l.strip() + " %s\n" % flavourname)
                        else:
                            wh.write(l)
                
        except Exception, e:
            print("Error appending flavour to file '%s' : '%s'" % (filename, str(e)))
            return
        shutil.move(filename + '.repl', filename)

    varsdestfile = os.path.join(os.getcwd(), debiandir, "control.d", "vars.%s" % flavourname)
    if not os.path.exists(varssrcfile):
        print("Error: file '%s' does not exist" % varssrcfile)
        return
    shutil.copy2(varssrcfile, varsdestfile)

    print("final kernel dir clean to generate the correct debian files")
    output, err = pexec(['fakeroot', 'debian/rules', 'clean'], True)
    if err:
        print("Error cleaning config")
        return


def usage():
    print("%s [options]" % os.path.basename(sys.argv[0]))
    print("    options:")
    print("      -h, --help:")
    print("        show this help file")
    print("      -f, --flavour:")
    print("        set flavourname to use (default is the current logged in user)")
    print("      -l, --local:")
    print("        set (dch) local name to use (else this is asked interactively)")
    

def main():
    flavourname = pwd.getpwuid(os.getuid())[0].lower().strip()
    localname   = None
    try:
        opts, args = gnu_getopt(sys.argv[1:], 'hf:l:', ['help', 'flavour=', 'local='])
        for opt, param in opts:
            if opt == '-h' or opt == '--help':
                usage()
                return
            elif opt == '-f' or opt == '--flavour':
                flavourname = param
            elif opt == '-l' or opt == '--local':
                localname = param
            else:
                print("Error: unexpected option in command line: '%s" % opt)
                return

    except GetoptError, e:
        print ("Error parsing command line arguments: '%s'" % str(e))
        return

   
    buf, err = pexec(["lsb_release" , "-c"])
    if not err:
        m = re.match(".*Codename:\s+(.*)", buf)
        if m:
            codename, = m.groups()
        else:
            print("Unexpected result from 'lsb_release -c' :\n'%s'" % buf.strip())
            return
    else:
        print("Error getting current distribution from lsb_release:\n'%s'" % buf.strip())
        return
       
    if codename not in [ "precise", "trusty" ]:
        print("Warning, untested combination")


    if "debian" not in os.listdir('.'):
        print("Error: script must be run in top ubuntu linux tree git directory")
        return

    debiandir = None

    # this depends on what is set up in debian.env
    try:
        with open(os.path.join(os.getcwd(),"debian","debian.env"),'rt') as envfh:
            envvar = envfh.readlines()
            for l in envvar:
                m = re.match("DEBIAN\s*=\s*(.+)", l)
                if m:
                    debiandir, = m.groups()
                    break
    except Exception,exc:
        print("Error opening debian environment setup:\n'%s'" % str(exc))
        return
    
    if debiandir == None:
        print("Error getting debian branch directory from debian/debian.env")
        return
    
    arch = get_arch(debiandir)
    if arch:
        config = generate_flavour(flavourname, arch, debiandir)
        if config:
            patch_flavour(flavourname, config, arch, debiandir, localname)
        else:
            return

    print("all patching done")
    print("you can now e.g. commit the changes:")
    print("")
    print("  git add .")
    print("  git commit -a -m \"%s modifications\"" % flavourname)
    print("")
    print("then build them:")
    print("")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-indep")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-perarch")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-%s" % flavourname)
    print("")
    print("if you want to create a debug package you can do it this way:")
    print("")
    # note that skipdbg is not part of the environment because the Makefiles assume that you do not
    # want a fully blown debug package when not doing a "full_build". Setting full_build is not an
    # option since this adds targets that we do not want to build. So use a variable override here.
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-%s skipdbg=false" % flavourname)


try:
    main()
except KeyboardInterrupt:
    pass
