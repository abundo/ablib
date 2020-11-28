# ablib

Common functions, for all abtools

## Installation

    cd /opt
    git clone https://github.com/abundo/ablib.git

    sudo apt install python3-pymysql \
        python3-pip \
        python3-requests

    sudo pip3 install -r requirements.txt


## Usage

Ensure PATH or PYTHONPATH includes parent folder. This can be done systemwide
or in the calling python code

Example

    import sys
    sys.path.insert(0, "/opt")
    import ablib.utils as abutils
