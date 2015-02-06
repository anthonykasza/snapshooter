SnapShooter
===========
Create a snapshot of a domain at a point in time.

Snapshooter collects information about a set of domains using rabbitmq to distribute asynchronous requests to workers. 
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
aptitude install -y python-virtualenv python-dev rabbitmq-server
```

Python modules
```
virtualenv ./venv
source venv/bin/activate
pip install -r requirements.txt
```

Extra Data
```
wget https://gist.githubusercontent.com/anthonykasza/44633151851154ccb735/raw/2bc833c9d88220b386d0af06dc7467cb6ae77d2a/whois%20server%20ips -O aux/whois_server_ips
```

Usage
-----
Run the client and each worker on systems with unique public IP addresses to avoid Whois throttling. 
Configure rabbitmq hosts in client and worker files to match. 

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
- thorough testing with rabbitmq has not been done
