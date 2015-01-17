SnapShooter
===========
Create a snapshot of a domain at a point in time.

Snapshooter collects information about a set of domains using zerorpc to distribute asynchronous requests to workers. 
Workers try their best to collect data. Results are returned as JSON documents.
Collectable artifacts includes each domain's:
- TLD, domain, and other labels
- IP addresses (how each name server responds)
- IP addresses' original TTL 
- IP addresses' ASNs
- Whois data (parsed and raw)
- Name servers' names
- Name servers' IP addresses
- Name servers' IP addresses' ASNs
- Name servers' domain Whois (parsed and raw)


Installation
------------
System libraries (Ubuntu)
```
aptitude install -y python-virtualenv python-dev libadns1-dev libffi-dev libtool automake
wget http://download.zeromq.org/zeromq-4.1.0-rc1.tar.gz
tar zxf zeromq-*
cd zeromq-*
./configure --prefix=/opt/zeromq
make 
make install
```

Python modules
```
virtualenv ./venv
source venv/bin/activate
pip install -r requirements.txt --allow-external adns-python --allow-unverified adns-python
```

Extra Data
```
wget https://gist.githubusercontent.com/anthonykasza/44633151851154ccb735/raw/2bc833c9d88220b386d0af06dc7467cb6ae77d2a/whois%20server%20ips -O aux/whois_server_ips
```

Usage
-----
Run the client and each worker on systems with unique public IP addresses to avoid Whois throttling. 
Configure zerorpc sockets in client and worker files to match. 

Start workers. Run client.
```
python snapshooter/workers/w1.py
python snapshooter/workers/w2.py
python snapshooter/workers/w3.py
python snapshooter/client.py
```

An example of worker output can be found [here](https://gist.github.com/anthonykasza/67798cc9985f665a1aee).


Use Cases
---------
- track a moving DGA botnet
- build a historic whois data set


Known Limitations
-----------------
This project is to be considered a prototype. And as such...
- pywhois doesn't work with all whois formats
    - the raw whois document is returned from workers as well as the parsed version
- zerorpc doesn't offer encryption or authentication by default
    - zeromq DOES offer encryption and authentication but isn't incorporated into this project
    - a cheap solution I found for my implementation was to set up a VPN between all workers and clients
