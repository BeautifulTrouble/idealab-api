#Idealab API

##Installation

1. First get a Python 3.x and git the repo

2. Run around creating a million little OAuth secrets and keys to fill in config.py from the provided example file, or get one from the secret location

3. Create a virtual environment called virtualenv

```shell
python3 -m venv virtualenv
```

4. Activate it with the provided symlink or however you wanted it

```shell
. ./activate
. ./my_obscenely_long_path_complicates_life/bin/activate
```

5. Install the requirements

```shell
pip install -r requirements.txt
```

6. Run the thing, optionally passing debug flag

```shell
./idealab.py
./idealab.py debug
```

7. Point your nginx at the thing properly with gunicorn or be lazy and send your requests directly to the locally running server.

  
```nginx
    location ^~ /api {
        proxy_pass http://solutions.thischangeseverything.org;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $server_name;
    }
```
