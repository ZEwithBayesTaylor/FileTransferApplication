# File Transfer App (Weiyao Li, wl2872)


## Project Objective
Implement a file transfer application with at least 3 clients and a server using both the TCP and UDP protocols where the overall system offers at least 10 unique files. The program has two modes of operation: the server and the client. The server instance is used to keep track of all the clients in the network along with their IP addresses and the files they are sharing. This information is pushed to clients, and the client instances use this to communicate directly with each other to initiate file transfers. All server-client communication is done over UDP, whereas clients communicate with each other over TCP.


## Functionalities
- Registration
- File Offering
- File Listing
- File Transfer
- De-registration

## Libraries
import sys <br/>
import socket<br/>
import threading<br/>
from threading import Thread<br/>
import time<br/>
from typing import Dict, List, Tuple, Union<br/>
import signal<br/>
import ipaddress<br/>
import argparse<br/>
import os<br/>

## Command-Line Instructions:
### Server Side
_python main.py -s 5000_ <br/>
(RUN THE SERVER FIRST)

### Client Side
#### Registration
- **Client1 (Dave):** `python main.py -c Dave 127.0.0.1 5000 5008 5009`
- **Client2 (Alice):** `python main.py -c Alice 127.0.0.1 5000 5004 5005`
- **Client3 (Bob):** `python main.py -c Bob 127.0.0.1 5000 5002 5003`

#### File Offering
- **Set Directory:** `setdir /Users/weiyaoli/Desktop/ownerDirectory` (CREATE YOUR OWN TEST OWNER DIRECTORY)
- **Offer Files (single/multiple):** `offer file1.py file2.pdf file3.pdf` (CREATE YOUR OWN TEST FILES LOCALLY FOR 3)

#### File Listing
- **View Files:** `list`

#### File Transfer
- **Set Receiving Directory:** `set /Users/weiyaoli/Desktop/receiverDirectory` (example: request file1.pdf Dave)
- **Request File from Owner:** `request <filename> <file owner>` (example: request file1.pdf Dave)

#### De-registration
- **Active Client Book-Keeping:** `dereg`


