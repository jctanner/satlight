#!/usr/bin/python

'''
"satlight"

An implementation of rhn-satellite to provide all
xmlrpc and http repsonses required by an rpath rbuilder.

xmlrpc server code derived from:
http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/81549
'''

import socket, os, sys
# Configure below
#LISTEN_HOST='127.0.0.1' # You should not use '' here, unless you have a real FQDN.
LISTEN_HOST='' # You should not use '' here, unless you have a real FQDN.
LISTEN_PORT=443

#KEYFILE='certs/saturnus.msnet.key.pem'    # Replace with your PEM formatted key file
#CERTFILE='certs/saturnus.msnet.cert.pem'  # Replace with your PEM formatted certificate file
# these are defaults realtive to module's directory
# Configure above

import SocketServer
import BaseHTTPServer
import SimpleHTTPServer
import SimpleXMLRPCServer

from OpenSSL import SSL

import pprint
import ast
import errno
import epdb
import fcntl
import posixpath
try:
    import cPickle as pickle
except ImportError:
    import pickle
import random
import rpm
import hashlib
import urllib
import optparse
from collections import namedtuple

class SecureXMLRPCServer(BaseHTTPServer.HTTPServer, SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    #request_queue_size = 256
    def __init__(self, server_address, HandlerClass, logRequests=True):
        """Secure XML-RPC server.

        It it very similar to SimpleXMLRPCServer but it uses HTTPS for transporting XML data.
        """
        self.logRequests = logRequests

        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self)
        SocketServer.BaseServer.__init__(self, server_address, HandlerClass)
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_privatekey_file (self.KEYFILE)
        ctx.use_certificate_file(self.CERTFILE)
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family,
                                                        self.socket_type))
        self.server_bind()
        self.server_activate()

class SecureXMLRpcRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler, SimpleHTTPServer.SimpleHTTPRequestHandler):
    """Secure XML-RPC request handler class.

    It it very similar to SimpleXMLRPCRequestHandler but it uses HTTPS for transporting XML data.
    """
    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.unquote(path))

        path = path.replace("/XMLRPC/$RHN", "")
        path = path.replace("/getPackage", "")

        words = path.split('/')
        words = filter(None, words)
        path = self.basePath
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        print "translated path:", path
        sys.stdout.flush()
        return path
        
    def do_POST(self):
        """Handles the HTTPS POST request.

        It was copied out from SimpleXMLRPCServer.py and modified to shutdown the socket cleanly.
        """

        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            print "###### request XML ######"
            print str(data)
            response = self.server._marshaled_dispatch(
                    data, getattr(self, '_dispatch', None)
                )
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            print "###### response XML ######"
            print response

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown() # Modified here!
    
