#!/bin/bash

psql -F ' ' --no-align --tuples-only --username postgres --dbname chimera -c \
	" 
WITH RECURSIVE paths(pnfsid, path, type) AS (
VALUES ('000000000000000000000000000000000000', '', 16384)
UNION
SELECT d.ipnfsid, path||'/'||d.iname,i.itype
FROM t_dirs d,t_inodes i, paths p
WHERE p.type=16384 AND d.iparent=p.pnfsid
AND d.iname != '.' AND d.iname != '..'
AND i.ipnfsid=d.ipnfsid
)
SELECT pnfsid,path FROM paths WHERE type=32768 ;" 
