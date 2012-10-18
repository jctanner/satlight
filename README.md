satlight 
=============

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


    Each time you add new rpms to the directory, capsule-indexer must be
    forced to refresh the index:
    
        psql -U postgres -p 5439 mint -c "delete from ci_rhn_channels"    
        
    If new packages are added to the directory, restart the satellite to
    clear the package cache. The first request for listAllPackages will
    be slow, but all future requests will be instantaneous.


    The capsules directory has a structure such as ...
        
        [root@devimage fakesat]# find capsules -type d
        capsules
        capsules/systems
        capsules/systems/RHN
        capsules/packages
        capsules/packages/rhel-x86_64-server-6
        capsules/packages/rhel-i386-server-optional-6
        capsules/packages/rhel-i386-server-6
        capsules/packages/rhel-x86_64-server-optional-6    

    Each subdirectory under capsules/packages is the name of a channel in satellite.
    Only copy rpms to those directories, otherwise the code will try to pull rpm
    headers from non-rpm files.    
