#!/usr/bin/env python


# ccc_generic.py: Complete Consistency Check
#  Consistency check between Storage and DQ2

import sys, os, fcntl, stat, socket, time, re, marshal, pprint, hashlib
import fcntl, errno
import urllib, urllib2
from select import select
try: import simplejson as json
except ImportError: import json

# Make sure another instance is not already running
LOCKFILE="/tmp/ccc_generic.lock"
_lock = open(LOCKFILE, 'w')
os.chmod(LOCKFILE, 0666)
try:    
    status = fcntl.lockf(_lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
except IOError, e:
    if e.errno in (errno.EAGAIN, errno.EACCES):
        print "Cannot lock %s, another instance of ccc may be running" % LOCKFILE
        sys.exit(1)
    else:
        raise
    
t1 = t0 = time.time()
print "Started at", time.ctime(t0)
timestamp = time.strftime("%F-%H%M", time.localtime(t0))

hostname = socket.gethostname()
version_msg = "ccc_generic.py running on %s" % hostname
print version_msg

storage_dump_file = None
storage_dump = None

check_dq2 = True
min_age = 6*3600 # 7 hours, don't flag any files newer than this
dq2_cache_dir = '/var/tmp/dq2/' # For caching dq2 lookups
dq2 = None
output_dir = ''

def Usage(progname):
    print "Usage: %s [-o output_dir] [-m min_age] [-c storage_dump_command | -f storage_dump_file ]  storage_root site" % progname
    print "   storage_root: Root directory of your storage "
    print "   site: Site name as registered in AGIS "
    print "   -m min_age: don't flag files newer than this (default=2 hours)"
    print "         use 's' for seconds(default), 'm'=minutes, 'h'=hours, 'd'=days"
    print "   -o specifies directory for (html) output, default is working directory"
    print "   -c command that outputs the list of files in your storage "
    print "   -f file that contains a list of the files in  your storage "
    print "   If neither -c nor  -f is used, the command will default to ", storage_dump

if "pychecker" in sys.argv[0]:     
    args = sys.argv[2:] 
else: 
    args = sys.argv[1:] 

required_args=[]

while args:
    arg = args.pop(0)
    if arg == '-o':
        output_dir = args.pop(0)
    elif arg == '-f':
        storage_dump_file = args.pop(0)
    elif arg == '-c':
        storage_dump = args.pop(0)
    elif arg == '-m':
        min_age = args.pop(0)
        mult = None
        suff = min_age[-1]
        if suff in 'sS':
            mult = 1
        elif suff in 'mM':
            mult = 60
        elif suff in 'hH':
            mult = 3600
        elif suff in 'dD':
            mult = 3600*24
        if mult:
            min_age = min_age[:-1]
        else:
            mult = 1
        min_age = float(min_age)*mult
    elif arg == '-h':
        Usage(sys.argv[0])
        sys.exit(0)
    elif arg[0] == '-':
        print "Invalid option", arg
        Usage(sys.argv[0])
        sys.exit(1)
    else: 
        required_args.append(arg)
if len(required_args) != 2:
    print "Missing arguments"
    Usage(sys.argv[0])
    sys.exit(1)
else:
    storage_root = required_args.pop(0)
    site = required_args.pop(0)
if not storage_dump and not storage_dump_file:
	storage_dump = "find " + storage_root + " -type f |"

if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)
    
site_dirs= {}

try:
    req = urllib2.Request("http://atlas-agis-api.cern.ch/request/ddmendpoint/query/list/?json&state=ACTIVE&rc_site="+site, None)
    opener = urllib2.build_opener()
    f = opener.open(req)
    res=json.load(f)
    for s in res:
        #print  s["name"], s["endpoint"]
        site_dirs[s["name"]]= s["endpoint"]
except:
    print "Unexpected error:", sys.exc_info()[0]
        
print "Using storage root", storage_root
print "Min age = ", min_age, "(seconds)"

sites=site_dirs.keys()

#keys for data tuples
POOL,TIME,SIZE = 0, 1, 2
FILEID,CTIME,GUID = 0, 1, 2

def unitize(x):
    suff = 'BKMGTPEZY'
    while x > 1024 and suff:
        x /= 1024.0
        suff = suff[1:]
    return "%.4g%s" % (x, suff[0])

