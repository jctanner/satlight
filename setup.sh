#!/bin/bash

# this line gets rid of "-2:" inside rpm filenames
# must be run from capsules/packages
# for fn in `find . -name "*\-[0-9]*:*"`; do mv -f $fn `echo "$fn" | sed "s/-[0-9]*:/-/"`; done

rpm --import gpg/rhel6.3/RPM-GPG-KEY*

mkdir -p /root/fakesat/data
mkdir -p /root/fakesat/capsules/systems/RHN

mkdir -p /root/fakesat/certs
cd /root/fakesat/certs
openssl req -new -x509 -keyout server.key -out server.crt -days 999 -nodes
openssl x509 -req -days 3650 -in server.crt -signkey server.key -out cert.pem
