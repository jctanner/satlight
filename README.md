"satlight" 

    An implementation of rhn-satellite to provide all
    xmlrpc and http repsonses required by an rpath rbuilder.

    xmlrpc server code derived from: 
        http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/81549

    To run:
    
    python /root/fakesat/satellite.py \
        --pki-path /root/fakesat/certs \
        --capsule-path /root/fakesat/capsules/packages \
        --output /var/log/satellite.log \
        --pidfile /var/satellite/satellite.pid \
        --datadir /var/satellite/  