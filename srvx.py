#!/usr/bin/env python
"""
SrvX Module

Communicates with SrvX via QServer protocol
"""

__author__  = 'Gavin M. Roy <gavinmroy@gmail.com>'
__date__    = '2010-01-10'
__version__ = '0.1'

import logging
import random
import socket
import time

# Core Classes
class SrvX():

    def __init__(self, host='127.0.0.1', port=7702, password=None, auth_user=None, auth_password=None):

        logging.info('Connecting to %s:%i' % (host, int(port)))
        
        # Create our socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Connect to our remote host
        self.socket.connect((host, int(port)))
        
        # By default we're not authenticated
        self.authenticated = False

        # Create our buffer string which will be used to hold info across responses if needed
        self.response = ''
        
        # Send the QServer username and password 
        self._send_command('PASS %s' % password, True)
        
        # Authenticate
        self.authenticate(auth_user, auth_password)
 
    def authenticate(self, username, password):
    
        logging.debug('Processing AuthServ Authentication Request')

        # Send the AuthServ auth request
        response = self._send_command('AuthServ AUTH %s %s' % (username, password))
    
        # Parse the response    
        if response['data'][0] == 'I recognize you.':
            logging.info('Authenticated with AuthServ')
            self.authenticated = True
        else:
            raise AuthServAuthenticationFailure(response['data'][0])
    
    def disconnect(self):
        
        logging.debug('Closing connection to QServer')
        self.socket.close()

    def generate_token(self):
        
        # Return a token generated from a random number        
        return 'GS%05d' % random.randint(0,65535)
        
    def get_response(self):

        data = ''
        command_length = 0
        response_done = False

        # Loop until the response is done
        while not response_done:
            
            # Append data from the socket into the global buffer        
            self.response += self.socket.recv(32768)

            # Split the content into a list
            lines = self.response.split('\n')
            
            # Loop through each line in the list
            for line in lines:
        
                # If it finds the token
                if line.find(self.token) > -1:
                
                    logging.debug('Matched on token %s' % self.token)
                    
                    # Do an initial split to so we know our response code
                    parts = line.split(' ')
                    response_code = parts[1]
                    
                    # We did not auth with QServer Successfully
                    if response_code == 'X':
                        command_length += len(line)
                        self.disconnect()
                        raise QServerAuthenticationFailure()
                    
                    elif response_code == 'S':
                        logging.debug('Got a S packet, processing more')
                        command_length += len(line) + 1
                        continue

                    elif response_code == 'E':
                        
                        # We've reached the end of the response
                        logging.debug('Got a E packet, ending response')
                        command_length += len(line) + 1
                        response_done = True
                        break
                        
                    else:
                        # Append the buffer
                        logging.debug('Unexpected line: "%s"' % line)
                        command_length += len(line) + 1
                        data += '%s\n' % line
                else:
                    command_length += len(line) + 1
                    data += '%s\n' % line      
                
                            
        # Remove our command from the response buffer
        self.response = self.response[command_length:]
        logging.debug('Processed %i bytes leaving %i bytes in the global buffer' % (command_length, len(self.response)))        

        # Build our response packet
        response = {'data': []}
        lines = data.split('\n')
        for line in lines:
            
            if not response.has_key('from'):
                parts = line.split(' ')
                response['from'] = parts[0]
            
            content = line[line.find(':') + 1:]
            response['data'].append(content.strip())

        # Return the response
        return response        

    def _send_command(self, command, no_response = False):
    
        # Get our token
        self.token = self.generate_token()
        
        # Put a token infront of the command
        command = '%s %s\n' % (self.token, command)
        
        # Send the command
        logging.debug('Sending: %s' % command.strip())
        self.socket.send(command)
        
        # return the response
        if not no_response:
            return self.get_response()


class AuthServ(SrvX):
    pass     

class ChanServ(SrvX):

    def info(self, channel):
        response = self._command('info %s' % channel)
    
        info = {'channel': response['data'][0].split(' ')[0]}
    
        for line in response['data'][1:]:
            parts = line.split(':')
            if len(parts) > 1:
                info[parts[0].strip()] = parts[1].strip()
            else:
                if len(line.strip()) > 0:
                    logging.error('Odd info response: %s' % line)            
        return info
    
    def _command(self, command):
        return self._send_command('chanserv %s' % command)
    
    def say(self, channel, message):
        response = self._command('say %s %s' % (channel, message))

class OpServ(SrvX):
    pass
        
# Exceptions
class AuthServAuthenticationFailure(Exception):
    pass
    
class QServerAuthenticationFailure(Exception):
    pass


def json_dumps(data):
    import json
    print json.dumps(data)

# If run via the command line
if __name__ == '__main__':
    import optparse
    
    usage = "usage: %prog [options]"
    version_string = "%%prog %s" % __version__
    description = "Command Line SrvX Tool"
    
    # Create our parser and setup our command line options
    parser = optparse.OptionParser(usage=usage,
                                   version=version_string,
                                   description=description)
 
    parser.add_option("-i", "--ipaddr", action="store", dest="ipaddr", 
                        default='127.0.0.1',
                        help="Host IP Address")     

    parser.add_option("-p", "--port", action="store", dest="port", 
                        default=7702,
                        help="Host TCP Port")     

    parser.add_option("-k", "--password", action="store", dest="password", 
                        help="QServer password")     

    parser.add_option("-a", "--auth", action="store", dest="auth", 
                        help="AuthServ username:password pair to use")     
                         
    # Parse our options and arguments                                                                        
    options, args = parser.parse_args()    

    # Make sure they passed in the password and auth string
    if not options.password or not options.auth:
        print 'Error: missing required parameters'
        parser.print_help();

    # Make sure the auth string is in foo:bar format
    auth = options.auth.split(':')
    if len(auth) < 2:
        print 'Error: invalid authserv credentials'
        parser.print_help();
    
    # Turn on debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    chanserv = ChanServ(options.ipaddr, options.port, options.password, auth[0], auth[1])
    info = chanserv.info('#gswww')
    print info
    
    chanserv.say('#gswww', "Help! Help! I'm being repressed!")
    
    
    