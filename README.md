YASC
====

Yet Another Sprinkler Controller
for under 20 Euro

Controller
----------



Installation
------------

#### Controller
Required Python 3.6

Get the repo:
```
git clone https://github.com/asmyczek/YASC.git
```

In YASC directory create virtual environment and load it if not done automatically:

```
virtualenv -p python3 venv
source venv/bin/activate
```

Install requirements.txt: 
```
pip install -r requirements.txt
```
Ignore GPIO errors if you don't run it on a Pi.

Set environment variables:
```
export YASC_PATH={path_to_yasc}/YASC
export YASC_ENV=dev
export YASC_LOG_LEVEL=debug
```

Start the app:
```
./start_yasc.sh
```
Go to [http://localhost:8080/](http://localhost:8080/) or your Pi.

#### Setup as a linux service

Copy _systemd/YASC.service_ to _/lib/systemd/system/_. Change _path_to_yasc_ to the location of your YASC installation.

Now enable it on boot and start it:
```
sudo systemctl enable YASC.service
sudo systemctl start YASC.service
```

You can check status of the service with:
```
sudo systemctl status YASC.service
```

Or logs in _yasc_path/yasc.log_.

#### Integrate with Home Assistant

Copy _homeassistant/yasc.yaml_ file into your _~/.homeassistant/packages_ directory.
Verify that
```
packages: !include_dir_named packages
```
is set it _configuration.yaml_.
