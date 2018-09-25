YASC
====

Yet Another Sprinkler Controller
for under 20 Euro

Controller
----------

I started this project to get my kids interested in electronic circuits and teach them how to solder, which these days is a life skill :) 
Now this basic sprinkler system waters my garden and is fully controlled by Homeassistant and Google Assistant. Extensions to come, a rain gauge is on the way.  

![](https://lh3.googleusercontent.com/a6N789xV5oDt8jh0Qn5VYW2zBy4iyal2yQnXuPkcXrr1Y-X9QVDBmpfnKf4J1FpvvP2emqxOHeC5Iscv36OH9ilmP9xmun3PU4-e8W9p7OVMtAFqipfhIe0-IHOGxOyYf9NBVXxesiOt3gdePdRPUyLi8VJmB6OEnxcw8TI8Sy0saU-NhPiNBGtnKGMOZiHQQCD04aIwopvchUiga4I-9O5TvQ-OsDC941GfZiYC28I2fdA3q6-tMx_3BzV8F1mOjv2P2-KemvZezjiqVP2uQLiHZmOz3CrlIuizNn8OnNKwYYLWao4ZsyccS7k8eAHIPIq2zTIewFZGzVZkJEZXmK2r-aOzKwQIDKuvvsPR5AE9BO8Lk8ETkdQdZz4tynnYgNd01SUvYTTJb7biQb2W2jxTAwtE_vRUVSqSSHIddZB710GpwMwjU4zZ49fU8fkBurUyMjE-XxZiT8VmlS3AeKS_4btxxjPTPXSEPh_YVLOWDRH1Veu3IMH3cp4hq8zXFIFQ0wwIGKISenruc1ivqITLiELr1Pv5Ki8Ov3S07fboVbvW1QCr9k1-R8acBrEXZBRW5HVCM8S6TgEDSDDrUuPULfiGw9fXvwtt41qfCIU3VRRPYbkBi21r9YAyh0-G7k5AjkkTCRvivRztbCSFQKYY84AyZQQu4kZgJNAYB5ryY-5z-WhOmmP3qQ=w798-h520-no)

After playing with different setups, I opted out for [this basic circuit](https://myhydropi.com/connecting-a-relay-board-to-a-raspberry-pi).
You will only need:
* Raspberry Pi Zero W
* 8 channel relay board, anyone should work
* 8x:
  * 2N3904 or 2N2222 transistor
  * 10kOhms resistor
  * 2.2kOhms resistor

![](https://lh3.googleusercontent.com/5vuxwFigFl1NevICuI66TL0qtRF-SfMiTIZeypeMLtwxuSgmE90M6ilOHXvAjEJYDJyfRavocbVtVdXyz6r0uWgiiRIiCBh_SaRNa8rGdYpf6foPZVExXP06lAjve30PN_B8vrwgFoB2YHDWCo83Pu2zM6KM_7yiJ-WWbZNeZQh-30t4rPR5d4Xs3E2p_2D3jxuWF0tCW_7KMYDkJzxZjw3jUOmb1KUy99dEBZxxFP_dga3RLefOwBqdL_iFQWqu5LP9oZskKW9PTa2HCMcN9oG9nDmeHT0aBNaqQsOqaigLGrVtJQfIvYFnO_68PLoeMfMgNHSOs67dzpD4iID2g26keMj8IKV6yuGdTxFnrmTgTBxGKktaa5M26LH0L4vqPxRyOPQdL0SSQAFUHEPYzWsXqV9szYn6zzhxs8mLB1FXm0qyg3m7B0avsnbn08LNsVUpRYJhUM_Eq0c3RZo0Fri4hbYBwJq_0NF2JocHxkUn49ErQezY9I5z0xotfsljjeUo-ylMueNtTB8zrHvG3_Pg_i34zu5mdwNqNAjAnTI5kWR0wfC8UoKGXJL_3_q3jHBhIMHOHy_-NumJdBqTMzlT67PxqtYEc8whuWyKIjQ5oIpGTcvx1SYKKv91wHfsIiRuTBVaZ-ClUUgRCm-QjN8UHDi1_B1HAeY-cZwlOPiuSPiMxvdIfxRwNQ=w490-h308-no)

Most irrigation valves run on 22-28VAC, not DC power. A step down converter with a rectifier would do the job, but since I have a drawer full of micro usb power supplies, I kept the Pi and sprinkler circuits separate.

To adjust your circuit to YASC code, just update _ZONES_ list in _pi_controller.py_ to connected GPIO pins.

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
Adjust mqtt topics and verify that
```
packages: !include_dir_named packages
```
is configured in _configuration.yaml_.