def plural(var, label):
    fmt="%d %s"
    if var != 1: fmt += 's'
    return fmt % (var, label)

class Page:
    def __init__(self, basename, title=None, html=False):
        title = title or basename
        if html:
            suffix = '.html'
        else:
            suffix = ''
        self.html = html
        self.title = title
        self.filename = "%s-%s%s" % (basename, timestamp, suffix)
        self.fullname = os.path.join(output_dir, self.filename)
        self._f = None # File is not opened until we write to it
    def close(self):
        if not self._f:
            return
        if self.html:
            self._f.write("\n</pre></body></html>\n")
        self._f.close()
        self._f = None
    def write(self, text):
        if self._f is None:
            self._f = open(self.fullname, 'w')
            if self.html:
                self._f.write("<html><head><title>%s</title></head><body>\n<pre>" % self.title)
        self._f.write(text)
        self._f.flush()
    def __del__(self):
        if self._f:
            self.close()

main_page = Page('ccc', title='ccc results for %s'%timestamp, html=True)
msg = "Started at %s" % time.ctime(t0)
print "Writing to", os.path.join(output_dir,main_page.filename)
print >> main_page, msg
print >> main_page, version_msg

index_page = os.path.join(output_dir, 'index.html')
if os.path.exists(index_page):
    print "Updating", index_page
    f = open(index_page, 'r')
    lines = f.readlines()
    f.close()
    f = open(index_page, 'w')
    marker = lines.index("<!---MARKER>\n")
    for line in lines[:marker]:
        f.write(line)
else:
    print "Creating", index_page
    f = open(index_page, 'w')
    f.write(
"""<html><head><title>Complete Consistency Check</title></head><body>
<H3>CCC: Complete Consistency Check</H3>
<pre>\n""")
f.write("<a href=%s>Results for %s</a>\n" % (main_page.filename, timestamp))
f.write("""<!---MARKER>
</pre>
</body></html>\n""")
f.close()


datasets_by_site={} #Complete and incomplete replicas, value is dictionary

if check_dq2:
    try:
        from dq2.clientapi.DQ2 import DQ2
        from dq2.common.DQConstants import DatasetState
        dq2 = DQ2()
    except:
        msg = """Cannot import dq2.clientapi, not checking dq2
Finished at %s""" % time.ctime()
        print >> main_page, msg
        print msg
        sys.exit(0)
    print "Starting DQ2 check at %s" % time.ctime()
    for site in sites:
        exception_occurred = False
        all = None
        completes = None
        datasets_by_site[site] = {} #Value is dict dsn->complete (True/False)
        for retry in xrange(5):
            try:
                print "Listing dq2 datasets for", site
                all = dq2.listDatasetsByNameInSite(site) #,complete=0)
                completes = dq2.listDatasetsByNameInSite(site,complete=1)
                break
            except:
                exc, msg, tb = sys.exc_info()
                exception_occurred = True
                if retry<4:
                    time.sleep(60)
        if (completes is None or all is None) and exception_occurred:
            print msg
            continue # next site
        d = datasets_by_site[site]
        for r in all:
            d[r] = False
        for r in completes:
            d[r] = True
        del all
        del completes
        
cmds = []

print "Fetching data...",
sys.stdout.flush()
if not storage_dump_file:
	cmds += [('storage_dump', os.popen(storage_dump))]
cmd_fds = dict([(fd, name) for (name, fd) in cmds])
cmd_out = dict([(name, ([],'')) for (name, p) in cmds])
## first element is list of lines, second element is partial line buffer
print "Data gathering started at %s" % time.ctime()
while cmd_fds:
	for fd in select(cmd_fds.keys(), [], [], 60)[0]:
	    key = cmd_fds[fd]
	    data = fd.read(8192)
	    if not data:
		status = fd.close()
		if status:
		    print "command failed for", key, "status", status, cmd_fds[fd]
		    os._exit(-1)
		print "%s Command finished: %s" % (time.ctime(), cmd_fds[fd])
		del cmd_fds[fd]
	    else:
		lines, buf = cmd_out[key]
		if buf:
		    buf += data
		else:
		    buf = data
		l = buf.split('\n')
		if buf.endswith('\n'):
		    buf = ''
		else:
		    buf = l[-1]
		lines += l[:-1] #last line is either empty or incomplete
		cmd_out[key] = (lines, buf)

