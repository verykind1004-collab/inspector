python-utils/drivers/
=====================

Directory for bundled DB driver packages.
python-utils connects to Oracle and PostgreSQL using Python drivers,
so no sqlplus or psql CLI is required on this server.


Directory structure
-------------------
drivers/
├── install.sh          Run this once to install Python packages
├── README.txt          This file
├── python/             Python packages installed by install.sh
│   ├── cx_Oracle.*     Oracle driver (Python 2.7: cx_Oracle 7.3)
│   └── psycopg2/       PostgreSQL driver (psycopg2-binary 2.8.6)
└── instantclient/      Oracle Instant Client .so files (manual step)


Quick start
-----------
1. Install Python drivers:

   cd python-utils/drivers
   bash install.sh

2. (Oracle only) Install Oracle Instant Client:

   a. Download instantclient-basiclite from Oracle:
      https://www.oracle.com/database/technologies/instant-client/linux-x86-64-downloads.html
      Version: 11.2 or later (match your Oracle DB version)

   b. Extract to python-utils/drivers/instantclient/:
      unzip instantclient-basiclite-linux.x64-19.x.x.x.0dbru.zip
      mv instantclient_19_x/* python-utils/drivers/instantclient/

   c. Restart python-utils:
      cd python-utils && bash start.sh

   start.sh automatically sets LD_LIBRARY_PATH to include instantclient/.


Driver versions (Python 2.7 compatible)
----------------------------------------
cx_Oracle    7.3.0   Oracle 11.2+ (requires Oracle Instant Client)
psycopg2     2.8.6   PostgreSQL 9.4+ (libpq bundled in psycopg2-binary)


Offline installation
---------------------
If the server has no internet access, copy wheel files manually:

  cx_Oracle-7.3.0-cp27-cp27mu-linux_x86_64.whl   → drivers/python/
  psycopg2_binary-2.8.6-cp27-cp27mu-linux_x86_64.whl → drivers/python/

Then run:
  pip2 install cx_Oracle-7.3.0-*.whl --target=drivers/python --no-deps
  pip2 install psycopg2_binary-2.8.6-*.whl --target=drivers/python --no-deps
