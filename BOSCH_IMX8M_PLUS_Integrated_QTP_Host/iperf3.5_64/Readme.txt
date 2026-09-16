On Target side 

apt-get install iperf3

On PC side 

https://iperf.fr/iperf-download.php

Board selection        PC command on commander
[1] Server            iperf3 -c <board-IP> -t 10
[2] Client TCP        iperf3 -s -p 5201
[3] Client UDP        iperf3 -s -p 5201
[4] Client Both       iperf3 -s -p 5201


C:\Deva_Workspace\App\iperf3.5_64\iperf3.5_64>iperf3 -s
-----------------------------------------------------------
Server listening on 5201
-----------------------------------------------------------