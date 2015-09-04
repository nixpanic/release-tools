#!/bin/sh


function generate_release_notes ()
{
    orig_version=$1
    latest_version=$2
    repo=$3;

    cd $3;

for i in $(git log $1..$2 | grep BUG | grep -v ">" | cut -f 2 -d ":") ;do
    echo -n "$i - " >> /tmp/release_notes && echo `bugzilla query -b $i | sed -e 's/.*\ -\ //'` >> /tmp/release_notes;
done

# the below style of using awk can also be used as it acts as the logical cut with delimiter being ' - '
#for i in $(git log $1..$2 | grep BUG | grep -v ">" | cut -f 2 -d ":") ;do
#    echo -n "$i - " >> /tmp/release_notes && echo `bugzilla query -b $i | awk -F' - ' '{print $3'}` >> /tmp/release_notes;
#done
}

function main ()
{
    generate_release_notes $1 $2 $3;
}

main "$@"
