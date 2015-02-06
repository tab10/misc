#!/bin/sh

dirs=`cat $2`
if [ $1 == gauss ];
    then
    for x in ${dirs}; do
        cd ${x}
        python -m misc.update_conts
        g_kuh_sbm -s conf.gro -f traj.xtc -n native_contacts.ndx -noshortcut -abscut -cut 0.1 -qiformat list
        mv qimap.out qimap.dat
        cd ../
    done
else
    for x in ${dirs}; do
        cd ${x}
        python -m misc.update_conts
        g_kuh_sbm -s conf.gro -f traj.xtc -n native_contacts.ndx -noshortcut -noabscut -cut 0.2 -qiformat list
        mv qimap.out qimap.dat
        cd ../
    done

fi