def test(basePath = None, pkiPath = None, dataDir = None, verbose = False, HandlerClass = SecureXMLRpcRequestHandler,ServerClass = SecureXMLRPCServer):
    """Test xml rpc over https server"""

    if basePath is None:    
        basePath = os.path.join(os.getcwd(), 'capsules', 'packages')
    HandlerClass.basePath = basePath

    KEYFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs", "server.key")
    CERTFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs", "server.crt")
    if pkiPath is not None:
        KEYFILE = os.path.join(pkiPath, os.path.basename(KEYFILE))
        CERTFILE = os.path.join(pkiPath, os.path.basename(CERTFILE))
        SecureXMLRPCServer.KEYFILE = KEYFILE
        SecureXMLRPCServer.CERTFILE = CERTFILE

    if dataDir is None:
        dataDir = "data"
    systemsFile = os.path.join(dataDir, 'systems')

    class ServiceRoot:
        pass

    class Authorization:

        def login(self, username, password):
            return "fakesessionid"

    class Channel:
        def software(self):
            return "blah"

    class ChannelSoftware:
        def __init__(self):
            self.packages = {}

        def availableEntitlements(self, sessionid, channel):
            return "999"

        def listAllPackages(self,sessionid, channelname):
            if self.packages.get(channelname) is None:
                self.packages[channelname] = self._listAllPackages(sessionid, channelname)
            return self.packages[channelname]

        def _listAllPackages(self, sessionid, channelname):
            '''
            Method: listAllPackages

            Description:
            Lists all packages in the channel, regardless of the package version
            Parameters:
            string sessionKey
            string channelLabel - channel to query
            Returns:

            array:
                struct - package
                    string "name"
                    string "version"
                    string "release"
                    string "epoch"
                    string "checksum"
                    string "checksum_type"
                    int "id"
                    string "arch_label"
                    string "last_modified_date"
                    string "last_modified" - (Deprecated)
            '''
            # capsules/packages/rhel-i386-server-6
            # list rpms in channel directory
           
            # http://docs.fedoraproject.org/en-US/Fedora_Draft_Documentation/0.1/html/RPM_Guide/ch16s04.html
            path = os.path.join(basePath, str(channelname))
            dirList=os.listdir(path)
            if verbose: print dirList
            packagelist = []
            #ts = rpm.ts()   #  transaction set
            ts = rpm.TransactionSet()   #  transaction set
            #import epdb; epdb.st()
            for package in dirList:
                # open file and get header
                fdno = os.open(path + '/' + package, os.O_RDONLY)
                hdr = ts.hdrFromFdno(fdno)

                # get the inode number to use a packageid
                osdata = os.fstat(fdno) 
                #import epdb; epdb.st()
                #if verbose: print osdata
                packageid = int(osdata.st_ino)
                if verbose:  print packageid
                os.close(fdno)

                # get the sha1sum
                psha1sum = hashlib.sha1(open(path + '/' + package,'rb').read()).hexdigest()

                # set epoch to an int
                epoch = hdr['epoch']
                if epoch == None:
                    epoch = -1

                teststruct = {  'name':hdr['name'], 
                                'id':packageid,
                                'version':str(hdr['version']),
                                'release':str(hdr['release']),
                                'epoch':str(epoch), 
                                'checksum':str(psha1sum),
                                'checksum_type':str('sha1'), 
                                'arch_label':str(hdr['arch']), 
                                'last_modified_date':str(hdr['buildtime'])  }
                if verbose: print teststruct
                packagelist.append(teststruct)

            #return ['one', 'two', 'three', 'four']
            #return str(pstruct)
            #import epdb; epdb.st()
            return packagelist

    class Registration:
        def __attributes2label(self, arch, osrelease):
            channels = [{'rhel-i386-server-6':{'architecture':'i386-redhat-linux', 'os_release':'6Server'}}]
            channels.append({'rhel-x86_64-server-6':{'architecture': 'x86_64-redhat-linux', 'os_release':'6Server'}})

            channelname = ""
            for channel in channels:
                if channel[channel.keys()[0]]['architecture'] == arch:
                    if channel[channel.keys()[0]]['os_release'] == osrelease:
                        channelname = channel.keys()[0]

            return channelname

        def new_system(self, indata):
            # this should return a true systemid (1023165033)            

            #import epdb; epdb.st() 
            if verbose: print indata
            '''
            (Epdb) indata
            {'username': 'fakename', 'password': 'fakepass', 
            'profile_name': 'rbuilder rba.dark.net; channel: rhel-i386-server-6', 
            'architecture': 'i386-redhat-linux', 'os_release': '6Server'}
            '''

            # figure out what the base channel is
            basechannel = self.__attributes2label(indata['architecture'], indata['os_release'])
            #basechannel = self._Registration__attributes2label(indata['architecture'], indata['os_release'])

            # load systems data
            if os.path.exists(systemsFile):
                f = open(systemsFile, 'r')
                data = f.read()
                f.close()
            else:
                data = pickle.dumps({'000000000': []})
            unpickled_data = pickle.loads(data)

            # find last sid, increment
            idlist = []
            for key in unpickled_data.keys():
                idlist.append(key)
            sidlist = sorted(idlist)
            lastid = sidlist[-1]
            newid = str(int(lastid) + 1).zfill(9)

            # save the new id
            #unpickled_data[newid] = []
            unpickled_data[newid] = [basechannel]
            data = pickle.dumps(unpickled_data)
            f = open(systemsFile, 'w')
            f.truncate()
            f.write(data)
            f.close()

            return newid

        def welcome_message(self):
            return "welcome to fakesat"
                 
    class Up2date:
        def login(self, systemid):

            # This should return the authDict contained in the .auth files
            # found in /srv/rbuilder/capsules/systems/RHN/ 

            #data = f.read()
            #unpickled_data = pickle.loads(data)
            #return unpickled_data['authDict']
            '''
            'authDict': {'X-RHN-Server-Id': 1023165033, 
                        'X-RHN-Auth-Server-Time': '1350358803.4', 
                        'X-RHN-Auth': '4ia2WhVlWWUiMgKcsb3lNA==', 
                        'X-RHN-Auth-Channels': 
                            [['rhel-x86_64-server-6', '20121012161227', '1', '1'], 
                            ['rhel-x86_64-server-optional-6', '20121012161227', '0', '1']], 
                        'X-RHN-Auth-User-Id': '', 
                        'X-RHN-Auth-Expire-Offset': '3600.0'}}
            '''            

            # load systems data
            f = open(systemsFile, 'r')
            data = f.read()
            f.close()
            unpickled_data = pickle.loads(data)

            # assemble special list of channels
            subscribedchannels = unpickled_data[systemid]
            channellist = []
            for channel in subscribedchannels:
                channellist.append([channel, '20121012161227', '1', '1'])

            returndict = {  'X-RHN-Server-Id': systemid,
                            'X-RHN-Auth-Server-Time': '1350358803.4',
                            'X-RHN-Auth': '4ia2WhVlWWUiMgKcsb3lNA==',
                            'X-RHN-Auth-Channels': channellist,
                            'X-RHN-Auth-User-Id': '',
                            'X-RHN-Auth-Expire-Offset': '3600.0' }

            if verbose: print returndict
            return returndict

        def subscribeChannels(self, systemid, channellist, username, password):

            if verbose: print channellist

            #f = open('capsules/systems/RHN/systemid-rhel-x86_64-server-6.auth', 'r')
            #data = f.read()
            #unpickled_data = pickle.loads(data)
            #return unpickled_data['authDict']
            #return 'ok'            

            # load known system info
            f = open(systemsFile, 'r')
            data = f.read()
            f.close()
            unpickled_data = pickle.loads(data)

            # append new channels to system
            current_channels = unpickled_data[systemid]
            for channel in channellist:
                current_channels.append(channel)
            unpickled_data[systemid] = current_channels

            # write data
            data = pickle.dumps(unpickled_data)
            f = open(systemsFile, 'w')
            f.truncate()
            f.write(data)
            f.close()

            # assemble special list of channels
            subscribedchannels = unpickled_data[systemid]
            channellist = []
            for channel in subscribedchannels:
                channellist.append([channel, '20121012161227', '1', '1'])

            returndict = {  'X-RHN-Server-Id': systemid,
                            'X-RHN-Auth-Server-Time': '1350358803.4',
                            'X-RHN-Auth': '4ia2WhVlWWUiMgKcsb3lNA==',
                            'X-RHN-Auth-Channels': channellist,
                            'X-RHN-Auth-User-Id': '',
                            'X-RHN-Auth-Expire-Offset': '3600.0' }
            if verbose: print returndict
            return returndict

    class Get:
        def get(self):
            return "blah"

    class Queue:
        def get(self, systemid, anumber, astruct):
            return str("1")
            

    # required methods for capsule-indexer
    '''
    auth.login
    software.channel.availableEntitlements
    registration.new_system
    up2date.login
    up2date.subscribeChannels
    channel.software.listAllPackages
    '''
    #"GET /XMLRPC/$RHN/rhel-x86_64-server-6/getPackage/gdbm-1.8.0-36.el6.x86_64.rpm HTTP/1.1" 501

    # required for rhel machines
    '''
    registration.welcome_message
    registration.add_hw_profile ... skip w/ --nohardware
    registration.add_packages   ... skip w/ --nopackages
    queue.get   ???
    '''


    root = ServiceRoot()
    root.auth = Authorization()
    root.channel = Channel()
    root.channel.software = ChannelSoftware()
    root.registration = Registration()
    root.up2date = Up2date()
    root.queue = Queue()
    root.get = Get()
    
    server_address = (LISTEN_HOST, LISTEN_PORT) # (address, port)
    server = ServerClass(server_address, HandlerClass)    
    server.register_instance(root, allow_dotted_names=True)    

    sa = server.socket.getsockname()
    print "Serving HTTPS on", sa[0], "port", sa[1]
    sys.stdout.flush()
    server.serve_forever()

