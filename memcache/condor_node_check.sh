#!/bin/sh

#  Worker node health check script, to run from condor startd
#
#  configuration:  add to /etc/condor/condor_config.local:
#  START = (NodeOnline =?= True)
#  STARTD_CRON_NAME = CRON
#  CRON_JOBLIST = nodecheck
#  CRON_nodecheck_EXECUTABLE = /usr/local/sbin/condor_node_check.sh
#  CRON_nodecheck_PERIOD = 15m
#  CRON_nodecheck_MODE = periodic
#  CRON_nodecheck_RECONFIG = false
#  CRON_nodecheck_KILL = true
#
#  Get memclient.py from:
#  http://repo.mwt2.org/viewvc/util/
#  
#  See:
#  https://nmi.cs.wisc.edu/node/1470
#
#  $Id: condor_node_check.sh,v 1.6 2011/08/31 19:25:16 sarah Exp $ 
#

echo "node_check run $( date ) by $USER" >> /var/log/condor_node_check.log

MEMCLIENT=/usr/local/bin/memclient.py

HOST=$( hostname -s )
SCRATCHFILE=/scratch/node_check.testfile
ERRFILE=/tmp/node_check.err

/bin/rm -f $ERRFILE >& /dev/null


setOffline(){
   msg=$1
   timestamp=$(date +%s)
   $MEMCLIENT put  $HOST.status    offline
   $MEMCLIENT put  $HOST.message   "$msg"
   $MEMCLIENT put  $HOST.timestamp $timestamp
   echo "NodeOnline = False"
   echo "NodeOnlineReason = '$msg'"
}

setMidline(){
   msg=$1
   timestamp=$(date +%s)
   $MEMCLIENT put  $HOST.status    midline
   $MEMCLIENT put  $HOST.message   "$msg"
   $MEMCLIENT put  $HOST.timestamp $timestamp
   echo "NodeOnline = True"
   echo "NodeMidline = True"
   echo "NodeOnlineReason = '$msg'"
}

setOnline(){
   timestamp=$(date +%s)
   $MEMCLIENT put  $HOST.status    online
   $MEMCLIENT put  $HOST.message   ''
   $MEMCLIENT put  $HOST.timestamp $timestamp
   echo "NodeOnline = True"
   echo "NodeMidline = False"
}


# Test if the node has been set offline manually

MANUALSTATUS=$( $MEMCLIENT get $HOST.manualstatus )

if [ $MANUALSTATUS == 'offline' ]; then
	MANUALREASON=$( $MEMCLIENT get $HOST.manualreason )
	setOffline "Manual offline: $MANUALREASON"
	exit 1
fi



#########
# TESTS #
#########


# Able to write to /tmp ?
msg=`touch $ERRFILE 2>&1`
if [ $? != 0 ] ; then
    setOffline "$msg"
    exit 1
fi

# Able to write to /scratch ?
touch $SCRATCHFILE >& $ERRFILE &&  /bin/rm $SCRATCHFILE >& $ERRFILE 

if [ $? != 0 ] ; then
    setOffline "$(cat $ERRFILE)"
    exit 1
fi

# Correct permissions on /scratch ?
SCRATCHPERMS=$( stat -c '%a' /scratch/ ) ;
if [ $SCRATCHPERMS != 1777 ] ; then
    setOffline "permissions on scratch should be 1777, are $SCRATCHPERMS"
    exit 1
fi

/bin/rm -f $ERRFILE

# 5000 free inodes in /scratch ?
avail=$(df -iP /scratch | tail -1 | awk '{print $4;}')
if (( avail < 5000 )); then
    setOffline "ERROR only $avail inodes free in /scratch"
    exit 2
fi

# 10GB free in /scratch ?
avail=$(df -P -B1G /scratch | tail -1 | awk '{print $4;}')
#  is there a better way to parse the output of df,
#  without using "tail" and "awk"?
if (( avail < 10 )); then
    setOffline "ERROR only $avail GB free in /scratch"
    exit 2
fi

# 5GB free in / ?
avail=$(df -P -B1G / | tail -1 | awk '{print $4;}')
#  is there a better way to parse the output of df,
#  without using "tail" and "awk"?
if (( avail < 5 )); then
    setOffline "ERROR only $avail GB free in /"
    exit 8
fi


# NFS mount /share/certificates sane and CERN cert available:
if [[ ! -e /etc/grid-security/certificates/1d879c6c.0 ]] ; then
	setOffline "ERROR certs not mounted or missing"
	exit 7
fi


#  Home dirs NFS mount sane?

if [[ ! -e ~osg ]] ; then
    setOffline  "ERROR cannot access VO user ~osg"
    exit 4
fi

if [[ ! -e ~uc3 ]] ; then
    setOffline  "ERROR cannot access VO user ~uc3"
    exit 4
fi



# CVMFS mounts common to all jobs


if [[ ! -e /share/osg/mwt2/app ]] ; then
    setOffline "ERROR cannot access /share/osg/mwt2/app"
    exit 5
fi

if [[ ! -e /share/certificates ]] ; then
    setOffline "ERROR cannot access /share/certificates"
    exit 5
fi

if [[ ! -e /share/wn-client ]] ; then
    setOffline "ERROR cannot access /share/wn-client"
    exit 5
fi


# If the node is online for Atlas jobs, check those items that are Atlas only
# If any tests fail, put the node into midline

if [[ $MANUALSTATUS == "online" ]]; then

  # USATLAS home dirs NFS mount sane?

  if [[ ! -e ~usatlas1 ]] ; then
      setMidline  "ERROR cannot access ~usatlas1"
      exit 4
  fi

  # CVMFS mount sane?

  if [[ ! -e /cvmfs/atlas.cern.ch/repo/sw/software ]] ; then
      setMidline "ERROR cannot access /cvmfs/atlas.cern.ch/repo/sw/software"
      exit 5
  fi

  if [[ ! -e /cvmfs/atlas-condb.cern.ch/repo/conditions ]] ; then
      setMidline "ERROR cannot access /cvmfs/atlas.cern.ch/repo/conditions"
      exit 5
  fi


  # PNFS mount OK?

  if ! grep -q /pnfs /proc/mounts ; then
      setMidline "ERROR /pnfs not mounted"
      exit 6
  fi

  p=$( grep /pnfs /proc/mounts )
  if ! ( echo $p | grep -q noac ); then
      setMidline "ERROR /pnfs mounted without noac"
      exit 6
  fi
fi

# We have passed all tests

# If the node is not marked online or midline in memcached, consider us offline
#
# This could because by several reasons
#
# 1) New node
# 2) Networking problems - cannot reach memcached
# 3) Memcached down or rebooted

case $MANUALSTATUS in

(online)

  setOnline
  exit 0
  ;;

(midline)

  MANUALREASON=$( $MEMCLIENT get $HOST.manualreason )
# setMidline "Manual midline: $MANUALREASON"
  setMidline ""
  exit 0
  ;;

(*)

  setOffline "Automatic offline: node not marked online or midline in memcache!"
  exit 1
  ;;

esac

setOffline "Automatic offline: Internal condor_node_offline error"
exit 1
