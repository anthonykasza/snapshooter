import logging
import random
import sys
import os
import time
import datetime
import json
import dns.resolver
import pythonwhois
from collections import defaultdict
from publicsuffix import PublicSuffixList
logging.basicConfig(level=logging.DEBUG)


class Worker(object):
    def __init__(self, whois_sleep_seconds=10, nameservers=['8.8.8.8', '8.8.4.4'], log_filename=None):
        ''' initialize a worker object to do work
        '''
        self.psl = PublicSuffixList()
        self.whois_sleep_seconds = whois_sleep_seconds
        self.my_resolver = dns.resolver.Resolver()
        self.my_resolver.nameservers = nameservers

        with open(os.path.join(os.path.dirname(__file__), '../aux/whois_server_ips')) as f:
            self.whois_server_ips = json.load(f)

        self.logger = logging.getLogger('snapshooter_worker')
        self.logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        self.logger.addHandler(ch)
        if log_filename:
            fh = logging.FileHandler(log_filename)
            self.logger.addHandler(fh)
           

    def _datetime_list_to_str(self, dt):
        ''' convert a list of datetimes to a list of strings
        '''
        return [str(each) for each in dt]


    def _datetime_to_str(self, dt):
        ''' convert a datetimes to a string
        '''
        return str(dt)
        

    def _log_this(self, domain, msg):
        ''' log a message
        '''
        self.logger.debug("%s\t%s\t%s\t%s" % (self.get_now(), "snapshooter_worker", domain, msg))


    def get_now(self):
        ''' get the time right now, a good candidate for testing RPC
        '''
        return str(datetime.datetime.now()).replace(' ', '_')


    def get_whois(self, domain, tld, retries=3, queried_servers=set(), remaining_servers=set()):
        ''' given a domain, find whois information in a semi-intelligent way
            using the TLD to server IP list in aux, rotate between whois server IPs authoritative for the TLD
            if all the IPs are throttling us, sleep and try again (sleeping decrements retries)
        '''
        self._log_this(domain, 'received whois call')
        # base case
        if retries < 1:
            self._log_this(domain, 'whois failed all time, bailing')
            return {}

        tld = '.' + tld.strip('.')

        # we know a set of IPs responsible for whois info for this tld, so we try to rotate between them 
        if tld in self.whois_server_ips:
            self._log_this(domain, 'tld found in whois_server_ips') 
            # this is the first iteration 
            if len(queried_servers) == 0 and len(remaining_servers) == 0:
                remaining_servers.update([ip for hostname in self.whois_server_ips[tld] for ip in self.whois_server_ips[tld][hostname]])
                self._log_this(domain, 'iterating over the following whois servers: %s' % (remaining_servers))

            # we've queried all the servers we can and now need to try sleeping
            if len(remaining_servers) == 0 and len(queried_servers) > 0:
                self._log_this(domain, 'querying whois with no specified server')
                try:
                    w = pythonwhois.get_whois(domain)
                except:
                    sys.stderr.write('domain: %s whois returned no results retries remaining: %d\n' % (domain, retries)) 
                    time.sleep(self.whois_sleep_seconds)
                    return self.get_whois(domain, tld, retries=retries-1)
            # remaining servers exist, let's try querying them before trying sleep
            else:
                server = random.sample(remaining_servers, 1)[0]
                queried_servers.add(server)
                remaining_servers.remove(server)
                self._log_this(domain, 'querying whois with specific server: %s' % (server))
                try:
                    w = pythonwhois.parse.parse_raw_whois(pythonwhois.net.get_whois_raw(domain, server=server))
                except:
                    sys.stderr.write('domain: %s whois returned no results from server: %s, retries remaining: %d\n' % (domain, server, retries)) 
                    # NO SLEEP
                    return self.get_whois(domain, tld, retries=retries, remaining_servers=remaining_servers, queried_servers=queried_servers)
        # the tld is not in our whois server list and we must use sleep to avoid being throttled
        else:
            self._log_this(domain, 'querying whois with no specified server')
            try:
                w = pythonwhois.get_whois(domain)
            except:
                sys.stderr.write('domain: %s whois returned no results retries remaining: %d\n' % (domain, retries)) 
                time.sleep(self.whois_sleep_seconds)
                return self.get_whois(domain, tld, retries=retries-1)
            
        # once we have a response...
        # messagepack (used by zerorpc) can't serialize datetime objects, so we make them strings :\
        for date in ('expiration_date', 'creation_date', 'updated_date', 'changedate'):
            if date in w:
                w[date] = self._datetime_list_to_str(w[date])
            for category in ('registrant', 'tech', 'billing', 'admin'):
                if ('contacts' in w) and (category in w['contacts']) and (w['contacts'][category] is not None) and (date in w['contacts'][category]):
                    w['contacts'][category][date] = self._datetime_to_str(w['contacts'][category][date])
        return w


    def get_asn(self, ip, domain):
        ''' given an IP address as a string, return Team Cymru ASN lookup results            
            radata example:    "33667 | 98.239.64.0/18 | US | arin | 2007-04-20"
        '''
        self._log_this(domain, 'received asn call %s' % (ip))
        return None
        #
        # This is disabled to avoid hammering TC's IP to ASN service. 
        # Enable at your own discretion.
        #
        #####################
        #try:
        #    ans = self.my_resolver.query(str(ip) + ".origin.asn.cymru.com", "TXT")
        #    for rdata in ans:
        #        result = [str(rdata).strip().strip('"') for rdata in str(rdata).split('|')]
        #        return result
        #except:
        #    return None
        #####################

    
    def get_ipv4s(self, domain):
        ''' given a domain, return a set of IPv4 information
            - ip2asn is used to reduce lookups to get_asn for the same IP
            - all the for loops and DNS queries might be confusing, so let's explain it:
                1. have 8.8.8.8 locate the NS records for the name we are interested in (find the authoritative name servers)
                2. locate the A records for those NS records (find the IPs the authoritative domains resolve to)
                3. send queries to those name server IPs for the A records of the original name (query the authoritative systems for the names' IP addresses)
            - this is similar to a 'dig +trace [name]' command, but lets Google recurse for the answer a bit and doesn't go directly to the roots
            - doing it this way give us the authoritative TTL for the name
            - there is risk here of an attacker controlled name server providing incorrect or poisoned responses to workers
        '''
        self._log_this(domain, 'received ipv4s call %s')
        ip2asn = {}
        ipv4s = []
        self.my_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        try:
            ns_names = self.my_resolver.query(domain, "NS")
            for ns_name in ns_names.rrset:
                self._log_this(domain, 'NS record: %s found' % (ns_name))
                ns_ips = self.my_resolver.query(str(ns_name), "A")
                for ns_ip in ns_ips.rrset:
                    self._log_this(domain, 'A record: %s, found for name %s' % (ns_ip, ns_name))
                    self.my_resolver.nameservers = [str(ns_ip)]
                    ans = self.my_resolver.query(domain, "A")
                    for rdata in ans.rrset:
                        ip_address = str(rdata)
                        self._log_this(domain, 'A record: %s found' % (ip_address))
                        ip_ttl = ans.rrset.ttl
                        try:
                            if ip_address in ip2asn.keys():
                                self._log_this(domain, 'using cached results for IP: %s' % (ip_address))
                                asn, ip_prefix, _, _, _ = ip2asn[ip_address]
                                ip_asn = int(asn)
                            else:
                                self._log_this(domain, 'attempting ASN lookup for IP: %s' % (ip_address))  
                                asn, ip_prefix, _, _, _ = self.get_asn(domain, ip_address)
                                ip2asn[ip_address] = asn, ip_prefix, '', '', ''
                                ip_asn = int(asn)
                        except:
                            self._log_this(domain, 'failed lookup for IP: %s' % (ip_address))
                            ip_prefix = ''
                            ip_country = ''
                            ip_asn = 0
                            ip2asn[ip_address] = ip_asn, ip_prefix, ip_country, '', ''
                        ipv4s.append({'ip_address': str(ip_address), 
                                      'ip_ttl': ip_ttl, 'ns_name': str(ns_name), 
                                      'ns_ip': str(ns_ip), 'asn': ip_asn, 
                                      'ip_prefix': ip_prefix, 'ip_country': ip_country})
        except:
            pass
        return ipv4s


    def get_authoritative_domains(self, domain, nameservers):
        ''' given a domain, return information about the domain's authoritative domain
        '''
        self._log_this(domain, 'received auth call')
        auths = list()
        for server in nameservers:
            d = self.psl.get_public_suffix(server).split('.')[0].strip('.').lower()
            tld = self.psl.get_public_suffix(server).replace(d, '', 1).strip('.').lower()
            subs = server.replace('.'.join(['', d, tld]), '', 1).lower()
            self._log_this(domain, 'subs: %s, d: %s, tld: %s' % (subs, d, tld))
            w = self.get_whois("%s.%s" % (d, tld), tld)
            auths.append({'tld': tld, 'domain': d, 'subs': subs, 'whois': w})
        return auths


    def get_domain(self, domain):
        ''' given a domain, find:
            - IPv4s and TTLs
            - whois information
            - nameserver:
                - hostnames
                - IPv4s
                - whois information
        '''
        self._log_this(domain, 'received domain call')
        publicsuffix = self.psl.get_public_suffix(domain)
        dn_domain = publicsuffix.split('.')[0]
        dn_tld = '.'.join(publicsuffix.split('.')[1:])
        dn_subs = domain.replace('.'.join([dn_domain, dn_tld]), '', 1).split('.')
        w = self.get_whois(domain, dn_tld)
        dn_ips = self.get_ipv4s(domain)
        # try the nameserver found by DNS queries, then the nameservers from whois, then just skip it
        try: 
            nameservers = set([each['ns_name'] for each in dn_ips])
        except:
            try:
                nameserver = set(w['nameservers'])
            except:
                nameservers = set([])
        dn_authorities = self.get_authoritative_domains(domain, nameservers)
        self._log_this(domain, 'sending results')
        now = self.get_now()
        return {'ts': now, 'tld': dn_tld, 'domain': dn_domain, 
                'subs': dn_subs, 'ips': dn_ips, 'whois': w, 
                'request': domain, 'authorities': dn_authorities}


