Complete Consistency Check
---

Complete Consistency Check (CCC) is a tool developed within US ATLAS to
perform consistency checking between ATLAS dataset and file catalogs and local storage. A
detailed report is produced listing all files and datasets in inconsistent states. The report
gives sufficient information to clean up inconsistencies, but does not itself make any changes
to storage systems, file or dataset catalogs.  Currently supported systems are DQ2, 
Rucio, generic disk, and dCache (PNFS/Chimera).  Support for LFC has been deprecated.

There is currently a known limitation in Rucio support, in the case where a file is in the rucio file catalog but not in dataset catalog.  We do not currently have a method to detect this type of inconsistency at the site level.  There is a procedure initiated by central operations to detect files in this state.  Please contact DDM support at `atlas-dq2-ops@cern.ch ` if you need this check run for your site.

`ccc_pnfs_rucio.py` will download the list of datasets listed in DQ2 for a site, compute
Rucio paths for each file in the datasets, and check that against what is in PNFS. It will 
additionally check PNFS against disk. A report is generated in the output directory with a 
summary of discrepancies found.

`ccc_generic.py` checks a list of datasets in DQ2 against files on a generic mounted disk. It
is as of this writing not updated to compute Rucio paths.  Please contact support@mwt2.org
if you are interested in a version of ccc_generic.py that supports Rucio.

`ccc_pnfs.py` is a deprecated script that compares DQ2, LFC, and PNFS.  It is replaced by
`ccc_pnfs_rucio.py`.


How to run
----------

Download ccc_pnfs_rucio.py and ccc_config.py.  Change the values in ccc_config.py to reflect your installation. If you have used a previous version of a CCC script, note that the format for DQ2 endpoints has changed.

Before attempting to run the script, CCC requires the dq2 clients to be set up. See `ccc_wrapper.sh` for an example on how to set this up on a machine with CVMFS.  By default CCC also requires passwordless ssh access to the PNFS server and to each of the dCache pool servers.  If using the `-np` (no pool) option, ssh access to the pool servers is not neccessary.  If using the `-p pnfs_file` option to provind a pnfs dump file, ssh access to the PNFS server is not neccessary.

```
Usage: ./ccc_pnfs_rucio.py [-o output_dir] [-p pnfs_file] [-l lfc_file] [-np] [-nd] [-nl]
   normal usage requires no options
   -m min_age: don't flag files newer than this (default=2 hours)
         use 's' for seconds(default), 'm'=minutes, 'h'=hours, 'd'=days
         Used to avoid flagging files that are recently created and not yet registered.
   -o specifies directory for (html) output, default is working directory
   -p pnfs_file reads pnfsDump output from file, instead of 
         using ssh to run pnfsDump on the pnfs server
   -np (no pool) skips checking of /dcache/pool on pool nodes
   -nd (no dq2) skips checking of registered dq2 datasets
```

CCC can take up to a day to run, depending on the size of the site.  It is recommended to run the command in an interactive screen session, or non-interactively using the `nohup` command. Note that `nohup` requires both stdout and stderr to be directed to a file. If you do not redirect them on the command line, these outputs will be sent to a file `nohup.out` in the current working directory.

Once CCC is running, it can be killed without harming storage systems. However, some clean-up
may be neccessary.

- `/tmp/ccc.lock` must be manually deleted
- If the next run of CCC fails with an error about a corrupted marshal file, CCC may have been interrupted while writing a DQ2 cache file.  Delete the file from `/var/tmp/DQ2` and restart CCC.
- The HTML report will be incomplete. It is recommended to delete the report so as to avoid confusion when reviewing historic CCC results.


Created files
-------------

The script will create a directory `/var/tmp/dq2/` and use it to cache dq2 responses. As this cache is 
filled out the run time of the script will improve.

A text file `/tmp/ccc.lock` is created to make sure only one copy of ccc runs at a time.

An html report named `ccc-DATE-TIME.html` will be created in the output directory, along with text files
for each of the file states detected. For instance, if there are pnfs orphans, the file pnfs-orphans-DATE-TIME
is created.

Concepts and terminology
------------------------

When the storage catalog systems are compared they are organized in a heirarchy, from highest to lowest
level, that being closest to physical disk.  In order these are DQ2 -> Rucio File Catalog ->
PNFS -> filesystem.  

GHOST: A file that is present in a higher level storage catalog, but not in a lower one or on disk.
Ghost files often cause job failures when a job runs at the site and fails to fetch the missing input
file.

ORPHAN: A file that is missing in the higher level storage catalog, but is present in the lower one or
on disk.  Orphans do not cause job failures.  They are typically 'dark data', and may need to be
removed manually.  

DAMAGED DATASET: A dataset that is listed as haing a complete replica at the site, but lower level
catalogs or disk show missing files.  Damaged datasets may cause job failures, for the same reason
as ghost files.

MISSING DATASET: A dataset that is listed as haing a complete replica at the site, but lower level
catalogs or disk show all files are missing.  Missing datasets may cause job failures, for the same reason
as ghost files.

INCOMPLETE DATASET: A dataset is listed as having a incomplete replica at the site, and the lower
level catalog and file system confirm that.  These are not a problem. 

EMPTY DATASET: A dataset listed as having 0 files in the catalog. These are not a problem.

UNKNOWN DATASET: The catalog lists the dataset as present at the site, but when the catalog was
queried for a list of files it returned an 'unknown dataset' error.  If a dataset appears in this
catagory repeatedly it may be broken in the catalog and need attention by the catalog admins.

OK DATASET:  A dataset that is listed as haing a complete replica at the site, and the lower level
catalogs and file system show all files present. Most datasets should be in this category.