def daemonize(output, pidfile):
    lockfile = pidfile + ".lck"
    # we won't release the lock until we've written the pidfile. we won't know that until the end of this function
    lockfd = os.open(lockfile, os.O_WRONLY | os.O_CREAT)
    # instead of failing if the file exists (in the line above), attempt to obtain a kernel lock on the file
    # this overcomes situations where a daemon dies before cleaning up the lock file
    fcntl.flock(lockfd, fcntl.LOCK_EX)

    if os.path.exists(pidfile):
        pid = open(pidfile).read()
        if pid.isdigit():
            pid = int(pid)
        if pid == '':
            pid = 0
            os.unlink(pidfile)
        else:
            try:
                os.kill(pid, 0)
            except OSError, e:
                if e.errno == errno.ESRCH:
                    os.unlink(pidfile)
            else:
                print >> sys.stderr, "Daemon already running as PID: %d" % pid
                sys.exit(1)

    pid = os.fork()
    if pid:
        os._exit(0)
    os.setsid()

    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, sys.stdin.fileno())
    os.close(devnull)

    if not output:
        output = os.devnull
    outfd = os.open(output, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    os.dup2(outfd, sys.stdout.fileno())
    os.dup2(outfd, sys.stderr.fileno())
    os.close(outfd)

    os.chdir('/')

    pid = os.fork()
    if pid:
        os._exit(0)
    pidfd = os.open(pidfile, os.O_WRONLY | os.O_CREAT)
    os.write(pidfd, str(os.getpid()))
    os.unlink(lockfile)
    os.close(lockfd)

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--capsule-path", dest = "capsulePath", help = "Path to capsule packages")
    parser.add_option("--pki-path", dest = "pkiPath", help = "directory where PKI files are stored (server.key, server.crt)")
    parser.add_option("-N", "--no-daemon", dest = "daemonize", action = "store_false", default = True, help = "Do not daemonize")
    parser.add_option("-o", "--output", dest = "output", default = os.devnull, help = "Output logs to FILE", metavar = "FILE")
    parser.add_option("-p", "--pidfile", dest = "pidfile", help = "Store pid in FILE", metavar = "FILE")
    parser.add_option("-d", "--datadir", dest = "dataDir", help = "Where to store system data")
    parser.add_option("-v", "--verbose", dest = "verbose", action = "store_true", default = False, help = "set debug on")
    (options, args) = parser.parse_args()
    if options.daemonize:
        if not (options.pidfile and options.output):
            print >> sys.stderr, "Please specify both a pid file and an output file"
            sys.exit(1)
        daemonize(options.output, options.pidfile)
    print "starting HTTP server"
    sys.stdout.flush()
    test(options.capsulePath, options.pkiPath, options.dataDir, options.verbose)