del cmds, cmd_fds ## close all open file descriptors


# Build list of (reduced) pathname 
lines = cmd_out['storage_dump'][0]
del cmd_out['storage_dump']
prefix = storage_root
prefix_len = len(prefix)
path_list=set()
for path in lines:
	if not path.startswith(prefix):
	    continue
	path = path[prefix_len:]
	path_list.add(path)
print "%s path list done" % time.ctime()

def scopeof(dsn):
  if dsn.startswith('user.') or dsn.startswith('group.'):
    scope=dsn.split('.', 2)[0:2]
    scope='/'.join(scope)
  else:
    scope=dsn.split('.', 1)[0]
  return scope

def read_cache(dataset):
    data = None
    parts = dataset.split('.')
    cache_dir = dq2_cache_dir + '/'.join(parts[:-1])
    cache_file = cache_dir + '/' + parts[-1] + '.m'
    if os.path.exists(cache_file):
        try:
            cf = open(cache_file)
            data = marshal.load(cf)
            cf.close()
        except: #possibly corrupt file? 
            try:
                os.unlink(cache_file)
            except:
                pass
    return data

def write_cache(dataset, data):
    parts = dataset.split('.')
    cache_dir = dq2_cache_dir + '/'.join(parts[:-1])
    cache_file = cache_dir + '/' + parts[-1] + '.m'
    try: 
        os.makedirs(cache_dir)
    except:
        pass
    try:
        cf = open(cache_file, 'w')
        marshal.dump(data, cf)
        cf.close()
    except: #Don't leave bad data around
        try: 
            os.unlink(cache_file)
        except:
            pass

def is_obsolete(dataset, site):
    # Only user datasets which are > 30 days old
    if not dq2:
        print "WARNING, dq2 API not initialized"
        return False
    if not "USERDISK" in site:
        return False
    try:
        result = dq2.getMetaDataAttribute(dataset, ['creationdate'])
    except:
        exc, msg, tb = sys.exc_info()
        print "WARNING, dq2GetMetaDataAttribute(%s) fails" % dataset
        print msg
        return False
    if result:
        result = result.get('creationdate')
        try:
            t = time.strptime(result, '%Y-%m-%d %H:%M:%S')
            if time.time() - t > 30*24*3600: # 30 days
                return True
        except:
            print "WARNING cannot parse timestamp '%s'" % result
        
    return False

