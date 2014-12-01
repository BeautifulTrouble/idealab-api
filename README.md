#Idealab API

##Installation

* Run around creating a million little OAuth secrets and keys to fill in config.py from the provided example file, or get one from the secret location

* Create a virtual environment called virtualenv

```shell
python -m venv virtualenv
```

* Activate it with the provided symlink or however you wanted it

```shell
. ./activate
. ./my\ obscenely\ long\ path\ complicates\ life/bin/activate
```

* Install the requirements

```shell
pip install -r requirements.txt
```

* Run the thing, optionally passing debug flag

```shell
./idealab.py
./idealab.py debug
```

* Point your nginx at the thing properly with gunicorn or be lazy and send your requests directly to the locally running server.

  
```nginx
    location ^~ /api {
        proxy_pass http://solutions.thischangeseverything.org:9000;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $server_name;
    }
```