# Check against DQ2, if possible
if check_dq2:
    status_codes = (UNKNOWN, EMPTY, MISSING, DAMAGED, INCOMPLETE, OK) = (
        "UNKNOWN", "EMPTY", "MISSING",  "DAMAGED", "INCOMPLETE", "OK")
    msg = "Checking DQ2 against LFC/Rucio"
    print msg
    print >> main_page, msg
    print "Will check sites:", " ".join(sites)
    print "Checking DQ2 against disk."
    dq2_orphans = Page("dq2-orphans")
    n_orphans = 0
    orphan_bytes = 0
    orphanpaths = set( path for path in path_list if '/rucio/' in path and '/test/' not in path and '/loadtest/' not in path and '/permanentTests/' not in path )

    for site in sites:
        cache_stats={
            'mem_hit': 0,
            'disk_hit': 0,
            'mem_store': 0,
            'disk_store': 0,
            'mem_miss': 0,
            'disk_miss': 0
        }

        datasets_by_status = {} # status_code -> [datasets]
        for s in status_codes:
            datasets_by_status[s] = []
        msg ="%s..."%site
        print msg,
        print >> main_page, msg,
        replica_complete = datasets_by_site[site]  ### XXX RENAME THIS VRBL!
        datasets = replica_complete.keys()
        datasets.sort()
        n_complete = 0
        for dataset in datasets:
            if replica_complete[dataset]: 
                n_complete += 1
        msg = "%s, %s complete" % (plural(len(datasets), "replica"),
                                   n_complete)
        print msg
        sys.stdout.flush()
        print >> main_page, msg
        
        for dataset in datasets:
            frozen = False
            dq2_reply = read_cache(dataset)
            data_cached = dq2_reply
            if data_cached:
                cache_stats['disk_hit']+=1
            else: 
                cache_stats['disk_miss']+=1
                exception_occurred = False
                for retry in xrange(5):
                    try:
                        dq2_reply = dq2.listFilesInDataset(dataset)
                        frozen = (dq2.getState(dataset) == DatasetState.FROZEN)
                        break
                    except:
                        exc, msg, tb = sys.exc_info()
                        print "ERROR", msg
                        exception_occurred = True
                        dq2_reply = None

                        if "unknown dataset" in str(msg).lower():  #  should use exception class instead
                            break
                        if retry < 4:
                            print "RETRY", retry
                            time.sleep(60)
                if dq2_reply is None:
                    if not exception_occurred:
                        print "ERROR, listFilesInDataset(%s) returns None" % dataset
                    datasets_by_status[UNKNOWN].append(dataset)
                    continue
            if dq2_reply:
                if frozen and not data_cached:
                    write_cache(dataset, dq2_reply)
                file_dict, dq2_timestamp = dq2_reply
		dspaths=[]
		for value in file_dict.values():
			  m=hashlib.md5()
			  m.update(value['scope']+':'+value['lfn'])
			  path=site_dirs[site] + '/rucio/' + value['scope'].replace('.', '/')  + '/' + m.hexdigest()[0:2] + '/' + m.hexdigest()[2:4] + '/' + value['lfn']
			  dspaths.append(path)
		guids=dspaths
            else:
                ## XXXX disable this for now, it's slow and it requires a proxy which we may not have
                ##if is_obsolete(dataset, site):
                ##    delete_dataset(dataset, site)
                ##    continue
                ##print "WARNING, listFilesInDataset(%s) returns %s" % (
                ##    dataset,str(dq2_reply))
                guids = ()
                dspaths = []

            ok = True
            n = 0
	    for path in dspaths:
		if path in orphanpaths:
		    n += 1
		    orphanpaths.discard(path)
		else:
		    ok = False
            if replica_complete[dataset]:
                if ok:
                    if n==0:
                        status = EMPTY
                    else:
                        status = OK
                else:
                    if n==0:
                        status = MISSING
                    else:
                        status = DAMAGED
            else:
                if n==0:
                    status = EMPTY
                else:
                    status = INCOMPLETE
            datasets_by_status[status].append("%s [%d/%d]" %
                                              (dataset, n, len(guids)))

        print "%s dq2 dataset load data done for site %s" % (time.ctime(), site)
        print cache_stats
        sys.stdout.flush()

        for status in status_codes:
            n_status = len(datasets_by_status[status])
            if n_status:
                msg = "%s %s" % (plural(n_status, "replica"), status)
                print "\t"+msg
                if status in ('DAMAGED', 'MISSING'):
                    msg = "<b>%s</b>" % msg
                p = Page("datasets-%s-%s" % (site, status))
                print >> main_page, "\t<a href=%s>%s</a>" % (p.filename, msg)
                for d in datasets_by_status[status]:
                    print >> p, d
                p.close()
                print "%s dq2 dataset write to file done for site %s status %s" % (time.ctime(), site, status)
                sys.stdout.flush()

        print "%s dq2 dataset check done for site %s" % (time.ctime(), site)
        sys.stdout.flush()

    n_orphans=len(orphanpaths)
    orphan_bytes = 0
    for path in orphanpaths:
	try:
		 size = os.stat(storage_root + path)[stat.ST_SIZE] #PNFS may lie
        except:
		 print "Cannot stat", storage_root + path
	orphan_bytes += size
	print >> dq2_orphans, path, size
    del orphanpaths
    if n_orphans:
	msg = "%s (%s) (dark data)" % (plural(n_orphans, "dq2 orphan"), unitize(orphan_bytes))
	print msg
	print >> main_page, "<a href=%s>%s</a>" % (dq2_orphans.filename, msg)
    else:
	print "OK"
	print >> main_page, "OK"
    dq2_orphans.close()
    print "%s dq2 versus disk check done" % time.ctime()


done_msg = "Finished at %s" % time.ctime()
print >> main_page, done_msg
main_page.close()



print done_msg

            
